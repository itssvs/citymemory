// Set VITE_API_URL when the frontend is deployed separately (e.g. Vercel + Render).
const BASE = import.meta.env.VITE_API_URL || ''

// The login token is kept in sessionStorage (per browser tab) and in memory as a fallback.
const KEY = 'citymemory.session'
let memory = null
export const session = {
  get() {
    try { return JSON.parse(sessionStorage.getItem(KEY)) || memory } catch { return memory }
  },
  set(v) {
    memory = v
    try { v ? sessionStorage.setItem(KEY, JSON.stringify(v)) : sessionStorage.removeItem(KEY) } catch { /* storage blocked */ }
  },
}
let onLoggedOut = () => {}
export const setLoggedOutHandler = (fn) => { onLoggedOut = fn }

async function req(path, opts = {}) {
  const s = session.get()
  const headers = { ...(opts.headers || {}) }
  if (s?.token) headers.Authorization = `Bearer ${s.token}`
  const res = await fetch(BASE + path, { ...opts, headers })
  const body = await res.json().catch(() => ({}))
  if (res.status === 401 && s?.token) { session.set(null); onLoggedOut() }
  if (!res.ok) throw new Error(body.detail || `Request failed (${res.status})`)
  return body
}
const json = (method, body) => ({ method, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) })

export const api = {
  login: (username, password) => req('/api/auth/login', json('POST', { username, password })),
  register: (username, password, name) => req('/api/auth/register', json('POST', { username, password, name })),
  demoLogin: (role) => req('/api/auth/demo', json('POST', { role })),
  logout: () => req('/api/auth/logout', { method: 'POST' }),
  myComplaints: () => req('/api/me/complaints'),
  publicAssets: () => req('/api/public/assets'),
  overview: () => req('/api/overview'),
  calendar: (month) => req(`/api/calendar?month=${month}`),
  workOrders: (status = 'open') => req(`/api/work-orders?status=${status}`),
  assignWork: (assetId, body) => req(`/api/assets/${encodeURIComponent(assetId)}/work-orders`, json('POST', body)),
  startWork: (id) => req(`/api/work-orders/${id}/start`, { method: 'POST' }),
  completeWork: (id, form) => req(`/api/work-orders/${id}/complete`, { method: 'POST', body: form }),
  health: () => req('/api/health'),
  stats: () => req('/api/stats'),
  aiSummary: (id) => req(`/api/assets/${encodeURIComponent(id)}/ai-summary`),
  patterns: () => req('/api/patterns'),
  assets: () => req('/api/assets'),
  priority: (limit = 20) => req(`/api/priority?limit=${limit}`),
  asset: (id) => req(`/api/assets/${encodeURIComponent(id)}`),
  search: (q) => req(`/api/search?q=${encodeURIComponent(q)}`),
  contractors: () => req('/api/contractors'),
  review: () => req('/api/review'),
  backtest: () => req('/api/backtest'),
  reset: () => req('/api/reset', { method: 'POST' }),
  complain: (form) => req('/api/complaints', { method: 'POST', body: form }),
  decide: (id, body) =>
    req(`/api/complaints/${id}/review`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
    }),
  repair: (body) =>
    req('/api/repairs', {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
    }),
  photo: (url) => (url ? BASE + url : null),
}

export const rupees = (n) => '₹' + Math.round(n || 0).toLocaleString('en-IN')
export const day = (iso) =>
  iso ? new Date(iso).toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' }) : '—'
export const label = (s) => (s || '').replace(/_/g, ' ')
export const TYPE_ICON = { road: 'Road', drain: 'Drain', streetlight: 'Light', footpath: 'Footpath', toilet: 'Toilet' }
export const MATCHER = { sbert: 'multilingual sentence embeddings', hash: 'hashing embeddings', tfidf: 'TF-IDF text similarity' }
export const level = (score) => (score >= 55 ? 'high' : score >= 35 ? 'mid' : 'low')
