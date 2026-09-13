import {
  Activity,
  ArrowLeft,
  BarChart3,
  CalendarDays,
  CheckCircle2,
  Download,
  Eye,
  FileJson,
  Mail,
  MessageCircle,
  Printer,
  Send,
  ShieldCheck,
  Sparkles,
  Star,
  Target,
  TrendingUp,
  WalletCards,
  X,
} from 'lucide-react'
import { FormEvent, useEffect, useState } from 'react'
import ReactMarkdown from 'react-markdown'
import { Link, useLocation, useParams } from 'react-router-dom'
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  Cell,
  CartesianGrid,
  ComposedChart,
  Legend,
  Line,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import remarkGfm from 'remark-gfm'
import { LoadingScreen } from '../components/LoadingScreen'
import { useToast } from '../context/ToastContext'
import { api } from '../lib/api'
import { currency, date, number, reportType } from '../lib/format'
import type { ReportDetail, SystemStatus } from '../types'

const chartColors = ['#4d8dff', '#f6c945', '#56d6a7', '#9c7cff', '#ff806e', '#55c5f8', '#d977f0', '#8fa6c7']
const tooltipStyle = { background: '#0b1322', border: '1px solid #293a5c', borderRadius: 12, boxShadow: '0 18px 45px rgba(0,0,0,.32)' }
const compact = (value: number) => Intl.NumberFormat('en', { notation: 'compact', maximumFractionDigits: 1 }).format(value)

export function ReportDetailPage() {
  const { id } = useParams()
  const location = useLocation()
  const { showToast } = useToast()
  const [report, setReport] = useState<ReportDetail | null>(null)
  const [system, setSystem] = useState<SystemStatus | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [deliveryOpen, setDeliveryOpen] = useState(false)
  const [channel, setChannel] = useState<'email' | 'telegram'>('email')
  const [destination, setDestination] = useState('')
  const [sending, setSending] = useState(false)

  useEffect(() => {
    if (!id) return
    Promise.all([
      api<ReportDetail>(`/reports/${id}`),
      api<SystemStatus>('/system/status'),
    ]).then(([reportData, systemData]) => {
      setReport(reportData)
      setSystem(systemData)
      if ((location.state as { created?: boolean } | null)?.created) showToast('Report generated and saved')
    }).catch((reason) => setError(reason.message)).finally(() => setLoading(false))
  }, [id])

  const toggleFavorite = async () => {
    if (!report) return
    try {
      const updated = await api<ReportDetail>(`/reports/${report.id}/favorite`, {
        method: 'PATCH',
        body: JSON.stringify({ favorite: !report.favorite }),
      })
      setReport(updated)
      showToast(updated.favorite ? 'Saved to favorites' : 'Removed from favorites')
    } catch (reason) {
      showToast(reason instanceof Error ? reason.message : 'Could not update report', 'error')
    }
  }

  const deliver = async (event: FormEvent) => {
    event.preventDefault()
    if (!report) return
    setSending(true)
    try {
      const result = await api<{ message: string }>(`/reports/${report.id}/deliver`, {
        method: 'POST',
        body: JSON.stringify({ channel, destination }),
      })
      showToast(result.message)
      setDeliveryOpen(false)
      setDestination('')
    } catch (reason) {
      showToast(reason instanceof Error ? reason.message : 'Delivery failed', 'error')
    } finally {
      setSending(false)
    }
  }

  if (loading) return <LoadingScreen compact />
  if (error || !report) {
    return <div className="error-page"><h2>Report unavailable</h2><p>{error || 'This report could not be found.'}</p><Link to="/reports">Return to report library</Link></div>
  }

  const revenueTimeline = report.chart_data.revenue_by_quarter || []
  const conversionTimeline = report.chart_data.conversions_by_quarter || []
  const spendTimeline = report.chart_data.spend_by_quarter || []
  const regions = (report.chart_data.revenue_by_region || []).slice(0, 8)
  const products = (report.chart_data.top_products || []).slice(0, 6)
  const channels = (report.chart_data.channel_performance || []).slice(0, 8)
  const acquisitionFunnel = (report.chart_data.acquisition_funnel || [
    { name: 'Impressions', value: report.metrics.impressions },
    { name: 'Clicks', value: report.metrics.clicks },
    { name: 'Conversions', value: report.metrics.conversions },
  ]).filter((item) => item.value > 0)
  const funnelBase = acquisitionFunnel[0]?.value || 0
  const funnelPlot = acquisitionFunnel.map((item) => ({
    ...item,
    rate: funnelBase ? item.value / funnelBase * 100 : 0,
  }))
  const marketingPeriods = Array.from(new Set([
    ...spendTimeline.map((item) => item.name),
    ...conversionTimeline.map((item) => item.name),
  ]))
  const marketingTimeline = marketingPeriods.map((name) => ({
    name,
    spend: spendTimeline.find((item) => item.name === name)?.value || 0,
    conversions: conversionTimeline.find((item) => item.name === name)?.value || 0,
  }))
  const hasVisuals = Boolean(revenueTimeline.length || regions.length || products.length || marketingTimeline.length || channels.length || funnelPlot.length)
  const railTimeline = revenueTimeline.length ? revenueTimeline : conversionTimeline
  const railIsRevenue = Boolean(revenueTimeline.length)

  return (
    <div className="report-view">
      <div className="report-back-row">
        <Link to="/reports"><ArrowLeft size={16} /> Report library</Link>
        <span>PRIVATE · VERIFIED</span>
      </div>

      <header className="report-header">
        <div className="report-header__main">
          <span className="report-type-pill"><Sparkles size={14} /> {reportType(report.report_type)}</span>
          <h2>{report.title}</h2>
          <p>{report.summary}</p>
          <div className="report-meta">
            <span><CalendarDays size={16} /> {date(report.created_at)}</span>
            <span><ShieldCheck size={16} /> {report.provider}</span>
            <span><CheckCircle2 size={16} /> Evidence checked</span>
          </div>
        </div>
        <div className="report-actions">
          <button className={report.favorite ? 'secondary-button active' : 'secondary-button'} onClick={toggleFavorite}><Star size={17} fill={report.favorite ? 'currentColor' : 'none'} /> {report.favorite ? 'Favorited' : 'Favorite'}</button>
          <button className="secondary-button" onClick={() => window.print()}><Printer size={17} /> Print</button>
          <a className="primary-button primary-button--small" href={`/api/reports/${report.id}/download?format=markdown`}><Download size={17} /> Export</a>
        </div>
      </header>

      <div className="report-kpi-grid">
        <div><span><WalletCards size={17} /> Revenue</span><strong>{currency(report.metrics.revenue)}</strong></div>
        <div><span><Target size={17} /> Conversions</span><strong>{number(report.metrics.conversions)}</strong></div>
        <div><span><TrendingUp size={17} /> Click-through rate</span><strong>{report.metrics.ctr.toFixed(2)}%</strong></div>
        <div><span><ShieldCheck size={17} /> Cost / conversion</span><strong>{currency(report.metrics.cost_per_conversion, false)}</strong></div>
      </div>

      <div className="report-layout">
        <article className="report-document">
          <div className="document-ruler"><span>INTELLIGENCE BRIEF</span><span>{report.id.slice(0, 8).toUpperCase()}</span></div>
          {hasVisuals && (
            <section className="report-visuals" aria-labelledby="visual-evidence-title">
              <div className="report-visuals__head">
                <div><span className="card-kicker"><Activity size={13} /> LIVE EVIDENCE</span><h3 id="visual-evidence-title">Visual intelligence board</h3></div>
                <p>Plots are rendered from the immutable chart snapshot saved with this report.</p>
              </div>
              <div className="report-plot-grid">
                {revenueTimeline.length > 0 && (
                  <figure className="report-plot-card report-plot-card--wide">
                    <figcaption><span><TrendingUp size={17} /> Revenue trajectory</span><small>Verified revenue by reporting period</small></figcaption>
                    <div className="report-plot report-plot--large">
                      <ResponsiveContainer width="100%" height="100%">
                        <AreaChart data={revenueTimeline} margin={{ top: 16, right: 18, left: 0, bottom: 0 }}>
                          <defs><linearGradient id="reportRevenueFill" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stopColor="#4d8dff" stopOpacity={0.42} /><stop offset="1" stopColor="#4d8dff" stopOpacity={0.02} /></linearGradient></defs>
                          <CartesianGrid vertical={false} stroke="#22304a" strokeDasharray="3 7" />
                          <XAxis dataKey="name" axisLine={false} tickLine={false} tick={{ fill: '#8190a8', fontSize: 11 }} />
                          <YAxis axisLine={false} tickLine={false} tick={{ fill: '#65758f', fontSize: 10 }} tickFormatter={(value) => `$${compact(Number(value))}`} width={54} />
                          <Tooltip contentStyle={tooltipStyle} labelStyle={{ color: '#dbe7f8' }} formatter={(value) => [currency(Number(value)), 'Revenue']} />
                          <Area type="monotone" dataKey="value" name="Revenue" stroke="#62a0ff" strokeWidth={3} fill="url(#reportRevenueFill)" activeDot={{ r: 5, fill: '#f6c945', stroke: '#08101d', strokeWidth: 2 }} />
                        </AreaChart>
                      </ResponsiveContainer>
                    </div>
                  </figure>
                )}

                {regions.length > 0 && (
                  <figure className="report-plot-card">
                    <figcaption><span><BarChart3 size={17} /> Regional contribution</span><small>Top markets ranked by revenue</small></figcaption>
                    <div className="report-plot">
                      <ResponsiveContainer width="100%" height="100%">
                        <BarChart data={regions} layout="vertical" margin={{ top: 8, right: 10, left: 8, bottom: 0 }}>
                          <CartesianGrid horizontal={false} stroke="#22304a" strokeDasharray="3 7" />
                          <XAxis type="number" hide />
                          <YAxis type="category" dataKey="name" axisLine={false} tickLine={false} width={82} tick={{ fill: '#91a0b7', fontSize: 10 }} />
                          <Tooltip contentStyle={tooltipStyle} cursor={{ fill: 'rgba(77,141,255,.07)' }} formatter={(value) => [currency(Number(value)), 'Revenue']} />
                          <Bar dataKey="value" radius={[0, 7, 7, 0]} barSize={15}>{regions.map((item, index) => <Cell key={item.name} fill={chartColors[index % chartColors.length]} />)}</Bar>
                        </BarChart>
                      </ResponsiveContainer>
                    </div>
                  </figure>
                )}

                {products.length > 0 && (
                  <figure className="report-plot-card">
                    <figcaption><span><Target size={17} /> Product mix</span><small>Revenue concentration by leading product</small></figcaption>
                    <div className="report-plot">
                      <ResponsiveContainer width="100%" height="100%">
                        <PieChart>
                          <Tooltip contentStyle={tooltipStyle} formatter={(value) => [currency(Number(value)), 'Revenue']} />
                          <Pie data={products} dataKey="value" nameKey="name" innerRadius="49%" outerRadius="76%" paddingAngle={3} stroke="#0b1322" strokeWidth={3}>
                            {products.map((item, index) => <Cell key={item.name} fill={chartColors[index % chartColors.length]} />)}
                          </Pie>
                          <Legend iconType="circle" iconSize={7} wrapperStyle={{ color: '#8d9bb0', fontSize: 10 }} />
                        </PieChart>
                      </ResponsiveContainer>
                    </div>
                  </figure>
                )}

                {marketingTimeline.length > 0 && (
                  <figure className="report-plot-card report-plot-card--wide">
                    <figcaption><span><Activity size={17} /> Acquisition momentum</span><small>Marketing investment and conversion output by period</small></figcaption>
                    <div className="report-plot report-plot--large">
                      <ResponsiveContainer width="100%" height="100%">
                        <ComposedChart data={marketingTimeline} margin={{ top: 16, right: 6, left: 0, bottom: 0 }}>
                          <CartesianGrid vertical={false} stroke="#22304a" strokeDasharray="3 7" />
                          <XAxis dataKey="name" axisLine={false} tickLine={false} tick={{ fill: '#8190a8', fontSize: 11 }} />
                          <YAxis yAxisId="spend" axisLine={false} tickLine={false} width={54} tick={{ fill: '#65758f', fontSize: 10 }} tickFormatter={(value) => `$${compact(Number(value))}`} />
                          <YAxis yAxisId="conversions" orientation="right" axisLine={false} tickLine={false} width={42} tick={{ fill: '#65758f', fontSize: 10 }} tickFormatter={(value) => compact(Number(value))} />
                          <Tooltip contentStyle={tooltipStyle} formatter={(value, name) => name === 'spend' ? [currency(Number(value)), 'Spend'] : [number(Number(value)), 'Conversions']} />
                          <Legend iconType="circle" iconSize={8} formatter={(value) => value === 'spend' ? 'Marketing spend' : 'Conversions'} wrapperStyle={{ color: '#8d9bb0', fontSize: 10 }} />
                          <Bar yAxisId="spend" dataKey="spend" fill="#4d8dff" radius={[6, 6, 0, 0]} barSize={24} />
                          <Line yAxisId="conversions" type="monotone" dataKey="conversions" stroke="#f6c945" strokeWidth={3} dot={{ r: 3, fill: '#f6c945' }} />
                        </ComposedChart>
                      </ResponsiveContainer>
                    </div>
                  </figure>
                )}

                {channels.length > 0 && (
                  <figure className="report-plot-card">
                    <figcaption><span><BarChart3 size={17} /> Channel efficiency</span><small>Conversion output versus acquisition cost</small></figcaption>
                    <div className="report-plot">
                      <ResponsiveContainer width="100%" height="100%">
                        <ComposedChart data={channels} margin={{ top: 12, right: 4, left: -8, bottom: 14 }}>
                          <CartesianGrid vertical={false} stroke="#22304a" strokeDasharray="3 7" />
                          <XAxis dataKey="name" axisLine={false} tickLine={false} interval={0} angle={-18} textAnchor="end" height={48} tick={{ fill: '#8190a8', fontSize: 9 }} />
                          <YAxis yAxisId="conversions" axisLine={false} tickLine={false} tick={{ fill: '#65758f', fontSize: 9 }} tickFormatter={(value) => compact(Number(value))} />
                          <YAxis yAxisId="cpa" orientation="right" axisLine={false} tickLine={false} tick={{ fill: '#65758f', fontSize: 9 }} tickFormatter={(value) => `$${compact(Number(value))}`} />
                          <Tooltip contentStyle={tooltipStyle} formatter={(value, name) => name === 'cpa' ? [currency(Number(value), false), 'CPA'] : [number(Number(value)), 'Conversions']} />
                          <Bar yAxisId="conversions" dataKey="conversions" fill="#56d6a7" radius={[5, 5, 0, 0]} barSize={18} />
                          <Line yAxisId="cpa" type="monotone" dataKey="cpa" stroke="#ff806e" strokeWidth={2.5} dot={{ r: 3, fill: '#ff806e' }} />
                        </ComposedChart>
                      </ResponsiveContainer>
                    </div>
                  </figure>
                )}

                {funnelPlot.length > 0 && (
                  <figure className="report-plot-card">
                    <figcaption><span><Eye size={17} /> Acquisition funnel</span><small>Stage retention indexed to total reach</small></figcaption>
                    <div className="report-plot">
                      <ResponsiveContainer width="100%" height="100%">
                        <BarChart data={funnelPlot} layout="vertical" margin={{ top: 12, right: 16, left: 10, bottom: 0 }}>
                          <CartesianGrid horizontal={false} stroke="#22304a" strokeDasharray="3 7" />
                          <XAxis type="number" domain={[0, 100]} axisLine={false} tickLine={false} tick={{ fill: '#65758f', fontSize: 9 }} tickFormatter={(value) => `${value}%`} />
                          <YAxis type="category" dataKey="name" axisLine={false} tickLine={false} width={76} tick={{ fill: '#91a0b7', fontSize: 10 }} />
                          <Tooltip contentStyle={tooltipStyle} formatter={(value) => [`${Number(value).toFixed(2)}%`, 'Share of reach']} />
                          <Bar dataKey="rate" radius={[0, 8, 8, 0]} barSize={19}>{funnelPlot.map((item, index) => <Cell key={item.name} fill={chartColors[index % chartColors.length]} />)}</Bar>
                        </BarChart>
                      </ResponsiveContainer>
                    </div>
                    <p className="report-plot-note">{acquisitionFunnel.map((item) => `${item.name}: ${number(item.value)}`).join(' · ')}</p>
                  </figure>
                )}
              </div>
              <div className="report-visuals__seal"><ShieldCheck size={15} /> Same filters, calculations, and source rows as the written analysis</div>
            </section>
          )}
          <div className="markdown-body">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{report.content}</ReactMarkdown>
          </div>
          <footer className="document-footer"><ShieldCheck size={18} /><span>Generated from verified source records inside your private workspace.</span></footer>
        </article>

        <aside className="report-rail">
          {railTimeline.length > 0 && (
            <section className="report-chart-card">
              <span className="card-kicker">{railIsRevenue ? 'REVENUE TIMELINE' : 'CONVERSION TIMELINE'}</span>
              <h3>Quarterly signal</h3>
              <div className="report-mini-chart">
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart data={railTimeline} margin={{ top: 12, right: 4, left: -24, bottom: 0 }}>
                    <defs><linearGradient id="detailFill" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stopColor="#f6c945" stopOpacity={0.35} /><stop offset="1" stopColor="#f6c945" stopOpacity={0} /></linearGradient></defs>
                    <CartesianGrid vertical={false} stroke="#1b263d" strokeDasharray="3 6" />
                    <XAxis dataKey="name" axisLine={false} tickLine={false} tick={{ fill: '#6f7e98', fontSize: 10 }} />
                    <YAxis hide />
                    <Tooltip contentStyle={tooltipStyle} formatter={(value) => railIsRevenue ? currency(Number(value), false) : number(Number(value))} />
                    <Area type="monotone" dataKey="value" stroke="#f6c945" strokeWidth={2.5} fill="url(#detailFill)" />
                  </AreaChart>
                </ResponsiveContainer>
              </div>
            </section>
          )}

          <section className="report-insight-card">
            <span className="card-kicker">KEY SIGNALS</span>
            {report.insights.map((item, index) => <div key={`${index}-${item}`}><span>{String(index + 1).padStart(2, '0')}</span><p>{item}</p></div>)}
          </section>

          <section className="report-scope-card">
            <span className="card-kicker">ANALYSIS SCOPE</span>
            {Object.entries(report.report_filters).length
              ? Object.entries(report.report_filters).map(([key, value]) => <div key={key}><span>{key}</span><strong>{value}</strong></div>)
              : <div><span>Dataset</span><strong>Complete scope</strong></div>}
          </section>

          <section className="delivery-card">
            <Send size={22} />
            <div><h3>Send to stakeholders</h3><p>Deliver this report by email or Telegram.</p></div>
            <button className="secondary-button" onClick={() => setDeliveryOpen(true)}>Open delivery</button>
          </section>

          <a className="json-export" href={`/api/reports/${report.id}/download?format=json`}><FileJson size={17} /> Download structured JSON</a>
        </aside>
      </div>

      {deliveryOpen && (
        <div className="modal-layer" role="presentation" onMouseDown={() => setDeliveryOpen(false)}>
          <form className="delivery-dialog" role="dialog" aria-modal="true" onSubmit={deliver} onMouseDown={(event) => event.stopPropagation()}>
            <div className="dialog-head"><div><span>REPORT DELIVERY</span><h3>Send intelligence</h3></div><button type="button" onClick={() => setDeliveryOpen(false)}><X size={19} /></button></div>
            <div className="delivery-tabs">
              <button type="button" className={channel === 'email' ? 'active' : ''} onClick={() => { setChannel('email'); setDestination('') }}><Mail size={18} /> Email</button>
              <button type="button" className={channel === 'telegram' ? 'active' : ''} onClick={() => { setChannel('telegram'); setDestination('') }}><MessageCircle size={18} /> Telegram</button>
            </div>
            <label className="studio-field">
              <span>{channel === 'email' ? 'Recipient email' : 'Telegram chat ID'}</span>
              <input type={channel === 'email' ? 'email' : 'text'} value={destination} onChange={(event) => setDestination(event.target.value)} placeholder={channel === 'email' ? 'stakeholder@company.com' : '123456789'} required />
            </label>
            <div className="integration-state">
              <i className={(channel === 'email' ? system?.email_delivery : system?.telegram_delivery) ? 'ready' : ''} />
              {(channel === 'email' ? system?.email_delivery : system?.telegram_delivery) ? 'Integration configured' : 'Add credentials in Render before delivery'}
            </div>
            <button className="primary-button dialog-submit" disabled={sending}>{sending ? 'Sending...' : <><Send size={17} /> Send report</>}</button>
          </form>
        </div>
      )}
    </div>
  )
}
