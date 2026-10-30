import { useEffect, useState } from 'react'
import { HardHat, MessageSquareText, Wrench } from 'lucide-react'
import { api, day, label } from '../api'
import { lakh, Seg, TYPE_NAME, TypeBadge, typeFromId } from '../ui'

export function ReviewQueue({ onChanged, onOpenAsset }) {
  const [items, setItems] = useState(null)
  const [target, setTarget] = useState({})
  const [err, setErr] = useState('')
  const load = () => api.review().then(setItems).catch((e) => setErr(e.message))
  useEffect(() => { load() }, [])
  const act = async (c, body) => {
    setErr('')
    try { await api.decide(c.id, body); await load(); onChanged && onChanged() } catch (e) { setErr(e.message) }
  }

  return (
    <section className="card">
      <div className="card-head">
        <div>
          <h2 className="h-card">Review queue</h2>
          <p className="sub">Complaints the system could not place with confidence. It suggests an asset; you decide.</p>
        </div>
        {items && <span className="tag dark">{items.length} waiting</span>}
      </div>
      {err && <div className="error-box">{err}</div>}
      {!items && <p className="muted">Loading…</p>}
      {items?.length === 0 && <p className="empty-state">Nothing to review. New complaints that are far from known assets, or worded vaguely, will wait here.</p>}
      <div className="rows">
        {items?.map((c) => (
          <div key={c.id} className="row-item static" style={{ gridTemplateColumns: '44px minmax(0,1fr) auto' }}>
            <TypeBadge type={c.category} tone="warm" />
            <div style={{ minWidth: 0 }}>
              <p className="row-title" style={{ whiteSpace: 'normal' }}>{c.text}</p>
              <p className="row-sub">
                #{c.id}, {day(c.created_at)}. Suggested: <button className="btn-text" style={{ textDecoration: 'underline' }} onClick={() => onOpenAsset(c.asset_id)}>{c.asset_name}</button>
                {c.match_score != null && <> (match {c.match_score})</>}
              </p>
            </div>
            <div className="row-end" style={{ flexWrap: 'wrap', justifyContent: 'flex-end' }}>
              <button className="btn-dark" style={{ height: 40, padding: '0 18px', fontSize: 13.5 }} onClick={() => act(c, { action: 'confirm' })}>Confirm match</button>
              <input className="input" style={{ width: 150, padding: '10px 14px' }} placeholder="Other asset ID" aria-label="Move to another asset ID"
                value={target[c.id] || ''} onChange={(e) => setTarget({ ...target, [c.id]: e.target.value.toUpperCase() })} />
              <button className="btn-light" style={{ height: 40 }} disabled={!target[c.id]} onClick={() => act(c, { action: 'reassign', asset_id: target[c.id] })}>Move</button>
            </div>
          </div>
        ))}
      </div>
    </section>
  )
}

export function Contractors() {
  const [rows, setRows] = useState(null)
  useEffect(() => { api.contractors().then(setRows) }, [])
  if (!rows) return <section className="card muted">Loading…</section>
  const best = Math.max(...rows.map((r) => r.avg_days_lasted || 0), 1)
  return (
    <section className="card">
      <div className="card-head">
        <div>
          <h2 className="h-card">How long each contractor's repairs last</h2>
          <p className="sub">Average days a repair held before the same asset failed again. Each pill is 20 days; longer is better.</p>
        </div>
      </div>
      <div className="rows">
        {rows.map((r) => (
          <div key={r.contractor} className="row-item static">
            <span className="badge-ic"><HardHat size={18} /></span>
            <div style={{ minWidth: 0 }}>
              <p className="row-title">{r.contractor}</p>
              <p className="row-sub">{r.repairs} repairs, {lakh(r.spend)} spent</p>
            </div>
            <div className="row-metric">
              Repairs lasted <b className="num">{r.avg_days_lasted ?? '—'} days</b>
              <Seg value={Math.round((r.avg_days_lasted || 0) / 20)} total={Math.ceil(best / 20)} tone={r.avg_days_lasted === best ? 'yellow' : ''}
                label={`${r.avg_days_lasted} days on average`} />
            </div>
            <span className={`tag ${r.failed_again / r.repairs > 0.7 ? 'coral' : ''}`}>{r.failed_again} of {r.repairs} failed again</span>
          </div>
        ))}
      </div>
    </section>
  )
}

export function Insights() {
  const [bt, setBt] = useState(null)
  useEffect(() => { api.backtest().then(setBt) }, [])
  if (!bt) return <section className="card muted">Loading…</section>
  return (
    <div className="stack">
      <section className="card">
        <div className="card-head">
          <div>
            <h2 className="h-card">Does the failure estimate hold up?</h2>
            <p className="sub" style={{ maxWidth: 640 }}>
              For each asset with enough history, we hide its latest failure, estimate a window from the earlier gaps,
              then check whether the real failure fell inside it. {bt.note}
            </p>
          </div>
        </div>
        <div className="kpi-row">
          <div className="kpi"><b className="num">{bt.tested_assets}</b><span>assets tested</span></div>
          <div className="kpi yellow"><b className="num">{bt.inside_window}</b><span>caught inside the window</span></div>
          <div className="kpi"><b className="num">{bt.hit_rate != null ? Math.round(bt.hit_rate * 100) + '%' : '—'}</b><span>hit rate</span></div>
          <div className="kpi"><b className="num">{bt.median_days_outside_when_missed}</b><span>median days off when missed</span></div>
        </div>
      </section>
      <section className="card">
        <table className="table">
          <thead><tr><th>Asset</th><th>Estimated window</th><th>Actual failure</th><th>Result</th></tr></thead>
          <tbody>
            {bt.results.map((r) => (
              <tr key={r.asset_id}>
                <td><b>{r.name}</b><div className="muted small">{r.asset_id}</div></td>
                <td className="num">{day(r.window[0])} to {day(r.window[1])}</td>
                <td className="num">{day(r.actual)}</td>
                <td className={r.hit ? 'hit' : 'miss'}>{r.hit ? 'Inside the window' : `${r.days_outside} days outside`}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </div>
  )
}

const KIND_IC = { complaint: MessageSquareText, repair: Wrench }

export function SearchResults({ q, onOpenAsset, onClear }) {
  const [res, setRes] = useState(null)
  useEffect(() => { setRes(null); api.search(q).then(setRes) }, [q])
  return (
    <section className="card">
      <div className="card-head">
        <div><h2 className="h-card">Results for “{q}”</h2><p className="sub">Assets, complaints and repairs, closest matches first.</p></div>
        <button className="btn-light" onClick={onClear}>Clear search</button>
      </div>
      {!res && <p className="muted">Searching…</p>}
      {res?.length === 0 && <p className="empty-state">Nothing in the history matches. Try a street name, an asset ID like ROAD-2045, or words like “drain overflow”.</p>}
      <div className="rows">
        {res?.map((r, i) => {
          const Ic = KIND_IC[r.kind]
          return (
            <button key={i} className="row-item" style={{ gridTemplateColumns: '44px minmax(0,1fr) auto' }} onClick={() => onOpenAsset(r.asset_id)}>
              {Ic ? <span className="badge-ic"><Ic size={18} /></span> : <TypeBadge type={typeFromId(r.asset_id)} />}
              <div style={{ minWidth: 0 }}>
                <p className="row-title">{r.title}</p>
                <p className="row-sub">{r.kind === 'asset' ? r.asset_id : `${r.subtitle}${r.date ? `, ${day(r.date)}` : ''}`}</p>
              </div>
              <span className="tag">{label(r.kind)}</span>
            </button>
          )
        })}
      </div>
    </section>
  )
}

export { TYPE_NAME }
