import { useState } from 'react'
import { api, MATCHER } from '../api'
import AssetMap from './AssetMap'

const CATS = [['road', 'Road / pothole'], ['drain', 'Drain'], ['streetlight', 'Streetlight'], ['footpath', 'Footpath'], ['toilet', 'Public toilet']]
const STATUS_TEXT = { auto: 'Linked to a known asset', review: 'Possible match, sent for engineer review', new_asset: 'New issue registered', duplicate: 'Already reported by you' }

export default function ReportForm({ assets, onSubmitted, onOpenAsset }) {
  const [pin, setPin] = useState(null)
  const [f, setF] = useState({ category: 'road', text: '', reporter: '' })
  const [photo, setPhoto] = useState(null)
  const [res, setRes] = useState(null)
  const [err, setErr] = useState('')
  const [busy, setBusy] = useState(false)

  const submit = async (e) => {
    e.preventDefault()
    setErr(''); setRes(null)
    if (!pin) return setErr('Tap the map to drop a pin where the problem is.')
    const fd = new FormData()
    fd.append('text', f.text); fd.append('category', f.category)
    fd.append('lat', pin.lat); fd.append('lng', pin.lng)
    if (f.reporter) fd.append('reporter', f.reporter)
    if (photo) fd.append('photo', photo)
    setBusy(true)
    const t0 = performance.now()
    try {
      const r = await api.complain(fd)
      r.ms = Math.round(performance.now() - t0)
      setRes(r)
      onSubmitted && onSubmitted()
    } catch (x) { setErr(x.message) } finally { setBusy(false) }
  }

  return (
    <div className="report">
      <div className="report-map">
        <AssetMap assets={assets.filter((a) => a.type === f.category)} pin={pin} onPick={setPin} height={520} />
        <p className="muted small">Tap the map to place your pin. Circles show existing {f.category} assets.</p>
      </div>
      <div className="panel">
        <h2>Report a civic issue</h2>
        <form onSubmit={submit} className="stack">
          <label>What is the problem?
            <select value={f.category} onChange={(e) => setF({ ...f, category: e.target.value })}>
              {CATS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
            </select>
          </label>
          <label>Describe it
            <textarea required rows={3} placeholder="e.g. big pothole near the bus stop, water stagnant after rain" value={f.text} onChange={(e) => setF({ ...f, text: e.target.value })} />
          </label>
          <label>Photo (optional)
            <input type="file" accept="image/*" onChange={(e) => setPhoto(e.target.files[0])} />
          </label>
          <label>Your name or phone (optional)
            <input value={f.reporter} onChange={(e) => setF({ ...f, reporter: e.target.value })} />
          </label>
          <div className="muted small">{pin ? `Pin: ${pin.lat.toFixed(5)}, ${pin.lng.toFixed(5)}` : 'No pin yet'}</div>
          {err && <div className="error">{err}</div>}
          <button className="btn" disabled={busy}>{busy ? 'Checking history…' : 'Submit complaint'}</button>
        </form>

        {res && (
          <div className={`result result-${res.status}`}>
            <div className="result-status">{STATUS_TEXT[res.status]}</div>
            <p>{res.message}</p>
            <div className="muted small">Asset {res.asset_id} · {res.asset_name} · answered in {res.ms} ms</div>
            {res.match && (
              <div className="match">
                <div>Location score <b>{res.match.distance_score}</b> ({res.match.distance_m} m away)</div>
                <div>Meaning similarity <b>{res.match.text_score}</b> <span className="muted">({MATCHER[res.matcher] || res.matcher})</span></div>
                <div>Combined <b>{res.match.score}</b> <span className="muted">(auto-link ≥ 0.62, review ≥ 0.38)</span></div>
              </div>
            )}
            {res.asset_id && <button className="btn ghost" onClick={() => onOpenAsset(res.asset_id)}>Open asset history</button>}
          </div>
        )}
      </div>
    </div>
  )
}
