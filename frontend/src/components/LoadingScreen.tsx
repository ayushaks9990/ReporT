import { Logo } from './Logo'

export function LoadingScreen({ compact = false }: { compact?: boolean }) {
  if (compact) {
    return (
      <div className="panel-loading" aria-label="Loading">
        <span /><span /><span />
      </div>
    )
  }
  return (
    <div className="app-loading">
      <Logo />
      <div className="loading-track"><span /></div>
      <small>Calibrating intelligence workspace</small>
    </div>
  )
}

