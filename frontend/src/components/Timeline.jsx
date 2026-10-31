// Ward-wide searchable timeline: every complaint, repair and repair job, each linked to its asset.
import { useEffect, useMemo, useState } from 'react'
import { CalendarRange, ClipboardList, MessageSquareText, Search, Wrench, X } from 'lucide-react'
import { api, label } from '../api'
import { lakh, TYPE_ICON_C, TYPE_NAME } from '../ui'

const KINDS = [
  ['complaint', 'Complaints', MessageSquareText],
  ['repair', 'Repairs', Wrench],
  ['job', 'Repair jobs', ClipboardList],
]
const TYPES = ['road', 'drain', 'streetlight', 'footpath', 'toilet']
const MON = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
const MONTH_LONG = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December']
const MATCH_TEXT = { auto: 'Linked to this asset automatically', review: 'Waiting for an engineer to confirm the link', new_asset: 'First report of a new location', confirmed: 'Link confirmed by an engineer', rejected: 'Engineer said it is a different spot' }

const iso = (d) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
const ago = (days) => { const d = new Date(); d.setDate(d.getDate() - days); return iso(d) }
const fyStart = () => { const d = new Date(); return `${d.getMonth() >= 3 ? d.getFullYear() : d.getFullYear() - 1}-04-01` }
const lastDay = (ym) => { const [y, m] = ym.split('-').map(Number); return iso(new Date(y, m, 0)) }
const PRESETS = [
  ['all', 'All time', () => ['', '']],
  ['30', 'Last 30 days', () => [ago(30), '']],
  ['90', 'Last 3 months', () => [ago(91), '']],
  ['365', 'Last 12 months', () => [ago(365), '']],
  ['fy', 'This financial year', () => [fyStart(), '']],
]
const fmt = (s) => { const d = new Date(s); return `${d.getDate()} ${MON[d.getMonth()]} ${d.getFullYear()}` }

function MonthStrip({ months, start, end, onPick }) {
  const max = Math.max(...months.map((m) => m.complaint + m.repair + m.job), 1)
  const inRange = (m) => (!start || lastDay(m.month) >= start) && (!end || `${m.month}-01` <= end)
  return (
    <div className="tl-strip" role="list" aria-label="Events per month, last 24 months. Choose a month to show only that month.">
      {months.map((m, i) => {
        const [y, mo] = m.month.split('-').map(Number)
        const total = m.complaint + m.repair + m.job
        const name = `${MONTH_LONG[mo - 1]} ${y}: ${m.complaint} complaints, ${m.repair} repairs, ${m.job} jobs`
        return (
          <button key={m.month} role="listitem" className={`tl-month ${inRange(m) ? 'in' : ''}`} title={name} aria-label={name}
            onClick={() => onPick(`${m.month}-01`, lastDay(m.month))}>
            <span className="tl-bars" style={{ height: `${(total / max) * 100}%` }}>
              {m.repair > 0 && <i className="r" style={{ flex: m.repair }} />}
              {m.job > 0 && <i className="j" style={{ flex: m.job }} />}
              {m.complaint > 0 && <i className="c" style={{ flex: m.complaint }} />}
            </span>
            <span className="tl-mlabel">{mo === 1 || i === 0 ? `${MON[mo - 1]} ${String(y).slice(2)}` : mo % 3 === 1 ? MON[mo - 1] : ''}</span>
          </button>
        )
      })}
    </div>
  )
}

function Event({ e, onOpenAsset }) {
  const TypeIc = TYPE_ICON_C[e.asset_type]
  const d = new Date(e.date)
  const KindIc = { complaint: MessageSquareText, repair: Wrench, job: ClipboardList }[e.kind]
  const kicker = e.kind === 'complaint' ? `Complaint, ${e.source === 'staff' ? 'logged by staff' : 'from a citizen'}`
    : e.kind === 'repair' ? `${e.repair_type === 'permanent' ? 'Permanent' : e.repair_type === 'temporary' ? 'Temporary' : 'A'} repair done` : 'Repair job'
  return (
    <li className={`tl-event ${e.kind}`}>
      <div className="tl-date" aria-hidden="true"><b className="num">{d.getDate()}</b><span>{MON[d.getMonth()]}</span></div>
      <div className="tl-rail" aria-hidden="true"><span className="tl-dot"><KindIc size={15} /></span></div>
      <article className="tl-body" aria-label={`${kicker}, ${fmt(e.date)}, ${e.asset_name}`}>
        <div className="tl-top">
          <p className="tl-kicker">{kicker} · <time dateTime={e.date}>{fmt(e.date)}</time></p>
          {e.match_on && <span className="tag">{e.match_on === 'meaning' ? `Similar meaning ${e.match}` : e.match_on === 'asset' ? 'Matches asset' : 'Matches words'}</span>}
        </div>
        <p className="tl-title">{e.title}</p>
        {e.kind !== 'complaint' && e.text && <p className="tl-note">{e.text}</p>}
        <button className="tl-asset" onClick={() => onOpenAsset(e.asset_id)}>
          {TypeIc && <TypeIc size={14} aria-hidden="true" />}<b>{e.asset_id}</b><span>{e.asset_name}</span>
        </button>
        <div className="tags">
          {e.kind === 'complaint' && <>
            {e.link && <span className={`tag ${e.opened_failure ? 'dark' : ''}`}>{e.link}</span>}
            {e.match_status && MATCH_TEXT[e.match_status] && (
              <span className={`tag ${e.match_status === 'review' ? 'yellow' : ''}`}>
                {MATCH_TEXT[e.match_status]}{e.match_status === 'auto' && e.match_score ? ` (score ${Number(e.match_score).toFixed(2)})` : ''}
              </span>
            )}
            {e.cause && e.cause !== 'unknown' && <span className="tag">Likely cause: {label(e.cause)}</span>}
          </>}
          {e.kind === 'repair' && <>
            {e.cost != null && <span className="tag num">{lakh(e.cost)}</span>}
            <span className={`tag ${e.failed_again ? 'coral' : 'good'}`}>{e.held}</span>
            {e.work_order_id && <span className="tag">From repair job #{e.work_order_id}</span>}
          </>}
          {e.kind === 'job' && <>
            <span className={`tag ${e.overdue ? 'coral' : e.status === 'completed' ? 'good' : 'yellow'}`}>
              {e.overdue ? `Overdue by ${e.days_overdue} day${e.days_overdue === 1 ? '' : 's'}` : e.status_label}
            </span>
            {e.due_date && <span className="tag">Target {fmt(e.due_date)}</span>}
          </>}
        </div>
        {(e.photo_url || e.after_photo_url) && (
          <div className="photo-pair">
            {e.photo_url && <figure><img src={api.photo(e.photo_url)} alt={`Photo with the complaint about ${e.asset_name}`} loading="lazy" /><figcaption>Reported photo</figcaption></figure>}
            {e.after_photo_url && <figure><img src={api.photo(e.after_photo_url)} alt={`Photo after the repair of ${e.asset_name}`} loading="lazy" /><figcaption>After the repair</figcaption></figure>}
          </div>
        )}
      </article>
    </li>
  )
}

export default function Timeline({ initialQ = '', onOpenAsset, version = 0 }) {
  const [q, setQ] = useState(initialQ)
  const [typed, setTyped] = useState(initialQ)
  const [preset, setPreset] = useState('all')
  const [range, setRange] = useState(['', ''])
  const [types, setTypes] = useState([])
  const [kinds, setKinds] = useState(['complaint', 'repair', 'job'])
  const [asset, setAsset] = useState('')
  const [sort, setSort] = useState('date')
  const [data, setData] = useState(null)
  const [events, setEvents] = useState([])
  const [err, setErr] = useState('')
  const [busy, setBusy] = useState(false)

  useEffect(() => { setQ(initialQ); setTyped(initialQ) }, [initialQ])

  const params = useMemo(() => {
    const p = new URLSearchParams()
    if (range[0]) p.set('start', range[0])
    if (range[1]) p.set('end', range[1])
    if (types.length) p.set('types', types.join(','))
    p.set('kinds', kinds.join(','))
    if (asset) p.set('asset_id', asset)
    if (q) { p.set('q', q); p.set('sort', sort) }
    return p
  }, [range, types, kinds, asset, q, sort])

  const load = (offset = 0) => {
    const p = new URLSearchParams(params)
    p.set('offset', offset); p.set('limit', 40)
    setBusy(true); setErr('')
    return api.timeline(p.toString())
      .then((d) => { setData(d); setEvents((prev) => (offset ? [...prev, ...d.events] : d.events)) })
      .catch((x) => setErr(x.message))
      .finally(() => setBusy(false))
  }
  useEffect(() => { load(0) }, [params, version]) // eslint-disable-line react-hooks/exhaustive-deps

  const toggle = (list, set, v) => set(list.includes(v) ? list.filter((x) => x !== v) : [...list, v])
  const pickPreset = (key, fn) => { setPreset(key); setRange(fn()) }
  const pickMonth = (s, e) => { setPreset('custom'); setRange([s, e]) }
  const filtered = q || asset || types.length || kinds.length < 3 || preset !== 'all'
  const clear = () => { setQ(''); setTyped(''); setPreset('all'); setRange(['', '']); setTypes([]); setKinds(['complaint', 'repair', 'job']); setAsset(''); setSort('date') }

  // group the loaded events by month for headings
  const groups = []
  for (const e of events) {
    const k = e.date.slice(0, 7)
    if (!groups.length || groups[groups.length - 1].k !== k) groups.push({ k, items: [] })
    groups[groups.length - 1].items.push(e)
  }
  const c = data?.counts || {}
  const rangeText = range[0] || range[1] ? `${range[0] ? fmt(range[0]) : 'the start'} to ${range[1] ? fmt(range[1]) : 'today'}` : 'all time'

  return (
    <div className="stack">
      <section className="card" aria-labelledby="tl-h">
        <div className="card-head">
          <div>
            <h2 id="tl-h" className="h-card">Ward timeline</h2>
            <p className="sub">Every complaint, repair and repair job, linked to the road, drain or light it is about. Search by meaning, street or asset ID.</p>
          </div>
          {filtered && <button className="btn-light" onClick={clear}><X size={15} aria-hidden="true" />Clear filters</button>}
        </div>

        <form className="tl-search" role="search" onSubmit={(e) => { e.preventDefault(); setQ(typed.trim()) }}>
          <label className="sr-only" htmlFor="tl-q">Search the timeline</label>
          <Search size={18} aria-hidden="true" />
          <input id="tl-q" value={typed} onChange={(e) => setTyped(e.target.value)}
            placeholder={'Try "water stagnant after rain", "Main Road" or ROAD-2045'} />
          {q && <select aria-label="Order results" value={sort} onChange={(e) => setSort(e.target.value)}>
            <option value="date">Newest first</option><option value="match">Closest match first</option>
          </select>}
          <button className="btn-dark" type="submit">Search</button>
        </form>

        <div className="tl-filters">
          <div className="tl-frow" role="group" aria-labelledby="f-when">
            <span id="f-when" className="tl-flabel"><CalendarRange size={15} aria-hidden="true" />When</span>
            <div className="filter-pills">
              {PRESETS.map(([k, txt, fn]) => <button key={k} className={preset === k ? 'on' : ''} aria-pressed={preset === k} onClick={() => pickPreset(k, fn)}>{txt}</button>)}
            </div>
            <span className="tl-dates">
              <label>From <input type="date" value={range[0]} max={range[1] || undefined} onChange={(e) => { setPreset('custom'); setRange([e.target.value, range[1]]) }} /></label>
              <label>To <input type="date" value={range[1]} min={range[0] || undefined} onChange={(e) => { setPreset('custom'); setRange([range[0], e.target.value]) }} /></label>
            </span>
          </div>
          <div className="tl-frow" role="group" aria-labelledby="f-what">
            <span id="f-what" className="tl-flabel">Show</span>
            <div className="filter-pills">
              {KINDS.map(([k, txt, Ic]) => (
                <button key={k} className={`kind-${k} ${kinds.includes(k) ? 'on' : ''}`} aria-pressed={kinds.includes(k)}
                  onClick={() => kinds.length > 1 || !kinds.includes(k) ? toggle(kinds, setKinds, k) : null}>
                  <Ic size={14} aria-hidden="true" />{txt}{data && <span className="num"> {c[k] ?? 0}</span>}
                </button>
              ))}
            </div>
          </div>
          <div className="tl-frow" role="group" aria-labelledby="f-type">
            <span id="f-type" className="tl-flabel">Asset</span>
            <div className="filter-pills">
              {TYPES.map((t) => <button key={t} className={types.includes(t) ? 'on' : ''} aria-pressed={types.includes(t)} onClick={() => toggle(types, setTypes, t)}>{TYPE_NAME[t]}</button>)}
            </div>
            <select className="tl-asset-pick" aria-label="One asset" value={asset} onChange={(e) => setAsset(e.target.value)}>
              <option value="">All assets</option>
              {data?.assets.map((a) => <option key={a.asset_id} value={a.asset_id}>{a.asset_id}: {a.name}</option>)}
            </select>
          </div>
        </div>
      </section>

      {data && (
        <section className="card" aria-label="Summary of the selection">
          <p className="tl-summary" aria-live="polite">
            <b className="num">{data.total}</b> events{q && <> matching “{q}”</>}, {rangeText}:
            {' '}<b className="num">{c.complaint || 0}</b> complaints, <b className="num">{c.repair || 0}</b> repairs
            {data.repair_spend > 0 && <> costing <b className="num">{lakh(data.repair_spend)}</b></>}, <b className="num">{c.job || 0}</b> repair jobs,
            across <b className="num">{data.assets_involved}</b> asset{data.assets_involved === 1 ? '' : 's'}.
          </p>
          <MonthStrip months={data.months} start={range[0]} end={range[1]} onPick={pickMonth} />
          <p className="split-keys">
            <span><i className="c" aria-hidden="true" />Complaints</span><span><i className="r" aria-hidden="true" />Repairs</span><span><i className="j" aria-hidden="true" />Repair jobs</span>
            <span className="ink2">Choose a month to see only that month.</span>
          </p>
        </section>
      )}

      {err && <div className="error-box" role="alert">{err}</div>}
      <section className="card" aria-label="Events" aria-busy={busy}>
        {!data && <p className="muted">Loading the timeline…</p>}
        {data && events.length === 0 && (
          <p className="empty-state">Nothing in the history matches these filters. Try a wider date range, or search for words like “drain overflow” or a street name.</p>
        )}
        {groups.map((g) => {
          const [y, m] = g.k.split('-').map(Number)
          return (
            <div key={g.k} className="tl-group">
              <h3 className="tl-gh">{MONTH_LONG[m - 1]} {y}</h3>
              <ol className="tl-list">{g.items.map((e) => <Event key={e.id} e={e} onOpenAsset={onOpenAsset} />)}</ol>
            </div>
          )
        })}
        {data && events.length < data.total && (
          <div style={{ display: 'flex', alignItems: 'center', gap: 14, marginTop: 8 }}>
            <button className="btn-light" onClick={() => load(events.length)} disabled={busy}>{busy ? 'Loading…' : 'Show older events'}</button>
            <span className="small ink2">Showing {events.length} of {data.total}</span>
          </div>
        )}
      </section>
    </div>
  )
}
