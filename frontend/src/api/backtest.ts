import { api } from './client'

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
}

export type StrategyInfo = {
  id: string
  name: string
  interval: string
  description: string
  implemented: boolean
}

export type StrategyProfile = {
  profile_id: string
  name: string
  description: string
}

export type BatchInfo = {
  batch_id: string
  strategy: string
  start_date: string
  end_date: string
  created_at: string
  count: number
}

export const backtestApi = {
  strategies: () => api<StrategyInfo[]>('/api/v1/backtest/strategies'),
  profiles: () => api<StrategyProfile[]>('/api/v1/backtest/profiles'),
  runs: (batchId?: string) => {
    const q = batchId ? `?batch_id=${encodeURIComponent(batchId)}` : ''
    return api<BacktestRun[]>(`/api/v1/backtest/runs${q}`)
  },
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
}
