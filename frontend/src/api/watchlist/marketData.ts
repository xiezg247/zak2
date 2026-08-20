import { api } from '../client'
import type { BarsResponse, Fundamentals, NotifyLogOut, QuoteOut } from './types'

export const watchlistMarketDataApi = {
  notifyLog: (limit?: number) => {
    const q = limit != null ? `?limit=${encodeURIComponent(String(limit))}` : ''
    return api<NotifyLogOut>(`/api/v1/watchlist/notify-log${q}`)
  },
  bars: (vtSymbol: string, interval = 'd', limit = 120) =>
    api<BarsResponse>(
      `/api/v1/bars/${encodeURIComponent(vtSymbol)}?interval=${interval}&limit=${limit}`,
    ),
  quotes: (symbols: string) =>
    api<QuoteOut[]>(`/api/v1/quotes?symbols=${encodeURIComponent(symbols)}`),
  fundamentals: (vtSymbol: string) =>
    api<Fundamentals>(`/api/v1/watchlist/items/${encodeURIComponent(vtSymbol)}/fundamentals`),
}
