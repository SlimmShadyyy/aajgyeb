"""Fetch wind actuals (FUELHH) and forecasts (WINDFOR) from Elexon BMRS."""
import time as _time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
import requests

BASE = "https://data.elexon.co.uk/bmrs/api/v1/datasets"
OUT = Path(__file__).resolve().parents[1] / "data"
OUT.mkdir(exist_ok=True)


def get(endpoint: str, params: dict, retries: int = 3) -> pd.DataFrame:
    for attempt in range(1, retries + 1):
        try:
            r = requests.get(f"{BASE}/{endpoint}/stream", params=params, timeout=120)
            if r.status_code >= 400:
                print("HTTP", r.status_code, r.text[:500])
            r.raise_for_status()
            return pd.DataFrame(r.json())
        except requests.RequestException as e:
            print(f"  attempt {attempt} failed: {e}")
            _time.sleep(2 * attempt)
    raise RuntimeError(f"{endpoint} failed after {retries} attempts: {params}")


def fetch_actuals(start: str, end: str) -> pd.DataFrame:
    df = get("FUELHH", {
        "settlementDateFrom": start,
        "settlementDateTo": end,
        "fuelType": "WIND",
    })
    df["startTime"] = pd.to_datetime(df["startTime"], utc=True)
    return df[["startTime", "settlementDate", "settlementPeriod", "generation"]] \
        .drop_duplicates().sort_values("startTime")


def fetch_forecasts(start: datetime, end: datetime, step_days: int = 1) -> pd.DataFrame:
    chunk_dir = OUT / "chunks"
    chunk_dir.mkdir(exist_ok=True)
    frames, cur = [], start
    while cur < end:
        nxt = min(cur + timedelta(days=step_days), end)
        f = chunk_dir / f"windfor_{cur:%Y%m%d}.parquet"
        if f.exists():  # resume support
            df = pd.read_parquet(f)
        else:
            df = get("WINDFOR", {
                "publishDateTimeFrom": cur.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "publishDateTimeTo": nxt.strftime("%Y-%m-%dT%H:%M:%SZ"),
            })
            df.to_parquet(f, index=False)
        print(f"WINDFOR {cur:%Y-%m-%d} -> {nxt:%Y-%m-%d}: {len(df)} rows", flush=True)
        frames.append(df)
        cur = nxt
    df = pd.concat(frames, ignore_index=True)
    df["startTime"] = pd.to_datetime(df["startTime"], utc=True)
    df["publishTime"] = pd.to_datetime(df["publishTime"], utc=True)
    return df[["startTime", "publishTime", "generation"]] \
        .drop_duplicates().sort_values(["startTime", "publishTime"])


if __name__ == "__main__":
    actuals = fetch_actuals("2026-01-01", "2026-01-31")
    actuals.to_parquet(OUT / "actuals.parquet", index=False)
    print("actuals:", actuals.shape)

    utc = timezone.utc
    fc = fetch_forecasts(datetime(2025, 12, 15, tzinfo=utc), datetime(2026, 2, 1, tzinfo=utc))
    fc.to_parquet(OUT / "forecasts.parquet", index=False)
    print("forecasts:", fc.shape)