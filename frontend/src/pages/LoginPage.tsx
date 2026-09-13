import {
  ArrowRight,
  BarChart3,
  Check,
  Eye,
  EyeOff,
  LockKeyhole,
  Mail,
  ShieldCheck,
  Sparkles,
  UserRound,
} from 'lucide-react'
import { FormEvent, useState } from 'react'
import { Navigate, useNavigate } from 'react-router-dom'
import { Logo } from '../components/Logo'
import { useAuth } from '../context/AuthContext'

export function LoginPage() {
  const { user, login, register } = useAuth()
  const navigate = useNavigate()
  const [mode, setMode] = useState<'login' | 'register'>('login')
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')

  if (user) return <Navigate to="/" replace />

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    setError('')
    setSubmitting(true)
    try {
      if (mode === 'register') await register(name, email, password)
      else await login(email, password)
      navigate('/')
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Unable to continue')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="auth-page">
      <section className="auth-story">
        <div className="auth-grid" aria-hidden="true" />
        <div className="auth-story__top"><Logo /></div>
        <div className="auth-story__content">
          <div className="eyebrow-pill"><Sparkles size={15} /> DATA-GROUNDED INTELLIGENCE</div>
          <h1>Turn business data into <em>decisions.</em></h1>
          <p>Analyze revenue, expose campaign efficiency, and build executive-ready reports through a verified multi-agent workflow.</p>
          <div className="auth-proof">
            <div><strong>2,000</strong><span>verified records</span></div>
            <div><strong>7</strong><span>report modes</span></div>
            <div><strong>100%</strong><span>private workspace</span></div>
          </div>
        </div>

        <div className="auth-console">
          <div className="auth-console__head">
            <span><i /> LIVE ANALYSIS</span>
            <small>Q4 SIGNAL</small>
          </div>
          <div className="mini-chart" aria-hidden="true">
            {[38, 55, 43, 68, 62, 84, 78, 96].map((height, index) => (
              <span key={index} style={{ height: `${height}%` }} />
            ))}
          </div>
          <div className="agent-line">
            <span><Check size={14} /></span>
            <div><strong>Analyst agent</strong><small>Evidence verified across source data</small></div>
            <b>DONE</b>
          </div>
        </div>
      </section>

      <section className="auth-panel">
        <div className="auth-panel__mobile-brand"><Logo /></div>
        <div className="auth-form-wrap">
          <span className="form-kicker">SECURE WORKSPACE</span>
          <h2>{mode === 'login' ? 'Welcome back' : 'Create your workspace'}</h2>
          <p>{mode === 'login' ? 'Sign in to continue to your intelligence command center.' : 'Start building data-grounded reports in under a minute.'}</p>

          <div className="auth-tabs" role="tablist" aria-label="Authentication mode">
            <button className={mode === 'login' ? 'active' : ''} onClick={() => { setMode('login'); setError('') }}>Sign in</button>
            <button className={mode === 'register' ? 'active' : ''} onClick={() => { setMode('register'); setError('') }}>Create account</button>
          </div>

          <form onSubmit={submit} className="auth-form">
            {mode === 'register' && (
              <label>
                <span>Full name</span>
                <div className="input-shell"><UserRound size={18} /><input value={name} onChange={(event) => setName(event.target.value)} placeholder="Ayush Shaw" autoComplete="name" required minLength={2} /></div>
              </label>
            )}
            <label>
              <span>Email address</span>
              <div className="input-shell"><Mail size={18} /><input type="email" value={email} onChange={(event) => setEmail(event.target.value)} placeholder="you@example.com" autoComplete="email" required /></div>
            </label>
            <label>
              <span>Password</span>
              <div className="input-shell">
                <LockKeyhole size={18} />
                <input type={showPassword ? 'text' : 'password'} value={password} onChange={(event) => setPassword(event.target.value)} placeholder={mode === 'register' ? 'At least 8 characters' : 'Enter your password'} autoComplete={mode === 'login' ? 'current-password' : 'new-password'} required minLength={mode === 'register' ? 8 : 1} />
                <button type="button" onClick={() => setShowPassword((value) => !value)} aria-label={showPassword ? 'Hide password' : 'Show password'}>
                  {showPassword ? <EyeOff size={18} /> : <Eye size={18} />}
                </button>
              </div>
            </label>

            {mode === 'register' && <small className="password-hint"><ShieldCheck size={14} /> Use at least one letter and one number.</small>}
            {error && <div className="form-error" role="alert">{error}</div>}

            <button className="primary-button auth-submit" disabled={submitting}>
              {submitting ? <span className="button-spinner" /> : mode === 'login' ? 'Enter workspace' : 'Create workspace'}
              {!submitting && <ArrowRight size={18} />}
            </button>
          </form>

          <div className="security-note"><ShieldCheck size={17} /><span>Your password is Argon2-hashed and your session stays in a secure HTTP-only cookie.</span></div>
        </div>
        <div className="auth-panel__footer"><BarChart3 size={15} /> AI Analytic Platform · Revenue Intelligence</div>
      </section>
    </div>
  )
}
