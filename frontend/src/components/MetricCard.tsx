import type { ReactNode } from 'react'
import { ArrowDownRight, ArrowUpRight } from 'lucide-react'

type Props = {
  label: string
  value: string
  detail: string
  icon: ReactNode
  accent: 'blue' | 'yellow' | 'violet' | 'cyan'
  change?: number | null
}

export function MetricCard({ label, value, detail, icon, accent, change }: Props) {
  return (
    <article className={`metric-card metric-card--${accent}`}>
      <div className="metric-card__top">
        <span className="metric-icon">{icon}</span>
        {change !== undefined && change !== null && (
          <span className={`metric-change ${change >= 0 ? 'positive' : 'negative'}`}>
            {change >= 0 ? <ArrowUpRight size={14} /> : <ArrowDownRight size={14} />}
            {Math.abs(change).toFixed(1)}%
          </span>
        )}
      </div>
      <span className="metric-label">{label}</span>
      <strong>{value}</strong>
      <small>{detail}</small>
    </article>
  )
}

