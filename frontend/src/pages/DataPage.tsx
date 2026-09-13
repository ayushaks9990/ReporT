import {
  ArrowRight,
  Braces,
  Check,
  CircleAlert,
  CloudUpload,
  Database,
  FileJson,
  FileSpreadsheet,
  Gauge,
  GitMerge,
  LoaderCircle,
  Rows3,
  ShieldCheck,
  Sparkles,
  Trash2,
  Upload,
  WandSparkles,
  X,
} from 'lucide-react'
import { ChangeEvent, DragEvent, FormEvent, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useDatasets } from '../context/DatasetContext'
import { useToast } from '../context/ToastContext'
import { api } from '../lib/api'
import { date } from '../lib/format'
import type { DatasetDetail, DatasetItem } from '../types'

const salesFields = [
  ['revenue', 'Revenue', true],
  ['units_sold', 'Units sold', false],
  ['product', 'Product', false],
  ['region', 'Region', false],
  ['quarter', 'Time period / quarter', false],
  ['category', 'Category', false],
  ['customer_segment', 'Customer segment', false],
] as const

const marketingFields = [
  ['budget', 'Budget / spend', false],
  ['impressions', 'Impressions', false],
  ['clicks', 'Clicks', false],
  ['conversions', 'Conversions', false],
  ['channel', 'Channel', false],
  ['campaign_name', 'Campaign name', false],
  ['quarter', 'Time period / quarter', false],
  ['target_segment', 'Target segment', false],
] as const

export function DataPage() {
  const navigate = useNavigate()
  const inputRef = useRef<HTMLInputElement>(null)
  const { datasets, activeId, setActiveId, refreshDatasets } = useDatasets()
  const { showToast } = useToast()
  const [file, setFile] = useState<File | null>(null)
  const [name, setName] = useState('')
  const [kind, setKind] = useState('auto')
  const [dragging, setDragging] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [editor, setEditor] = useState<DatasetDetail | null>(null)
  const [mapping, setMapping] = useState<Record<string, string>>({})
  const [mappingKind, setMappingKind] = useState<'sales' | 'marketing'>('sales')
  const [savingMapping, setSavingMapping] = useState(false)
  const [deleteTarget, setDeleteTarget] = useState<DatasetItem | null>(null)
  const [deleting, setDeleting] = useState(false)
  const [error, setError] = useState('')

  const chooseFile = (value: File | null) => {
    if (!value) return
    const suffix = value.name.toLowerCase()
    if (!suffix.endsWith('.csv') && !suffix.endsWith('.json')) {
      setError('Choose a CSV or JSON file.')
      return
    }
    if (value.size > 5 * 1024 * 1024) {
      setError('Choose a file smaller than 5 MB.')
      return
    }
    setFile(value)
    setName(value.name.replace(/\.(csv|json)$/i, '').replaceAll(/[_-]/g, ' '))
    setError('')
  }

  const onFileChange = (event: ChangeEvent<HTMLInputElement>) => chooseFile(event.target.files?.[0] || null)
  const onDrop = (event: DragEvent) => {
    event.preventDefault()
    setDragging(false)
    chooseFile(event.dataTransfer.files?.[0] || null)
  }

  const openEditor = async (dataset: DatasetItem) => {
    try {
      const detail = await api<DatasetDetail>(`/datasets/${dataset.id}`)
      setEditor(detail)
      setMapping(detail.mapping)
      setMappingKind(detail.kind)
    } catch (reason) {
      showToast(reason instanceof Error ? reason.message : 'Could not open dataset', 'error')
    }
  }

  const upload = async (event: FormEvent) => {
    event.preventDefault()
    if (!file) {
      setError('Choose a CSV or JSON file first.')
      return
    }
    setUploading(true)
    setError('')
    const body = new FormData()
    body.append('file', file)
    body.append('name', name)
    body.append('kind', kind)
    try {
      const result = await api<DatasetDetail>('/datasets/upload', { method: 'POST', body })
      await refreshDatasets()
      setEditor(result)
      setMapping(result.mapping)
      setMappingKind(result.kind)
      setFile(null)
      setName('')
      if (inputRef.current) inputRef.current.value = ''
      showToast(result.status === 'ready' ? 'Dataset validated and ready' : 'Dataset uploaded — finish field mapping')
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Upload failed')
    } finally {
      setUploading(false)
    }
  }

  const saveMapping = async (): Promise<DatasetDetail | null> => {
    if (!editor) return null
    setSavingMapping(true)
    try {
      const updated = await api<DatasetDetail>(`/datasets/${editor.id}/mapping`, {
        method: 'PATCH',
        body: JSON.stringify({ kind: mappingKind, mapping }),
      })
      setEditor(updated)
      await refreshDatasets()
      showToast('Field mapping saved')
      return updated
    } catch (reason) {
      showToast(reason instanceof Error ? reason.message : 'Mapping could not be saved', 'error')
      return null
    } finally {
      setSavingMapping(false)
    }
  }

  const analyze = (dataset: DatasetItem | DatasetDetail) => {
    if (dataset.status !== 'ready') {
      showToast('Finish mapping before analyzing this dataset', 'error')
      return
    }
    setActiveId(dataset.id)
    setEditor(null)
    navigate('/')
  }

  const remove = async () => {
    if (!deleteTarget) return
    setDeleting(true)
    try {
      await api<void>(`/datasets/${deleteTarget.id}`, { method: 'DELETE' })
      if (activeId === deleteTarget.id) setActiveId('')
      setDeleteTarget(null)
      await refreshDatasets()
      showToast('Dataset deleted')
    } catch (reason) {
      showToast(reason instanceof Error ? reason.message : 'Could not delete dataset', 'error')
    } finally {
      setDeleting(false)
    }
  }

  const fields = mappingKind === 'sales' ? salesFields : marketingFields

  return (
    <div className="page-stack data-page">
      <section className="data-hero">
        <div className="data-hero__content">
          <span className="eyebrow-pill"><CloudUpload size={15} /> BRING YOUR OWN DATA</span>
          <h2>Upload it. Map it. <em>Decode it.</em></h2>
          <p>Turn any clean sales or marketing CSV/JSON file into the same high-quality dashboards, graphs, and multi-agent reports.</p>
          <div className="data-trust"><span><ShieldCheck size={15} /> Private to your account</span><span><Gauge size={15} /> Automatic type detection</span><span><GitMerge size={15} /> Smart field mapping</span></div>
        </div>
        <div className="data-hero__visual" aria-hidden="true"><span /><span /><span /></div>
      </section>

      <div className="data-workspace">
        <form className="upload-panel" onSubmit={upload}>
          <div className="step-heading"><span>01</span><div><h3>Upload a source file</h3><p>Up to 10,000 rows and 5 MB per dataset.</p></div></div>
          <button
            type="button"
            className={`dropzone ${dragging ? 'dragging' : ''} ${file ? 'has-file' : ''}`}
            onClick={() => inputRef.current?.click()}
            onDragEnter={() => setDragging(true)}
            onDragLeave={() => setDragging(false)}
            onDragOver={(event) => event.preventDefault()}
            onDrop={onDrop}
          >
            <input ref={inputRef} type="file" accept=".csv,.json,text/csv,application/json" onChange={onFileChange} />
            {file ? (
              <>
                <span className="dropzone-icon success">{file.name.toLowerCase().endsWith('.csv') ? <FileSpreadsheet size={26} /> : <FileJson size={26} />}</span>
                <strong>{file.name}</strong>
                <small>{(file.size / 1024).toFixed(1)} KB · Ready to upload</small>
                <b><Check size={14} /> VALID FILE</b>
              </>
            ) : (
              <>
                <span className="dropzone-icon"><Upload size={26} /></span>
                <strong>Drop your CSV or JSON here</strong>
                <small>or click to choose a file from your computer</small>
                <b>CSV · JSON</b>
              </>
            )}
          </button>

          <div className="upload-fields">
            <label className="studio-field"><span>Dataset name</span><input value={name} onChange={(event) => setName(event.target.value)} placeholder="Q4 revenue export" maxLength={120} /></label>
            <label className="studio-field"><span>Data type</span><select value={kind} onChange={(event) => setKind(event.target.value)}><option value="auto">Auto-detect</option><option value="sales">Sales data</option><option value="marketing">Marketing data</option></select></label>
          </div>
          {error && <div className="error-banner">{error}</div>}
          <button className="primary-button upload-submit" disabled={uploading || !file}>{uploading ? <><LoaderCircle className="spin" size={18} /> Validating data</> : <><WandSparkles size={18} /> Upload and map</>}</button>
          <div className="template-links"><span>Need a starting format?</span><a href="/api/dataset-templates/sales">Sales template</a><a href="/api/dataset-templates/marketing">Marketing template</a></div>
        </form>

        <section className="data-guide-panel">
          <span className="card-kicker">WHAT HAPPENS NEXT</span>
          <div className="data-guide-step"><span><Braces size={18} /></span><div><strong>Schema scan</strong><p>Headers, types, missing values, and numeric fields are inspected.</p></div><b>01</b></div>
          <div className="data-guide-step"><span><GitMerge size={18} /></span><div><strong>Smart mapping</strong><p>Your columns are matched to business metrics and dimensions.</p></div><b>02</b></div>
          <div className="data-guide-step"><span><Sparkles size={18} /></span><div><strong>Instant intelligence</strong><p>Fresh KPIs, premium graphs, and agent reports become available.</p></div><b>03</b></div>
          <div className="data-safety-note"><ShieldCheck size={19} /><p><strong>Account-level isolation</strong>Your uploads and mappings are only accessible through your authenticated session.</p></div>
        </section>
      </div>

      <section className="dataset-section">
        <div className="section-header"><div><span>DATA SOURCES</span><h2>Your analysis workspace</h2></div><span className="panel-badge"><Database size={15} /> {datasets.length + 1} sources</span></div>
        <div className="dataset-grid">
          <article className={`dataset-card bundled ${activeId === '' ? 'active' : ''}`}>
            <div className="dataset-card__top"><span className="dataset-icon"><Database size={20} /></span><span className="ready-pill"><i /> READY</span></div>
            <h3>Bundled demo data</h3>
            <p>1,000 sales + 1,000 marketing records</p>
            <div className="dataset-stats"><span><Rows3 size={14} /> 2,000 rows</span><span>COMBINED</span></div>
            <button className={activeId === '' ? 'secondary-button active' : 'secondary-button'} onClick={() => { setActiveId(''); navigate('/') }}>{activeId === '' ? <><Check size={16} /> Active source</> : <>Use dataset <ArrowRight size={15} /></>}</button>
          </article>
          {datasets.map((dataset) => (
            <article className={`dataset-card ${activeId === dataset.id ? 'active' : ''}`} key={dataset.id}>
              <div className="dataset-card__top">
                <span className="dataset-icon">{dataset.original_filename.toLowerCase().endsWith('.csv') ? <FileSpreadsheet size={20} /> : <FileJson size={20} />}</span>
                <span className={dataset.status === 'ready' ? 'ready-pill' : 'ready-pill warning'}><i /> {dataset.status === 'ready' ? 'READY' : 'MAP FIELDS'}</span>
              </div>
              <h3>{dataset.name}</h3>
              <p>{dataset.original_filename}</p>
              <div className="dataset-stats"><span><Rows3 size={14} /> {dataset.row_count.toLocaleString()} rows</span><span>{dataset.kind.toUpperCase()}</span></div>
              <div className="dataset-card__actions">
                <button className="secondary-button" onClick={() => openEditor(dataset)}>{dataset.status === 'ready' ? 'Review mapping' : 'Map columns'}</button>
                {dataset.status === 'ready' && <button className={activeId === dataset.id ? 'dataset-use active' : 'dataset-use'} onClick={() => analyze(dataset)}>{activeId === dataset.id ? <Check size={16} /> : <ArrowRight size={16} />}</button>}
                <button className="dataset-delete" onClick={() => setDeleteTarget(dataset)} aria-label={`Delete ${dataset.name}`}><Trash2 size={16} /></button>
              </div>
              <small>Added {date(dataset.created_at)}</small>
            </article>
          ))}
        </div>
      </section>

      {editor && (
        <div className="mapping-layer">
          <section className="mapping-drawer" role="dialog" aria-modal="true" aria-labelledby="mapping-title">
            <header><div><span>DATASET MAPPING</span><h2 id="mapping-title">{editor.name}</h2><p>{editor.row_count.toLocaleString()} rows · {editor.columns.length} columns detected</p></div><button onClick={() => setEditor(null)} aria-label="Close mapping"><X size={20} /></button></header>
            <div className="mapping-body">
              <div className="mapping-type">
                <span>Analyze this file as</span>
                <div><button className={mappingKind === 'sales' ? 'active' : ''} onClick={() => { setMappingKind('sales'); setMapping({}) }}><FileSpreadsheet size={17} /> Sales</button><button className={mappingKind === 'marketing' ? 'active' : ''} onClick={() => { setMappingKind('marketing'); setMapping({}) }}><Gauge size={17} /> Marketing</button></div>
              </div>
              <div className="mapping-title-row"><div><h3>Match your columns</h3><p>AI Analytic Platform suggested the mappings it recognized. Review them before analysis.</p></div><span>{Object.values(mapping).filter(Boolean).length} mapped</span></div>
              <div className="mapping-grid">
                {fields.map(([target, label, required]) => (
                  <label key={target}>
                    <span>{label}{required && <b>Required</b>}</span>
                    <select value={mapping[target] || ''} onChange={(event) => setMapping((current) => ({ ...current, [target]: event.target.value }))}>
                      <option value="">Not mapped</option>
                      {editor.columns.map((column) => <option value={column} key={column}>{column} · {editor.column_types[column]}</option>)}
                    </select>
                  </label>
                ))}
              </div>
              {mappingKind === 'marketing' && <div className="mapping-hint"><CircleAlert size={16} /> Map at least one metric: budget, impressions, clicks, or conversions.</div>}

              <div className="preview-head"><div><h3>Data preview</h3><p>First {editor.preview.length} rows after safe parsing</p></div><span><ShieldCheck size={15} /> UTF-8 validated</span></div>
              <div className="data-preview"><table><thead><tr>{editor.columns.slice(0, 8).map((column) => <th key={column}>{column}</th>)}</tr></thead><tbody>{editor.preview.map((row, index) => <tr key={index}>{editor.columns.slice(0, 8).map((column) => <td key={column}>{String(row[column] ?? '—')}</td>)}</tr>)}</tbody></table></div>
            </div>
            <footer><button className="secondary-button" onClick={() => setEditor(null)}>Close</button><button className="secondary-button" disabled={savingMapping} onClick={saveMapping}>{savingMapping ? 'Saving...' : 'Save mapping'}</button><button className="primary-button primary-button--small" disabled={savingMapping || (mappingKind === 'sales' ? !mapping.revenue : !['budget', 'impressions', 'clicks', 'conversions'].some((key) => mapping[key]))} onClick={async () => { const updated = await saveMapping(); if (updated) analyze(updated) }}><Sparkles size={16} /> Save & analyze</button></footer>
          </section>
        </div>
      )}

      {deleteTarget && (
        <div className="modal-layer" role="presentation" onMouseDown={() => setDeleteTarget(null)}><section className="confirm-dialog" role="dialog" aria-modal="true" onMouseDown={(event) => event.stopPropagation()}><span className="danger-icon"><Trash2 size={22} /></span><h3>Delete this dataset?</h3><p><strong>{deleteTarget.name}</strong> and its uploaded rows will be removed. Existing generated reports remain available.</p><div><button className="secondary-button" onClick={() => setDeleteTarget(null)}>Keep dataset</button><button className="danger-button" disabled={deleting} onClick={remove}>{deleting ? 'Deleting...' : 'Delete dataset'}</button></div></section></div>
      )}
    </div>
  )
}
