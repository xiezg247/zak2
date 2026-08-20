export type * from './types'
import { watchlistCoreApi } from './core'
import { watchlistStrategyApi } from './strategy'
import { watchlistMarketDataApi } from './marketData'

/** 兼容门面：按域拆分实现，对外仍统一 `watchlistApi` */
export const watchlistApi = {
  ...watchlistCoreApi,
  ...watchlistStrategyApi,
  ...watchlistMarketDataApi,
}
