import { useEffect, useState } from 'react'
import { api, day, rupees } from '../api'

export function ReviewQueue({ onChanged, onOpenAsset }) {
  const [items, setItems] = useState(null)
  const [target, setTarget] = useState({})
  const load = () => api.review().then(setItems)
  useEffect(() => { load() }, [])
  const act = async (c, body) => { await api.decide(c.id, body); await load(); onChanged && onChanged() }

  if (!items) return <div className="panel muted">Loading…</div>
  return (
    <div className="panel">
      <h2>Engineer review queue</h2>
      <p className="muted">Uncertain matches and unregistered assets wait here. The system suggests; an engineer decides.</p>
      {items.length === 0 && <p className="empty">Nothing to review. File a complaint far from known assets, or a vaguely worded one, to see this queue fill.</p>}
      {items.map((c) => (
        <div key={c.id} className="review-item">
          <div>
            <div className="asset-id">Complaint #{c.id} · {day(c.created_at)} · {c.category}</div>
            <div>{c.text}</div>
            <div className="muted small">
              Suggested: <a onClick={() => onOpenAsset(c.asset_id)}>{c.asset_id}</a> ({c.asset_name})
              {c.match_score != null && <> · match score {c.match_score}</>}
            </div>
          </div>
          <div className="review-actions">
            <button className="btn" onClick={() => act(c, { action: 'confirm' })}>Confirm</button>
            <input placeholder="Other asset ID" value={target[c.id] || ''} onChange={(e) => setTarget({ ...target, [c.id]: e.target.value.toUpperCase() })} />
            <button className="btn ghost" disabled={!target[c.id]} onClick={() => act(c, { action: 'reassign', asset_id: target[c.id] })}>Move</button>
          </div>
        </div>
      ))}
    </div>
  )
}

export function Contractors() {
  const [rows, setRows] = useState(null)
  useEffect(() => { api.contractors().then(setRows) }, [])
  if (!rows) return <div className="panel muted">Loading…</div>
  const max = Math.max(...rows.map((r) => r.avg_days_lasted || 0), 1)
  return (
    <div className="panel">
      <h2>Repair durability by contractor</h2>
      <p className="muted">Average days a repair lasted before the same asset failed again. Longer is better.</p>
      <table className="table">
        <thead><tr><th>Contractor</th><th>Repairs</th><th>Failed again</th><th style={{ width: '40%' }}>Avg days lasted</th><th>Spend</th></tr></thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.contractor}>
              <td>{r.contractor}</td><td>{r.repairs}</td><td>{r.failed_again}</td>
              <td><div className="bar-inline"><div className="bar"><div className="fill ok" style={{ width: `${((r.avg_days_lasted || 0) / max) * 100}%` }} /></div><b>{r.avg_days_lasted ?? '—'}</b></div></td>
              <td>{rupees(r.spend)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

export function Insights() {
  const [bt, setBt] = useState(null)
  useEffect(() => { api.backtest().then(setBt) }, [])
  if (!bt) return <div className="panel muted">Loading…</div>
  return (
    <div className="panel">
      <h2>Does the failure estimate hold up?</h2>
      <p className="muted">For each asset with enough history, we hide its most recent failure, estimate a window from the earlier gaps, and check whether the real failure fell inside it. {bt.note}</p>
      <div className="kpis">
        <div><b>{bt.tested_assets}</b><span>assets tested</span></div>
        <div><b>{bt.inside_window}</b><span>inside window</span></div>
        <div><b>{bt.hit_rate != null ? Math.round(bt.hit_rate * 100) + '%' : '—'}</b><span>hit rate</span></div>
        <div><b>{bt.median_days_outside_when_missed}</b><span>median days off (misses)</span></div>
      </div>
      <table className="table">
        <thead><tr><th>Asset</th><th>Estimated window</th><th>Actual failure</th><th>Result</th></tr></thead>
        <tbody>
          {bt.results.map((r) => (
            <tr key={r.asset_id}>
              <td>{r.asset_id} · {r.name}</td><td>{day(r.window[0])} to {day(r.window[1])}</td><td>{day(r.actual)}</td>
              <td className={r.hit ? 'ok-text' : 'warn-text'}>{r.hit ? 'Inside' : `${r.days_outside} days outside`}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

export function SearchResults({ q, onOpenAsset }) {
  const [res, setRes] = useState(null)
  useEffect(() => { setRes(null); api.search(q).then(setRes) }, [q])
  if (!res) return <div className="panel muted">Searching…</div>
  return (
    <div className="panel">
      <h2>Search: “{q}”</h2>
      {res.length === 0 && <p className="empty">No matching history.</p>}
      {res.map((r, i) => (
        <div key={i} className="search-item" onClick={() => onOpenAsset(r.asset_id)}>
          <span className={`t-kind ${r.kind}`}>{r.kind}</span> <b>{r.asset_id}</b> {r.title}
          <div className="muted small">{r.subtitle} {r.date && '· ' + day(r.date)}</div>
        </div>
      ))}
    </div>
  )
}
