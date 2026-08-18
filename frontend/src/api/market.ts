import { api } from './client'

export type MarketOverview = {
  redis_available: boolean
  quote_count: number
  updated_at: string | null
  is_trading: boolean
  emotion: {
    trade_date: string
    max_limit_times: number
    max_board_vt_symbol: string
    linked_board_count: number
    linked_board_vt_symbols: string[]
    updated_at: string
  } | null
  emotion_cycle: EmotionCycle | null
  ranks_available: string[]
}

export type EmotionCycle = {
  stage: string
  stage_label: string
  position_factor: number
  position_pct_min: number
  position_pct_max: number
  allow_new_positions: boolean
  allowed_modes: string[]
  allowed_mode_labels: string[]
  warnings: string[]
  source: string
  trade_date: string | null
  inputs: {
    limit_up_count?: number
    limit_down_count?: number
    up_ratio?: number
    total_amount?: number
    max_limit_times?: number
    limit_ladder_depth?: number
    prev_leader_limit_down?: boolean
    sample_size?: number
    fear_greed_index?: number
    index_above_ma5?: boolean | null
    limit_break_rate?: number | null
  }
}

export type RankRow = {
  rank: number
  symbol: string
  exchange: string
  vt_symbol: string
  tf_symbol: string
  name: string
  score: number
  last_price: number | null
  change_pct: number | null
  turnover_rate: number | null
  amount: number | null
  volume_ratio: number | null
  limit_times: number | null
}

export type SectorFlowRow = {
  trade_date: string
  sector_kind: string
  sector_id: string
  name: string
  change_pct: number
  net_flow_yi: number
  flow_source: string
}

export type RadarCard = {
  card_id: string
  title: string
  subtitle: string
  source: string
  computed_at: string
  empty_message: string
  rows: Record<string, unknown>[]
}

export type RadarResonanceEntry = {
  vt_symbol: string
  name: string
  card_count: number
  card_titles: string[]
  resonance_score: number
  change_pct: number | null
  last_price: number | null
  seal_time_label?: string
}

export type LimitListRow = {
  trade_date: string
  vt_symbol: string
  ts_code: string
  name: string
  limit_times: number
  first_time: string
  last_time: string
  fd_amount: number
  open_times: number
  strth: number
  updated_at: string
  seal_time_score: number
  seal_time_label: string
}

export type LimitListOut = {
  trade_date: string
  total: number
  rows: LimitListRow[]
}

export type RadarResonance = {
  min_cards: number
  top_n: number
  total: number
  entries: RadarResonanceEntry[]
}

export type RadarHorizon = {
  variant: string
  strategy_key: string
  computed_at: string | null
  scanned_total: number
  refined_total: number
  rows: Array<{
    vt_symbol: string
    name: string
    resonance_score: number
    card_count: number
    card_titles: string[]
    change_pct: number | null
    last_price: number | null
    seal_time_label?: string
  }>
  empty: boolean
  label: string
}

export type RadarPredict = {
  variant: string
  model_label: string
  computed_at: string | null
  scanned_total: number
  refined_total: number
  kline_missing: number
  rows: Array<{
    vt_symbol: string
    name: string
    predict_score: number
    resonance_score: number
    card_count: number
    card_titles: string[]
    change_pct: number | null
    last_price: number | null
    seal_time_label?: string
    reasons: string[]
  }>
  empty: boolean
  label: string
}

export type ResonanceWeightItem = {
  card_id: string
  title: string
  weight: number
  default_weight: number
}

export type ResonanceWeights = {
  items: ResonanceWeightItem[]
  weights: Record<string, number>
}

export type EmotionThresholds = {
  recession_limit_down: number
  ice_max_boards: number
  ice_limit_down: number
  ice_up_ratio_max: number
  climax_ladder_depth: number
  climax_limit_up: number
  divergence_limit_up_min: number
  divergence_limit_spread: number
  startup_max_boards: number
  startup_limit_up: number
  amount_floor_yuan: number
  recession_break_rate: number
  fear_greed_overheat: number
  hysteresis_enabled: boolean
  is_default: boolean
}

export type EmotionThresholdsPatch = Partial<Omit<EmotionThresholds, 'is_default'>>

export type PlanDraftOut = {
  plan_id: string
  trade_date: string
  status: string
  emotion_expected: string
  symbol_count: number
  symbols: { vt_symbol: string; name?: string }[]
  replaced: boolean
}

export const marketApi = {
  overview: () => api<MarketOverview>('/api/v1/market/overview'),
  emotionCycle: () => api<EmotionCycle>('/api/v1/market/emotion-cycle'),
  ranks: (field = 'change_pct', topN = 50) =>
    api<RankRow[]>(`/api/v1/market/ranks?field=${encodeURIComponent(field)}&top_n=${topN}`),
  sectorDates: () => api<string[]>('/api/v1/sectors/dates'),
  sectorFlow: (
    opts: { kind?: string; trade_date?: string; sort?: string; limit?: number } = {},
  ) => {
    const q = new URLSearchParams()
    q.set('kind', opts.kind || 'industry')
    q.set('sort', opts.sort || 'net_flow_yi')
    q.set('limit', String(opts.limit || 50))
    if (opts.trade_date) q.set('trade_date', opts.trade_date)
    return api<SectorFlowRow[]>(`/api/v1/sectors/flow?${q}`)
  },
  radarCards: () => api<RadarCard[]>('/api/v1/radar/cards'),
  radarHorizon: () => api<RadarHorizon>('/api/v1/radar/horizon'),
  radarPredict: () => api<RadarPredict>('/api/v1/radar/predict'),
  radarResonance: (opts: { top_n?: number; min_cards?: number } = {}) => {
    const q = new URLSearchParams()
    q.set('top_n', String(opts.top_n ?? 20))
    q.set('min_cards', String(opts.min_cards ?? 2))
    return api<RadarResonance>(`/api/v1/radar/resonance?${q}`)
  },
  resonanceWeights: () => api<ResonanceWeights>('/api/v1/radar/resonance/weights'),
  putResonanceWeights: (weights: Record<string, number>) =>
    api<ResonanceWeights>('/api/v1/radar/resonance/weights', {
      method: 'PUT',
      body: JSON.stringify({ weights }),
    }),
  limitList: (tradeDate?: string) => {
    const q = tradeDate ? `?trade_date=${encodeURIComponent(tradeDate)}` : ''
    return api<LimitListOut>(`/api/v1/market/limit-list${q}`)
  },
  emotionThresholds: () => api<EmotionThresholds>('/api/v1/market/emotion-cycle/thresholds'),
  putEmotionThresholds: (body: EmotionThresholdsPatch) =>
    api<EmotionThresholds>('/api/v1/market/emotion-cycle/thresholds', {
      method: 'PUT',
      body: JSON.stringify(body),
    }),
  resetEmotionThresholds: () =>
    api<EmotionThresholds>('/api/v1/market/emotion-cycle/thresholds/reset', {
      method: 'POST',
    }),
  createPlanDraft: (body: { top_n?: number; trade_date?: string } = {}) =>
    api<PlanDraftOut>('/api/v1/radar/plan-draft', {
      method: 'POST',
      body: JSON.stringify(body),
    }),
}
