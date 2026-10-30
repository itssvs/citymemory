import { useEffect, useState } from 'react'
import { ClipboardCheck, HardHat, Landmark, Link2, MapPinPlus, UserRound } from 'lucide-react'
import { api } from '../api'
import { usePrefs } from '../i18n'
import { BrandMark, GovStrip, SiteFooter } from '../ui'

const DEMO = [
  ['citizen', UserRound, ''],
  ['engineer', HardHat, 'warm'],
  ['commissioner', Landmark, 'dark'],
]

export default function Login({ onLogin }) {
  const { t } = usePrefs()
  const [mode, setMode] = useState('login')
  const [f, setF] = useState({ username: '', password: '', name: '' })
  const [err, setErr] = useState('')
  const [busy, setBusy] = useState(false)
  const [demo, setDemo] = useState(false)
  useEffect(() => { api.health().then((h) => setDemo(!!h.demo)).catch(() => {}) }, [])

  const submit = async (e) => {
    e.preventDefault()
    setErr(''); setBusy(true)
    try {
      onLogin(mode === 'login' ? await api.login(f.username, f.password) : await api.register(f.username, f.password, f.name))
    } catch (x) { setErr(x.message) } finally { setBusy(false) }
  }
  const tryDemo = async (role) => {
    setErr(''); setBusy(true)
    try { onLogin(await api.demoLogin(role)) } catch (x) { setErr(x.message) } finally { setBusy(false) }
  }
  const steps = [[MapPinPlus, 'lg_s1'], [Link2, 'lg_s2'], [ClipboardCheck, 'lg_s3']]

  return (
    <>
      <a className="skip-link" href="#main">{t('skip')}</a>
      <GovStrip />
      <div className="frame">
        <main className="login" id="main" tabIndex={-1}>
          <section className="login-hero" aria-labelledby="hero-title">
            <div>
              <p className="brand-row"><BrandMark size={30} /><span className="brand-name">CityMemory</span></p>
              <h1 id="hero-title" className="h-greet">{t('lg_head')}</h1>
              <p className="lead">{t('lg_lead')}</p>
            </div>
            <div>
              <h2 className="h-section" style={{ marginBottom: 12 }}>{t('lg_how')}</h2>
              <ol className="how-list">
                {steps.map(([Ic, k], i) => (
                  <li key={k}><span className="how-n num">{i + 1}</span><Ic size={18} aria-hidden="true" /><span>{t(k)}</span></li>
                ))}
              </ol>
            </div>
          </section>

          <div className="login-side">
            <section className="card">
              <h2 className="h-card" style={{ marginBottom: 18 }}>{mode === 'login' ? t('lg_title') : t('lg_register')}</h2>
              <form className="form" onSubmit={submit}>
                {mode === 'register' && <label className="field">{t('lg_name')}<input required autoComplete="name" value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} /></label>}
                <label className="field">{t('lg_user')}<input required autoComplete="username" value={f.username} onChange={(e) => setF({ ...f, username: e.target.value })} /></label>
                <label className="field">{t('lg_pass')}
                  <input required type="password" autoComplete={mode === 'login' ? 'current-password' : 'new-password'} minLength={mode === 'register' ? 8 : undefined}
                    value={f.password} onChange={(e) => setF({ ...f, password: e.target.value })} />
                </label>
                {err && <div className="error-box" role="alert">{err}</div>}
                <button className="btn-dark" disabled={busy}>{busy ? t('lg_wait') : mode === 'login' ? t('lg_title') : t('lg_create')}</button>
              </form>
              <p className="switch" style={{ marginTop: 16 }}>
                {mode === 'login'
                  ? <>{t('lg_new')} <button onClick={() => { setMode('register'); setErr('') }}>{t('lg_register')}</button>. {t('lg_staff')}</>
                  : <>{t('lg_have')} <button onClick={() => { setMode('login'); setErr('') }}>{t('lg_title')}</button></>}
              </p>
            </section>

            {demo && (
              <section aria-labelledby="demo-title">
                <h2 id="demo-title" className="h-section" style={{ marginBottom: 4 }}>{t('demo')}</h2>
                <p className="sub" style={{ marginBottom: 12 }}>{t('demoSub')}</p>
                <div className="rows">
                  {DEMO.map(([role, Ic, tone]) => (
                    <button key={role} className="demo-row" onClick={() => tryDemo(role)} disabled={busy}>
                      <span className={`badge-ic ${tone}`}><Ic size={18} aria-hidden="true" /></span>
                      <span><b>{t(`role_${role}`)}</b><br /><span className="small ink2">{t(`demo_${role}`)}</span></span>
                      <span className="small strong">{t('open')}</span>
                    </button>
                  ))}
                </div>
              </section>
            )}
          </div>
        </main>
        <SiteFooter />
      </div>
    </>
  )
}
