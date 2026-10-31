import { useEffect, useState } from 'react'
import { Ellipsis, HardHat, House, History, Map as MapIcon, Target, Waypoints } from 'lucide-react'
import { api, label } from '../api'
import Patterns from '../components/Patterns'
import Timeline from '../components/Timeline'
import { Contractors, Insights } from '../components/Views'
import { Gauge, lakh, PillProgress, Seg, Shell, SplitBar, StatCard, TYPE_NAME, TypeBadge } from '../ui'
import { AssetDrawer, AssetList, MapCard, useStaffData } from './staff'

const MON = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

function MonthBars({ months }) {
  const max = Math.max(...months.map((m) => m.count), 1)
  const last = months.length - 1
  return (
    <section className="card dark" aria-label="Complaints per month">
      <div className="cal-head">
        <h2 className="h-card">Complaints per month</h2>
        <span className="cal-month">Last 12 months</span>
      </div>
      <div className="dbars" role="list">
        {months.map((m, i) => (
          <div key={m.month} role="listitem" className={`dbar ${i === last ? 'now' : ''}`} title={`${MON[Number(m.month.slice(5)) - 1]} ${m.month.slice(0, 4)}: ${m.count} complaints`}
            aria-label={`${MON[Number(m.month.slice(5)) - 1]}: ${m.count} complaints`}>
            {(i === last || m.count === max) && <b className="num">{m.count}</b>}
            <div className="dbar-fill" style={{ height: `${(m.count / max) * 100}%` }} />
            <span>{MON[Number(m.month.slice(5)) - 1][0]}</span>
          </div>
        ))}
      </div>
      <div className="cal-legend">
        <span><i className="k-fixed" />This month</span>
        <span><i className="k-filed" />Earlier months</span>
      </div>
    </section>
  )
}

function DecisionRow({ x, onOpen }) {
  return (
    <button className="row-item" onClick={() => onOpen(x.asset_id)} aria-label={`${x.name}. Open history`}>
      <TypeBadge type={x.type} tone="hot" />
      <div style={{ minWidth: 0 }}>
        <p className="row-title">{x.name}</p>
        <p className="row-sub">{x.asset_id}, {label(x.cause)}, {x.incidents_12m} failures this year</p>
      </div>
      <div className="row-metric">
        <span>Patched <b className="num">{lakh(x.patch_spend_total)}</b> of <b className="num">{lakh(x.replacement_cost)}</b></span>
        <Seg value={Math.min(10, Math.round((x.patch_spend_total / x.replacement_cost) * 10))} total={10}
          label={`Patch spend is ${Math.round((x.patch_spend_total / x.replacement_cost) * 100)}% of a permanent fix`} />
      </div>
      <div className="row-end">
        <span className="tag dark num">Pays back in {x.years_to_break_even} yrs</span>
        <Ellipsis size={18} color="var(--muted)" aria-hidden="true" />
      </div>
    </button>
  )
}

function Overview({ onOpen }) {
  const [o, setO] = useState(null)
  const [err, setErr] = useState('')
  useEffect(() => { api.overview().then(setO).catch((e) => setErr(e.message)) }, [])
  if (err) return <div className="error-box">{err}</div>
  if (!o) return <section className="card muted">Loading the ward overview…</section>
  const k = o.kpis, d = o.decision
  const maxSpend = Math.max(...o.spend_by_type.map((s) => s.temporary + s.permanent), 1)
  const avg = k.avg_days_repair_lasted || 0
  return (
    <>
      <div className="grid12">
        <div className="span-7">
          <StatCard
            title="Repair spend, last 12 months"
            sub="Money spent on repairs in the ward, and complaints received"
            items={[
              { label: 'Temporary patches', display: lakh(k.patch_spend_12m), note: 'spent on patches that may fail again', tone: 'coral' },
              { label: 'Permanent fixes', display: lakh(k.permanent_spend_12m), note: 'spent on fixes meant to last', tone: 'yellow' },
              { label: 'Complaints', value: k.complaints_12m, note: 'received from citizens and staff', tone: 'dark' },
            ]}
          >
            <SplitBar label="How repair spend splits between patches and permanent fixes" parts={[
              { label: 'Patches', value: k.patch_spend_12m, display: lakh(k.patch_spend_12m), tone: 'coral' },
              { label: 'Permanent', value: k.permanent_spend_12m, display: lakh(k.permanent_spend_12m), tone: 'yellow' },
            ]} />
          </StatCard>
        </div>
        <div className="span-5"><MonthBars months={o.complaints_by_month} /></div>
      </div>

      <div className="grid12">
        <div className="span-4 stack">
          <section className="card gauge-card">
            <div className="left">
              <div><h2 className="h-card">Average repair life</h2><p className="sub">Days before the same asset fails again</p></div>
              <p className="small muted">{k.recurring_assets} of {k.assets} assets are failing repeatedly.</p>
            </div>
            <Gauge value={avg} goal={180} centerLabel="Goal, days" centerValue="180" tag={`${avg} days`} />
          </section>
          <section className="card">
            <div className="pp-head">
              <div><h2 className="h-card">Cost of waiting</h2><p className="sub">Yearly patching vs a one-time fix</p></div>
              <div className="pp-pct"><b className="num">{Math.round((d.patch_spend_per_year_now / d.one_time_investment) * 100)}%</b><span className="small muted">of the fix, every year</span></div>
            </div>
            <PillProgress frac={d.patch_spend_per_year_now / d.one_time_investment} tip={`${lakh(d.patch_spend_per_year_now)} a year`}
              left="₹0" right={`${lakh(d.one_time_investment)} once`} />
          </section>
        </div>
        <div className="span-8">
          <section className="card">
            <div className="card-head">
              <div>
                <h2 className="h-card">Stop patching these {d.assets}</h2>
                <p className="sub">They cost {lakh(d.patch_spend_per_year_now)} in patches last year. Fixing all of them is {lakh(d.one_time_investment)}, once.</p>
              </div>
            </div>
            <div className="rows">{o.stop_patching.map((x) => <DecisionRow key={x.asset_id} x={x} onOpen={onOpen} />)}</div>
            <p className="note" style={{ marginTop: 14 }}>Pay-back assumes last year's patch spend continues. {o.data_note}</p>
          </section>
        </div>
      </div>

      <div className="grid12">
        <section className="card span-6">
          <div className="card-head"><div><h2 className="h-card">Spend by asset type</h2><p className="sub">Last 12 months</p></div></div>
          <div className="cmp">
            {o.spend_by_type.map((s) => (
              <div key={s.type} className="cmp-row" style={{ gridTemplateColumns: '110px 1fr 80px' }}
                title={`${TYPE_NAME[s.type]}: ${lakh(s.temporary)} patches, ${lakh(s.permanent)} permanent`}>
                <span className="strong">{TYPE_NAME[s.type]}</span>
                <div className="cmp-bar" style={{ display: 'flex', gap: 2, background: 'var(--row)' }}>
                  <i className="coral" style={{ width: `${(s.temporary / maxSpend) * 100}%` }} />
                  {s.permanent > 0 && <i className="yellow" style={{ width: `${(s.permanent / maxSpend) * 100}%` }} />}
                </div>
                <b className="num">{lakh(s.temporary + s.permanent)}</b>
              </div>
            ))}
          </div>
          <p className="split-keys" style={{ marginTop: 8 }}>
            <span><i className="coral" aria-hidden="true" />Patches</span><span><i className="yellow" aria-hidden="true" />Permanent fixes</span>
          </p>
        </section>
        {o.contractors.shortest && (
          <section className="card span-6">
            <div className="card-head"><div><h2 className="h-card">Contractor accountability</h2><p className="sub">How long repairs hold, on average</p></div></div>
            <div className="rows">
              {[o.contractors.shortest, o.contractors.longest].map((c, i) => (
                <div key={c.contractor} className="row-item static" style={{ gridTemplateColumns: '44px minmax(0,1fr) auto' }}>
                  <span className={`badge-ic ${i === 0 ? 'hot' : 'warm'}`}><HardHat size={18} /></span>
                  <div><p className="row-title">{c.contractor}</p><p className="row-sub">{c.repairs} repairs, {c.failed_again} failed again</p></div>
                  <span className={`tag ${i === 0 ? 'coral' : 'yellow'} num`}>{c.avg_days_lasted} days</span>
                </div>
              ))}
            </div>
          </section>
        )}
      </div>
    </>
  )
}

export default function CommissionerApp({ user, onLogout }) {
  const [page, setPage] = useState('overview')
  const [open, setOpen] = useState(null)
  const [search, setSearch] = useState('')
  const { assets, err } = useStaffData()
  const go = (p) => { setPage(p); if (p !== 'timeline') setSearch('') }
  const nav = [
    ['overview', 'Overview', House],
    ['timeline', 'Timeline', History],
    ['assets', 'Assets', MapIcon],
    ['patterns', 'Patterns', Waypoints],
    ['contractors', 'Contractors', HardHat],
    ['prediction', 'Prediction check', Target],
  ]
  return (
    <Shell
      user={user} nav={nav} page={page} setPage={go} onLogout={onLogout} onSearch={page === 'timeline' ? undefined : (q) => { setSearch(q); setPage('timeline') }}
      subline="Where the ward's repair money goes, and where it keeps going."
      cta={<button className="btn-dark" onClick={() => go('contractors')}>Contractor report</button>}
    >
      {err && <div className="error-box">{err}</div>}
      {(
        <>
          {page === 'overview' && <Overview onOpen={setOpen} />}
          {page === 'assets' && (
            <div className="grid12">
              <div className="span-7"><MapCard assets={assets} selected={open} onOpen={setOpen} height={640} title="Every tracked asset" /></div>
              <div className="span-5"><AssetList assets={assets} selected={open} onOpen={setOpen} title="Assets by priority" sub="Read-only. Engineers verify complaints and log repairs." /></div>
            </div>
          )}
          {page === 'timeline' && <Timeline initialQ={search} onOpenAsset={setOpen} />}
          {page === 'patterns' && <Patterns assets={assets} onOpenAsset={setOpen} />}
          {page === 'contractors' && <Contractors />}
          {page === 'prediction' && <Insights />}
        </>
      )}
      <AssetDrawer id={open} onClose={() => setOpen(null)} />
    </Shell>
  )
}
