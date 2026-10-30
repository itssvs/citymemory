// The repair job for one asset: assign it, mark work started, mark it fixed.
import { useEffect, useState } from 'react'
import { Camera, CircleCheck, Clock, HardHat, Play } from 'lucide-react'
import { api, day } from '../api'
import { lakh } from '../ui'

const todayPlus = (n) => {
  const d = new Date(); d.setDate(d.getDate() + n)
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

export function WoStatus({ wo }) {
  if (wo.overdue) return <span className="wo-pill overdue"><Clock size={13} />Overdue by {wo.days_overdue} day{wo.days_overdue === 1 ? '' : 's'}</span>
  return <span className={`wo-pill ${wo.status}`}>{wo.status_label}</span>
}

function AssignForm({ asset, recommendation, targetDays, onDone }) {
  const [names, setNames] = useState([])
  const [f, setF] = useState({ contractor: '', repair_type: recommendation === 'replace' ? 'permanent' : 'temporary', due_date: todayPlus(targetDays || 7), notes: '' })
  const [err, setErr] = useState('')
  const [busy, setBusy] = useState(false)
  useEffect(() => { api.contractors().then((r) => setNames(r.map((c) => c.contractor))).catch(() => {}) }, [])
  const submit = async (e) => {
    e.preventDefault(); setErr(''); setBusy(true)
    try { await api.assignWork(asset.asset_id, f); onDone() } catch (x) { setErr(x.message) } finally { setBusy(false) }
  }
  return (
    <form className="form" onSubmit={submit}>
      <div className="field" role="group" aria-label="Type of repair">
        Type of repair
        <div className="choice">
          {[['temporary', 'Temporary patch'], ['permanent', 'Permanent fix']].map(([v, l]) => (
            <button type="button" key={v} className={f.repair_type === v ? 'on' : ''} aria-pressed={f.repair_type === v}
              onClick={() => setF({ ...f, repair_type: v })}>{l}</button>
          ))}
        </div>
        {recommendation === 'replace' && f.repair_type === 'temporary' && (
          <span className="hint warn">The records recommend a permanent fix for this asset. Another patch is likely to fail again.</span>
        )}
      </div>
      <label className="field">Contractor
        <input list="contractor-names" required placeholder="Choose or type a contractor" value={f.contractor}
          onChange={(e) => setF({ ...f, contractor: e.target.value })} />
        <datalist id="contractor-names">{names.map((n) => <option key={n} value={n} />)}</datalist>
      </label>
      <label className="field">Target date
        <input type="date" required min={todayPlus(0)} value={f.due_date} onChange={(e) => setF({ ...f, due_date: e.target.value })} />
        <span className="hint">Standard time for this type of asset: {targetDays} days.</span>
      </label>
      <label className="field">Instructions (optional)
        <input placeholder="What needs doing" value={f.notes} onChange={(e) => setF({ ...f, notes: e.target.value })} />
      </label>
      {err && <div className="error-box">{err}</div>}
      <button className="btn-dark" disabled={busy}><HardHat size={16} />{busy ? 'Assigning…' : 'Assign repair'}</button>
    </form>
  )
}

function CompleteForm({ wo, onDone, onCancel }) {
  const [f, setF] = useState({ cost: '', notes: '' })
  const [photo, setPhoto] = useState(null)
  const [err, setErr] = useState('')
  const [busy, setBusy] = useState(false)
  const submit = async (e) => {
    e.preventDefault(); setErr(''); setBusy(true)
    const fd = new FormData()
    fd.append('cost', f.cost); fd.append('notes', f.notes)
    if (photo) fd.append('photo', photo)
    try { await api.completeWork(wo.id, fd); onDone() } catch (x) { setErr(x.message) } finally { setBusy(false) }
  }
  return (
    <form className="form" onSubmit={submit} style={{ marginTop: 14 }}>
      <label className="field">Actual cost (₹)
        <input type="number" required min="0" step="100" inputMode="numeric" value={f.cost} onChange={(e) => setF({ ...f, cost: e.target.value })} />
      </label>
      <label className="field">What was done
        <input placeholder="For example: resurfaced 40 m, drain rebuilt" value={f.notes} onChange={(e) => setF({ ...f, notes: e.target.value })} />
      </label>
      <label className="file-pick">
        <span className="btn-round"><Camera size={15} /></span>
        <span>{photo ? photo.name : 'Add an after-repair photo'}</span>
        <input type="file" accept="image/*" onChange={(e) => setPhoto(e.target.files[0] || null)} />
      </label>
      {err && <div className="error-box">{err}</div>}
      <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
        <button className="btn-dark" disabled={busy}><CircleCheck size={16} />{busy ? 'Saving…' : 'Mark as fixed'}</button>
        <button type="button" className="btn-light" onClick={onCancel}>Cancel</button>
      </div>
    </form>
  )
}

/** Work-order card shown in the asset panel. Only engineers can change it. */
export default function WorkOrderCard({ asset, wo, history, recommendation, targetDays, canEdit, onChanged }) {
  const [finishing, setFinishing] = useState(false)
  const [err, setErr] = useState('')
  const start = async () => { setErr(''); try { await api.startWork(wo.id); onChanged() } catch (x) { setErr(x.message) } }
  const last = (history || []).find((w) => w.status === 'completed')

  return (
    <section className="card wo-card" aria-label="Repair job">
      <div className="card-head" style={{ marginBottom: 14 }}>
        <div>
          <h3 className="h-section">Repair job</h3>
          {!wo && <p className="sub">{canEdit ? 'No repair is assigned yet.' : 'No repair is assigned at the moment.'}</p>}
        </div>
        {wo && <WoStatus wo={wo} />}
      </div>

      {wo && (
        <>
          <dl className="wo-facts">
            <div><dt>Contractor</dt><dd>{wo.contractor}</dd></div>
            <div><dt>Type</dt><dd>{wo.repair_type === 'permanent' ? 'Permanent fix' : 'Temporary patch'}</dd></div>
            <div><dt>Assigned</dt><dd>{day(wo.created_at)}</dd></div>
            <div><dt>Target date</dt><dd className={wo.overdue ? 'late' : ''}>{day(wo.due_date)}{wo.days_left != null && ` (${wo.days_left} day${wo.days_left === 1 ? '' : 's'} left)`}</dd></div>
            {wo.started_at && <div><dt>Work started</dt><dd>{day(wo.started_at)}</dd></div>}
          </dl>
          {wo.notes && <p className="sub" style={{ marginTop: 10 }}>{wo.notes}</p>}
          {canEdit && !finishing && (
            <div style={{ display: 'flex', gap: 10, marginTop: 16, flexWrap: 'wrap' }}>
              {wo.status === 'assigned' && <button className="btn-light" onClick={start}><Play size={15} style={{ verticalAlign: -2 }} /> Mark work started</button>}
              <button className="btn-dark" onClick={() => setFinishing(true)}><CircleCheck size={16} />Mark as fixed</button>
            </div>
          )}
          {canEdit && finishing && <CompleteForm wo={wo} onDone={() => { setFinishing(false); onChanged() }} onCancel={() => setFinishing(false)} />}
        </>
      )}

      {!wo && canEdit && <AssignForm asset={asset} recommendation={recommendation} targetDays={targetDays} onDone={onChanged} />}
      {!wo && last && (
        <p className="note" style={{ marginTop: 12 }}>Last job: {last.contractor}, fixed {day(last.completed_at)} for {lakh(last.cost)}.</p>
      )}
      {err && <div className="error-box" style={{ marginTop: 10 }}>{err}</div>}
    </section>
  )
}
