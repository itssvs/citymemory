// Shared pieces for the engineer and commissioner dashboards.
import { useEffect, useState } from 'react'
import { Ellipsis } from 'lucide-react'
import { api, label } from '../api'
import AssetMap, { MapLegend } from '../components/AssetMap'
import AssetPanel from '../components/AssetPanel'
import { Drawer, Seg, TYPE_NAME, TypeBadge, scoreTone } from '../ui'

export function useStaffData() {
  const [assets, setAssets] = useState([])
  const [stats, setStats] = useState(null)
  const [err, setErr] = useState('')
  const refresh = () =>
    Promise.all([api.priority(100), api.stats()])
      .then(([a, s]) => { setAssets(a); setStats(s); setErr('') })
      .catch((e) => setErr(e.message))
  useEffect(() => { refresh() }, [])
  return { assets, stats, err, refresh }
}

/** One asset as a row: what it is, how often it failed in 12 months (pills), priority chip. */
export function AssetRow({ a, selected, onOpen }) {
  const tone = scoreTone(a.priority)
  return (
    <button className={`row-item ${selected ? 'sel' : ''}`} onClick={() => onOpen(a.asset_id)} aria-label={`${a.name}, priority ${a.priority}. Open history`}>
      <TypeBadge type={a.type} tone={tone === 'high' ? 'hot' : tone === 'mid' ? 'warm' : ''} />
      <div style={{ minWidth: 0 }}>
        <p className="row-title">{a.name}</p>
        <p className="row-sub">{a.asset_id}, {label(a.cause) === 'unknown' ? TYPE_NAME[a.type].toLowerCase() : label(a.cause)}</p>
      </div>
      <div className="row-metric">
        Failures this year: <b className="num">{a.incidents_12m}/12</b>
        <Seg value={Math.min(a.incidents_12m, 12)} total={12} label={`${a.incidents_12m} failures in the last 12 months`} />
      </div>
      <div className="row-end">
        {a.job ? <span className={`tag ${a.job.overdue ? 'coral' : 'good'}`}>{a.job.overdue ? 'Job overdue' : a.job.status_label}</span>
          : a.recommendation === 'replace' && <span className="tag dark">Stop patching</span>}
        <span className={`score-chip ${tone}`} title="Priority out of 100">{a.priority}</span>
        <Ellipsis size={18} color="var(--muted)" aria-hidden="true" />
      </div>
    </button>
  )
}

const TYPES = ['', 'road', 'drain', 'streetlight', 'footpath', 'toilet']

export function AssetList({ assets, selected, onOpen, title, sub, limit }) {
  const [type, setType] = useState('')
  const [all, setAll] = useState(false)
  const shown = assets.filter((a) => !type || a.type === type)
  const cut = limit && !all ? shown.slice(0, limit) : shown
  return (
    <section className="card">
      <div className="card-head">
        <div><h2 className="h-card">{title}</h2>{sub && <p className="sub">{sub}</p>}</div>
        <div className="filter-pills" role="group" aria-label="Filter by type">
          {TYPES.map((t) => <button key={t || 'all'} className={type === t ? 'on' : ''} aria-pressed={type === t} onClick={() => setType(t)}>{t ? TYPE_NAME[t] : 'All'}</button>)}
        </div>
      </div>
      <div className="rows">
        {cut.map((a) => <AssetRow key={a.asset_id} a={a} selected={selected === a.asset_id} onOpen={onOpen} />)}
        {cut.length === 0 && <p className="empty-state">No {TYPE_NAME[type]?.toLowerCase()} assets on record.</p>}
      </div>
      {limit && shown.length > limit && (
        <button className="btn-light" style={{ marginTop: 14 }} onClick={() => setAll(!all)}>{all ? 'Show fewer' : `Show all ${shown.length}`}</button>
      )}
    </section>
  )
}

export function MapCard({ assets, selected, onOpen, height = 440, title }) {
  return (
    <section className="card flush map-card">
      <AssetMap assets={assets} selected={selected} onSelect={onOpen} height={height} fit />
      {title && <div className="map-overlay"><p className="strong">{title}</p><p className="small muted">Click a circle to open its history.</p></div>}
      <MapLegend />
    </section>
  )
}

export function AssetDrawer({ id, onClose, canEdit = false, onChanged }) {
  return (
    <Drawer open={!!id} onClose={onClose} label="Asset history">
      {id && <AssetPanel assetId={id} onClose={onClose} canEdit={canEdit} onChanged={onChanged} />}
    </Drawer>
  )
}
