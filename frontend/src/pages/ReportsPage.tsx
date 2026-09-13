import {
  ArrowRight,
  CalendarDays,
  FileBarChart,
  Filter,
  Plus,
  Search,
  Sparkles,
  Star,
  Trash2,
  X,
} from 'lucide-react'
import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { EmptyState } from '../components/EmptyState'
import { LoadingScreen } from '../components/LoadingScreen'
import { useToast } from '../context/ToastContext'
import { api, queryString } from '../lib/api'
import { date, reportType } from '../lib/format'
import type { ReportListItem } from '../types'

const types = [
  ['', 'All report types'],
  ['executive_summary', 'Executive briefs'],
  ['sales_performance', 'Sales performance'],
  ['marketing_campaign', 'Campaign intelligence'],
  ['product_analysis', 'Product analysis'],
  ['regional_analysis', 'Regional analysis'],
  ['custom', 'Custom reports'],
]

export function ReportsPage() {
  const { showToast } = useToast()
  const [reports, setReports] = useState<ReportListItem[]>([])
  const [search, setSearch] = useState('')
  const [type, setType] = useState('')
  const [favorites, setFavorites] = useState(false)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [deleteTarget, setDeleteTarget] = useState<ReportListItem | null>(null)
  const [deleting, setDeleting] = useState(false)

  const loadReports = () => {
    setLoading(true)
    setError('')
    api<ReportListItem[]>(`/reports${queryString({
      search,
      report_type: type,
      favorite: favorites ? true : undefined,
    })}`)
      .then(setReports)
      .catch((reason) => setError(reason.message))
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    const timer = window.setTimeout(loadReports, 260)
    return () => window.clearTimeout(timer)
  }, [search, type, favorites])

  const toggleFavorite = async (report: ReportListItem) => {
    try {
      await api(`/reports/${report.id}/favorite`, {
        method: 'PATCH',
        body: JSON.stringify({ favorite: !report.favorite }),
      })
      if (favorites && report.favorite) {
        setReports((current) => current.filter((item) => item.id !== report.id))
      } else {
        setReports((current) => current.map((item) => item.id === report.id ? { ...item, favorite: !item.favorite } : item))
      }
      showToast(report.favorite ? 'Removed from favorites' : 'Saved to favorites')
    } catch (reason) {
      showToast(reason instanceof Error ? reason.message : 'Could not update report', 'error')
    }
  }

  const remove = async () => {
    if (!deleteTarget) return
    setDeleting(true)
    try {
      await api<void>(`/reports/${deleteTarget.id}`, { method: 'DELETE' })
      setReports((current) => current.filter((item) => item.id !== deleteTarget.id))
      setDeleteTarget(null)
      showToast('Report deleted')
    } catch (reason) {
      showToast(reason instanceof Error ? reason.message : 'Could not delete report', 'error')
    } finally {
      setDeleting(false)
    }
  }

  return (
    <div className="page-stack reports-page">
      <section className="reports-hero">
        <div>
          <span className="eyebrow-pill"><FileBarChart size={15} /> PRIVATE REPORT LIBRARY</span>
          <h2>Every signal. Ready when you need it.</h2>
          <p>Search, revisit, export, and deliver every verified intelligence run.</p>
        </div>
        <Link className="primary-button" to="/studio"><Plus size={18} /> Create report</Link>
      </section>

      <section className="library-toolbar">
        <label className="library-search">
          <Search size={18} />
          <input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search reports by title or metric..." />
          {search && <button onClick={() => setSearch('')} aria-label="Clear search"><X size={16} /></button>}
        </label>
        <label className="library-type">
          <Filter size={17} />
          <select value={type} onChange={(event) => setType(event.target.value)}>
            {types.map(([value, label]) => <option value={value} key={value}>{label}</option>)}
          </select>
        </label>
        <button className={favorites ? 'favorite-filter active' : 'favorite-filter'} onClick={() => setFavorites((value) => !value)}>
          <Star size={17} fill={favorites ? 'currentColor' : 'none'} /> Favorites
        </button>
      </section>

      <div className="library-summary">
        <span>{loading ? 'Scanning library...' : `${reports.length} ${reports.length === 1 ? 'report' : 'reports'} found`}</span>
        {(search || type || favorites) && <button onClick={() => { setSearch(''); setType(''); setFavorites(false) }}>Clear filters</button>}
      </div>

      {error && <div className="error-banner">{error}</div>}
      {loading ? <LoadingScreen compact /> : reports.length ? (
        <section className="report-library-grid">
          {reports.map((report, index) => (
            <article className="library-card" key={report.id} style={{ animationDelay: `${Math.min(index, 8) * 45}ms` }}>
              <div className="library-card__top">
                <span className="report-type-pill">{reportType(report.report_type)}</span>
                <button className={report.favorite ? 'star-button active' : 'star-button'} onClick={() => toggleFavorite(report)} aria-label={report.favorite ? 'Remove from favorites' : 'Add to favorites'}>
                  <Star size={18} fill={report.favorite ? 'currentColor' : 'none'} />
                </button>
              </div>
              <Link to={`/reports/${report.id}`} className="library-card__body">
                <span className="library-document"><FileBarChart size={22} /></span>
                <h3>{report.title}</h3>
                <p>{report.summary}</p>
              </Link>
              <div className="filter-chips">
                {Object.entries(report.report_filters).slice(0, 3).map(([key, value]) => <span key={key}>{value}</span>)}
                {!Object.keys(report.report_filters).length && <span>Complete dataset</span>}
              </div>
              <footer>
                <span><CalendarDays size={15} /> {date(report.created_at)}</span>
                <div>
                  <button onClick={() => setDeleteTarget(report)} aria-label="Delete report"><Trash2 size={16} /></button>
                  <Link to={`/reports/${report.id}`} aria-label="Open report"><ArrowRight size={17} /></Link>
                </div>
              </footer>
            </article>
          ))}
        </section>
      ) : (
        <EmptyState
          title={search || type || favorites ? 'No reports match these filters' : 'Your intelligence library is empty'}
          copy={search || type || favorites ? 'Try a broader search or clear the active filters.' : 'Generate your first report and it will appear here automatically.'}
          action={search || type || favorites
            ? <button className="text-button" onClick={() => { setSearch(''); setType(''); setFavorites(false) }}>Clear filters</button>
            : <Link className="primary-button primary-button--small" to="/studio"><Sparkles size={16} /> Open AI Studio</Link>}
        />
      )}

      {deleteTarget && (
        <div className="modal-layer" role="presentation" onMouseDown={() => setDeleteTarget(null)}>
          <section className="confirm-dialog" role="dialog" aria-modal="true" aria-labelledby="delete-title" onMouseDown={(event) => event.stopPropagation()}>
            <span className="danger-icon"><Trash2 size={22} /></span>
            <h3 id="delete-title">Delete this report?</h3>
            <p><strong>{deleteTarget.title}</strong> will be permanently removed from your private library.</p>
            <div>
              <button className="secondary-button" onClick={() => setDeleteTarget(null)}>Keep report</button>
              <button className="danger-button" disabled={deleting} onClick={remove}>{deleting ? 'Deleting...' : 'Delete report'}</button>
            </div>
          </section>
        </div>
      )}
    </div>
  )
}

