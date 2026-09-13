import { RotateCcw, SlidersHorizontal } from 'lucide-react'
import type { FilterOptions, Filters } from '../types'

type Props = {
  options: FilterOptions
  filters: Filters
  onChange: (filters: Filters) => void
  fields?: Array<keyof Filters>
}

const labels: Record<keyof Filters, string> = {
  region: 'All regions',
  quarter: 'All quarters',
  product: 'All products',
  channel: 'All channels',
}

const optionKeys: Record<keyof Filters, keyof FilterOptions> = {
  region: 'regions',
  quarter: 'quarters',
  product: 'products',
  channel: 'channels',
}

export function FilterBar({ options, filters, onChange, fields = ['region', 'quarter', 'product', 'channel'] }: Props) {
  const active = Object.values(filters).filter(Boolean).length
  return (
    <div className="filter-bar">
      <div className="filter-bar__label">
        <SlidersHorizontal size={17} />
        <span>Data scope</span>
        {active > 0 && <b>{active}</b>}
      </div>
      <div className="filter-bar__fields">
        {fields.map((field) => (
          <label className="select-field" key={field}>
            <span className="sr-only">{labels[field]}</span>
            <select
              value={filters[field] || ''}
              onChange={(event) => onChange({ ...filters, [field]: event.target.value || undefined })}
            >
              <option value="">{labels[field]}</option>
              {options[optionKeys[field]].map((item) => <option value={item} key={item}>{item}</option>)}
            </select>
          </label>
        ))}
        {active > 0 && (
          <button className="reset-button" onClick={() => onChange({})} title="Clear filters">
            <RotateCcw size={16} /> Reset
          </button>
        )}
      </div>
    </div>
  )
}

