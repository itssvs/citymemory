import { useEffect, useState } from 'react'
import { Sparkles, TrendingDown, TrendingUp } from 'lucide-react'
import { api, day, MATCHER } from '../api'
import { Seg, TYPE_NAME, TypeBadge } from '../ui'
import AssetMap, { MapLegend } from './AssetMap'

export default function Patterns({ assets, onOpenAsset }) {
  const [res, setRes] = useState(null)
  const [err, setErr] = useState('')
  const [sel, setSel] = useState(0)
  useEffect(() => { api.patterns().then(setRes).catch((e) => setErr(e.message)) }, [])

  if (err) return <section className="card"><div className="error-box">{err}</div></section>
  if (!res) return <section className="card muted">Grouping every complaint in the ward by meaning…</section>
  const ps = res.patterns
  if (!ps.length) return <section className="card empty-state">No recurring patterns yet.</section>
  const p = ps[Math.min(sel, ps.length - 1)]
  const inPattern = new Set(p.assets.map((a) => a.asset_id))
  const maxSize = Math.max(...ps.map((x) => x.size))
  const types = Object.keys(p.categories)

  return (
    <div className="grid12">
      <section className="card span-5">
        <div className="card-head">
          <div>
            <h2 className="h-card">Recurring patterns</h2>
            <p className="sub">Every complaint grouped by what it means, across assets, using {MATCHER[res.method] || res.method}.</p>
          </div>
        </div>
        <div className="rows">
          {ps.map((x, i) => (
            <button key={x.id} className={`row-item ${i === sel ? 'sel' : ''}`} style={{ gridTemplateColumns: '44px minmax(0,1fr) auto' }}
              onClick={() => setSel(i)} aria-pressed={i === sel}>
              <TypeBadge type={Object.keys(x.categories)[0]} tone={x.cross_type ? 'hot' : ''} />
              <div style={{ minWidth: 0 }}>
                <p className="row-title">{x.label}</p>
                <p className="row-sub">{x.size} complaints across {x.assets.length} asset{x.assets.length > 1 ? 's' : ''}</p>
                <div className="tags">
                  {x.cross_type && <span className="tag coral">Spans {Object.keys(x.categories).map((c) => TYPE_NAME[c].toLowerCase()).join(' and ')}</span>}
                  {x.label_source === 'llm' && <span className="tag"><Sparkles size={11} style={{ verticalAlign: -1 }} /> AI named</span>}
                </div>
              </div>
              <Seg value={Math.max(1, Math.round((x.size / maxSize) * 10))} total={10} tone={x.cross_type ? '' : 'dark'} label={`${x.size} complaints`} />
            </button>
          ))}
        </div>
      </section>

      <div className="span-7 pattern-detail">
        <section className="card flush map-card">
          <AssetMap assets={assets.filter((a) => inPattern.has(a.asset_id))} onSelect={onOpenAsset} height={320} fit />
          <MapLegend />
        </section>
        <section className="card">
          <div className="card-head">
            <div>
              <h2 className="h-card">{p.label}</h2>
              {p.description && <p className="sub">{p.description}</p>}
            </div>
            <span className={`tag ${p.trend === 'rising' ? 'coral' : ''}`}>
              {p.trend === 'rising' ? <TrendingUp size={12} style={{ verticalAlign: -2 }} /> : <TrendingDown size={12} style={{ verticalAlign: -2 }} />} {p.trend}
            </span>
          </div>
          <div className="kpi-row" style={{ marginBottom: 16 }}>
            <div className="kpi" style={{ background: 'var(--row)' }}><b className="num">{p.size}</b><span>complaints</span></div>
            <div className="kpi" style={{ background: 'var(--row)' }}><b className="num">{p.assets.length}</b><span>assets</span></div>
            <div className="kpi yellow"><b className="num">{p.last_90_days}</b><span>last 90 days</span></div>
            <div className="kpi" style={{ background: 'var(--row)' }}><b className="num">{p.previous_90_days}</b><span>90 days before</span></div>
          </div>
          {p.cross_type && (
            <p className="callout" style={{ marginBottom: 16 }}>
              The same complaint shows up on {types.map((c) => `${p.categories[c]} ${TYPE_NAME[c].toLowerCase()}`).join(' and ')} reports.
              Fixing the shared cause could stop several failures at once.
            </p>
          )}
          <h3 className="h-section" style={{ marginBottom: 10 }}>What people wrote</h3>
          <ul className="quote-list">{p.examples.map((e) => <li key={e}>“{e}”</li>)}</ul>
          <h3 className="h-section" style={{ margin: '18px 0 10px' }}>Assets involved</h3>
          <div className="chip-row">
            {p.assets.map((a) => (
              <button key={a.asset_id} className="tag" style={{ border: 0, cursor: 'pointer', padding: '6px 12px', background: 'var(--row)' }}
                onClick={() => onOpenAsset(a.asset_id)}>{a.name}, {a.complaints}</button>
            ))}
          </div>
          <p className="note" style={{ marginTop: 14 }}>
            From {day(p.first)} to {day(p.last)}{p.spread_m > 0 && `, assets up to ${p.spread_m} m apart`}.
          </p>
        </section>
      </div>
    </div>
  )
}
