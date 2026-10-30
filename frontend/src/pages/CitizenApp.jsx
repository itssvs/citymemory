import { useEffect, useState } from 'react'
import { ClipboardList, House, MapPinPlus } from 'lucide-react'
import { api } from '../api'
import ReportForm from '../components/ReportForm'
import { stepLabel, usePrefs } from '../i18n'
import { CalendarCard, Shell, StatCard, TypeBadge } from '../ui'

function ComplaintCard({ c, highlight }) {
  const { t, date } = usePrefs()
  const done = c.steps.filter((s) => s.done).length
  return (
    <article className={`complaint-card ${highlight ? 'new' : ''}`}>
      <div className="cc-head">
        <div style={{ display: 'flex', gap: 12, alignItems: 'center', minWidth: 0 }}>
          <TypeBadge type={c.category} />
          <div style={{ minWidth: 0 }}>
            <p className="row-title" style={{ whiteSpace: 'normal' }}>{c.text}</p>
            <p className="row-sub">{c.asset_name}, {t('reportedOn', { d: date(c.created_at) })} · {t('rf_ref')} #{c.id}</p>
          </div>
        </div>
        <span className={`status ${c.status.replace(/\s/g, '-').toLowerCase()}`}>{t(c.status)}</span>
      </div>
      <ol className="cc-steps" aria-label={`${done} / ${c.steps.length}`}>
        {c.steps.map((s, i) => (
          <li key={i} className={`${s.done ? 'done' : ''} ${i === c.steps.length - 1 ? 'final' : ''}`}>
            <i aria-hidden="true" />
            <span>{stepLabel(t, s)}{s.date && i > 0 ? `, ${date(s.date)}` : ''}</span>
          </li>
        ))}
      </ol>
      {c.target_date && c.status !== 'Fixed' && (
        <p className="small"><b>{t('target')}:</b> {date(c.target_date)}</p>
      )}
      {c.others_reported > 0 && (
        <p className="note">
          {c.others_reported === 1 ? t('others1') : t('others', { n: c.others_reported })}
          {c.times_failed > 1 && ` ${t('failedN', { n: c.times_failed })}`}
        </p>
      )}
      {(c.photo_url || c.after_photo_url) && (
        <div className="photo-pair">
          {c.photo_url && <figure><img src={api.photo(c.photo_url)} alt={t('yourPhoto')} /><figcaption>{t('yourPhoto')}</figcaption></figure>}
          {c.after_photo_url && <figure><img src={api.photo(c.after_photo_url)} alt={t('afterPhoto')} /><figcaption>{t('afterPhoto')}</figcaption></figure>}
        </div>
      )}
    </article>
  )
}

export default function CitizenApp({ user, onLogout }) {
  const { t } = usePrefs()
  const [page, setPage] = useState('home')
  const [assets, setAssets] = useState([])
  const [mine, setMine] = useState(null)
  const [lastId, setLastId] = useState(null)
  const [err, setErr] = useState('')
  const load = () => {
    api.publicAssets().then(setAssets).catch(() => {})
    api.myComplaints().then(setMine).catch((e) => setErr(e.message))
  }
  useEffect(() => { load() }, [page]) // fresh status every time a page is opened

  const count = (...st) => (mine || []).filter((c) => st.includes(c.status)).length
  const active = ['Waiting for repair', 'Repair assigned', 'Work started']
  const nav = [['home', t('nav_home'), House], ['report', t('nav_report'), MapPinPlus], ['mine', t('nav_mine'), ClipboardList]]

  return (
    <Shell
      user={user} nav={nav} page={page} setPage={setPage} onLogout={onLogout}
      subline={t('cit_sub')}
      cta={page !== 'report' && <button className="btn-dark" onClick={() => setPage('report')}><MapPinPlus size={18} aria-hidden="true" />{t('nav_report')}</button>}
    >
      {err && <div className="error-box">{err}</div>}
      {page === 'home' && mine && (
        <>
          <div className="grid12">
            <div className="span-7">
              <StatCard
                title={t('yourReports')}
                items={[
                  { label: t('st_fixed'), value: count('Fixed'), note: t('st_fixed_note'), tone: 'yellow' },
                  { label: t('st_repairing'), value: count(...active), note: t('st_repairing_note'), tone: 'coral' },
                  { label: t('st_review'), value: count('Under review'), note: t('st_review_note'), tone: 'dark' },
                ]}
                footer={mine.length === 1 ? t('total1') : t('total', { n: mine.length })}
              />
            </div>
            <div className="span-5"><CalendarCard title={t('calTitle')} /></div>
          </div>
          <section className="card">
            <div className="card-head">
              <div><h2 className="h-card">{t('latest')}</h2><p className="sub">{t('latestSub')}</p></div>
              {mine.length > 3 && <button className="btn-light" onClick={() => setPage('mine')}>{t('seeAll', { n: mine.length })}</button>}
            </div>
            <div className="rows">
              {mine.slice(0, 3).map((c) => <ComplaintCard key={c.id} c={c} highlight={c.id === lastId} />)}
              {mine.length === 0 && <p className="empty-state">{t('none')}</p>}
            </div>
          </section>
        </>
      )}
      {page === 'report' && (
        <ReportForm citizen assets={assets} onSubmitted={load} onCreated={setLastId} onOpenAsset={() => setPage('mine')} />
      )}
      {page === 'mine' && (
        <section className="card">
          <div className="card-head"><div><h2 className="h-card">{t('nav_mine')}</h2><p className="sub">{t('mineSub')}</p></div></div>
          {!mine && <p className="muted">Loading…</p>}
          <div className="rows">
            {mine?.map((c) => <ComplaintCard key={c.id} c={c} highlight={c.id === lastId} />)}
            {mine?.length === 0 && <p className="empty-state">{t('none')}</p>}
          </div>
        </section>
      )}
    </Shell>
  )
}
