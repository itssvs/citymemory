import { useEffect, useState } from 'react'
import { CircleCheck, Hammer, MessageSquareText, Sparkles, TriangleAlert, Wrench } from 'lucide-react'
import { api, day, label, rupees } from '../api'
import { CloseBtn, lakh, TYPE_NAME, TypeBadge, scoreTone } from '../ui'
import WorkOrderCard from './WorkOrder'

function Briefing({ assetId, fallback, version }) {
  const [s, setS] = useState(null)
  useEffect(() => {
    let live = true
    setS(null)
    api.aiSummary(assetId).then((r) => live && setS(r)).catch(() => live && setS({ text: fallback, source: 'template' }))
    return () => { live = false }
  }, [assetId, version])
  return (
    <section className="briefing">
      <div className="briefing-label">
        <Sparkles size={15} />
        {!s ? 'Writing a briefing from the records…' : s.source === 'llm' ? `AI briefing by ${s.model}, written only from the records below` : 'Briefing from the records'}
      </div>
      <p>{s ? s.text : fallback}</p>
    </section>
  )
}

function Verdict({ cost }) {
  const replace = cost.recommendation === 'replace'
  const fixed = cost.recommendation === 'fixed'
  const max = Math.max(cost.patch_spend_total, cost.replacement_cost, 1)
  const title = replace ? 'Stop patching. Plan a permanent fix.' : fixed ? 'Fixed permanently'
    : cost.recommendation === 'patch' ? 'Patching is still reasonable' : 'Not enough repair history yet'
  return (
    <section className={`verdict ${replace ? 'replace' : fixed ? 'fixed' : ''}`}>
      <div className="verdict-title">{replace ? <TriangleAlert size={18} color="#f8d44c" /> : <CircleCheck size={18} />}{title}</div>
      {cost.replacement_cost > 0 && (
        <div className="cmp">
          <div className="cmp-row"><span>Spent on patches so far</span><div className="cmp-bar"><i className="coral" style={{ width: `${(cost.patch_spend_total / max) * 100}%` }} /></div><b className="num">{rupees(cost.patch_spend_total)}</b></div>
          <div className="cmp-row"><span>One permanent fix</span><div className="cmp-bar"><i className="yellow" style={{ width: `${(cost.replacement_cost / max) * 100}%` }} /></div><b className="num">{rupees(cost.replacement_cost)}</b></div>
        </div>
      )}
      <p className={replace ? 'muted' : 'sub'}>{cost.message}</p>
    </section>
  )
}

export default function AssetPanel({ assetId, onClose, canEdit = false, onChanged }) {
  const [d, setD] = useState(null)
  const [err, setErr] = useState('')
  const [version, setVersion] = useState(0)
  const load = () => api.asset(assetId).then((r) => { setD(r); setVersion((v) => v + 1) }).catch((e) => setErr(e.message))
  useEffect(() => { setD(null); setErr(''); load() }, [assetId])
  const changed = () => { load(); onChanged && onChanged() }

  if (err) return <><div className="drawer-head"><span /><CloseBtn onClick={onClose} /></div><div className="error-box">{err}</div></>
  if (!d) return <><div className="drawer-head"><p className="muted">Loading {assetId}…</p><CloseBtn onClick={onClose} /></div></>
  const a = d.asset, p = d.priority
  const tone = scoreTone(p.score)
  return (
    <>
      <div className="drawer-head">
        <div style={{ display: 'flex', gap: 14, alignItems: 'center' }}>
          <TypeBadge type={a.type} tone={tone === 'high' ? 'hot' : tone === 'mid' ? 'warm' : ''} />
          <div>
            <p className="muted small">{a.asset_id}, {TYPE_NAME[a.type]}{a.registered ? '' : ' (not yet verified)'}</p>
            <h2 className="h-card">{a.name}</h2>
          </div>
        </div>
        <CloseBtn onClick={onClose} />
      </div>

      <div className="kpi-row">
        <div className={`kpi ${tone === 'high' ? 'coral' : tone === 'mid' ? 'yellow' : ''}`}><b className="num">{p.score}</b><span>priority of 100</span></div>
        <div className="kpi"><b className="num">{d.stats.incidents}</b><span>failures in total</span></div>
        <div className="kpi"><b className="num">{d.stats.complaints}</b><span>complaints</span></div>
        <div className="kpi"><b className="num">{d.stats.repairs}</b><span>repairs</span></div>
      </div>
      {d.stats.recurring && <div className="callout">Failing repeatedly: {d.stats.incidents_12m} separate failures in the last 12 months.</div>}

      <Briefing assetId={a.asset_id} fallback={d.summary} version={version} />
      <Verdict cost={d.cost} />
      <WorkOrderCard asset={a} wo={d.work_order} history={d.work_orders} recommendation={d.cost.recommendation}
        targetDays={d.target_days} canEdit={canEdit} onChanged={changed} />

      <section className="card">
        <h3 className="h-section" style={{ marginBottom: 14 }}>Why it ranks here</h3>
        <div className="why">
          {p.components.map((c) => (
            <div key={c.name} className="why-row">
              <span>{c.name}</span>
              <div className="bar"><i style={{ width: `${Math.min(100, (c.points / 35) * 100)}%` }} /></div>
              <b className="num">{c.points}</b>
              <small>{c.reason}</small>
            </div>
          ))}
        </div>
      </section>

      <div className="two-col">
        <section className="card">
          <h3 className="h-section" style={{ marginBottom: 10 }}>Likely cause</h3>
          <div className="chip-row">
            {Object.entries(d.cause.counts).length
              ? Object.entries(d.cause.counts).map(([k, v]) => <span key={k} className={`tag ${k === d.cause.primary ? 'dark' : ''}`}>{label(k)} ({v})</span>)
              : <span className="muted">No cause signals yet</span>}
          </div>
          <p className="note" style={{ marginTop: 10 }}>
            {d.cause.sources?.llm ? `${d.cause.sources.llm} of ${d.stats.complaints} complaints tagged by the AI model` : 'Tagged by keyword rules'}
          </p>
        </section>
        <section className="card">
          <h3 className="h-section" style={{ marginBottom: 10 }}>Next likely failure</h3>
          {d.failure_window.available
            ? <><p className="strong">{day(d.failure_window.earliest)} to {day(d.failure_window.latest)}</p><p className="note">Based on an average gap of {d.failure_window.mean_gap_days} days. An estimate, not a forecast.</p></>
            : <p className="muted">Needs at least three past failures.</p>}
        </section>
      </div>

      <section>
        <h3 className="h-section" style={{ marginBottom: 12 }}>History</h3>
        <ol className="timeline">
          {d.timeline.map((e) => (
            <li key={e.kind + e.id}>
              {e.kind === 'complaint'
                ? <span className="tl-ic"><MessageSquareText size={16} /></span>
                : <span className={`tl-ic ${e.repair_type === 'permanent' ? 'permanent' : 'repair'}`}>{e.repair_type === 'permanent' ? <Hammer size={16} /> : <Wrench size={16} />}</span>}
              <div>
                <p className="tl-meta">{day(e.date)}, {e.kind === 'complaint' ? 'complaint' : e.repair_type === 'permanent' ? 'permanent fix' : 'patch'}</p>
                {e.kind === 'complaint' ? (
                  <>
                    <p className="tl-text">{e.text}</p>
                    <div className="tags">
                      {e.cause && e.cause !== 'unknown' && <span className="tag" title={e.cause_reason || ''}>{label(e.cause)}{e.cause_source === 'llm' ? ', AI tagged' : ''}</span>}
                      {e.match_status === 'review' && <span className="tag yellow">Waiting for review</span>}
                    </div>
                    {e.photo_url && <img src={api.photo(e.photo_url)} alt="Photo attached to the complaint" className="thumb" />}
                  </>
                ) : (
                  <>
                    <p className="tl-text">{e.notes || 'Repair'}, by {e.contractor}, {lakh(e.cost)}</p>
                    <p className={`tl-lasted ${e.lasted_days != null ? 'bad' : 'ok'}`}>
                      {e.lasted_days != null ? `Failed again after ${e.lasted_days} days` : 'Holding so far'}
                    </p>
                    {e.after_photo_url && <img src={api.photo(e.after_photo_url)} alt="Photo after the repair" className="thumb" />}
                  </>
                )}
              </div>
            </li>
          ))}
        </ol>
      </section>
    </>
  )
}
