// Engineer's list of repair jobs: overdue first, then by target date.
import { useEffect, useState } from 'react'
import { Ellipsis } from 'lucide-react'
import { api, day } from '../api'
import { lakh, TypeBadge } from '../ui'
import { WoStatus } from './WorkOrder'

export default function WorkOrders({ onOpen, version }) {
  const [status, setStatus] = useState('open')
  const [items, setItems] = useState(null)
  const [err, setErr] = useState('')
  useEffect(() => { setItems(null); api.workOrders(status).then(setItems).catch((e) => setErr(e.message)) }, [status, version])
  const overdue = (items || []).filter((w) => w.overdue).length

  return (
    <section className="card">
      <div className="card-head">
        <div>
          <h2 className="h-card">Repair jobs</h2>
          <p className="sub">{status === 'open'
            ? (items ? `${items.length} open${overdue ? `, ${overdue} past the target date` : ''}. Open a job to start or close it.` : 'Loading…')
            : 'Finished jobs, newest first.'}</p>
        </div>
        <div className="filter-pills" role="group" aria-label="Show">
          {[['open', 'Open'], ['completed', 'Finished']].map(([k, l]) => (
            <button key={k} className={status === k ? 'on' : ''} aria-pressed={status === k} onClick={() => setStatus(k)}>{l}</button>
          ))}
        </div>
      </div>
      {err && <div className="error-box">{err}</div>}
      {items?.length === 0 && (
        <p className="empty-state">{status === 'open' ? 'No open repair jobs. Assign one from any asset in your work queue.' : 'No finished jobs yet.'}</p>
      )}
      <div className="rows">
        {items?.map((w) => (
          <button key={w.id} className={`row-item ${w.overdue ? 'late' : ''}`} onClick={() => onOpen(w.asset_id)} aria-label={`${w.asset_name}, ${w.status_label}. Open`}>
            <TypeBadge type={w.asset_type} tone={w.overdue ? 'hot' : ''} />
            <div style={{ minWidth: 0 }}>
              <p className="row-title">{w.asset_name}</p>
              <p className="row-sub">{w.contractor}, {w.repair_type === 'permanent' ? 'permanent fix' : 'temporary patch'}</p>
            </div>
            <div className="row-metric">
              {w.status === 'completed'
                ? <span>Fixed {day(w.completed_at)} for <b className="num">{lakh(w.cost)}</b></span>
                : <span>Target <b className="num">{day(w.due_date)}</b></span>}
            </div>
            <div className="row-end"><WoStatus wo={w} /><Ellipsis size={18} color="var(--muted)" aria-hidden="true" /></div>
          </button>
        ))}
      </div>
    </section>
  )
}
