import {
  ArrowRight,
  BarChart3,
  Bot,
  BrainCircuit,
  CalendarRange,
  Check,
  CircleCheck,
  FileBarChart,
  Globe2,
  Layers3,
  LoaderCircle,
  PackageSearch,
  Send,
  ShieldCheck,
  Sparkles,
  Target,
  WandSparkles,
} from 'lucide-react'
import type { LucideIcon } from 'lucide-react'
import { FormEvent, useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { FilterBar } from '../components/FilterBar'
import { useDatasets } from '../context/DatasetContext'
import { api, queryString } from '../lib/api'
import type { FilterOptions, Filters, ReportDetail, SystemStatus } from '../types'

type ReportChoice = {
  id: string
  name: string
  description: string
  icon: LucideIcon
  fields: Array<keyof Filters>
}

const reportChoices: ReportChoice[] = [
  { id: 'executive_summary', name: 'Executive brief', description: 'A complete decision-ready view of revenue and marketing.', icon: BrainCircuit, fields: ['quarter', 'region'] },
  { id: 'sales_performance', name: 'Sales performance', description: 'Revenue, unit velocity, products, and regional movement.', icon: BarChart3, fields: ['region', 'quarter', 'product'] },
  { id: 'marketing_campaign', name: 'Campaign intelligence', description: 'Spend efficiency, conversion quality, and channel signals.', icon: Target, fields: ['channel', 'quarter', 'product'] },
  { id: 'quarterly_summary', name: 'Quarterly pulse', description: 'Period movement, momentum, efficiency, and priorities.', icon: CalendarRange, fields: ['quarter', 'region', 'channel'] },
  { id: 'product_analysis', name: 'Product analysis', description: 'Deep dive into one product and its campaign footprint.', icon: PackageSearch, fields: ['product', 'quarter', 'region'] },
  { id: 'regional_analysis', name: 'Regional analysis', description: 'Market performance, product mix, and growth opportunity.', icon: Globe2, fields: ['region', 'quarter'] },
  { id: 'custom', name: 'Ask the data', description: 'Start from a business question and build a tailored report.', icon: WandSparkles, fields: ['region', 'quarter', 'product', 'channel'] },
]

const autogenStages = [
  { name: 'Data Analyst', detail: 'Investigating the verified evidence snapshot' },
  { name: 'Report Writer', detail: 'Building a decision-ready executive narrative' },
  { name: 'Independent Critic', detail: 'Auditing numbers, claims, and recommendations' },
]

const localStages = [
  { name: 'Evidence engine', detail: 'Calculating verified KPIs and chart series' },
  { name: 'Report composer', detail: 'Building the executive decision brief' },
  { name: 'Verification pass', detail: 'Checking scope, claims, and recommendations' },
]

const emptyOptions: FilterOptions = { regions: [], quarters: [], products: [], channels: [] }

export function StudioPage() {
  const { activeId, activeDataset } = useDatasets()
  const navigate = useNavigate()
  const [type, setType] = useState('executive_summary')
  const [options, setOptions] = useState<FilterOptions>(emptyOptions)
  const [filters, setFilters] = useState<Filters>({})
  const [focus, setFocus] = useState('')
  const [question, setQuestion] = useState('')
  const [generating, setGenerating] = useState(false)
  const [stage, setStage] = useState(0)
  const [error, setError] = useState('')
  const [system, setSystem] = useState<SystemStatus | null>(null)
  const pipelineStages = system?.autogen_enabled ? autogenStages : localStages

  useEffect(() => {
    Promise.all([
      api<FilterOptions>(`/meta/options${queryString({ dataset_id: activeId })}`),
      api<SystemStatus>('/system/status'),
    ]).then(([optionData, systemData]) => {
      setOptions(optionData)
      setSystem(systemData)
    }).catch((reason) => setError(reason.message))
  }, [activeId])

  useEffect(() => {
    if (!generating) {
      setStage(0)
      return
    }
    const timer = window.setInterval(() => {
      setStage((current) => Math.min(current + 1, pipelineStages.length - 1))
    }, 1300)
    return () => window.clearInterval(timer)
  }, [generating, pipelineStages.length])

  const selected = useMemo(
    () => reportChoices.find((choice) => choice.id === type) || reportChoices[0],
    [type],
  )

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    if (type === 'custom' && !question.trim()) {
      setError('Write a business question before generating a custom report.')
      return
    }
    setError('')
    setGenerating(true)
    try {
      const report = await api<ReportDetail>('/reports/generate', {
        method: 'POST',
        body: JSON.stringify({ report_type: type, dataset_id: activeId || null, filters, focus, question }),
      })
      navigate(`/reports/${report.id}`, { state: { created: true } })
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Report generation failed')
      setGenerating(false)
    }
  }

  return (
    <div className="studio-layout">
      <form className="studio-main" onSubmit={submit}>
        <section className="studio-intro">
          <div>
            <span className="eyebrow-pill"><Sparkles size={15} /> NEW ANALYSIS RUN</span>
            <h2>What should the agents investigate?</h2>
            <p>Choose a report mode, focus the dataset, and define the decision you need to make.</p>
          </div>
          <div className="run-id"><span>RUN</span><strong>{new Date().toISOString().slice(2, 10).replaceAll('-', '')}</strong></div>
        </section>

        <section className="studio-section">
          <div className="step-heading"><span>01</span><div><h3>Choose the intelligence mode</h3><p>Each mode changes how the agents inspect and frame your data.</p></div></div>
          <div className="report-type-grid">
            {reportChoices.map(({ id, name, description, icon: Icon }) => (
              <button type="button" className={type === id ? 'report-type-card active' : 'report-type-card'} onClick={() => setType(id)} key={id}>
                <span className="report-type-icon"><Icon size={21} /></span>
                <span><strong>{name}</strong><small>{description}</small></span>
                <i>{type === id && <Check size={13} />}</i>
              </button>
            ))}
          </div>
        </section>

        <section className="studio-section">
          <div className="step-heading"><span>02</span><div><h3>Set the data scope</h3><p>Leave filters open to analyze the complete dataset.</p></div></div>
          <FilterBar options={options} filters={filters} onChange={setFilters} fields={selected.fields} />
        </section>

        <section className="studio-section">
          <div className="step-heading"><span>03</span><div><h3>Direct the analysis</h3><p>Give the agents context about the outcome you care about.</p></div></div>
          {type === 'custom' && (
            <label className="studio-field">
              <span>Business question <b>Required</b></span>
              <textarea value={question} onChange={(event) => setQuestion(event.target.value)} placeholder="Which product and region combination has the strongest revenue potential without increasing acquisition cost?" rows={4} />
              <small>{question.length}/1000</small>
            </label>
          )}
          <label className="studio-field">
            <span>Analysis focus <em>Optional</em></span>
            <textarea value={focus} onChange={(event) => setFocus(event.target.value)} placeholder="Example: Emphasize risks, budget efficiency, and actions for the next quarter." rows={type === 'custom' ? 3 : 4} />
            <small>{focus.length}/800</small>
          </label>
          {type === 'custom' && (
            <div className="prompt-suggestions">
              <span>Try:</span>
              {['Find the strongest growth signal', 'Compare channels by efficiency', 'Identify revenue concentration risk'].map((prompt) => (
                <button type="button" key={prompt} onClick={() => setQuestion(prompt)}>{prompt}</button>
              ))}
            </div>
          )}
        </section>

        {error && <div className="error-banner">{error}</div>}

        <div className="studio-submit-row">
          <div><ShieldCheck size={18} /><span>All generated metrics are checked against the source dataset.</span></div>
          <button className="primary-button studio-submit" disabled={generating}>
            {generating ? <><LoaderCircle className="spin" size={19} /> {system?.autogen_enabled ? 'Agents are working' : 'Engine is working'}</> : <><Sparkles size={18} /> Generate report <ArrowRight size={17} /></>}
          </button>
        </div>
      </form>

      <aside className="studio-rail">
        <section className="agent-console">
          <div className="agent-console__top">
            <div><span className="status-line"><i /> {system?.autogen_enabled ? 'AUTOGEN PIPELINE' : 'VERIFIED PIPELINE'}</span><h3>{generating ? 'Analysis in progress' : 'Ready to deploy'}</h3></div>
            <Bot size={25} />
          </div>
          <div className="agent-stages">
            {pipelineStages.map((item, index) => {
              const complete = generating ? index < stage : false
              const active = generating ? index === stage : index === 0
              return (
                <div className={`${active ? 'active' : ''} ${complete ? 'complete' : ''}`} key={item.name}>
                  <span>{complete ? <Check size={15} /> : active && generating ? <LoaderCircle className="spin" size={15} /> : index + 1}</span>
                  <div><strong>{item.name}</strong><small>{item.detail}</small></div>
                  {complete && <b>DONE</b>}
                </div>
              )
            })}
          </div>
        </section>

        <section className="scope-card">
          <span className="card-kicker">CURRENT CONFIGURATION</span>
          <div><span><FileBarChart size={17} /> Report</span><strong>{selected.name}</strong></div>
          <div><span><Layers3 size={17} /> Source</span><strong>{activeDataset?.name || 'Bundled demo data'}</strong></div>
          <div><span><Target size={17} /> Scope</span><strong>{Object.values(filters).filter(Boolean).length ? `${Object.values(filters).filter(Boolean).length} active filters` : 'Complete dataset'}</strong></div>
          <div><span><BrainCircuit size={17} /> Engine</span><strong>{system?.ai_mode || 'Checking...'}</strong></div>
          <div><span><ShieldCheck size={17} /> Guardrail</span><strong>Evidence locked</strong></div>
        </section>

        <section className="quality-card">
          <div className="quality-score"><CircleCheck size={31} /><span><strong>Verified</strong><small>Dataset grounding</small></span></div>
          <p>{system?.autogen_enabled
            ? 'Microsoft AutoGen coordinates an analyst, writer, and independent critic before the report enters your library.'
            : 'The verified engine keeps every metric grounded locally; add a GROQ key to activate the AutoGen review pipeline.'}</p>
          <div className="quality-tags"><span>GROUNDED</span><span>{system?.autogen_enabled ? 'AUTOGEN ACTIVE' : 'FALLBACK READY'}</span><span>PRIVATE</span></div>
        </section>
      </aside>

      {generating && (
        <div className="generation-overlay" role="status" aria-live="polite">
          <div className="generation-orb"><Sparkles size={29} /></div>
          <span>BUILDING VERIFIED INTELLIGENCE</span>
          <h3>{pipelineStages[stage].name}</h3>
          <p>{pipelineStages[stage].detail}</p>
          <div className="generation-progress"><span style={{ width: `${(stage + 1) / pipelineStages.length * 100}%` }} /></div>
          <small>Keep this tab open while the intelligence pipeline completes the report.</small>
        </div>
      )}
    </div>
  )
}
