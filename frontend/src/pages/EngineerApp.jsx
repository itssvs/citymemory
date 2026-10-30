import { useState } from 'react'
import { ClipboardList, House, Inbox, Map as MapIcon, Waypoints } from 'lucide-react'
import WorkOrders from '../components/WorkOrders'
import Patterns from '../components/Patterns'
import { ReviewQueue, SearchResults } from '../components/Views'
import { CalendarCard, Gauge, lakh, PillProgress, Shell, StatCard } from '../ui'
import { AssetDrawer, AssetList, MapCard, useStaffData } from './staff'

export default function EngineerApp({ user, onLogout }) {
  const [page, setPage] = useState('home')
  const [open, setOpen] = useState(null)
  const [search, setSearch] = useState('')
  const { assets, stats, err, refresh } = useStaffData()
  const [version, setVersion] = useState(0)
  const changed = () => { refresh(); setVersion((v) => v + 1) }
  const go = (p) => { setPage(p); setSearch('') }

  const pending = stats?.pending_review || 0
  const nav = [
    ['home', 'Today', House],
    ['jobs', 'Repair jobs', ClipboardList, (stats?.overdue_work_orders || 0) > 0],
    ['map', 'Ward map', MapIcon],
    ['review', 'Review queue', Inbox, pending > 0],
    ['patterns', 'Patterns', Waypoints],
  ]
  const worst = assets.find((a) => a.recommendation === 'replace')
  const held = stats && stats.repairs_judged_90 ? Math.round((stats.repairs_held_90 / stats.repairs_judged_90) * 100) : 0

  return (
    <Shell
      user={user} nav={nav} page={search ? '' : page} setPage={go} onLogout={onLogout} onSearch={setSearch}
      subline="What keeps failing in the ward, and what to fix first."
      cta={<button className="btn-dark" onClick={() => go('review')}>Review matches{pending > 0 && <span className="count num">{pending}</span>}</button>}
    >
      {err && <div className="error-box">{err}</div>}
      {search ? <SearchResults q={search} onOpenAsset={setOpen} onClear={() => setSearch('')} /> : (
        <>
          {page === 'home' && stats && (
            <>
              <div className="grid12">
                <div className="span-7">
                  <StatCard
                    title="Ward health today"
                    sub={`Out of ${stats.assets} assets tracked`}
                    items={[
                      { label: 'Failing repeatedly', value: stats.recurring_assets, note: 'assets that broke again after a repair', tone: 'yellow' },
                      { label: 'Need a permanent fix', value: stats.replace_recommended, note: 'patching now costs more than fixing', tone: 'coral' },
                      { label: 'Open issues', value: stats.open_issues, note: 'reported since their last repair', tone: 'dark' },
                    ]}
                    footer={`Repair jobs: ${stats.open_work_orders} open, ${stats.overdue_work_orders} past their target date.`}
                  />
                </div>
                <div className="span-5"><CalendarCard title="Complaints and repairs" /></div>
              </div>

              <div className="grid12">
                <div className="span-4 stack">
                  <section className="card gauge-card">
                    <div className="left">
                      <div>
                        <h2 className="h-card">Repairs that last</h2>
                        <p className="sub">Share of repairs that held 90 days or more</p>
                      </div>
                      <p className="small muted">{stats.repairs_held_90} of {stats.repairs_judged_90} repairs. Average life {stats.avg_days_lasted} days.</p>
                    </div>
                    <Gauge value={held} goal={100} centerLabel="Goal" centerValue="80%" tag={`${held}%`} />
                  </section>
                  {worst && (
                    <section className="card" style={{ cursor: 'pointer' }} onClick={() => setOpen(worst.asset_id)}>
                      <div className="pp-head">
                        <div><h2 className="h-card">Patching vs fixing</h2><p className="sub">{worst.name}</p></div>
                        <div className="pp-pct"><b className="num">{Math.round((worst.patch_spend_total / worst.replacement_cost) * 100)}%</b><span className="small muted">of a permanent fix</span></div>
                      </div>
                      <PillProgress frac={worst.patch_spend_total / worst.replacement_cost} tip={`${lakh(worst.patch_spend_total)} patched`}
                        left="₹0" right={`${lakh(worst.replacement_cost)} fix`} tone="coral" />
                    </section>
                  )}
                </div>
                <div className="span-8">
                  <AssetList assets={assets} selected={open} onOpen={setOpen} limit={6} title="Fix first" sub="Ranked by repeat failures, recency, severity, spend and how long it has been open." />
                </div>
              </div>
              <MapCard assets={assets} selected={open} onOpen={setOpen} height={380} title="Where it is happening" />
            </>
          )}

          {page === 'map' && (
            <div className="grid12">
              <div className="span-7"><MapCard assets={assets} selected={open} onOpen={setOpen} height={640} title="Every tracked asset" /></div>
              <div className="span-5"><AssetList assets={assets} selected={open} onOpen={setOpen} title="All assets" /></div>
            </div>
          )}
          {page === 'jobs' && <WorkOrders onOpen={setOpen} version={version} />}
          {page === 'review' && <ReviewQueue onChanged={refresh} onOpenAsset={setOpen} />}
          {page === 'patterns' && <Patterns assets={assets} onOpenAsset={setOpen} />}
        </>
      )}
      <AssetDrawer id={open} onClose={() => setOpen(null)} canEdit onChanged={changed} />
    </Shell>
  )
}
