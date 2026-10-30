import { useEffect, useState } from 'react'
import { api, day, label, level, rupees, TYPE_ICON } from '../api'

function CostCompare({ cost }) {
  const max = Math.max(cost.patch_spend_total, cost.replacement_cost, 1)
  const replace = cost.recommendation === 'replace'
  return (
    <div className={`reco ${replace ? 'reco-replace' : 'reco-patch'}`}>
      <div className="reco-title">{replace ? 'Stop patching: plan a permanent fix' : cost.recommendation === 'patch' ? 'Patching is still reasonable' : 'Not enough repair history'}</div>
      {cost.replacement_cost > 0 && (
        <div className="bars">
          <div className="bar-row">
            <span>Spent on patches so far</span>
            <div className="bar"><div style={{ width: `${(cost.patch_spend_total / max) * 100}%` }} className="fill warn" /></div>
            <b>{rupees(cost.patch_spend_total)}</b>
          </div>
          <div className="bar-row">
            <span>One permanent fix</span>
            <div className="bar"><div style={{ width: `${(cost.replacement_cost / max) * 100}%` }} className="fill ok" /></div>
            <b>{rupees(cost.replacement_cost)}</b>
          </div>
        </div>
      )}
      <p>{cost.message}</p>
    </div>
  )
}

function RepairForm({ assetId, onDone }) {
  const [f, setF] = useState({ repair_type: 'temporary', cost: '', contractor: '', notes: '' })
  const [err, setErr] = useState('')
  const submit = async (e) => {
    e.preventDefault()
    setErr('')
    try {
      await api.repair({ ...f, cost: Number(f.cost), asset_id: assetId })
      setF({ repair_type: 'temporary', cost: '', contractor: '', notes: '' })
      onDone()
    } catch (x) { setErr(x.message) }
  }
  return (
    <form className="repair-form" onSubmit={submit}>
      <h4>Log a repair</h4>
      <div className="row">
        <select value={f.repair_type} onChange={(e) => setF({ ...f, repair_type: e.target.value })}>
          <option value="temporary">Temporary (patch)</option>
          <option value="permanent">Permanent fix</option>
        </select>
        <input required type="number" min="0" placeholder="Cost (₹)" value={f.cost} onChange={(e) => setF({ ...f, cost: e.target.value })} />
      </div>
      <input required placeholder="Contractor" value={f.contractor} onChange={(e) => setF({ ...f, contractor: e.target.value })} />
      <input placeholder="What was done" value={f.notes} onChange={(e) => setF({ ...f, notes: e.target.value })} />
      {err && <div className="error">{err}</div>}
      <button className="btn">Save repair</button>
    </form>
  )
}

function AiSummary({ assetId, fallback, version }) {
  const [s, setS] = useState(null)
  useEffect(() => {
    let live = true
    setS(null)
    api.aiSummary(assetId).then((r) => live && setS(r)).catch(() => live && setS({ text: fallback, source: 'template' }))
    return () => { live = false }
  }, [assetId, version])
  return (
    <div className="summary">
      <div className="summary-label">
        {!s ? 'Writing briefing…' : s.source === 'llm' ? `AI briefing · ${s.model} · written only from the records below` : 'Briefing from records (AI model offline)'}
      </div>
      {s ? s.text : fallback}
    </div>
  )
}

export default function AssetPanel({ assetId, onClose, onChanged }) {
  const [d, setD] = useState(null)
  const [err, setErr] = useState('')
  const [version, setVersion] = useState(0)
  const load = () => api.asset(assetId).then((r) => { setD(r); setVersion((v) => v + 1) }).catch((e) => setErr(e.message))
  useEffect(() => { setD(null); load() }, [assetId])

  if (err) return <div className="panel"><div className="error">{err}</div></div>
  if (!d) return <div className="panel muted">Loading {assetId}…</div>
  const a = d.asset
  const p = d.priority
  return (
    <div className="panel asset-panel">
      <div className="panel-head">
        <div>
          <div className="asset-id">{a.asset_id} · {TYPE_ICON[a.type]}{!a.registered && <span className="tag">unregistered</span>}</div>
          <h2>{a.name}</h2>
        </div>
        <button className="icon-btn" onClick={onClose} aria-label="Close">×</button>
      </div>

      <div className="kpis">
        <div><b>{d.stats.incidents}</b><span>failures</span></div>
        <div><b>{d.stats.complaints}</b><span>complaints</span></div>
        <div><b>{d.stats.repairs}</b><span>repairs</span></div>
        <div className={`score ${level(p.score)}`}><b>{p.score}</b><span>priority</span></div>
      </div>
      {d.stats.recurring && <div className="flag">Recurring: {d.stats.incidents_12m} failures in the last 12 months</div>}

      <AiSummary assetId={a.asset_id} fallback={d.summary} version={version} />

      <CostCompare cost={d.cost} />

      <h4>Why it ranks here</h4>
      <div className="breakdown">
        {p.components.map((c) => (
          <div key={c.name} className="bd-row">
            <span className="bd-name">{c.name}</span>
            <div className="bar"><div className="fill" style={{ width: `${Math.min(100, (c.points / 35) * 100)}%` }} /></div>
            <span className="bd-pts">{c.points}</span>
            <div className="bd-reason">{c.reason}</div>
          </div>
        ))}
      </div>

      <div className="two">
        <div>
          <h4>Likely cause</h4>
          <div className="chips">
            {Object.entries(d.cause.counts).length
              ? Object.entries(d.cause.counts).map(([k, v]) => <span key={k} className={`chip ${k === d.cause.primary ? 'chip-main' : ''}`}>{label(k)} · {v}</span>)
              : <span className="muted">No cause signals yet</span>}
          </div>
          <div className="muted small source-note">
            {d.cause.sources?.llm ? `${d.cause.sources.llm} of ${d.stats.complaints} complaints tagged by the AI model` : 'Tagged by keyword rules (AI model offline)'}
          </div>
        </div>
        <div>
          <h4>Next failure window</h4>
          {d.failure_window.available
            ? <p className="window">{day(d.failure_window.earliest)} to {day(d.failure_window.latest)}<br /><small>avg gap {d.failure_window.mean_gap_days} days · estimate, not a forecast</small></p>
            : <p className="muted">{d.failure_window.reason}</p>}
        </div>
      </div>

      <h4>Timeline</h4>
      <ol className="timeline">
        {d.timeline.map((e) => (
          <li key={e.kind + e.id} className={e.kind}>
            <div className="t-date">{day(e.date)}</div>
            {e.kind === 'complaint' ? (
              <div className="t-body">
                <span className="t-kind">Complaint</span> {e.text}
                {e.cause && e.cause !== 'unknown' && (
                  <span className={`chip small ${e.cause_source === 'llm' ? 'chip-ai' : ''}`} title={`${e.cause_source === 'llm' ? 'AI' : 'Keyword rule'}: ${e.cause_reason || ''}`}>
                    {label(e.cause)}{e.cause_source === 'llm' ? ' · AI' : ''}
                  </span>
                )}
                {e.match_status === 'review' && <span className="tag">needs review</span>}
                {e.photo_url && <img src={api.photo(e.photo_url)} alt="complaint" className="thumb" />}
              </div>
            ) : (
              <div className="t-body">
                <span className={`t-kind ${e.repair_type}`}>{e.repair_type === 'permanent' ? 'Permanent fix' : 'Patch'}</span>
                {' '}{e.notes} · {e.contractor} · {rupees(e.cost)}
                <div className="lasted">{e.lasted_days != null ? `Failed again after ${e.lasted_days} days` : 'Holding so far'}</div>
              </div>
            )}
          </li>
        ))}
      </ol>

      <RepairForm assetId={a.asset_id} onDone={() => { load(); onChanged && onChanged() }} />
    </div>
  )
}
