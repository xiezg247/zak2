import assert from 'node:assert/strict'
import {
  parseFastSlowFromConfigKey,
  buildAlignedBacktestQuery,
  buildEnqueueRunBody,
  BOARD_BT_START,
  BOARD_BT_END,
  BOARD_BT_CAPITAL,
} from '../src/lib/boardBacktestParams.ts'

assert.deepEqual(parseFastSlowFromConfigKey('double_ma:5:10'), { fast: 5, slow: 10 })
assert.deepEqual(parseFastSlowFromConfigKey('bad'), { fast: 5, slow: 20 })

const q = buildAlignedBacktestQuery('trend_ma', '600519.SSE', 'x')
assert.equal(q.strategy, 'trend_ma')
assert.equal(q.fast_window, '20')
assert.equal(q.adx_period, '14')

const body = buildEnqueueRunBody('heuristic_v2', '600519.SSE', 'AshareShortBreakoutStrategy:5:10')
assert.equal(body.strategy, 'double_ma')
assert.equal(body.fast_window, 5)
assert.equal(body.slow_window, 10)
assert.equal(body.interval, 'd')
assert.equal(body.start_date, BOARD_BT_START)
assert.equal(body.end_date, BOARD_BT_END)
assert.equal(body.capital, BOARD_BT_CAPITAL)
assert.equal('rate' in body, false)

const q2 = buildAlignedBacktestQuery('double_ma', '1.SSE', 'double_ma:8:21')
assert.equal(q2.strategy, 'double_ma')
assert.equal(q2.fast_window, '8')
assert.equal(q2.slow_window, '21')

console.log('boardBacktestParams ok')
