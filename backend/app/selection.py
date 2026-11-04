"""Forecast selection: which forecast was available at decision time?"""
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

import pandas as pd

UK = ZoneInfo("Europe/London")
DEFAULT_CUTOFF = time(9, 0)  # UK local time on D-1 (assumption, configurable)


def _to_utc(d: date, t: time = time(0, 0)) -> pd.Timestamp:
    return pd.Timestamp(datetime.combine(d, t, tzinfo=UK)).tz_convert("UTC")


def cutoff_timestamp(delivery_date: date, cutoff: time = DEFAULT_CUTOFF) -> pd.Timestamp:
    """Decision cutoff as UTC: `cutoff` UK-local time on the day before delivery."""
    return _to_utc(delivery_date - timedelta(days=1), cutoff)


def delivery_window(delivery_date: date) -> tuple[pd.Timestamp, pd.Timestamp]:
    """[start, end) of the UK-local delivery day, in UTC (DST-safe)."""
    return _to_utc(delivery_date), _to_utc(delivery_date + timedelta(days=1))


def select_forecast(
    forecasts: pd.DataFrame, delivery_date: date, cutoff: time = DEFAULT_CUTOFF
) -> pd.DataFrame:
    """For each half-hour of `delivery_date`, return the latest forecast with
    publishTime <= cutoff on D-1.

    Input columns: startTime, publishTime, generation (all UTC-aware).
    Output adds: horizon_h (startTime - publishTime, hours), cutoff.
    Half-hours with no eligible forecast are simply absent (shown as gaps).
    """
    cut = cutoff_timestamp(delivery_date, cutoff)
    start, end = delivery_window(delivery_date)

    eligible = forecasts[
        (forecasts["startTime"] >= start)
        & (forecasts["startTime"] < end)
        & (forecasts["publishTime"] <= cut)  # inclusive: published exactly at cutoff counts
    ]
    latest = (
        eligible.sort_values(["startTime", "publishTime"])
        .groupby("startTime", as_index=False)
        .tail(1)
        .copy()
    )
    latest["horizon_h"] = (latest["startTime"] - latest["publishTime"]).dt.total_seconds() / 3600
    latest["cutoff"] = cut
    latest["delivery_date"] = delivery_date
    return latest.sort_values("startTime").reset_index(drop=True)


def select_range(
    forecasts: pd.DataFrame, start: date, end: date, cutoff: time = DEFAULT_CUTOFF
) -> pd.DataFrame:
    """Apply select_forecast to every delivery day in [start, end]."""
    days = pd.date_range(start, end, freq="D").date
    parts = [select_forecast(forecasts, d, cutoff) for d in days]
    parts = [p for p in parts if not p.empty]
    return pd.concat(parts, ignore_index=True) if parts else forecasts.iloc[0:0]