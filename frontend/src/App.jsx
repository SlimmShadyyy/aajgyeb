import { useEffect, useState } from 'react'
import {
  ResponsiveContainer, LineChart, Line, BarChart, Bar,
  XAxis, YAxis, CartesianGrid, Tooltip, Legend, ReferenceLine,
} from 'recharts'
import { api } from './api'
import './App.css'

const fmt = (v, d = 0) => (v == null ? '–' : Number(v).toLocaleString('en-GB', { maximumFractionDigits: d }))
const hhmm = (iso) => iso?.slice(11, 16)
const dayhh = (iso) => iso?.slice(5, 10) + ' ' + iso?.slice(11, 16)

function useData(path, params) {
  const [state, set] = useState({ data: null, error: null, loading: true })
  const key = JSON.stringify([path, params])
  useEffect(() => {
    let live = true
    set((s) => ({ ...s, loading: true, error: null }))
    api(path, params)
      .then((data) => live && set({ data, error: null, loading: false }))
      .catch((error) => live && set({ data: null, error: error.message, loading: false }))
    return () => { live = false }
  }, [key])
  return state
}

function Status({ s }) {
  if (s.loading) return <p className="muted">Loading…</p>
  if (s.error) return <p className="err">{s.error}</p>
  return null
}

function Kpi({ label, value, unit, hint }) {
  return (
    <div className="kpi" title={hint}>
      <div className="kpi-label">{label}</div>
      <div className="kpi-value">{value}<span> {unit}</span></div>
    </div>
  )
}

function Decision({ day, cutoff }) {
  const s = useData('forecast/latest', { delivery_date: day, cutoff })
  const d = s.data
  return (
    <section>
      <h2>Forecast available at decision time for {day}</h2>
      <Status s={s} />
      {d && d.n_periods === 0 && <p className="err">No forecast was published before the cutoff.</p>}
      {d && d.n_periods > 0 && (
        <>
          <div className="kpis">
            <Kpi label="Latest forecast used" value={dayhh(d.latest_publish_time)} unit="UTC"
              hint="Most recent publish time among the selected forecasts" />
            <Kpi label="Decision cutoff" value={dayhh(d.cutoff_utc)} unit="UTC" />
            <Kpi label="Newest forecast age at cutoff"
              value={fmt((new Date(d.cutoff_utc) - new Date(d.latest_publish_time)) / 36e5, 1)}
              unit="hours"
              hint="Cutoff minus publish time of the newest forecast run used" />
            <Kpi label="Average forecast wind" value={fmt(d.mean_forecast_mw)} unit="MW" />
            <Kpi label="Hours covered" value={`${d.n_periods}/${d.expected_periods}`} unit="" />
          </div>
          <ResponsiveContainer width="100%" height={340}>
            <LineChart data={d.points}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="startTime" tickFormatter={hhmm} minTickGap={30} />
              <YAxis tickFormatter={(v) => fmt(v)} unit=" MW" width={90} />
              <Tooltip labelFormatter={dayhh} formatter={(v) => `${fmt(v)} MW`} />
              <Legend />
              <Line dataKey="forecast" name="Forecast (known at cutoff)" stroke="#2563eb" dot={false} strokeWidth={2} />
              {d.points.some((p) => p.actual != null) && (
                <Line dataKey="actual" name="Actual (after the fact)" stroke="#16a34a" dot={false} strokeDasharray="4 3" />
              )}
            </LineChart>
          </ResponsiveContainer>
          <p className="muted">
            Residual demand to buy = demand − this wind forecast. Each hour uses the latest forecast
            published at or before the cutoff.
          </p>
        </>
      )}
    </section>
  )
}

function VsActual({ start, end, cutoff }) {
  const s = useData('forecast/vs-actual', { start, end, cutoff })
  const pts = s.data?.points ?? []
  return (
    <section>
      <h2>Forecast vs actual, {start} to {end}</h2>
      <Status s={s} />
      {pts.length > 0 && (
        <>
          <ResponsiveContainer width="100%" height={340}>
            <LineChart data={pts}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="startTime" tickFormatter={(v) => v.slice(5, 10)} minTickGap={50} />
              <YAxis tickFormatter={(v) => fmt(v)} unit=" MW" width={90} />
              <Tooltip labelFormatter={dayhh} formatter={(v) => `${fmt(v)} MW`} />
              <Legend />
              <Line dataKey="forecast" name="Forecast" stroke="#2563eb" dot={false} />
              <Line dataKey="actual" name="Actual" stroke="#16a34a" dot={false} />
            </LineChart>
          </ResponsiveContainer>
          <h3>Error (forecast − actual)</h3>
          <ResponsiveContainer width="100%" height={220}>
            <LineChart data={pts}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="startTime" tickFormatter={(v) => v.slice(5, 10)} minTickGap={50} />
              <YAxis tickFormatter={(v) => fmt(v)} unit=" MW" width={90} />
              <Tooltip labelFormatter={dayhh} formatter={(v) => `${fmt(v)} MW`} />
              <ReferenceLine y={0} stroke="#888" />
              <Line dataKey="error" name="Error" stroke="#dc2626" dot={false} />
            </LineChart>
          </ResponsiveContainer>
        </>
      )}
    </section>
  )
}

function BarBlock({ title, data, x, keys }) {
  return (
    <div className="card">
      <h3>{title}</h3>
      <ResponsiveContainer width="100%" height={260}>
        <BarChart data={data}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey={x} />
          <YAxis tickFormatter={(v) => fmt(v)} unit=" MW" width={80} />
          <Tooltip formatter={(v) => `${fmt(v)} MW`} />
          <Legend />
          {keys.map(([k, name, color]) => <Bar key={k} dataKey={k} name={name} fill={color} />)}
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}

function Accuracy({ start, end, cutoff }) {
  const s = useData('metrics', { start, end, cutoff })
  const d = s.data
  const m = d?.summary
  const hist = d?.histogram?.map((h) => ({ ...h, label: `${h.from_mw}` }))
  return (
    <section>
      <h2>Forecast accuracy, {start} to {end}</h2>
      <Status s={s} />
      {m?.n > 0 && (
        <>
          <div className="kpis">
            <Kpi label="MAE" value={fmt(m.mae_mw)} unit="MW" hint="Average absolute error" />
            <Kpi label="RMSE" value={fmt(m.rmse_mw)} unit="MW" hint="Penalises large misses" />
            <Kpi label="Bias" value={fmt(m.bias_mw)} unit="MW" hint="Positive = forecast too high on average" />
            <Kpi label="Buffer (P90)" value={fmt(m.recommended_buffer_mw_p90)} unit="MW"
              hint="Forecast overshoots actual by no more than this 90% of the time" />
            <Kpi label="Buffer (P95)" value={fmt(m.recommended_buffer_mw_p95)} unit="MW" />
            <Kpi label="Samples" value={fmt(m.n)} unit="" />
          </div>
          <p className="muted">
            Error = forecast − actual. When the forecast is too high, wind falls short and extra power must be
            bought, so the buffer is taken from the over-forecast tail.
          </p>
          <div className="grid">
            <BarBlock title="Error distribution (MW bins, count)" data={hist} x="label" keys={[['count', 'Hours', '#6366f1']]} />
            <BarBlock title="MAE / RMSE by forecast horizon (hours ahead)" data={d.by_horizon} x="group"
              keys={[['mae_mw', 'MAE', '#2563eb'], ['rmse_mw', 'RMSE', '#f59e0b']]} />
            <BarBlock title="MAE by hour of day (UK time)" data={d.by_hour} x="group" keys={[['mae_mw', 'MAE', '#2563eb']]} />
            <BarBlock title="MAE and bias by actual wind level (quartiles)" data={d.by_level} x="group" keys={[['mae_mw', 'MAE', '#2563eb'], ['bias_mw', 'Bias', '#dc2626']]} />
          </div>
        </>
      )}
    </section>
  )
}

export default function App() {
  const [cfg, setCfg] = useState(null)
  const [tab, setTab] = useState('decision')
  const [day, setDay] = useState('2026-01-10')
  const [start, setStart] = useState('2026-01-01')
  const [end, setEnd] = useState('2026-01-31')
  const [cutoff, setCutoff] = useState('09:00')

  useEffect(() => { api('config').then(setCfg).catch(() => {}) }, [])
  const min = cfg?.min_date, max = cfg?.max_date

  return (
    <div className="app">
      <header>
        <h1>GB Wind Forecast: Day-Ahead Decision Support</h1>
        <p className="muted">National wind, Elexon FUELHH (actual) and WINDFOR (forecast). Delivery days in January 2026.</p>
      </header>

      <div className="controls">
        <label>Decision cutoff (UK time, day before)
          <input type="time" value={cutoff} onChange={(e) => e.target.value && setCutoff(e.target.value)} />
        </label>
        {tab === 'decision' ? (
          <label>Delivery day
            <input type="date" value={day} min={min} max={max} onChange={(e) => setDay(e.target.value)} />
          </label>
        ) : (
          <>
            <label>From <input type="date" value={start} min={min} max={max} onChange={(e) => setStart(e.target.value)} /></label>
            <label>To <input type="date" value={end} min={min} max={max} onChange={(e) => setEnd(e.target.value)} /></label>
          </>
        )}
      </div>

      <nav>
        {[['decision', 'Decision view'], ['vs', 'Forecast vs actual'], ['acc', 'Accuracy']].map(([k, l]) => (
          <button key={k} className={tab === k ? 'on' : ''} onClick={() => setTab(k)}>{l}</button>
        ))}
      </nav>

      {tab === 'decision' && <Decision day={day} cutoff={cutoff} />}
      {tab === 'vs' && <VsActual start={start} end={end} cutoff={cutoff} />}
      {tab === 'acc' && <Accuracy start={start} end={end} cutoff={cutoff} />}
    </div>
  )
}