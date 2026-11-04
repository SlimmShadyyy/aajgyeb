from datetime import date, time

import pandas as pd

from app.selection import cutoff_timestamp, select_forecast

D = date(2026, 1, 10)


def mk(rows):
    return pd.DataFrame(
        [{"startTime": pd.Timestamp(s, tz="UTC"), "publishTime": pd.Timestamp(p, tz="UTC"),
          "generation": g} for s, p, g in rows])


def test_cutoff_is_day_before():
    assert cutoff_timestamp(D, time(9, 0)) == pd.Timestamp("2026-01-09 09:00", tz="UTC")


def test_picks_latest_before_cutoff():
    fc = mk([("2026-01-10 12:00", "2026-01-08 12:00", 1000),
             ("2026-01-10 12:00", "2026-01-09 08:30", 2000),   # should win
             ("2026-01-10 12:00", "2026-01-09 10:00", 3000)])  # after cutoff
    out = select_forecast(fc, D, time(9, 0))
    assert len(out) == 1 and out.generation.iloc[0] == 2000


def test_publish_exactly_at_cutoff_is_included():
    fc = mk([("2026-01-10 12:00", "2026-01-09 09:00", 1500)])
    assert len(select_forecast(fc, D, time(9, 0))) == 1


def test_no_eligible_forecast_gives_gap():
    fc = mk([("2026-01-10 12:00", "2026-01-09 09:30", 1500)])
    assert select_forecast(fc, D, time(9, 0)).empty


def test_other_days_excluded():
    fc = mk([("2026-01-11 00:00", "2026-01-09 08:00", 1), ("2026-01-09 23:30", "2026-01-08 08:00", 2)])
    assert select_forecast(fc, D, time(9, 0)).empty


def test_horizon_computed():
    fc = mk([("2026-01-10 12:00", "2026-01-09 09:00", 1500)])
    assert select_forecast(fc, D, time(9, 0)).horizon_h.iloc[0] == 27