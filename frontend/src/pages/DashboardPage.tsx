import {
  ArrowRight,
  BadgeDollarSign,
  Boxes,
  ChartNoAxesCombined,
  CircleDollarSign,
  Eye,
  FileText,
  MousePointerClick,
  Sparkles,
  Target,
  TrendingUp,
} from 'lucide-react'
import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { EmptyState } from '../components/EmptyState'
import { FilterBar } from '../components/FilterBar'
import { LoadingScreen } from '../components/LoadingScreen'
import { MetricCard } from '../components/MetricCard'
import { SectionHeader } from '../components/SectionHeader'
import { useDatasets } from '../context/DatasetContext'
import { api, queryString } from '../lib/api'
import { currency, date, number, reportType } from '../lib/format'
import type { DashboardData, FilterOptions, Filters } from '../types'

const emptyOptions: FilterOptions = { regions: [], quarters: [], products: [], channels: [] }
const regionColors = ['#4d8dff', '#f6c945', '#8c6cff', '#29d3c2', '#ff7d66', '#6aa5ff']

export function DashboardPage() {
  const { activeId, activeDataset } = useDatasets()
  const [options, setOptions] = useState<FilterOptions>(emptyOptions)
  const [filters, setFilters] = useState<Filters>({})
  const [data, setData] = useState<DashboardData | null>(null)
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [error, setError] = useState('')
  const funnelData = data ? [
    { name: 'Impressions', value: data.kpis.impressions, color: '#4d8dff' },
    { name: 'Clicks', value: data.kpis.clicks, color: '#29d3c2' },
    { name: 'Conversions', value: data.kpis.conversions, color: '#f6c945' },
  ] : []

  useEffect(() => {
    setFilters({})
    api<FilterOptions>(`/meta/options${queryString({ dataset_id: activeId })}`).then(setOptions).catch((reason) => setError(reason.message))
  }, [activeId])

  useEffect(() => {
    let active = true
    if (data) setRefreshing(true)
    setError('')
    api<DashboardData>(`/dashboard${queryString({ ...filters, dataset_id: activeId })}`)
      .then((result) => { if (active) setData(result) })
      .catch((reason) => { if (active) setError(reason.message) })
      .finally(() => {
        if (active) {
          setLoading(false)
          setRefreshing(false)
        }
      })
    return () => { active = false }
  }, [filters, activeId])

  if (loading) return <LoadingScreen compact />

  return (
    <div className={`page-stack ${refreshing ? 'page-stack--refreshing' : ''}`}>
      <section className="welcome-strip">
        <div>
          <span className="status-line"><i /> LIVE DATASET · {activeDataset?.name || 'BUNDLED DEMO DATA'}</span>
          <h2>Your business, decoded.</h2>
          <p>Explore verified sales and marketing signals, then turn any view into an executive report.</p>
        </div>
        <Link className="primary-button" to="/studio"><Sparkles size={18} /> Generate intelligence</Link>
      </section>

      <FilterBar options={options} filters={filters} onChange={setFilters} />

      {error && <div className="error-banner">{error}</div>}

      {data && (
        <>
          <div className="metric-grid">
            <MetricCard
              label="Total revenue"
              value={currency(data.kpis.revenue)}
              detail={`${data.coverage.sales_records.toLocaleString()} sales records`}
              icon={<CircleDollarSign size={20} />}
              accent="blue"
              change={data.kpis.period_change}
            />
            <MetricCard
              label="Units sold"
              value={number(data.kpis.units)}
              detail="Across the selected scope"
              icon={<Boxes size={20} />}
              accent="cyan"
            />
            <MetricCard
              label="Conversions"
              value={number(data.kpis.conversions)}
              detail={`${data.kpis.conversion_rate.toFixed(2)}% from clicks`}
              icon={<Target size={20} />}
              accent="yellow"
            />
            <MetricCard
              label="Cost / conversion"
              value={currency(data.kpis.cost_per_conversion, false)}
              detail={`${currency(data.kpis.marketing_budget)} total spend`}
              icon={<BadgeDollarSign size={20} />}
              accent="violet"
            />
          </div>

          <div className="dashboard-grid">
            <article className="data-panel revenue-panel">
              <SectionHeader
                eyebrow="REVENUE VELOCITY"
                title="Quarterly performance"
                action={<span className="panel-badge"><TrendingUp size={15} /> {data.kpis.period_change === null ? 'Full timeline' : `${data.kpis.period_change >= 0 ? '+' : ''}${data.kpis.period_change}%`}</span>}
              />
              {data.charts.revenue_by_quarter.length ? <div className="chart-large">
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart data={data.charts.revenue_by_quarter} margin={{ top: 16, right: 6, left: -12, bottom: 0 }}>
                    <defs>
                      <linearGradient id="revenueFill" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%" stopColor="#4d8dff" stopOpacity={0.38} />
                        <stop offset="95%" stopColor="#4d8dff" stopOpacity={0} />
                      </linearGradient>
                    </defs>
                    <CartesianGrid stroke="#1b263d" strokeDasharray="3 7" vertical={false} />
                    <XAxis dataKey="name" stroke="#6f7e98" axisLine={false} tickLine={false} tick={{ fontSize: 12 }} />
                    <YAxis stroke="#6f7e98" axisLine={false} tickLine={false} tick={{ fontSize: 12 }} tickFormatter={(value) => currency(value)} />
                    <Tooltip contentStyle={{ background: '#0d1422', border: '1px solid #263451', borderRadius: 12 }} formatter={(value) => [currency(Number(value), false), 'Revenue']} />
                    <Area type="monotone" dataKey="value" stroke="#69a1ff" strokeWidth={3} fill="url(#revenueFill)" activeDot={{ r: 6, fill: '#f6c945', stroke: '#070b14', strokeWidth: 3 }} />
                  </AreaChart>
                </ResponsiveContainer>
              </div> : <EmptyState title="No revenue timeline" copy="This source contains marketing metrics only. The acquisition funnel below remains fully available." />}
            </article>

            <article className="data-panel region-panel">
              <SectionHeader eyebrow="MARKET MIX" title="Revenue by region" />
              {data.charts.revenue_by_region.length ? (
                <div className="donut-layout">
                  <div className="chart-donut">
                    <ResponsiveContainer width="100%" height="100%">
                      <PieChart>
                        <Pie data={data.charts.revenue_by_region} dataKey="value" nameKey="name" innerRadius={57} outerRadius={82} paddingAngle={3} stroke="none">
                          {data.charts.revenue_by_region.map((entry, index) => <Cell key={entry.name} fill={regionColors[index % regionColors.length]} />)}
                        </Pie>
                        <Tooltip contentStyle={{ background: '#0d1422', border: '1px solid #263451', borderRadius: 12 }} formatter={(value) => currency(Number(value), false)} />
                      </PieChart>
                    </ResponsiveContainer>
                    <div className="donut-center"><strong>{data.charts.revenue_by_region.length}</strong><span>regions</span></div>
                  </div>
                  <div className="legend-list">
                    {data.charts.revenue_by_region.slice(0, 5).map((item, index) => (
                      <div key={item.name}><i style={{ backgroundColor: regionColors[index % regionColors.length] }} /><span>{item.name}</span><strong>{currency(item.value)}</strong></div>
                    ))}
                  </div>
                </div>
              ) : <EmptyState title="No regional data" copy="Change the filters to expand the selected scope." />}
            </article>

            <article className="data-panel products-panel">
              <SectionHeader eyebrow="PRODUCT SIGNAL" title="Top revenue drivers" />
              {data.charts.top_products.length ? <div className="chart-medium">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={data.charts.top_products} layout="vertical" margin={{ left: 8, right: 16, top: 6 }}>
                    <CartesianGrid stroke="#1b263d" strokeDasharray="3 7" horizontal={false} />
                    <XAxis type="number" hide />
                    <YAxis type="category" dataKey="name" width={148} stroke="#9aa8bf" axisLine={false} tickLine={false} tick={{ fontSize: 12 }} />
                    <Tooltip cursor={{ fill: '#121c2e' }} contentStyle={{ background: '#0d1422', border: '1px solid #263451', borderRadius: 12 }} formatter={(value) => currency(Number(value), false)} />
                    <Bar dataKey="value" fill="#4d8dff" radius={[0, 7, 7, 0]} barSize={14} />
                  </BarChart>
                </ResponsiveContainer>
              </div> : <EmptyState title="No product revenue" copy="Map product and revenue fields in a sales source to unlock this view." />}
            </article>

            <article className="data-panel channels-panel">
              <SectionHeader eyebrow="ACQUISITION EFFICIENCY" title="Conversions by channel" action={<span className="panel-badge"><MousePointerClick size={15} /> {data.kpis.ctr.toFixed(2)}% CTR</span>} />
              <div className="channel-table">
                <div className="channel-table__head"><span>Channel</span><span>Conversions</span><span>CPA</span></div>
                {data.charts.channel_performance.slice(0, 6).map((item, index) => {
                  const max = data.charts.channel_performance[0]?.conversions || 1
                  return (
                    <div className="channel-row" key={item.name}>
                      <span><i>{String(index + 1).padStart(2, '0')}</i>{item.name}</span>
                      <span><b style={{ width: `${Math.max(7, item.conversions / max * 100)}%` }} />{number(item.conversions)}</span>
                      <strong>{currency(item.cpa, false)}</strong>
                    </div>
                  )
                })}
              </div>
            </article>

            <article className="data-panel funnel-panel">
              <SectionHeader eyebrow="FULL-FUNNEL SIGNAL" title="Acquisition journey" action={<span className="panel-badge"><Eye size={15} /> {number(data.kpis.impressions)} reached</span>} />
              {data.kpis.impressions || data.kpis.clicks || data.kpis.conversions ? (
                <div className="funnel-layout">
                  <div className="funnel-chart">
                    <ResponsiveContainer width="100%" height="100%">
                      <BarChart data={funnelData} layout="vertical" margin={{ top: 5, right: 28, left: 12, bottom: 0 }}>
                        <CartesianGrid stroke="#1b263d" strokeDasharray="3 7" horizontal={false} />
                        <XAxis type="number" hide />
                        <YAxis type="category" dataKey="name" width={96} stroke="#9aa8bf" axisLine={false} tickLine={false} tick={{ fontSize: 12 }} />
                        <Tooltip cursor={{ fill: '#121c2e' }} contentStyle={{ background: '#0d1422', border: '1px solid #263451', borderRadius: 12 }} formatter={(value) => [number(Number(value)), 'People']} />
                        <Bar dataKey="value" radius={[0, 8, 8, 0]} barSize={22}>
                          {funnelData.map((entry) => <Cell key={entry.name} fill={entry.color} />)}
                        </Bar>
                      </BarChart>
                    </ResponsiveContainer>
                  </div>
                  <div className="funnel-efficiency">
                    <div><span>Click-through</span><strong>{data.kpis.ctr.toFixed(2)}%</strong><small>Impression → click</small></div>
                    <div><span>Conversion rate</span><strong>{data.kpis.conversion_rate.toFixed(2)}%</strong><small>Click → conversion</small></div>
                    <div><span>Acquisition cost</span><strong>{currency(data.kpis.cost_per_conversion, false)}</strong><small>Spend per conversion</small></div>
                  </div>
                </div>
              ) : <EmptyState title="No funnel metrics" copy="Map impressions, clicks, conversions, or budget from a marketing source to unlock this view." />}
            </article>
          </div>

          <div className="dashboard-lower">
            <article className="data-panel insight-panel">
              <SectionHeader eyebrow="AUTO-DETECTED" title="Signals worth attention" action={<ChartNoAxesCombined size={20} />} />
              <div className="insight-list">
                {data.insights.map((insight, index) => (
                  <div key={insight}><span>{String(index + 1).padStart(2, '0')}</span><p>{insight}</p><ArrowRight size={16} /></div>
                ))}
              </div>
            </article>

            <article className="data-panel recent-panel">
              <SectionHeader eyebrow={`${data.report_count} SAVED`} title="Recent reports" action={<Link to="/reports">View all <ArrowRight size={15} /></Link>} />
              {data.recent_reports.length ? (
                <div className="recent-list">
                  {data.recent_reports.map((report) => (
                    <Link to={`/reports/${report.id}`} key={report.id}>
                      <span className="report-icon"><FileText size={18} /></span>
                      <span><strong>{report.title}</strong><small>{reportType(report.report_type)} · {date(report.created_at)}</small></span>
                      <ArrowRight size={16} />
                    </Link>
                  ))}
                </div>
              ) : (
                <EmptyState title="No reports yet" copy="Generate your first executive brief from the live dataset." action={<Link className="text-button" to="/studio">Open AI Studio <ArrowRight size={15} /></Link>} />
              )}
            </article>
          </div>
        </>
      )}
    </div>
  )
}
