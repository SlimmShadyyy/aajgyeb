# GB Wind Forecast: Day-Ahead Decision Support

A web app for a day-ahead power buying team. It shows (1) the wind forecast that was actually
available at decision time, and (2) how accurate such forecasts were, so purchases can include a
quantified buffer.

Data: national wind only, from Elexon BMRS. Actuals from `FUELHH` (fuelType `WIND`), forecasts
from `WINDFOR`. Delivery days: January 2026.

**Live app:** https://aajgyeb.vercel.app/

## AI tools disclosure

This project was built with the assistance of an AI tool (Anthropic's Claude) for planning, code
generation and debugging. I reviewed, ran and tested the code, and checked the data findings
myself.

## Key assumptions

| Assumption | Detail |
|---|---|
| Decision cutoff | Default **09:00 UK time on the day before delivery**. Configurable in the UI and API. This approximates the GB day-ahead gate closure and should be confirmed with the client. |
| Forecast selection | For each delivery hour, use the forecast with the latest `publishTime` **at or before** the cutoff (inclusive). Hours with no eligible forecast are left as gaps. |
| Resolution | `WINDFOR` is hourly, `FUELHH` is half-hourly. Actuals are averaged to hourly; hours missing a half-hour are dropped. |
| Error sign | `error = forecast - actual`. Positive means over-forecast (wind fell short), which is the risky direction for a buyer. |
| Buffer | The P90 / P95 of the over-forecast error, floored at 0. It includes any systematic bias. |
| MAPE | Excludes hours with actual < 100 MW. |
| Time zones | All data is UTC. The cutoff and the hour-of-day chart use Europe/London. |
| Data window | Delivery days 1-31 Jan 2026. Forecasts published from 15 Dec 2025 onward are fetched. |

## Data observations

- `WINDFOR` is published every 2-4 hours at :30 past the hour, so the freshest forecast at a
  09:00 cutoff is typically 1.5-3 hours old, and moving the cutoff by a few minutes can change
  which run is used.
- There are about 24 forecast versions per target hour.
- Some forecasts have negative horizons (published after the target hour). The cutoff filter
  excludes them.
- At a 09:00 cutoff, the forecast over-predicted wind in January 2026 (bias about +1.9 GW,
  MAE about 2.1 GW, 744 hourly samples). The cause was not investigated.

## Repository layout

```
.
├── backend/
│   ├── app/
│   │   ├── main.py          # FastAPI app and endpoints
│   │   ├── selection.py     # cutoff / forecast-selection logic
│   │   └── metrics.py       # error metrics and breakdowns
│   ├── scripts/fetch_data.py  # downloads data from Elexon
│   ├── data/                # bundled data (actuals / forecasts)
│   ├── tests/               # pytest unit tests for selection
│   ├── pytest.ini
│   ├── ruff.toml
│   └── requirements.txt     # local / Docker dependencies
├── frontend/                # React + Vite + Recharts dashboard
├── api/index.py             # Vercel serverless entry point
├── vercel.json              # Vercel build and routing config
├── requirements.txt         # minimal dependencies installed by Vercel
├── Dockerfile               # multi-stage: builds frontend, serves API + UI
├── docker-compose.yml
└── README.md
```

## API

| Endpoint | Purpose |
|---|---|
| `GET /api/health` | Health check |
| `GET /api/config` | Date range and default cutoff |
| `GET /api/forecast/latest?delivery_date=&cutoff=` | Forecast available at decision time for one day |
| `GET /api/forecast/vs-actual?start=&end=&cutoff=` | Selected forecast vs actual, with error |
| `GET /api/metrics?start=&end=&cutoff=` | Summary metrics and breakdowns |

`cutoff` is `HH:MM` UK time on the day before delivery.

## Run with Docker

```bash
docker compose up --build
```

Open http://localhost:8000 (API docs at http://localhost:8000/docs).

## Run locally without Docker

Backend (Python 3.12):

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate        # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Frontend (Node 18+), in a second terminal:

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173. Vite proxies `/api` to the backend on port 8000.

## Tests and lint

```bash
cd backend && pytest -q && ruff check .
cd frontend && npm run lint
```

## Refresh the data

Data is pre-fetched and committed so the app needs no live API calls.

```bash
cd backend
python scripts/fetch_data.py
```

Then regenerate the gzipped CSVs used by the Vercel deployment:

```bash
python -c "import pandas as pd; [pd.read_parquet(f'data/{n}.parquet').to_csv(f'data/{n}.csv.gz', index=False) for n in ('actuals','forecasts')]"
```

## Deployment

Deployed on Vercel: the frontend is built from `frontend/` and the FastAPI app runs as a single
Python serverless function (`api/index.py`). Vercel does not run Docker, so the `Dockerfile` is
for local use.

## Limitations and next steps

- One month of data is a small sample.
- The 09:00 cutoff is an assumption.
- With a fixed cutoff, forecast horizon is tied to hour of day, so the horizon chart is only
  meaningful when compared across cutoffs.
- Next: bias correction, a longer history, linking to the client's demand forecast, and
  investigating why the forecast runs high.
