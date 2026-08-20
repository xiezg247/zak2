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

const qDon = buildAlignedBacktestQuery('donchian', '1.SSE', 'donchian:20:10')
assert.equal(qDon.strategy, 'donchian')
assert.equal(qDon.entry_window, '20')
assert.equal(qDon.exit_window, '10')

const bodyRsi = buildEnqueueRunBody('rsi_reversal', '1.SSE', 'rsi_reversal:14:30:70')
assert.equal(bodyRsi.strategy, 'rsi_reversal')
assert.equal(bodyRsi.rsi_period, 14)
assert.equal(bodyRsi.oversold, 30)
assert.equal(bodyRsi.overbought, 70)

const qBoll = buildAlignedBacktestQuery('bollinger', '1.SSE', 'bollinger:20:2')
assert.equal(qBoll.strategy, 'bollinger')
assert.equal(qBoll.boll_period, '20')
assert.equal(qBoll.boll_dev, '2')

const bodyMa = buildEnqueueRunBody('ma_band', '1.SSE', 'ma_band:5:10:20:60')
assert.equal(bodyMa.strategy, 'ma_band')
assert.equal(bodyMa.ma_fast, 5)
assert.equal(bodyMa.ma_long, 60)

const qAtr = buildAlignedBacktestQuery('atr_breakout', '1.SSE', 'atr_breakout:20:14:2')
assert.equal(qAtr.strategy, 'atr_breakout')
assert.equal(qAtr.channel_period, '20')
assert.equal(qAtr.atr_mult, '2')

console.log('boardBacktestParams ok')
