"""Forecast accuracy metrics."""
import numpy as np
import pandas as pd

HORIZON_BINS = [0, 12, 18, 24, 30, 36, 48, np.inf]
MAPE_MIN_ACTUAL_MW = 100  # ignore near-zero actuals in MAPE


def join_actuals(selected: pd.DataFrame, actuals: pd.DataFrame) -> pd.DataFrame:
    """Inner-join selected forecasts with actuals on startTime and add error columns."""
    a = actuals[["startTime", "generation"]].rename(columns={"generation": "actual"})
    df = selected.rename(columns={"generation": "forecast"}).merge(a, on="startTime", how="inner")
    df["error"] = df["forecast"] - df["actual"]
    df["abs_error"] = df["error"].abs()
    return df


def summarize(df: pd.DataFrame) -> dict:
    if df.empty:
        return {"n": 0}
    e, ae = df["error"], df["abs_error"]
    big = df[df["actual"] >= MAPE_MIN_ACTUAL_MW]
    return {
        "n": int(len(df)),
        "bias_mw": float(e.mean()),
        "mae_mw": float(ae.mean()),
        "rmse_mw": float(np.sqrt((e**2).mean())),
        "mape_pct": float((big["abs_error"] / big["actual"]).mean() * 100) if len(big) else None,
        "abs_error_p50": float(ae.quantile(0.50)),
        "abs_error_p90": float(ae.quantile(0.90)),
        "abs_error_p95": float(ae.quantile(0.95)),
        # Over-forecast risk: wind forecast above actual -> buyer short.
        "recommended_buffer_mw_p90": float(max(e.quantile(0.90), 0)),
        "recommended_buffer_mw_p95": float(max(e.quantile(0.95), 0)),
        "mean_actual_mw": float(df["actual"].mean()),
    }


def _group(df: pd.DataFrame, key) -> list[dict]:
    out = []
    for k, g in df.groupby(key, observed=True):
        s = summarize(g)
        s["group"] = str(k)
        out.append(s)
    return out


def by_horizon(df: pd.DataFrame) -> list[dict]:
    return _group(df, pd.cut(df["horizon_h"], HORIZON_BINS, right=False))


def by_hour(df: pd.DataFrame) -> list[dict]:
    hours = df["startTime"].dt.tz_convert("Europe/London").dt.hour
    res = _group(df, hours)
    return sorted(res, key=lambda r: int(r["group"]))


def by_level(df: pd.DataFrame) -> list[dict]:
    q = pd.qcut(df["actual"], 4, duplicates="drop")
    names = {iv: f"{iv.left / 1000:.1f}–{iv.right / 1000:.1f} GW" for iv in q.cat.categories}
    out = []
    for iv, g in df.groupby(q, observed=True):
        s = summarize(g)
        s["group"] = names[iv]
        out.append(s)
    return out


def histogram(df: pd.DataFrame, bin_mw: int = 500) -> list[dict]:
    if df.empty:
        return []
    lo = int(np.floor(df["error"].min() / bin_mw) * bin_mw)
    hi = int(np.ceil(df["error"].max() / bin_mw) * bin_mw) + bin_mw
    counts, edges = np.histogram(df["error"], bins=np.arange(lo, hi + 1, bin_mw))
    return [{"from_mw": int(edges[i]), "to_mw": int(edges[i + 1]), "count": int(c)}
            for i, c in enumerate(counts)]

def to_hourly(actuals: pd.DataFrame) -> pd.DataFrame:
    """FUELHH is half-hourly, WINDFOR is hourly: average each hour's two actuals."""
    a = actuals[["startTime", "generation"]].copy()
    a["hour"] = a["startTime"].dt.floor("h")
    g = a.groupby("hour").agg(generation=("generation", "mean"), n=("generation", "size"))
    g = g[g["n"] == 2].reset_index().rename(columns={"hour": "startTime"})
    return g[["startTime", "generation"]]