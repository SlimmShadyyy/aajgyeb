"""FastAPI app: serves pre-fetched Elexon wind data and derived analytics."""
from datetime import date, time
from functools import lru_cache
from pathlib import Path
from fastapi.staticfiles import StaticFiles
import pandas as pd
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from . import metrics
from .selection import DEFAULT_CUTOFF, select_forecast, select_range

DATA = Path(__file__).resolve().parents[1] / "data"
MIN_DAY, MAX_DAY = date(2026, 1, 1), date(2026, 1, 31)

app = FastAPI(title="Wind Forecast Decision Support")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["GET"], allow_headers=["*"])


@lru_cache
def load() -> tuple[pd.DataFrame, pd.DataFrame]:
    a = pd.read_csv(DATA / "actuals.csv.gz")
    f = pd.read_csv(DATA / "forecasts.csv.gz")
    for df, cols in ((a, ["startTime"]), (f, ["startTime", "publishTime"])):
        for c in cols:
            df[c] = pd.to_datetime(df[c], utc=True)
    return metrics.to_hourly(a), f

def parse_cutoff(s: str) -> time:
    try:
        return time.fromisoformat(s)
    except ValueError:
        raise HTTPException(422, "cutoff must be HH:MM, e.g. 09:00")


def check_days(*days: date):
    for d in days:
        if not MIN_DAY <= d <= MAX_DAY:
            raise HTTPException(422, f"date {d} outside {MIN_DAY}..{MAX_DAY}")


def records(df: pd.DataFrame) -> list[dict]:
    df = df.copy()
    for c in df.select_dtypes(include=["datetimetz", "datetime"]).columns:
        df[c] = df[c].dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    return df.astype(object).where(df.notna(), None).to_dict("records")


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/config")
def config():
    return {"min_date": MIN_DAY, "max_date": MAX_DAY,
            "default_cutoff": DEFAULT_CUTOFF.strftime("%H:%M")}


@app.get("/api/forecast/latest")
def latest(delivery_date: date, cutoff: str = "09:00"):
    """Forecast available at decision time for one delivery day (+ actuals if known)."""
    check_days(delivery_date)
    actuals, fc = load()
    sel = select_forecast(fc, delivery_date, parse_cutoff(cutoff))
    out = sel.rename(columns={"generation": "forecast"})
    if not sel.empty:
        out = out.merge(actuals[["startTime", "generation"]].rename(
            columns={"generation": "actual"}), on="startTime", how="left")
    return {
        "delivery_date": delivery_date,
        "cutoff_utc": None if sel.empty else sel["cutoff"].iloc[0].isoformat(),
        "n_periods": int(len(sel)), "expected_periods": 24,
        "latest_publish_time": None if sel.empty else sel["publishTime"].max().isoformat(),
        "earliest_publish_time": None if sel.empty else sel["publishTime"].min().isoformat(),
        "mean_forecast_mw": None if sel.empty else float(sel["generation"].mean()),
        "points": records(out[["startTime", "publishTime", "horizon_h", "forecast"]
                              + (["actual"] if "actual" in out else [])]) if not sel.empty else [],
    }


@app.get("/api/forecast/vs-actual")
def vs_actual(start: date, end: date, cutoff: str = "09:00"):
    check_days(start, end)
    actuals, fc = load()
    sel = select_range(fc, start, end, parse_cutoff(cutoff))
    df = metrics.join_actuals(sel, actuals) if not sel.empty else sel
    cols = ["startTime", "publishTime", "horizon_h", "forecast", "actual", "error"]
    return {"points": records(df[cols]) if not df.empty else []}


@app.get("/api/metrics")
def get_metrics(start: date = MIN_DAY, end: date = MAX_DAY, cutoff: str = "09:00"):
    check_days(start, end)
    actuals, fc = load()
    sel = select_range(fc, start, end, parse_cutoff(cutoff))
    if sel.empty:
        return {"summary": {"n": 0}}
    df = metrics.join_actuals(sel, actuals)
    return {
        "summary": metrics.summarize(df),
        "by_horizon": metrics.by_horizon(df),
        "by_hour": metrics.by_hour(df),
        "by_level": metrics.by_level(df),
        "histogram": metrics.histogram(df),
    }

STATIC = Path(__file__).resolve().parents[1] / "static"
if STATIC.exists():  # only in the container; in dev, Vite serves the frontend
    app.mount("/", StaticFiles(directory=STATIC, html=True), name="static")