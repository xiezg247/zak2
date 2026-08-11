import { api } from './client'

export type Health = {
  postgres: { ok: boolean; error?: string; url?: string }
  redis: { ok: boolean; url?: string; updated_at?: string | null; quote_count?: number }
  llm: { configured: boolean; model: string; api_base: string }
  tushare_configured: boolean
  mcp?: { configured?: boolean; enabled?: boolean; status?: string; tool_count?: number; tools?: string[]; error?: string }
  quote_collector?: {
    running?: boolean
    provider?: string | null
    status?: string | null
    last_count?: number
    ts?: string | null
    hint?: string | null
  }
  note?: string
}

export type SchedulerJob = {
  job_id: string
  name: string
  description: string
  runnable: boolean
  run_hint: string | null
  status_label?: string
  enabled: boolean
  cron_hour: number | null
  cron_minute: number | null
  cron_day_of_week: string | null
  cron_hours?: string | null
  interval_seconds: number | null
  last_run: {
    last_run_at: string
    last_message: string
    last_success: boolean | null
  } | null
}

export type PurgeResult = {
  deleted: Record<string, number>
  total: number
  message: string
}

export type SyncResult = {
  success: boolean
  message: string
  skipped?: boolean
}

export type BarsOverview = {
  interval: string
  symbol_count: number
  min_start: string | null
  max_end: string | null
  as_of_trade_date: string | null
  ok_count: number
  stale_count: number
  unknown_count: number
}

export type AsyncJob = {
  job_id: string
  kind: string
}

export const opsApi = {
  health: () => api<Health>('/api/v1/ops/health'),
  forceCollector: () =>
    api<SyncResult>('/api/v1/ops/collector/force', {
      method: 'POST',
    }),
  barsOverview: () => api<BarsOverview>('/api/v1/ops/bars/overview'),
  jobs: () => api<SchedulerJob[]>('/api/v1/ops/scheduler/jobs'),
  setEnabled: (jobId: string, enabled: boolean) =>
    api<SchedulerJob>(`/api/v1/ops/scheduler/jobs/${encodeURIComponent(jobId)}`, {
      method: 'PATCH',
      body: JSON.stringify({ enabled }),
    }),
  runJob: (jobId: string) =>
    api<AsyncJob>(`/api/v1/ops/scheduler/jobs/${encodeURIComponent(jobId)}/run`, {
      method: 'POST',
    }),
  purge: () =>
    api<PurgeResult>('/api/v1/ops/cache/purge', {
      method: 'POST',
    }),
  syncCalendar: () =>
    api<SyncResult>('/api/v1/ops/sync/trade-calendar', { method: 'POST' }),
  syncSectorFlow: () =>
    api<SyncResult>('/api/v1/ops/sync/sector-flow', { method: 'POST' }),
  screenIntraday: () =>
    api<SyncResult>('/api/v1/ops/sync/screen-intraday', { method: 'POST' }),
  screenPostClose: () =>
    api<SyncResult>('/api/v1/ops/sync/screen-post-close', { method: 'POST' }),
}
