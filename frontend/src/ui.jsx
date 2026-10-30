// Shared visual building blocks for every CityMemory screen.
import { useCallback, useEffect, useRef, useState } from 'react'
import {
  Accessibility, Bot, ChevronLeft, ChevronRight, CircleHelp, Construction, Droplets, Footprints, Landmark, Languages, Lightbulb, LogOut,
  Search, ShieldCheck, Toilet, X,
} from 'lucide-react'
import { api } from './api'
import { usePrefs } from './i18n'

export const TYPE_ICON_C = { road: Construction, drain: Droplets, streetlight: Lightbulb, footpath: Footprints, toilet: Toilet }
export const typeFromId = (id = '') => ({ ROAD: 'road', DRAIN: 'drain', LIGHT: 'streetlight', PATH: 'footpath', TOILET: 'toilet' })[id.split('-')[0]] || 'road'
export const TYPE_NAME = { road: 'Road', drain: 'Drain', streetlight: 'Streetlight', footpath: 'Footpath', toilet: 'Public toilet' }
export const ROLE_NAME = { citizen: 'Citizen', engineer: 'Ward engineer', commissioner: 'Commissioner' }
export const lakh = (n) => {
  const v = Math.round(n || 0)
  return v >= 100000 ? `₹${(v / 100000).toFixed(v >= 1000000 ? 1 : 2).replace(/\.?0+$/, '')}L` : `₹${v.toLocaleString('en-IN')}`
}

export function TypeBadge({ type, tone = '' }) {
  const Ic = TYPE_ICON_C[type] || Construction
  return <span className={`badge-ic ${tone}`} aria-hidden="true"><Ic size={18} strokeWidth={2} /></span>
}

function initials(name) {
  return (name || '?').replace(/\(.*\)/, '').trim().split(/\s+/).slice(0, 2).map((w) => w[0]).join('').toUpperCase()
}

export function BrandMark({ size = 34 }) {
  // three overlapping circles: one asset, many reports, one memory
  return (
    <svg width={size} height={size} viewBox="0 0 34 34" aria-hidden="true">
      <circle cx="17" cy="11" r="8" fill="#26272b" />
      <circle cx="10.5" cy="22" r="8" fill="#26272b" />
      <circle cx="23.5" cy="22" r="8" fill="#26272b" />
      <circle cx="17" cy="18.5" r="4" fill="#f8d44c" />
    </svg>
  )
}

let healthCache = null
function useHealth() {
  const [h, setH] = useState(healthCache)
  useEffect(() => {
    if (healthCache) return
    api.health().then((x) => { healthCache = x; setH(x) }).catch(() => {})
  }, [])
  return h
}

function AiStatus() {
  const { t } = usePrefs()
  const h = useHealth()
  if (!h) return null
  const emb = h.ai.embedder.backend === 'sbert', llm = h.ai.llm.available
  const state = emb && llm ? 'ok' : emb || llm ? 'part' : ''
  const tip = `Complaint matching: ${emb ? 'AI model' : 'basic text matching'}. Written summaries: ${llm ? `on (${h.ai.llm.model})` : 'off'}.`
  return (
    <p className="ai-status" title={tip}>
      <Bot size={16} aria-hidden="true" />
      <span className={`dot ${state}`} aria-hidden="true" />
      <span>{t(state === 'ok' ? 'ai_on' : state === 'part' ? 'ai_part' : 'ai_off')}</span>
      <span className="sr-only">. {tip}</span>
    </p>
  )
}

/** Official strip across the top: who runs the service, text size, language. */
export function GovStrip() {
  const { t, lang, setLang, size, setSize } = usePrefs()
  const sizes = [['small', 'A−', 'smaller'], ['normal', 'A', 'normalText'], ['large', 'A+', 'larger']]
  return (
    <div className="gov-strip">
      <div className="gov-inner">
        <p className="gov-name"><Landmark size={16} aria-hidden="true" /><span><b>{t('corp')}</b><span className="gov-sep" aria-hidden="true"> | </span><span className="gov-service">{t('service')}</span></span></p>
        <div className="gov-tools">
          <div className="tool-group" role="group" aria-label={t('textSize')}>
            <span className="tool-label">{t('textSize')}</span>
            {sizes.map(([k, txt, name]) => (
              <button key={k} className={size === k ? 'on' : ''} aria-pressed={size === k} aria-label={t(name)} onClick={() => setSize(k)}>{txt}</button>
            ))}
          </div>
          {setLang && (
            <div className="tool-group" role="group" aria-label={t('language')}>
              <Languages size={15} aria-hidden="true" />
              <button className={lang === 'en' ? 'on' : ''} aria-pressed={lang === 'en'} lang="en" onClick={() => setLang('en')}>English</button>
              <button className={lang === 'ta' ? 'on' : ''} aria-pressed={lang === 'ta'} lang="ta" onClick={() => setLang('ta')}>தமிழ்</button>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

/** Centred dialog for the footer pages. Esc or the close button closes it; focus moves into it. */
export function Modal({ title, onClose, children }) {
  const { t } = usePrefs()
  const ref = useRef(null)
  useEffect(() => {
    const prev = document.activeElement
    ref.current?.focus()
    const k = (e) => e.key === 'Escape' && onClose()
    window.addEventListener('keydown', k)
    return () => { window.removeEventListener('keydown', k); prev?.focus?.() }
  }, [onClose])
  return (
    <>
      <div className="scrim" onClick={onClose} />
      <div className="modal" role="dialog" aria-modal="true" aria-labelledby="modal-title" tabIndex={-1} ref={ref}>
        <div className="drawer-head">
          <h2 id="modal-title" className="h-card">{title}</h2>
          <button className="icon-btn" onClick={onClose} aria-label={t('close')}><X size={18} /></button>
        </div>
        {children}
      </div>
    </>
  )
}

export function NoticeList() {
  const { t } = usePrefs()
  return (
    <dl className="notice-list">
      {['what', 'why', 'who', 'long', 'choice'].map((k) => <div key={k}><dt>{t(`pn_${k}`)}</dt><dd>{t(`pn_${k}_a`)}</dd></div>)}
    </dl>
  )
}

export function SiteFooter() {
  const { t, date } = usePrefs()
  const h = useHealth()
  const [open, setOpen] = useState(null)
  const close = useCallback(() => setOpen(null), [])
  return (
    <footer className="site-footer">
      <nav aria-label="Footer" className="foot-links">
        <button onClick={() => setOpen('privacy')}><ShieldCheck size={15} aria-hidden="true" />{t('privacy')}</button>
        <button onClick={() => setOpen('acc')}><Accessibility size={15} aria-hidden="true" />{t('accessibility')}</button>
        <button onClick={() => setOpen('help')}><CircleHelp size={15} aria-hidden="true" />{t('help')}</button>
      </nav>
      <p className="foot-meta">
        {h?.data_updated && <span>{t('updated')}: <b>{date(h.data_updated)}</b></span>}
        <span>{t('prototype')}</span>
      </p>
      {open === 'privacy' && <Modal title={t('privacy')} onClose={close}><NoticeList /></Modal>}
      {open === 'acc' && (
        <Modal title={t('acc_title')} onClose={close}>
          <ul className="plain-list">{t('acc_items').map((x) => <li key={x}>{x}</li>)}</ul>
        </Modal>
      )}
      {open === 'help' && (
        <Modal title={t('help_title')} onClose={close}>
          <dl className="notice-list">{t('help_items').map(([q, a]) => <div key={q}><dt>{q}</dt><dd>{a}</dd></div>)}</dl>
        </Modal>
      )}
    </footer>
  )
}

/** App frame: official strip, labelled side navigation, formal greeting, footer. */
export function Shell({ user, nav, page, setPage, subline, onSearch, cta, onLogout, children }) {
  const { t } = usePrefs()
  const [q, setQ] = useState('')
  const role = t(`role_${user.role}`)
  return (
    <>
      <a className="skip-link" href="#main">{t('skip')}</a>
      <GovStrip />
      <div className="frame">
        <div className="canvas">
          <aside className="rail" aria-label={t('menu')}>
            <div className="brand"><BrandMark /><span><span className="brand-name">CityMemory</span><span className="brand-ward">{t('ward')}</span></span></div>
            <nav className="nav-list" aria-label={t('menu')}>
              {nav.map(([key, label, Icon, dot]) => (
                <button key={key} className={`nav-btn ${page === key ? 'on' : ''}`} aria-current={page === key ? 'page' : undefined} onClick={() => setPage(key)}>
                  <Icon size={19} strokeWidth={2} aria-hidden="true" />
                  <span className="nav-text">{label}</span>
                  {dot ? <span className="dot" role="img" aria-label="needs attention" /> : null}
                </button>
              ))}
            </nav>
            {user.role !== 'citizen' && <AiStatus />}
            <div className="rail-spacer" />
            <div className="user-card">
              <span className={`avatar ${user.role}`} aria-hidden="true">{initials(user.name)}</span>
              <span className="user-text"><b>{user.name}</b><span>{role}</span></span>
            </div>
            <button className="nav-btn logout" onClick={onLogout}><LogOut size={18} aria-hidden="true" /><span className="nav-text">{t('logout')}</span></button>
          </aside>
          <main className="main" id="main" tabIndex={-1}>
            <header className="topbar">
              <div className="greet">
                <p className="eyebrow">{role} · {t('ward')}</p>
                <h1 className="h-greet">{t('welcome', { name: user.name })}</h1>
                {subline && <p className="sub">{subline}</p>}
              </div>
              {onSearch && (
                <form className="search-pill" role="search" onSubmit={(e) => { e.preventDefault(); if (q.trim().length > 1) onSearch(q.trim()) }}>
                  <Search size={18} aria-hidden="true" />
                  <input aria-label="Search asset history" placeholder="Search asset history" value={q} onChange={(e) => setQ(e.target.value)} />
                </form>
              )}
              {cta}
              <button className="btn-light only-mobile" onClick={onLogout}><LogOut size={16} aria-hidden="true" />{t('logout')}</button>
            </header>
            {children}
          </main>
        </div>
        <SiteFooter />
      </div>
    </>
  )
}

/**
 * Plain number blocks on the taupe card: each block is a big number with what it counts written under it.
 * Replaces the earlier bubbles, which made people compare circle sizes.
 */
export function StatCard({ title, sub, items, footer, children }) {
  return (
    <section className="card taupe stat-card" aria-label={title}>
      <div className="card-head"><div><h2 className="h-card">{title}</h2>{sub && <p className="sub ink2">{sub}</p>}</div></div>
      <dl className="stat-grid">
        {items.map((i) => (
          <div key={i.label} className={`stat ${i.tone || ''}`}>
            <dt>{i.label}</dt>
            <dd><b className="num">{i.display ?? i.value}</b>{i.note && <span>{i.note}</span>}</dd>
          </div>
        ))}
      </dl>
      {children}
      {footer && <p className="stat-foot">{footer}</p>}
    </section>
  )
}

/** One labelled stacked bar: how a total splits into parts. Every part names its share in text. */
export function SplitBar({ parts, label }) {
  const total = parts.reduce((s, p) => s + p.value, 0) || 1
  return (
    <figure className="split" aria-label={label}>
      <div className="split-bar" aria-hidden="true">
        {parts.map((p) => p.value > 0 && <i key={p.label} className={p.tone} style={{ width: `${(p.value / total) * 100}%` }} />)}
      </div>
      <figcaption className="split-keys">
        {parts.map((p) => (
          <span key={p.label}><i className={p.tone} aria-hidden="true" />{p.label}: <b className="num">{p.display}</b> ({Math.round((p.value / total) * 100)}%)</span>
        ))}
      </figcaption>
    </figure>
  )
}

/** Dark month calendar: yellow = a repair was done that day, grey = complaints filed, ring = today. */
export function CalendarCard({ title }) {
  const { t, months, dow } = usePrefs()
  const now = new Date()
  const [ym, setYm] = useState([now.getFullYear(), now.getMonth() + 1])
  const [data, setData] = useState(null)
  const key = `${ym[0]}-${String(ym[1]).padStart(2, '0')}`
  useEffect(() => { setData(null); api.calendar(key).then(setData).catch(() => setData({ error: true })) }, [key])
  const shift = (d) => setYm(([y, m]) => { const x = m + d; return x < 1 ? [y - 1, 12] : x > 12 ? [y + 1, 1] : [y, x] })
  const isFuture = ym[0] > now.getFullYear() || (ym[0] === now.getFullYear() && ym[1] >= now.getMonth() + 1)
  return (
    <section className="card dark" aria-label={title}>
      <div className="cal-head">
        <h2 className="h-card">{title}</h2>
        <div className="cal-month">
          <button onClick={() => shift(-1)} aria-label="Previous month"><ChevronLeft size={16} /></button>
          <span style={{ minWidth: 104, textAlign: 'center' }}>{months[ym[1] - 1]} {ym[0]}</span>
          <button onClick={() => shift(1)} aria-label="Next month" disabled={isFuture} style={{ opacity: isFuture ? 0.3 : 1 }}><ChevronRight size={16} /></button>
        </div>
      </div>
      <div className="cal-grid" role="grid">
        {dow.map((d, i) => <div key={i} className="cal-dow" aria-hidden="true">{d}</div>)}
        {data?.days && Array.from({ length: data.first_weekday }).map((_, i) => <div key={`b${i}`} />)}
        {data?.days?.map((d) => {
          const today = data.today === `${key}-${String(d.day).padStart(2, '0')}`
          const cls = d.repairs ? 'fixed' : d.complaints ? 'filed' : ''
          const tip = [d.complaints && `${t('filed')}: ${d.complaints}`, d.repairs && `${t('repairDone')}: ${d.repairs}`].filter(Boolean).join(', ')
          return (
            <div key={d.day} role="gridcell" aria-label={`${d.day} ${months[ym[1] - 1]}${tip ? ': ' + tip : ''}`}
              className={`cal-day ${cls} ${today ? 'today' : ''}`} data-tip={tip || undefined}>{d.day}</div>
          )
        })}
      </div>
      {!data && <p className="small" style={{ marginTop: 12, color: 'rgba(255,255,255,.75)' }}>Loading…</p>}
      <div className="cal-legend">
        <span><i className="k-today" />{t('today')}</span>
        <span><i className="k-fixed" />{t('repairDone')}</span>
        <span><i className="k-filed" />{t('filed')}</span>
        {data?.totals && <span style={{ marginLeft: 'auto' }}>{t('calTotals', { c: data.totals.complaints, r: data.totals.repairs })}</span>}
      </div>
    </section>
  )
}

/** Ring gauge (the "steps for today" card). */
export function Gauge({ value, goal, centerLabel, centerValue, tag }) {
  const r = 54, c = 2 * Math.PI * r
  const frac = Math.max(0, Math.min(1, goal ? value / goal : 0))
  return (
    <div className="gauge" role="img" aria-label={`${centerLabel} ${centerValue}; current ${tag}`}>
      <svg viewBox="0 0 132 132">
        <defs>
          <linearGradient id="gauge-g" x1="0" x2="1" y1="0" y2="1">
            <stop offset="0" stopColor="#f0675a" /><stop offset="1" stopColor="#c2412f" />
          </linearGradient>
        </defs>
        <circle cx="66" cy="66" r={r} fill="none" stroke="#e7e1d9" strokeWidth="12" />
        <circle cx="66" cy="66" r={r - 14} fill="none" stroke="#e6e0d8" strokeWidth="2" strokeDasharray="1.5 5" />
        <circle cx="66" cy="66" r={r} fill="none" stroke="url(#gauge-g)" strokeWidth="12" strokeLinecap="round"
          strokeDasharray={`${c * frac} ${c}`} />
      </svg>
      <div className="gauge-center"><span>{centerLabel}</span><b className="num">{centerValue}</b></div>
      {tag && <span className="gauge-tag num">{tag}</span>}
    </div>
  )
}

/** Pill progress bar with a value tooltip (the "weight loss plan" card). */
export function PillProgress({ frac, tip, left, right, tone = '' }) {
  const p = Math.max(0, Math.min(1, frac)) * 100
  return (
    <div>
      <div className="pp-track" role="progressbar" aria-valuenow={Math.round(p)} aria-valuemin={0} aria-valuemax={100} aria-label={tip}>
        <div className="pp-dots" style={{ paddingLeft: `${p}%` }}>{Array.from({ length: 8 }).map((_, i) => <i key={i} />)}</div>
        <div className={`pp-fill ${tone}`} style={{ width: `${p}%` }} />
        {p > 3 && <span className="pp-knob" style={{ left: `${p}%` }} />}
        <span className="pp-tip num" style={{ left: `${Math.min(Math.max(p, 8), 92)}%` }}>{tip}</span>
      </div>
      <div className="pp-ends num"><span>{left}</span><span>{right}</span></div>
    </div>
  )
}

/** Segmented pills (the "sessions completed" bar). */
export function Seg({ value, total, tone = '', label }) {
  return (
    <span className={`seg ${tone}`} role="img" aria-label={label || `${value} of ${total}`}>
      {Array.from({ length: total }).map((_, i) => <i key={i} className={i < value ? 'on' : ''} />)}
    </span>
  )
}

/** Slide-over panel on the right; closes on Esc or a click outside. */
export function Drawer({ open, onClose, label, children }) {
  useEffect(() => {
    if (!open) return
    const k = (e) => e.key === 'Escape' && onClose()
    window.addEventListener('keydown', k)
    return () => window.removeEventListener('keydown', k)
  }, [open, onClose])
  if (!open) return null
  return (
    <>
      <div className="scrim" onClick={onClose} />
      <aside className="drawer" role="dialog" aria-modal="true" aria-label={label}>{children}</aside>
    </>
  )
}

export function CloseBtn({ onClick }) {
  return <button className="icon-btn" onClick={onClick} aria-label="Close"><X size={18} /></button>
}

export const scoreTone = (s) => (s >= 55 ? 'high' : s >= 35 ? 'mid' : '')
