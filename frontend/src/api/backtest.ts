import { api, pageQuery, type Page } from './client'

export type BacktestRun = {
  id: string
  vt_symbol: string
  strategy: string
  interval: string
  start_date: string
  end_date: string
  total_return: number | null
  max_drawdown: number | null
  sharpe_ratio: number | null
  trade_count: number | null
  source: string
  batch_id: string | null
  statistics: Record<string, unknown>
  created_at: string
  equity_curve: { datetime: string; equity: number }[]
  trades: Record<string, unknown>[]
  engine?: string | null
  status?: string
  error_message?: string | null
  params?: Record<string, unknown>
}

export type StrategyInfo = {
  id: string
  name: string
  interval: string
  description: string
  implemented: boolean
  engine?: string
}

export type StrategyProfile = {
  profile_id: string
  name: string
  description: string
  fast_window: number
  slow_window: number
  capital: number
}

export type BatchInfo = {
  batch_id: string
  strategy: string
  start_date: string
  end_date: string
  created_at: string
  count: number
}

export type OptimizeSummary = {
  batch_id: string
  objective: string
  best: BacktestRun | null
  runs: BacktestRun[]
}

export const backtestApi = {
  strategies: () => api<StrategyInfo[]>('/api/v1/backtest/strategies'),
  profiles: () => api<StrategyProfile[]>('/api/v1/backtest/profiles'),
  runs: (batchId?: string) => {
    const q = batchId ? `?batch_id=${encodeURIComponent(batchId)}` : ''
    return api<BacktestRun[]>(`/api/v1/backtest/runs${q}`)
  },
  runsPage: (page = 1, pageSize = 20) =>
    api<Page<BacktestRun>>(`/api/v1/backtest/runs/page?${pageQuery(page, pageSize)}`),
  run: (id: string) => api<BacktestRun>(`/api/v1/backtest/runs/${encodeURIComponent(id)}`),
  batches: () => api<BatchInfo[]>('/api/v1/backtest/batches'),
  start: (body: Record<string, unknown>) =>
    api<{ job_id: string }>('/api/v1/backtest/runs', {
      method: 'POST',
      body: JSON.stringify(body),
    }),
  startBatch: (body: Record<string, unknown>) =>
    api<{ job_id: string; batch_id: string }>('/api/v1/backtest/runs/batch', {
      method: 'POST',
      body: JSON.stringify(body),
    }),
  startOptimize: (body: Record<string, unknown>) =>
    api<{ job_id: string; batch_id: string }>('/api/v1/backtest/optimize', {
      method: 'POST',
      body: JSON.stringify(body),
    }),
  optimizeSummary: (batchId: string, objective = 'sharpe_ratio') =>
    api<OptimizeSummary>(
      `/api/v1/backtest/optimize/${encodeURIComponent(batchId)}?objective=${encodeURIComponent(objective)}`,
    ),
}
