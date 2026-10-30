// Set VITE_API_URL when the frontend is deployed separately (e.g. Vercel + Render).
const BASE = import.meta.env.VITE_API_URL || ''

async function req(path, opts = {}) {
  const res = await fetch(BASE + path, opts)
  const body = await res.json().catch(() => ({}))
  if (!res.ok) throw new Error(body.detail || `Request failed (${res.status})`)
  return body
}

export const api = {
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
