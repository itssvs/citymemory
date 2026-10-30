import { useState } from 'react'
import { Camera, CircleCheck, MapPin, Search } from 'lucide-react'
import { api, MATCHER } from '../api'
import { usePrefs } from '../i18n'
import { TYPE_ICON_C } from '../ui'
import AssetMap, { MapLegend } from './AssetMap'
import PrivacyNotice from './PrivacyNotice'

const MAX_MB = 8

const CATS = ['road', 'drain', 'streetlight', 'footpath', 'toilet']

export default function ReportForm({ assets, onSubmitted, onOpenAsset, onCreated, citizen = false }) {
  const { t, lang } = usePrefs()
  const [pin, setPin] = useState(null)
  const [f, setF] = useState({ category: 'road', text: '' })
  const [photo, setPhoto] = useState(null)
  const [res, setRes] = useState(null)
  const [err, setErr] = useState('')
  const [busy, setBusy] = useState(false)
  const [consent, setConsent] = useState(false)

  const submit = async (e) => {
    e.preventDefault()
    setErr(''); setRes(null)
    if (!pin) return setErr(t('rf_needPin'))
    if (citizen && !consent) return setErr(t('rf_needConsent'))
    const fd = new FormData()
    fd.append('text', f.text); fd.append('category', f.category)
    fd.append('lat', pin.lat); fd.append('lng', pin.lng)
    if (photo) fd.append('photo', photo)
    if (citizen) fd.append('consent', 'true')
    setBusy(true)
    const t0 = performance.now()
    try {
      const r = await api.complain(fd)
      r.ms = Math.round(performance.now() - t0)
      setRes(r)
      onCreated && onCreated(r.complaint_id)
      onSubmitted && onSubmitted()
    } catch (x) { setErr(x.message) } finally { setBusy(false) }
  }

  return (
    <div className="grid12">
      <section className="card flush map-card span-7">
        <AssetMap assets={assets.filter((a) => a.type === f.category)} pin={pin} onPick={setPin} height={600} plain={citizen} fit />
        <div className="map-overlay">
          <p className="strong">{t('rf_tap')}</p>
          <p className="small ink2">{t('rf_circles')}</p>
        </div>
        <MapLegend plain={citizen} />
      </section>

      <section className="card span-5">
        <div className="card-head"><div><h2 className="h-card">{t('rf_title')}</h2><p className="sub">{t('rf_sub')}</p></div></div>
        <form className="form" onSubmit={submit}>
          <div className="field" role="group" aria-labelledby="rf-what">
            <span id="rf-what">{t('rf_what')}</span>
            <div className="choice">
              {CATS.map((c) => {
                const Ic = TYPE_ICON_C[c]
                return (
                  <button type="button" key={c} className={f.category === c ? 'on' : ''} aria-pressed={f.category === c}
                    onClick={() => setF({ ...f, category: c })}><Ic size={16} aria-hidden="true" />{t(c)}</button>
                )
              })}
            </div>
          </div>
          <label className="field">{t('rf_describe')}
            <textarea required minLength={10} placeholder={t('rf_placeholder')}
              value={f.text} onChange={(e) => setF({ ...f, text: e.target.value })} />
          </label>
          <label className="file-pick">
            <span className="btn-round" aria-hidden="true"><Camera size={15} /></span>
            <span>{photo ? photo.name : t('rf_photo')}</span>
            <input type="file" accept="image/jpeg,image/png,image/webp" onChange={(e) => {
              const f = e.target.files[0] || null
              if (f && f.size > MAX_MB * 1024 * 1024) { setErr(t('rf_tooBig', { n: MAX_MB })); setPhoto(null); return }
              setErr(''); setPhoto(f)
            }} />
          </label>
          <p className="pin-state" aria-live="polite"><MapPin size={16} aria-hidden="true" />{pin ? t('rf_pin') : t('rf_nopin')}</p>
          {citizen && <PrivacyNotice checked={consent} onChange={setConsent} />}
          {err && <div className="error-box" role="alert">{err}</div>}
          <button className="btn-dark" disabled={busy}>{busy ? <><Search size={16} aria-hidden="true" />{t('rf_checking')}</> : t('rf_submit')}</button>
        </form>

        {res && (
          <div className={`result ${res.status}`} style={{ marginTop: 18 }} role="status">
            <p className="result-title"><CircleCheck size={18} aria-hidden="true" />{t(res.status === 'review' ? 'res_title_review' : `res_${res.status}`)}</p>
            <p>{citizen || lang === 'ta' ? t(`res_msg_${res.status}`) : res.message}</p>
            <p className="note">{citizen ? `${t('rf_ref')} #${res.complaint_id}` : `${res.asset_id}, ${res.asset_name}`}. {t('rf_answered', { ms: res.ms })}</p>
            {res.match && (
              <div className="match-box">
                <span>Location match <b>{res.match.distance_score}</b> ({res.match.distance_m} m away)</span>
                <span>Meaning match <b>{res.match.text_score}</b> using {MATCHER[res.matcher] || res.matcher}</span>
                <span>Combined <b>{res.match.score}</b>. Links on its own at 0.62, asks an engineer from 0.38.</span>
              </div>
            )}
            {onOpenAsset && res.asset_id && (
              <button type="button" className="btn-light" onClick={() => onOpenAsset(res.asset_id)} style={{ alignSelf: 'flex-start' }}>
                {citizen ? t('rf_track') : 'Open asset history'}
              </button>
            )}
          </div>
        )}
      </section>
    </div>
  )
}
