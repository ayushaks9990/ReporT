import { FileSearch } from 'lucide-react'
import type { ReactNode } from 'react'

export function EmptyState({ title, copy, action }: { title: string; copy: string; action?: ReactNode }) {
  return (
    <div className="empty-state">
      <span><FileSearch size={28} /></span>
      <h3>{title}</h3>
      <p>{copy}</p>
      {action}
    </div>
  )
}

