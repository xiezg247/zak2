export const BOARD_BT_START = '2020-01-01'
export const BOARD_BT_END = '2026-06-01'
export const BOARD_BT_CAPITAL = 100000

const EXTRA_DEFAULTS: Record<string, Record<string, number>> = {
  donchian: { entry_window: 20, exit_window: 10 },
  rsi_reversal: { rsi_period: 14, oversold: 30, overbought: 70 },
  bollinger: { boll_period: 20, boll_dev: 2.0 },
  ma_band: { ma_fast: 5, ma_mid: 10, ma_slow: 20, ma_long: 60 },
  atr_breakout: { channel_period: 20, atr_period: 14, atr_mult: 2.0 },
}

function parseNumericParts(ck: string): number[] {
  const parts = (ck || '').split(':').slice(1)
  return parts.map(Number).filter((v) => Number.isFinite(v))
}

function extraParamsFor(mode: string, configKey: string): Record<string, number> {
  const keys = Object.keys(EXTRA_DEFAULTS[mode] ?? {})
  const values = parseNumericParts(configKey)
  const out: Record<string, number> = {}
  keys.forEach((key, i) => {
    out[key] = values[i] ?? EXTRA_DEFAULTS[mode][key]
  })
  return out
}

export function parseFastSlowFromConfigKey(ck: string): { fast: number; slow: number } {
  const parts = (ck || '').split(':')
  if (parts.length >= 3) {
    const fast = Number(parts[parts.length - 2])
    const slow = Number(parts[parts.length - 1])
    if (Number.isFinite(fast) && Number.isFinite(slow) && fast >= 2 && slow > fast) {
      return { fast, slow }
    }
  }
  return { fast: 5, slow: 20 }
}

export function buildAlignedBacktestQuery(
  mode: string,
  vt: string,
  configKey: string,
): Record<string, string> {
  if (mode === 'trend_ma') {
    return {
      strategy: 'trend_ma',
      vt_symbol: vt,
      fast_window: '20',
      slow_window: '60',
      adx_period: '14',
      adx_threshold: '25',
      trailing_stop_pct: '0.12',
    }
  }
  if (mode === 'medium_swing') {
    return {
      strategy: 'medium_swing',
      vt_symbol: vt,
      fast_window: '12',
      slow_window: '26',
      signal_period: '9',
      trend_ma_window: '60',
    }
  }
  if (EXTRA_DEFAULTS[mode]) {
    const p = extraParamsFor(mode, configKey)
    const q: Record<string, string> = { strategy: mode, vt_symbol: vt }
    Object.entries(p).forEach(([key, value]) => {
      q[key] = String(value)
    })
    return q
  }
  const { fast, slow } = parseFastSlowFromConfigKey(configKey)
  return {
    strategy: 'double_ma',
    vt_symbol: vt,
    fast_window: String(fast),
    slow_window: String(slow),
  }
}

export function buildEnqueueRunBody(
  mode: string,
  vt: string,
  configKey: string,
): Record<string, unknown> {
  if (mode === 'trend_ma') {
    return {
      vt_symbol: vt,
      strategy: 'trend_ma',
      interval: 'd',
      start_date: BOARD_BT_START,
      end_date: BOARD_BT_END,
      capital: BOARD_BT_CAPITAL,
      fast_window: 20,
      slow_window: 60,
      adx_period: 14,
      adx_threshold: 25,
      trailing_stop_pct: 0.12,
    }
  }
  if (mode === 'medium_swing') {
    return {
      vt_symbol: vt,
      strategy: 'medium_swing',
      interval: 'd',
      start_date: BOARD_BT_START,
      end_date: BOARD_BT_END,
      capital: BOARD_BT_CAPITAL,
      fast_window: 12,
      slow_window: 26,
      signal_period: 9,
      trend_ma_window: 60,
    }
  }
  if (EXTRA_DEFAULTS[mode]) {
    return {
      vt_symbol: vt,
      strategy: mode,
      interval: 'd',
      start_date: BOARD_BT_START,
      end_date: BOARD_BT_END,
      capital: BOARD_BT_CAPITAL,
      ...extraParamsFor(mode, configKey),
    }
  }
  const { fast, slow } = parseFastSlowFromConfigKey(configKey)
  return {
    vt_symbol: vt,
    strategy: 'double_ma',
    interval: 'd',
    start_date: BOARD_BT_START,
    end_date: BOARD_BT_END,
    capital: BOARD_BT_CAPITAL,
    fast_window: fast,
    slow_window: slow,
  }
}
