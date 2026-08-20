import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import { watchlistApi, type StrategyBoard } from '../api/watchlist'
import { backtestApi } from '../api/backtest'
import { buildAlignedBacktestQuery, buildEnqueueRunBody } from '../lib/boardBacktestParams'
import { confirmDialog } from '../lib/dialog'

const SIGNAL_MODE_KEY = 'zak2:watchlist:signal_mode'
const DEFAULT_MODE = 'heuristic_v2'

const FALLBACK_MODES: { value: string; label: string }[] = [
  { value: 'heuristic_v2', label: '启发式确认' },
  { value: 'double_ma', label: '双均线' },
  { value: 'trend_ma', label: '趋势双均线（ADX）' },
  { value: 'medium_swing', label: '中线波段（MACD）' },
]

function loadSignalMode(): string {
  try {
    return localStorage.getItem(SIGNAL_MODE_KEY) || DEFAULT_MODE
  } catch {
    /* ignore */
  }
  return DEFAULT_MODE
}

function saveSignalMode(mode: string) {
  localStorage.setItem(SIGNAL_MODE_KEY, mode)
}

/**
 * 策略看盘（原看板页）状态与逻辑：策略下拉、实时信号、信号名单、风控、同参回测。
 * 由宿主页面（自选页）统一驱动刷新与轮询。
 */
export function useStrategyBoard() {
  const router = useRouter()

  const board = ref<StrategyBoard | null>(null)
  const boardError = ref('')
  const enqueueing = ref(false)
  const activeSignalVt = ref('')
  const signalAdd = ref('')
  const signalError = ref('')
  const signalMsg = ref('')
  const signalMode = ref<string>(loadSignalMode())
  const strategyOptions = ref<{ value: string; label: string }[]>([])

  const riskForm = ref({
    total_capital: '',
    stop_loss_pct: '',
    caution_float_pct: '',
  })
  const prefsReady = ref(false)
  const riskError = ref('')
  const riskMsg = ref('')
  const riskSaving = ref(false)

  const panelSymbols = computed(() => board.value?.panel_symbols || [])
  const panelMax = 10

  function applyRiskPrefs(prefs: {
    total_capital: number | null
    stop_loss_pct: number
    caution_float_pct: number
  }) {
    riskForm.value = {
      total_capital: prefs.total_capital != null ? String(prefs.total_capital) : '',
      stop_loss_pct: String(Number((prefs.stop_loss_pct * 100).toFixed(4))),
      caution_float_pct: String(prefs.caution_float_pct),
    }
    prefsReady.value = true
  }

  function signalClass(sig: string) {
    if (sig === 'buy') return 'up'
    if (sig === 'sell') return 'down'
    return ''
  }

  async function loadStrategies() {
    try {
      const list = await backtestApi.strategies()
      strategyOptions.value = [
        { value: DEFAULT_MODE, label: '启发式确认' },
        ...list.filter((s) => s.implemented).map((s) => ({ value: s.id, label: s.name })),
      ]
    } catch {
      // 接口不可用时回退内置模式，保证下拉可用
      strategyOptions.value = FALLBACK_MODES
    }
  }

  /** 读取路由 ?signal_mode=，若已知则应用并持久化。返回是否命中。 */
  function applyQueryMode(query: { signal_mode?: unknown }): boolean {
    const sm = typeof query.signal_mode === 'string' ? query.signal_mode : ''
    const known = strategyOptions.value.some((o) => o.value === sm)
    if (known) {
      signalMode.value = sm
      saveSignalMode(sm)
    }
    return known
  }

  async function refreshBoard(quiet = false) {
    if (!quiet) boardError.value = ''
    const loadPrefs = !quiet || !prefsReady.value
    try {
      const [b, prefs] = await Promise.all([
        watchlistApi.strategyBoard({ signalMode: signalMode.value }),
        loadPrefs ? watchlistApi.tradingRisk() : Promise.resolve(null),
      ])
      board.value = b
      if (prefs) applyRiskPrefs(prefs)
    } catch (e) {
      boardError.value = e instanceof Error ? e.message : '策略看板加载失败'
    }
  }

  function onSignalModeChange() {
    saveSignalMode(signalMode.value)
    void refreshBoard()
  }

  function selectVt(vt: string) {
    if (!vt) return
    void router.push({ path: '/watchlist', query: { symbol: vt } })
  }

  function pickSignal(vt: string) {
    activeSignalVt.value = activeSignalVt.value === vt ? '' : vt
  }

  function resolveBoardVtSymbol(): string {
    return activeSignalVt.value || board.value?.signals[0]?.vt_symbol || ''
  }

  function openAlignedBacktest() {
    const vt = resolveBoardVtSymbol()
    if (!vt) {
      boardError.value = '无可用标的，请在信号区选中或等待信号'
      return
    }
    void router.push({
      path: '/backtest',
      query: buildAlignedBacktestQuery(signalMode.value, vt, board.value?.config_key || ''),
    })
  }

  async function enqueueAlignedBacktest() {
    const vt = resolveBoardVtSymbol()
    if (!vt) {
      boardError.value = '无可用标的，请在信号区选中或等待信号'
      return
    }
    const body = buildEnqueueRunBody(signalMode.value, vt, board.value?.config_key || '')
    const ok = await confirmDialog({
      title: '入队回测',
      message: `对 ${vt} 入队 ${body.strategy} ${body.fast_window}/${body.slow_window}，区间 ${body.start_date}～${body.end_date}，资金 ${body.capital}？`,
    })
    if (!ok) return
    enqueueing.value = true
    boardError.value = ''
    try {
      const { job_id } = await backtestApi.start(body)
      void router.push({ path: '/backtest', query: { job_id } })
    } catch (e) {
      boardError.value = e instanceof Error ? e.message : '入队回测失败'
    } finally {
      enqueueing.value = false
    }
  }

  async function saveTradingRisk() {
    if (!prefsReady.value) return
    riskError.value = ''
    riskMsg.value = ''
    const capitalRaw = riskForm.value.total_capital.trim()
    const stopRaw = Number(riskForm.value.stop_loss_pct)
    const cautionRaw = Number(riskForm.value.caution_float_pct)
    if (capitalRaw && !(Number(capitalRaw) > 0)) {
      riskError.value = '总资金须为空或大于 0'
      return
    }
    if (!(stopRaw > 0) || stopRaw > 50) {
      riskError.value = '止损%须在 (0, 50] 范围内'
      return
    }
    if (!(cautionRaw < 0)) {
      riskError.value = '浮亏警戒须为负数（如 -5）'
      return
    }
    riskSaving.value = true
    try {
      const prefs = await watchlistApi.putTradingRisk({
        total_capital: capitalRaw ? Number(capitalRaw) : null,
        stop_loss_pct: stopRaw / 100,
        caution_float_pct: cautionRaw,
      })
      applyRiskPrefs(prefs)
      riskMsg.value = '风控偏好已保存'
      await refreshBoard()
    } catch (e) {
      riskError.value = e instanceof Error ? e.message : '保存失败'
    } finally {
      riskSaving.value = false
    }
  }

  async function addToSignalPanel(raw?: string) {
    signalError.value = ''
    signalMsg.value = ''
    const symbol = (raw || signalAdd.value || '').trim()
    if (!symbol) {
      signalError.value = '请填写代码或先在信号区选中'
      return
    }
    try {
      await watchlistApi.addSignalPanelMember(symbol)
      signalAdd.value = ''
      signalMsg.value = `已加入信号名单：${symbol}`
      await refreshBoard()
    } catch (e) {
      signalError.value = e instanceof Error ? e.message : '加入失败'
    }
  }

  async function removeFromSignalPanel(vt: string) {
    signalError.value = ''
    try {
      await watchlistApi.removeSignalPanelMember(vt)
      signalMsg.value = `已移出信号名单：${vt}`
      await refreshBoard()
    } catch (e) {
      signalError.value = e instanceof Error ? e.message : '移除失败'
    }
  }

  return {
    board,
    boardError,
    enqueueing,
    activeSignalVt,
    signalAdd,
    signalError,
    signalMsg,
    signalMode,
    strategyOptions,
    riskForm,
    prefsReady,
    riskError,
    riskMsg,
    riskSaving,
    panelSymbols,
    panelMax,
    signalClass,
    loadStrategies,
    refreshBoard,
    onSignalModeChange,
    selectVt,
    pickSignal,
    openAlignedBacktest,
    enqueueAlignedBacktest,
    saveTradingRisk,
    addToSignalPanel,
    removeFromSignalPanel,
    applyQueryMode,
  }
}
