export type BoardSignalMode = 'heuristic_v2' | 'double_ma' | 'trend_ma'

export const BOARD_BT_START = '2020-01-01'
export const BOARD_BT_END = '2026-06-01'
export const BOARD_BT_CAPITAL = 100000

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
  mode: BoardSignalMode,
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
  const { fast, slow } = parseFastSlowFromConfigKey(configKey)
  return {
    strategy: 'double_ma',
    vt_symbol: vt,
    fast_window: String(fast),
    slow_window: String(slow),
  }
}

export function buildEnqueueRunBody(
  mode: BoardSignalMode,
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
