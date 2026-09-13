import {
  BarChart3,
  Bot,
  ChevronDown,
  Command,
  Database,
  FileText,
  LayoutDashboard,
  LogOut,
  Menu,
  Plus,
  Search,
  Sparkles,
  X,
} from 'lucide-react'
import { useEffect, useMemo, useRef, useState } from 'react'
import { NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { useDatasets } from '../context/DatasetContext'
import { api } from '../lib/api'
import type { SystemStatus } from '../types'
import { Logo } from './Logo'

const navigation = [
  { label: 'Overview', path: '/', icon: LayoutDashboard },
  { label: 'AI Studio', path: '/studio', icon: Sparkles },
  { label: 'Data Hub', path: '/data', icon: Database },
  { label: 'Reports', path: '/reports', icon: FileText },
]

const pageTitles: Record<string, { eyebrow: string; title: string }> = {
  '/': { eyebrow: 'Revenue command center', title: 'Business overview' },
  '/studio': { eyebrow: 'Multi-agent workspace', title: 'Intelligence studio' },
  '/data': { eyebrow: 'Private data workspace', title: 'Data hub' },
  '/reports': { eyebrow: 'Private knowledge base', title: 'Report library' },
}

export function AppShell() {
  const { user, logout } = useAuth()
  const { datasets, activeId, setActiveId } = useDatasets()
  const location = useLocation()
  const navigate = useNavigate()
  const [mobileNav, setMobileNav] = useState(false)
  const [accountOpen, setAccountOpen] = useState(false)
  const [commandOpen, setCommandOpen] = useState(false)
  const [commandQuery, setCommandQuery] = useState('')
  const [system, setSystem] = useState<SystemStatus | null>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    api<SystemStatus>('/system/status').then(setSystem).catch(() => undefined)
  }, [])

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'k') {
        event.preventDefault()
        setCommandOpen((current) => !current)
      }
      if (event.key === 'Escape') {
        setCommandOpen(false)
        setAccountOpen(false)
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])

  useEffect(() => {
    if (commandOpen) window.setTimeout(() => inputRef.current?.focus(), 50)
  }, [commandOpen])

  const page = location.pathname.startsWith('/reports/')
    ? { eyebrow: 'Verified intelligence', title: 'Report detail' }
    : pageTitles[location.pathname] || pageTitles['/']

  const commands = useMemo(() => [
    { label: 'Open business overview', hint: 'Dashboard', path: '/', icon: LayoutDashboard },
    { label: 'Create a new intelligence report', hint: 'AI Studio', path: '/studio', icon: Plus },
    { label: 'Upload or map a dataset', hint: 'Data Hub', path: '/data', icon: Database },
    { label: 'Search saved reports', hint: 'Library', path: '/reports', icon: Search },
  ].filter((item) => item.label.toLowerCase().includes(commandQuery.toLowerCase())), [commandQuery])

  const runCommand = (path: string) => {
    navigate(path)
    setCommandOpen(false)
    setCommandQuery('')
  }

  const handleLogout = async () => {
    await logout()
    navigate('/login')
  }

  return (
    <div className="app-shell">
      <aside className={`sidebar ${mobileNav ? 'sidebar--open' : ''}`}>
        <div className="sidebar__top">
          <Logo />
          <button className="icon-button sidebar__close" onClick={() => setMobileNav(false)} aria-label="Close navigation">
            <X size={20} />
          </button>
        </div>

        <nav className="sidebar__nav" aria-label="Primary navigation">
          <span className="nav-label">Workspace</span>
          {navigation.map(({ label, path, icon: Icon }) => (
            <NavLink
              to={path}
              key={path}
              end={path === '/'}
              onClick={() => setMobileNav(false)}
              className={({ isActive }) => `nav-item ${isActive ? 'nav-item--active' : ''}`}
            >
              <Icon size={19} />
              <span>{label}</span>
              {label === 'AI Studio' && <span className="nav-new">AI</span>}
            </NavLink>
          ))}
        </nav>

        <div className="source-switcher">
          <span className="nav-label">Active data source</span>
          <label>
            <Database size={16} />
            <select value={activeId} onChange={(event) => setActiveId(event.target.value)}>
              <option value="">Bundled demo data</option>
              {datasets.filter((item) => item.status === 'ready').map((item) => <option value={item.id} key={item.id}>{item.name}</option>)}
            </select>
          </label>
        </div>

        <div className="sidebar__signal">
          <div className="signal-orbit" aria-hidden="true">
            <span /><span /><span />
          </div>
          <div>
            <span className="status-line"><i /> Intelligence online</span>
            <strong>{system?.ai_mode || 'Connecting engine'}</strong>
            <small>{system ? `${system.dataset_records.toLocaleString()} verified records` : 'Reading system status'}</small>
          </div>
        </div>

        <button className="sidebar__profile" onClick={() => setAccountOpen((value) => !value)}>
          <span className="avatar">{user?.name.charAt(0).toUpperCase()}</span>
          <span className="profile-copy">
            <strong>{user?.name}</strong>
            <small>{user?.email}</small>
          </span>
          <ChevronDown size={17} />
        </button>
        {accountOpen && (
          <div className="profile-menu">
            <button onClick={handleLogout}><LogOut size={17} /> Sign out</button>
          </div>
        )}
      </aside>

      {mobileNav && <button className="nav-scrim" onClick={() => setMobileNav(false)} aria-label="Close navigation" />}

      <div className="workspace">
        <header className="topbar">
          <div className="topbar__title">
            <button className="icon-button mobile-menu" onClick={() => setMobileNav(true)} aria-label="Open navigation">
              <Menu size={21} />
            </button>
            <div>
              <span>{page.eyebrow}</span>
              <h1>{page.title}</h1>
            </div>
          </div>
          <div className="topbar__actions">
            <button className="command-trigger" onClick={() => setCommandOpen(true)}>
              <Search size={17} />
              <span>Quick search</span>
              <kbd><Command size={12} /> K</kbd>
            </button>
            <button className="primary-button primary-button--small" onClick={() => navigate('/studio')}>
              <Sparkles size={17} /> New report
            </button>
          </div>
        </header>

        <main className="main-content">
          <Outlet />
        </main>
      </div>

      <nav className="bottom-nav" aria-label="Mobile navigation">
        {navigation.map(({ label, path, icon: Icon }) => (
          <NavLink to={path} key={path} end={path === '/'}>
            <Icon size={20} />
            <span>{label === 'AI Studio' ? 'Studio' : label === 'Data Hub' ? 'Data' : label}</span>
          </NavLink>
        ))}
      </nav>

      {commandOpen && (
        <div className="modal-layer" role="presentation" onMouseDown={() => setCommandOpen(false)}>
          <section className="command-palette" role="dialog" aria-modal="true" aria-label="Quick navigation" onMouseDown={(event) => event.stopPropagation()}>
            <div className="command-search">
              <Search size={20} />
              <input
                ref={inputRef}
                value={commandQuery}
                onChange={(event) => setCommandQuery(event.target.value)}
                placeholder="Where do you want to go?"
              />
              <kbd>ESC</kbd>
            </div>
            <div className="command-results">
              <span className="nav-label">Actions</span>
              {commands.map(({ label, hint, path, icon: Icon }) => (
                <button key={path} onClick={() => runCommand(path)}>
                  <span className="command-icon"><Icon size={18} /></span>
                  <span><strong>{label}</strong><small>{hint}</small></span>
                </button>
              ))}
              {!commands.length && <div className="command-empty"><Bot size={24} /> No matching action</div>}
            </div>
          </section>
        </div>
      )}
    </div>
  )
}
