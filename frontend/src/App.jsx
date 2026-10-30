import { useEffect, useState } from 'react'
import { api, label, level, rupees, TYPE_ICON } from './api'
import AssetMap from './components/AssetMap'
import AssetPanel from './components/AssetPanel'
import Patterns from './components/Patterns'
import ReportForm from './components/ReportForm'
import { Contractors, Insights, ReviewQueue, SearchResults } from './components/Views'

const TABS = [['dashboard', 'Dashboard'], ['report', 'Report issue'], ['patterns', 'Patterns'], ['review', 'Review queue'], ['contractors', 'Contractors'], ['insights', 'Prediction check']]

function AiBadge({ h }) {
  if (!h) return null
  const emb = h.ai.embedder, l = h.ai.llm
  const full = emb.backend === 'sbert' && l.available
  return (
    <span className={`ai-badge ${full ? 'on' : 'part'}`} title={`Matching: ${emb.model}${emb.error ? ' (' + emb.error + ')' : ''}\nLLM: ${l.model} at ${l.host}${l.error ? ' (' + l.error + ')' : ''}`}>
      AI: {emb.backend === 'sbert' ? 'embeddings on' : 'embeddings off'} · {l.available ? `LLM on (${l.model})` : 'LLM off'}
    </span>
  )
}

function Stats({ s }) {
  if (!s) return null
  return (
    <div className="stats">
      <div><b>{s.assets}</b><span>assets tracked</span></div>
      <div><b>{s.complaints}</b><span>complaints linked</span></div>
      <div className="warn"><b>{s.recurring_assets}</b><span>recurring failures</span></div>
      <div className="warn"><b>{s.replace_recommended}</b><span>stop-patching alerts</span></div>
      <div><b>{rupees(s.patch_spend_total)}</b><span>spent on {s.temporary_repairs} patches</span></div>
      <div><b>{s.pending_review}</b><span>awaiting review</span></div>
    </div>
  )
}

function Queue({ items, selected, onSelect, filter, setFilter }) {
  const shown = filter ? items.filter((a) => a.type === filter) : items
  return (
    <div className="panel queue">
      <div className="queue-head">
        <h3>Priority queue</h3>
        <select value={filter} onChange={(e) => setFilter(e.target.value)}>
          <option value="">All types</option>
          {Object.entries(TYPE_ICON).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
        </select>
      </div>
      <ol>
        {shown.map((a, i) => (
          <li key={a.asset_id} className={selected === a.asset_id ? 'sel' : ''} onClick={() => onSelect(a.asset_id)}>
            <span className={`rank ${level(a.priority)}`}>{a.priority}</span>
            <div className="q-body">
              <div className="q-title">{i + 1}. {a.name}</div>
              <div className="muted small">{a.asset_id} · {a.incidents_12m} failures in 12 months · {label(a.cause)}</div>
              <div className="q-tags">
                {a.recurring && <span className="tag warn">recurring</span>}
                {a.recommendation === 'replace' && <span className="tag danger">stop patching</span>}
                {a.pending_review > 0 && <span className="tag">review</span>}
              </div>
            </div>
          </li>
        ))}
      </ol>
    </div>
  )
}

export default function App() {
  const [tab, setTab] = useState('dashboard')
  const [assets, setAssets] = useState([])
  const [stats, setStats] = useState(null)
  const [selected, setSelected] = useState(null)
  const [filter, setFilter] = useState('')
  const [q, setQ] = useState('')
  const [search, setSearch] = useState('')
  const [err, setErr] = useState('')
  const [health, setHealth] = useState(null)

  const refresh = () =>
    Promise.all([api.priority(100), api.stats()])
      .then(([a, s]) => { setAssets(a); setStats(s); setErr('') })
      .catch(() => setErr('Cannot reach the CityMemory API. Start the backend on port 8000.'))
  useEffect(() => { refresh(); api.health().then(setHealth).catch(() => {}) }, [])

  const openAsset = (id) => { setSelected(id); setSearch(''); setTab('dashboard') }
  const resetDemo = async () => { if (confirm('Restore the simulated demo data?')) { await api.reset(); setSelected(null); refresh() } }

  return (
    <div className="app">
      <header>
        <div className="brand">
          <span className="logo">CM</span>
          <div><b>CityMemory</b><small>Civic infrastructure history · Demo Ward</small></div>
          <span className="sim">Simulated data</span>
          <AiBadge h={health} />
        </div>
        <form className="search" onSubmit={(e) => { e.preventDefault(); if (q.trim().length > 1) setSearch(q.trim()) }}>
          <input placeholder="Search history: asset ID, street, “drain overflow”…" value={q} onChange={(e) => setQ(e.target.value)} />
        </form>
        <nav>
          {TABS.map(([k, v]) => <button key={k} className={tab === k && !search ? 'on' : ''} onClick={() => { setTab(k); setSearch('') }}>{v}</button>)}
          <button className="ghost-link" onClick={resetDemo} title="Restore demo data">Reset</button>
        </nav>
      </header>

      {err && <div className="error banner">{err}</div>}

      <main>
        {search ? <SearchResults q={search} onOpenAsset={openAsset} /> : (
          <>
            {tab === 'dashboard' && (
              <>
                <Stats s={stats} />
                <div className="grid">
                  <div className="map-col">
                    <div className="panel map-panel">
                      <AssetMap assets={filter ? assets.filter((a) => a.type === filter) : assets} selected={selected} onSelect={setSelected} />
                      <div className="legend">
                        <span><i className="dot high" /> high priority</span>
                        <span><i className="dot mid" /> medium</span>
                        <span><i className="dot low" /> low</span>
                        <span>Circle size = number of failures · dashed = unregistered</span>
                      </div>
                    </div>
                    <Queue items={assets} selected={selected} onSelect={setSelected} filter={filter} setFilter={setFilter} />
                  </div>
                  <div className="side-col">
                    {selected
                      ? <AssetPanel assetId={selected} onClose={() => setSelected(null)} onChanged={refresh} />
                      : <div className="panel intro">
                          <h3>How to read this</h3>
                          <p>Every complaint and repair is linked to a physical asset, so each road, drain and light keeps its own history.</p>
                          <p>The queue ranks assets by repeat failures, recency, severity, spend and how long an issue has been open. Open any asset to see why it ranks there, its full timeline, the likely cause and whether to stop patching.</p>
                          <p className="muted small">AI suggests matches and causes; engineers decide. All data here is simulated.</p>
                        </div>}
                  </div>
                </div>
              </>
            )}
            {tab === 'report' && <ReportForm assets={assets} onSubmitted={refresh} onOpenAsset={openAsset} />}
            {tab === 'patterns' && <Patterns assets={assets} onOpenAsset={openAsset} />}
            {tab === 'review' && <ReviewQueue onChanged={refresh} onOpenAsset={openAsset} />}
            {tab === 'contractors' && <Contractors />}
            {tab === 'insights' && <Insights />}
          </>
        )}
      </main>
    </div>
  )
}
