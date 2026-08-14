export type BoardSignalMode = 'heuristic_v2' | 'double_ma' | 'trend_ma'

export {
  BOARD_BT_START,
  BOARD_BT_END,
  BOARD_BT_CAPITAL,
  parseFastSlowFromConfigKey,
  buildAlignedBacktestQuery,
  buildEnqueueRunBody,
} from './boardBacktestParams.mjs'
