export type User = {
  id: string
  name: string
  email: string
  created_at: string
}

export type FilterOptions = {
  regions: string[]
  quarters: string[]
  products: string[]
  channels: string[]
}

export type Filters = {
  region?: string
  quarter?: string
  product?: string
  channel?: string
}

export type Kpis = {
  revenue: number
  units: number
  marketing_budget: number
  impressions: number
  clicks: number
  conversions: number
  ctr: number
  conversion_rate: number
  cost_per_conversion: number
  period_change: number | null
}

export type ValuePoint = { name: string; value: number }
export type ChannelPoint = {
  name: string
  conversions: number
  budget: number
  cpa: number
  impressions?: number
  clicks?: number
  ctr?: number
  conversion_rate?: number
}

export type ReportListItem = {
  id: string
  title: string
  report_type: string
  dataset_id: string | null
  summary: string
  provider: string
  report_filters: Filters
  favorite: boolean
  created_at: string
}

export type ReportDetail = ReportListItem & {
  content: string
  metrics: Kpis
  chart_data: {
    revenue_by_quarter: ValuePoint[]
    revenue_by_region: ValuePoint[]
    top_products: ValuePoint[]
    channel_performance: ChannelPoint[]
    conversions_by_quarter?: ValuePoint[]
    spend_by_quarter?: ValuePoint[]
    acquisition_funnel?: ValuePoint[]
  }
  insights: string[]
  updated_at: string
}

export type DashboardData = {
  filters: Filters
  coverage: { sales_records: number; marketing_records: number }
  kpis: Kpis
  charts: ReportDetail['chart_data']
  insights: string[]
  recent_reports: ReportListItem[]
  report_count: number
  dataset: { id: string | null; name: string; kind: string }
}

export type SystemStatus = {
  ai_mode: string
  model: string | null
  autogen_available: boolean
  autogen_enabled: boolean
  agent_pipeline: string[]
  email_delivery: boolean
  telegram_delivery: boolean
  dataset_records: number
}

export type DatasetItem = {
  id: string
  name: string
  original_filename: string
  kind: 'sales' | 'marketing'
  status: 'ready' | 'needs_mapping'
  row_count: number
  columns: string[]
  column_types: Record<string, 'number' | 'text' | 'empty'>
  mapping: Record<string, string>
  created_at: string
}

export type DatasetDetail = DatasetItem & {
  preview: Array<Record<string, string | number | boolean | null>>
}
