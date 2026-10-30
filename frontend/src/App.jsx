import { useEffect, useState } from 'react'
import { api, session, setLoggedOutHandler } from './api'
import CitizenApp from './pages/CitizenApp'
import CommissionerApp from './pages/CommissionerApp'
import EngineerApp from './pages/EngineerApp'
import Login from './pages/Login'
import { EnglishOnly } from './i18n'

const APPS = { citizen: CitizenApp, engineer: EngineerApp, commissioner: CommissionerApp }

export default function App() {
  const [s, setS] = useState(() => session.get())

  useEffect(() => { setLoggedOutHandler(() => setS(null)) }, [])

  const onLogin = (r) => { session.set(r); setS(r) }
  const onLogout = async () => {
    try { await api.logout() } catch { /* already logged out */ }
    session.set(null)
    setS(null)
  }

  const RoleApp = s?.user && APPS[s.user.role]
  if (!RoleApp) return <Login onLogin={onLogin} />
  // key: a fresh dashboard (no leftover state) whenever a different user logs in
  const app = <RoleApp key={s.user.username} user={s.user} onLogout={onLogout} />
  return s.user.role === 'citizen' ? app : <EnglishOnly>{app}</EnglishOnly>
}
