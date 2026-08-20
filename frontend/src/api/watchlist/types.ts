export type WatchlistItem = {
  symbol: string
  exchange: string
  name: string
  industry?: string
  sort_order: number
  vt_symbol: string
  tf_symbol: string
  last_price: number | null
  change_pct: number | null
  turnover_rate: number | null
  volume: number | null
  amount: number | null
  volume_ratio: number | null
  suspended?: boolean
}

export type WatchlistGroup = {
  id: string
  name: string
  sort_order: number
}

export type GroupMembersBatchResult = {
  ok: boolean
  action: 'add' | 'remove'
  added: number
  removed: number
  skipped: number
  errors: Array<{ symbol: string; detail: string }>
}

export type Bar = {
  datetime: string
  open: number
  high: number
  low: number
  close: number
  volume: number
  turnover: number
}

export type BarsResponse = {
  symbol: string
  exchange: string
  vt_symbol: string
  interval: string
  bars: Bar[]
}

export type StrategySignalRow = {
  vt_symbol: string
  name: string
  last_price: number | null
  change_pct: number | null
  signal: string
  signal_label: string
  signal_date: string | null
  strength: number | null
  strength_tier?: string | null
  strength_tier_label?: string | null
  reason_summary: string
  ref_buy_price: number | null
  ref_sell_price: number | null
  ma_gap_pct: number | null
  bar_as_of: string | null
}

export type StrategyPositionRow = {
  vt_symbol: string
  name: string
  cost_price: number
  volume: number
  buy_date: string
  last_price: number | null
  market_value: number | null
  unrealized_pnl: number | null
  unrealized_pnl_pct: number | null
  t1_locked: boolean
  exit_signal: string
  exit_signal_label: string
  ref_sell_price: number | null
  reason_summary: string
  risk_tags?: string[]
  risk_primary?: string
}

export type RiskSummary = {
  total_capital: number | null
  actual_position_pct: number | null
}

export type TradingRiskPrefs = {
  total_capital: number | null
  stop_loss_pct: number
  caution_float_pct: number
  realized_pnl_today: number | null
}

export type TradingRiskPrefsPut = {
  total_capital?: number | null
  stop_loss_pct?: number | null
  caution_float_pct?: number | null
  realized_pnl_today?: number | null
}

export type StrategyBoard = {
  config_key: string
  signal_mode?: string
  as_of: string | null
  source: string
  note: string
  panel_symbols: string[]
  signals: StrategySignalRow[]
  positions: StrategyPositionRow[]
  risk_summary?: RiskSummary | null
}

export type SignalPanel = {
  symbols: string[]
  max_symbols: number
  count: number
}

export type PositionItem = {
  symbol: string
  exchange: string
  vt_symbol: string
  cost_price: number
  volume: number
  buy_date: string
  notes: string
  source: string
  sort_order: number
  created_at: string
  updated_at: string
}

export type PositionUpsert = {
  symbol: string
  exchange?: string
  cost_price: number
  volume: number
  buy_date: string
  notes?: string
}

export type NotifyLogItem = {
  id: string
  event_type: string
  channel: string
  status: string
  error: string
  created_at: string
  payload: Record<string, unknown>
}

export type NotifyLogOut = {
  items: NotifyLogItem[]
  limit: number
  count: number
}

export type Fundamentals = {
  vt_symbol: string
  ts_code: string
  snapshot: {
    end_date: string
    revenue: number | null
    net_income: number | null
    revenue_yoy: number | null
    net_income_yoy: number | null
    roe: number | null
    debt_ratio: number | null
  } | null
  sync: {
    last_sync_at: string
    latest_end_date: string
    periods_count: number
    sync_status: string
    error_message: string
  } | null
  disclosures: {
    end_date: string
    pre_date: string
    ann_date: string
    actual_date: string
  }[]
}

export type QuoteOut = {
  symbol: string
  exchange: string
  vt_symbol: string
  tf_symbol: string
  name: string
  last_price: number | null
  change_pct: number | null
  turnover_rate: number | null
  volume: number | null
  amount: number | null
  amplitude: number | null
  volume_ratio: number | null
  industry: string
}
