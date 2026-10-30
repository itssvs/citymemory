import { useEffect, useState } from 'react'
import { api, day, MATCHER, TYPE_ICON } from '../api'
import AssetMap from './AssetMap'

export default function Patterns({ assets, onOpenAsset }) {
  const [res, setRes] = useState(null)
  const [err, setErr] = useState('')
  const [sel, setSel] = useState(0)
  useEffect(() => { api.patterns().then(setRes).catch((e) => setErr(e.message)) }, [])

  if (err) return <div className="panel error">{err}</div>
  if (!res) return <div className="panel muted">Finding recurring patterns across the ward…</div>
  const ps = res.patterns
  if (!ps.length) return <div className="panel empty">No recurring patterns yet.</div>
  const p = ps[Math.min(sel, ps.length - 1)]
  const inPattern = new Set(p.assets.map((a) => a.asset_id))

  return (
    <div className="patterns">
      <div className="panel">
        <h2>Recurring patterns across the ward</h2>
        <p className="muted small">
          Every complaint is grouped by meaning, not by asset, using {MATCHER[res.method] || res.method}. A pattern that spans
          several assets or asset types often points to one shared cause.
        </p>
        <ol className="pattern-list">
          {ps.map((x, i) => (
            <li key={x.id} className={i === sel ? 'sel' : ''} onClick={() => setSel(i)}>
              <div className="q-title">{x.label}</div>
              <div className="muted small">
                {x.size} complaints · {x.assets.length} asset{x.assets.length > 1 ? 's' : ''} · {x.last_90_days} in last 90 days
              </div>
              <div className="q-tags">
                {x.cross_type && <span className="tag danger">spans {Object.keys(x.categories).map((c) => TYPE_ICON[c].toLowerCase()).join(' + ')}</span>}
                <span className={`tag ${x.trend === 'rising' ? 'warn' : ''}`}>{x.trend}</span>
                {x.label_source === 'llm' && <span className="tag ai">AI label</span>}
              </div>
            </li>
          ))}
        </ol>
      </div>

      <div className="pattern-detail">
        <div className="panel map-panel">
          <AssetMap assets={assets.filter((a) => inPattern.has(a.asset_id))} onSelect={onOpenAsset} height={300} fit />
        </div>
        <div className="panel">
          <h2>{p.label}</h2>
          {p.description && <p>{p.description}</p>}
          <div className="kpis">
            <div><b>{p.size}</b><span>complaints</span></div>
            <div><b>{p.assets.length}</b><span>assets</span></div>
            <div><b>{p.last_90_days}</b><span>last 90 days</span></div>
            <div><b>{p.previous_90_days}</b><span>90 days before</span></div>
          </div>
          {p.cross_type && (
            <div className="flag">
              The same kind of complaint appears on {Object.entries(p.categories).map(([c, n]) => `${n} ${TYPE_ICON[c].toLowerCase()}`).join(' and ')} reports.
              Fixing the shared cause may stop several failures at once.
            </div>
          )}
          <h4>Typical complaints</h4>
          <ul className="examples">{p.examples.map((e) => <li key={e}>“{e}”</li>)}</ul>
          <h4>Assets involved</h4>
          <div className="chips">
            {p.assets.map((a) => (
              <button key={a.asset_id} className="chip chip-btn" onClick={() => onOpenAsset(a.asset_id)}>
                {a.asset_id} · {a.name} · {a.complaints}
              </button>
            ))}
          </div>
          <p className="muted small">From {day(p.first)} to {day(p.last)}{p.spread_m > 0 && ` · assets up to ${p.spread_m} m apart`}</p>
        </div>
      </div>
    </div>
  )
}
