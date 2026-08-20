import { api } from '../client'
import type {
  PositionItem,
  PositionUpsert,
  SignalPanel,
  StrategyBoard,
  TradingRiskPrefs,
  TradingRiskPrefsPut,
} from './types'

export const watchlistStrategyApi = {
  strategyBoard: (opts?: { configKey?: string; signalMode?: string }) => {
    const params = new URLSearchParams()
    if (opts?.configKey) params.set('config_key', opts.configKey)
    if (opts?.signalMode) params.set('signal_mode', opts.signalMode)
    const q = params.toString() ? `?${params.toString()}` : ''
    return api<StrategyBoard>(`/api/v1/watchlist/strategy-board${q}`)
  },
  tradingRisk: () => api<TradingRiskPrefs>('/api/v1/watchlist/trading-risk'),
  putTradingRisk: (body: TradingRiskPrefsPut) =>
    api<TradingRiskPrefs>('/api/v1/watchlist/trading-risk', {
      method: 'PUT',
      body: JSON.stringify(body),
    }),
  signalPanel: () => api<SignalPanel>('/api/v1/watchlist/signal-panel'),
  replaceSignalPanel: (symbols: string[]) =>
    api<SignalPanel>('/api/v1/watchlist/signal-panel', {
      method: 'PUT',
      body: JSON.stringify({ symbols }),
    }),
  addSignalPanelMember: (symbol: string) =>
    api<SignalPanel>('/api/v1/watchlist/signal-panel/members', {
      method: 'POST',
      body: JSON.stringify({ symbol }),
    }),
  removeSignalPanelMember: (vtSymbol: string) =>
    api<SignalPanel>(`/api/v1/watchlist/signal-panel/members/${encodeURIComponent(vtSymbol)}`, {
      method: 'DELETE',
    }),
  listPositions: () => api<PositionItem[]>('/api/v1/watchlist/positions'),
  addPosition: (body: PositionUpsert) =>
    api<PositionItem>('/api/v1/watchlist/positions', {
      method: 'POST',
      body: JSON.stringify(body),
    }),
  updatePosition: (vtSymbol: string, body: PositionUpsert) =>
    api<PositionItem>(`/api/v1/watchlist/positions/${encodeURIComponent(vtSymbol)}`, {
      method: 'PUT',
      body: JSON.stringify(body),
    }),
  removePosition: (vtSymbol: string) =>
    api<{ ok: boolean }>(`/api/v1/watchlist/positions/${encodeURIComponent(vtSymbol)}`, {
      method: 'DELETE',
    }),
}
