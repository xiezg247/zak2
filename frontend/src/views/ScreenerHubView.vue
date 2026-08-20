<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import AppShell from '../components/AppShell.vue'
import PagerBar from '../components/PagerBar.vue'
import { getToken } from '../api/client'
import { fmtDateTime } from '../lib/format'
import {
  jobsApi,
  screenerApi,
  type BuiltinRecipe,
  type HardFilterTemplate,
  type PatternMeta,
  type Preset,
  type RecipeWeightItem,
  type RecipeWeights,
  type RunDetail,
  type RunSummary,
  type Scheme,
} from '../api/screener'
import { watchlistApi } from '../api/watchlist'

const WEIGHT_EDITABLE = new Set(['intraday_multi', 'post_close_multi', 'ultra_short_unified'])

const route = useRoute()
const tab = ref<'condition' | 'recipe' | 'pattern' | 'peer'>('condition')
const presets = ref<Preset[]>([])
const templates = ref<HardFilterTemplate[]>([])
const recipes = ref<BuiltinRecipe[]>([])
const patterns = ref<PatternMeta[]>([])
const schemes = ref<Scheme[]>([])
const selectedPreset = ref('涨幅榜')
const selectedRecipe = ref('intraday_multi')
const selectedPattern = ref('ma_bull')
const peerSymbol = ref('600519.SSE')
const leaderVariant = ref<'mainline' | 'all_market'>('mainline')
const hardTemplate = ref('balanced')
const topN = ref(50)
const maxScan = ref(800)
const minChange = ref<number | null>(null)
const maxChange = ref<number | null>(null)
const minTurnover = ref<number | null>(null)
const maxTurnover = ref<number | null>(null)
const schemeName = ref('')
const selectedSchemeId = ref('')
const dataStatus = ref('')
const running = ref(false)
const statusText = ref('')
const error = ref('')
const current = ref<RunDetail | null>(null)
const history = ref<RunSummary[]>([])
const historyPage = ref(1)
const historyPages = ref(0)
const historyTotal = ref(0)
const historyBusy = ref(false)
const runBusy = ref(false)
const historyErr = ref('')
const showDiffDetail = ref(false)
const weightOpen = ref(true)
const weightItems = ref<RecipeWeightItem[]>([])
const weightDraft = ref<Record<string, number>>({})
const weightBusy = ref(false)
const weightErr = ref('')
const industryOptions = ref<string[]>([])
const selectedIndustries = ref<string[]>([])
const industryOpen = ref(false)
const industryErr = ref('')

const rows = computed(() => current.value?.result?.rows || [])

type ResultSortKey = 'last_price' | 'change_pct' | 'turnover_rate' | 'volume_ratio' | 'score' | null

const resultFilter = ref('')
const sortKey = ref<ResultSortKey>(null)
const sortDir = ref<'asc' | 'desc'>('desc')

function rowNum(row: Record<string, unknown>, key: string): number | null {
  const v = Number(row[key])
  return Number.isFinite(v) ? v : null
}

function rowScore(row: Record<string, unknown>): number | null {
  for (const k of ['similarity_score', 'pattern_score', 'leader_score', 'score'] as const) {
    const v = rowNum(row, k)
    if (v != null) return v
  }
  return null
}

function cmpNullable(
  a: number | null | undefined,
  b: number | null | undefined,
  dir: 'asc' | 'desc',
): number {
  const aMissing = a == null || Number.isNaN(a)
  const bMissing = b == null || Number.isNaN(b)
  if (aMissing && bMissing) return 0
  if (aMissing) return 1
  if (bMissing) return -1
  const d = (a as number) - (b as number)
  return dir === 'asc' ? d : -d
}

function toggleSort(key: Exclude<ResultSortKey, null>) {
  if (sortKey.value === key) {
    sortDir.value = sortDir.value === 'asc' ? 'desc' : 'asc'
  } else {
    sortKey.value = key
    sortDir.value = 'desc'
  }
}

function clearSort() {
  sortKey.value = null
}

function toggleColSort(key: string) {
  toggleSort(key as Exclude<ResultSortKey, null>)
}

function colSortMark(key: string): string {
  return sortMark(key as Exclude<ResultSortKey, null>)
}

function sortMark(key: Exclude<ResultSortKey, null>): string {
  if (sortKey.value !== key) return ''
  return sortDir.value === 'asc' ? ' ▲' : ' ▼'
}

function sortValue(row: Record<string, unknown>, key: Exclude<ResultSortKey, null>): number | null {
  if (key === 'score') return rowScore(row)
  return rowNum(row, key)
}

const displayedRows = computed(() => {
  const q = resultFilter.value.trim().toLowerCase()
  let list = rows.value as Record<string, unknown>[]
  if (q) {
    list = list.filter((row) => {
      const vt = String(row.vt_symbol || row.symbol || '').toLowerCase()
      const name = String(row.name || '').toLowerCase()
      const ind = String(row.industry || '').toLowerCase()
      return vt.includes(q) || name.includes(q) || ind.includes(q)
    })
  }
  const key = sortKey.value
  if (!key) return list
  const dir = sortDir.value
  return [...list].sort((a, b) => cmpNullable(sortValue(a, key), sortValue(b, key), dir))
})

type ColGroup = {
  label: string
  cls?: string
  cols: { key: string; label: string; sortable?: boolean; hint?: boolean }[]
}

const COL_GROUPS: ColGroup[] = [
  {
    label: '标的',
    cols: [
      { key: 'symbol', label: '代码' },
      { key: 'name', label: '名称' },
      { key: 'industry', label: '行业' },
    ],
  },
  {
    label: '行情',
    cls: 'g-quote',
    cols: [
      { key: 'last_price', label: '现价', sortable: true },
      { key: 'change_pct', label: '涨幅%', sortable: true },
      { key: 'turnover_rate', label: '换手%', sortable: true },
      { key: 'volume_ratio', label: '量比', sortable: true },
    ],
  },
  {
    label: '盘口',
    cls: 'g-tape',
    cols: [
      { key: 'limit_times', label: '连板' },
      { key: 'leader_tier', label: '分层' },
    ],
  },
  {
    label: '基本面',
    cls: 'g-fund',
    cols: [
      { key: 'pe_ttm', label: 'PE' },
      { key: 'total_mv_yi', label: '市值亿' },
    ],
  },
  {
    label: '资金',
    cls: 'g-flow',
    cols: [{ key: 'net_mf_wan', label: '净流入万' }],
  },
  {
    label: '评分',
    cls: 'g-score',
    cols: [
      { key: 'score', label: '得分', sortable: true },
      { key: 'pattern_hint', label: '形态说明', hint: true },
    ],
  },
]

const flatCols = COL_GROUPS.flatMap((g) => g.cols)

const selectedVts = ref<Record<string, true>>({})
const batchBusy = ref(false)

function rowVt(row: Record<string, unknown>): string {
  return String(row.vt_symbol || row.symbol || '').trim()
}

function clearSelected() {
  selectedVts.value = {}
}

function isSelected(vt: string): boolean {
  return !!selectedVts.value[vt]
}

function toggleVt(vt: string) {
  if (!vt) return
  const next = { ...selectedVts.value }
  if (next[vt]) delete next[vt]
  else next[vt] = true
  selectedVts.value = next
}

const selectedCount = computed(() => Object.keys(selectedVts.value).length)

const allDisplayedSelected = computed(() => {
  const list = displayedRows.value as Record<string, unknown>[]
  if (!list.length) return false
  return list.every((row) => {
    const vt = rowVt(row)
    return vt && isSelected(vt)
  })
})

function toggleSelectAllDisplayed() {
  const list = displayedRows.value as Record<string, unknown>[]
  if (allDisplayedSelected.value) {
    const next = { ...selectedVts.value }
    for (const row of list) {
      const vt = rowVt(row)
      if (vt) delete next[vt]
    }
    selectedVts.value = next
    return
  }
  const next = { ...selectedVts.value }
  for (const row of list) {
    const vt = rowVt(row)
    if (vt) next[vt] = true
  }
  selectedVts.value = next
}

function pruneSelectedToDisplayed() {
  const allow = new Set(
    (displayedRows.value as Record<string, unknown>[]).map(rowVt).filter(Boolean),
  )
  const next: Record<string, true> = {}
  for (const vt of Object.keys(selectedVts.value)) {
    if (allow.has(vt)) next[vt] = true
  }
  selectedVts.value = next
}

watch(displayedRows, () => pruneSelectedToDisplayed())

const industry = computed(() => current.value?.result?.industry_dist || [])
const diff = computed(() => current.value?.result?.diff)
const isCustom = computed(() => selectedPreset.value === '自定义筛选')
const isRadarLeader = computed(() => selectedRecipe.value === 'radar_leader')
const isWeightEditable = computed(() => WEIGHT_EDITABLE.has(selectedRecipe.value))
const activeTemplate = computed(() => templates.value.find((t) => t.id === hardTemplate.value))

function applyWeights(w: RecipeWeights) {
  weightItems.value = w.items
  weightDraft.value = { ...w.weights }
}

async function loadRecipeWeights() {
  if (!isWeightEditable.value) {
    weightItems.value = []
    weightDraft.value = {}
    weightErr.value = ''
    return
  }
  weightBusy.value = true
  weightErr.value = ''
  try {
    const w = await screenerApi.recipeWeights(selectedRecipe.value)
    applyWeights(w)
  } catch (e) {
    weightItems.value = []
    weightDraft.value = {}
    weightErr.value = e instanceof Error ? e.message : '权重加载失败'
  } finally {
    weightBusy.value = false
  }
}

async function saveRecipeWeights() {
  if (!isWeightEditable.value) return
  if (weightItems.value.length === 0) {
    weightErr.value = '权重尚未加载，无法保存'
    return
  }
  const payload: Record<string, number> = {}
  for (const item of weightItems.value) {
    const v = weightDraft.value[item.key]
    if (typeof v === 'number' && Number.isFinite(v)) {
      payload[item.key] = v
    }
  }
  if (Object.keys(payload).length === 0) {
    weightErr.value = '没有可保存的权重，请先加载或填写'
    return
  }
  weightBusy.value = true
  weightErr.value = ''
  try {
    const out = await screenerApi.putRecipeWeights(selectedRecipe.value, payload)
    applyWeights(out)
    statusText.value = '权重已保存'
  } catch (e) {
    weightErr.value = e instanceof Error ? e.message : '保存失败'
  } finally {
    weightBusy.value = false
  }
}

async function resetRecipeWeights() {
  if (!isWeightEditable.value) return
  weightBusy.value = true
  weightErr.value = ''
  try {
    const out = await screenerApi.putRecipeWeights(selectedRecipe.value, {})
    applyWeights(out)
    statusText.value = '已恢复默认权重'
  } catch (e) {
    weightErr.value = e instanceof Error ? e.message : '恢复失败'
  } finally {
    weightBusy.value = false
  }
}

function rowSealLabel(row: Record<string, unknown>): string {
  const label = String(row.seal_time_label || '').trim()
  if (label) return label
  const ft = String(row.first_time || '').trim()
  if (ft.length >= 4) return `${ft.slice(0, 2)}:${ft.slice(2, 4)} 封板`
  return ''
}

function emptyToNull(v: number | null): number | null {
  if (v === null || Number.isNaN(v as number)) return null
  return v
}

function hardFilterOverride(): { allowed_industries: string } | undefined {
  const picked = selectedIndustries.value.filter((s) => s.trim())
  if (!picked.length) return undefined
  return { allowed_industries: picked.join(',') }
}

function mergeHardFilter(body: Record<string, unknown>) {
  const hf = hardFilterOverride()
  if (hf) body.hard_filter = hf
  return body
}

function toggleIndustry(name: string) {
  const idx = selectedIndustries.value.indexOf(name)
  if (idx >= 0) {
    selectedIndustries.value = selectedIndustries.value.filter((s) => s !== name)
  } else {
    selectedIndustries.value = [...selectedIndustries.value, name]
  }
}

function isIndustrySelected(name: string) {
  return selectedIndustries.value.includes(name)
}

function parseAllowedIndustries(raw: unknown) {
  const text = String(raw || '').trim()
  if (!text) {
    selectedIndustries.value = []
    return
  }
  selectedIndustries.value = text
    .split(',')
    .map((s) => s.trim())
    .filter(Boolean)
}

function buildConditionBody() {
  const body: Record<string, unknown> = {
    preset: selectedPreset.value,
    top_n: topN.value,
    hard_filter_template: hardTemplate.value,
  }
  if (isCustom.value) {
    body.min_change_pct = emptyToNull(minChange.value)
    body.max_change_pct = emptyToNull(maxChange.value)
    body.min_turnover_rate = emptyToNull(minTurnover.value)
    body.max_turnover_rate = emptyToNull(maxTurnover.value)
  }
  return mergeHardFilter(body)
}

function buildSchemeConfig() {
  const hf = hardFilterOverride()
  let config: Record<string, unknown>
  if (tab.value === 'recipe') {
    config = {
      tab: 'recipe',
      recipe_id: selectedRecipe.value,
      top_n: topN.value,
      hard_filter_template: hardTemplate.value,
      variant: isRadarLeader.value ? leaderVariant.value : undefined,
    }
  } else if (tab.value === 'pattern') {
    config = {
      tab: 'pattern',
      pattern_id: selectedPattern.value,
      top_n: topN.value,
      max_scan: maxScan.value,
      hard_filter_template: hardTemplate.value,
    }
  } else if (tab.value === 'peer') {
    config = {
      tab: 'peer',
      vt_symbol: peerSymbol.value,
      top_n: Math.min(topN.value, 100),
      hard_filter_template: hardTemplate.value,
    }
  } else {
    config = {
      tab: 'condition',
      preset: selectedPreset.value,
      top_n: topN.value,
      hard_filter_template: hardTemplate.value,
    }
    if (isCustom.value) {
      config.min_change_pct = emptyToNull(minChange.value)
      config.max_change_pct = emptyToNull(maxChange.value)
      config.min_turnover_rate = emptyToNull(minTurnover.value)
      config.max_turnover_rate = emptyToNull(maxTurnover.value)
    }
  }
  if (hf) config.allowed_industries = hf.allowed_industries
  return config
}

async function loadIndustries() {
  industryErr.value = ''
  try {
    const { items } = await screenerApi.industries()
    industryOptions.value = items || []
  } catch (e) {
    industryOptions.value = []
    industryErr.value = e instanceof Error ? e.message : '行业列表加载失败'
  }
}

async function loadMeta() {
  const [p, t, r, pat, ds, s] = await Promise.all([
    screenerApi.presets(),
    screenerApi.hardFilterTemplates(),
    screenerApi.builtinRecipes(),
    screenerApi.patterns(),
    screenerApi.dataStatus(),
    screenerApi.schemes(),
  ])
  presets.value = p
  templates.value = t
  recipes.value = r
  patterns.value = pat
  schemes.value = s
  if (pat.length && !pat.some((x) => x.pattern_id === selectedPattern.value)) {
    selectedPattern.value = pat[0].pattern_id
  }
  const redisOk = ds.redis?.available
  const count = ds.redis?.quote_count ?? 0
  dataStatus.value = redisOk
    ? `Redis 行情 ${count} 只 · 更新 ${fmtDateTime(ds.redis.updated_at) || '—'}`
    : 'Redis 不可用'
}

async function loadHistory() {
  historyBusy.value = true
  historyErr.value = ''
  try {
    const p = await screenerApi.runsPage(historyPage.value, 20)
    history.value = p.items
    historyTotal.value = p.total
    historyPages.value = p.pages
  } catch (e) {
    historyErr.value = e instanceof Error ? e.message : '加载历史失败'
  } finally {
    historyBusy.value = false
  }
}

async function goHistoryPage(p: number) {
  historyPage.value = p
  await loadHistory()
}

async function pollJob(jobId: string) {
  for (let i = 0; i < 120; i++) {
    const job = await jobsApi.get(jobId)
    statusText.value = `${job.status} · ${Math.round(job.progress * 100)}%`
    if (job.status === 'success' && job.result_ref) {
      current.value = await screenerApi.run(job.result_ref)
      clearSelected()
      await loadHistory()
      return
    }
    if (job.status === 'failed') {
      throw new Error(job.error || '任务失败')
    }
    await new Promise((r) => setTimeout(r, 500))
  }
  throw new Error('任务超时')
}

async function runScreen() {
  error.value = ''
  running.value = true
  statusText.value = '提交中…'
  try {
    if (tab.value === 'condition') {
      const { job_id } = await screenerApi.runCondition(buildConditionBody())
      await pollJob(job_id)
    } else if (tab.value === 'pattern') {
      const { job_id } = await screenerApi.runPattern(
        mergeHardFilter({
          pattern_id: selectedPattern.value,
          top_n: Math.min(topN.value, 100),
          max_scan: maxScan.value,
          hard_filter_template: hardTemplate.value,
        }),
      )
      await pollJob(job_id)
    } else if (tab.value === 'peer') {
      const vt = peerSymbol.value.trim()
      if (!vt) throw new Error('请填写标杆代码')
      const { job_id } = await screenerApi.runReferencePeer(
        mergeHardFilter({
          vt_symbol: vt,
          top_n: Math.min(topN.value, 100),
          hard_filter_template: hardTemplate.value,
        }),
      )
      await pollJob(job_id)
    } else {
      const body: Record<string, unknown> = {
        recipe_id: selectedRecipe.value,
        top_n: topN.value,
        hard_filter_template: hardTemplate.value,
      }
      if (isRadarLeader.value) body.variant = leaderVariant.value
      const { job_id } = await screenerApi.runRecipe(mergeHardFilter(body))
      await pollJob(job_id)
    }
    statusText.value = '完成'
  } catch (e) {
    error.value = e instanceof Error ? e.message : '运行失败'
    statusText.value = '失败'
  } finally {
    running.value = false
  }
}

async function saveScheme() {
  const name = schemeName.value.trim()
  if (!name) {
    error.value = '请填写方案名称'
    return
  }
  error.value = ''
  try {
    const created = await screenerApi.createScheme(name, buildSchemeConfig())
    schemes.value = [created, ...schemes.value]
    selectedSchemeId.value = created.id
    schemeName.value = ''
    statusText.value = `已保存方案「${created.name}」`
  } catch (e) {
    error.value = e instanceof Error ? e.message : '保存失败'
  }
}

function applyScheme(s: Scheme) {
  selectedSchemeId.value = s.id
  const cfg = s.config || {}
  const tabVal = String(cfg.tab || 'condition')
  tab.value =
    tabVal === 'recipe'
      ? 'recipe'
      : tabVal === 'pattern'
        ? 'pattern'
        : tabVal === 'peer'
          ? 'peer'
          : 'condition'
  if (tab.value === 'recipe') {
    selectedRecipe.value = String(cfg.recipe_id || 'intraday_multi')
    if (cfg.variant === 'all_market' || cfg.variant === 'mainline') {
      leaderVariant.value = cfg.variant
    }
  } else if (tab.value === 'pattern') {
    selectedPattern.value = String(cfg.pattern_id || 'ma_bull')
    maxScan.value = Number(cfg.max_scan || 800)
  } else if (tab.value === 'peer') {
    peerSymbol.value = String(cfg.vt_symbol || '600519.SSE')
  } else {
    selectedPreset.value = String(cfg.preset || '涨幅榜')
    minChange.value = cfg.min_change_pct != null ? Number(cfg.min_change_pct) : null
    maxChange.value = cfg.max_change_pct != null ? Number(cfg.max_change_pct) : null
    minTurnover.value = cfg.min_turnover_rate != null ? Number(cfg.min_turnover_rate) : null
    maxTurnover.value = cfg.max_turnover_rate != null ? Number(cfg.max_turnover_rate) : null
  }
  topN.value = Number(cfg.top_n || 50)
  hardTemplate.value = String(cfg.hard_filter_template || 'balanced')
  parseAllowedIndustries(cfg.allowed_industries)
  statusText.value = `已加载方案「${s.name}」`
}

async function deleteScheme(id: string) {
  await screenerApi.deleteScheme(id)
  schemes.value = schemes.value.filter((s) => s.id !== id)
  if (selectedSchemeId.value === id) selectedSchemeId.value = ''
}

async function openRun(id: string) {
  runBusy.value = true
  error.value = ''
  try {
    current.value = await screenerApi.run(id)
    resultFilter.value = ''
    clearSelected()
    showDiffDetail.value = false
  } catch (e) {
    error.value = e instanceof Error ? e.message : '打开运行记录失败'
  } finally {
    runBusy.value = false
  }
}

function applyDiffFilter(vt: string) {
  resultFilter.value = vt
}

function toggleDiffDetail() {
  showDiffDetail.value = !showDiffDetail.value
}

async function addToWatchlist(row: Record<string, unknown>) {
  const vt = String(row.vt_symbol || row.symbol || '')
  if (!vt) return
  try {
    await watchlistApi.add(vt, String(row.name || ''))
    statusText.value = `已加入自选 ${vt}`
  } catch (e) {
    error.value = e instanceof Error ? e.message : '加入自选失败'
  }
}

async function addSelectedToWatchlist() {
  const list = displayedRows.value as Record<string, unknown>[]
  const queue = list.filter((row) => {
    const vt = rowVt(row)
    return vt && isSelected(vt)
  })
  if (!queue.length || batchBusy.value) return
  batchBusy.value = true
  error.value = ''
  let ok = 0
  let skip = 0
  let fail = 0
  try {
    for (const row of queue) {
      const vt = rowVt(row)
      const name = String(row.name || '')
      try {
        await watchlistApi.add(vt, name)
        ok++
      } catch (e) {
        const msg = e instanceof Error ? e.message : ''
        if (msg.includes('已在自选中')) skip++
        else fail++
      }
    }
    statusText.value = `已加入 ${ok} · 已在自选 ${skip} · 失败 ${fail}`
    if (fail > 0) error.value = '部分加入失败，见上方汇总'
  } finally {
    batchBusy.value = false
  }
}

type ScreenerResultRow = Record<string, unknown>

function findPeers(row: ScreenerResultRow) {
  const vt = String(row.vt_symbol || '').trim() || String(row.symbol || '').trim()
  if (!vt) return
  peerSymbol.value = vt
  tab.value = 'peer'
  void runScreen()
}

function exportCsv() {
  if (!current.value) return
  const url = screenerApi.exportCsvUrl(current.value.id)
  const a = document.createElement('a')
  a.download = `screener_${current.value.id}.csv`
  void fetch(url, { headers: { Authorization: `Bearer ${getToken()}` } })
    .then((r) => r.blob())
    .then((blob) => {
      a.href = URL.createObjectURL(blob)
      a.click()
      URL.revokeObjectURL(a.href)
    })
}

watch(selectedPreset, (name) => {
  if (name !== '自定义筛选') {
    minChange.value = null
    maxChange.value = null
    minTurnover.value = null
    maxTurnover.value = null
  } else if (minChange.value == null && maxChange.value == null) {
    minChange.value = 2
    maxChange.value = 9
    minTurnover.value = 1
  }
})

watch(
  [selectedRecipe, tab],
  () => {
    if (tab.value === 'recipe') void loadRecipeWeights()
    else {
      weightItems.value = []
      weightDraft.value = {}
      weightErr.value = ''
    }
  },
  { immediate: true },
)

onMounted(async () => {
  try {
    const qRecipe = typeof route.query.recipe === 'string' ? route.query.recipe : ''
    const qVariant = typeof route.query.variant === 'string' ? route.query.variant : ''
    if (qRecipe) {
      tab.value = 'recipe'
      selectedRecipe.value = qRecipe
      if (qRecipe === 'radar_leader') topN.value = 12
      if (qRecipe === 'radar_resonance') topN.value = 20
    }
    if (qVariant === 'mainline' || qVariant === 'all_market') leaderVariant.value = qVariant
    await Promise.all([loadMeta(), loadHistory(), loadIndustries()])
  } catch (e) {
    error.value = e instanceof Error ? e.message : '加载失败'
  }
})
</script>

<template>
  <AppShell title="选股 Hub" :subtitle="dataStatus" active="screener">
    <div class="workspace">
      <section class="left">
        <div class="cfg-card">
          <div class="tabs">
            <button :class="{ on: tab === 'condition' }" type="button" @click="tab = 'condition'">
              条件选股
            </button>
            <button :class="{ on: tab === 'recipe' }" type="button" @click="tab = 'recipe'">
              多因子配方
            </button>
            <button :class="{ on: tab === 'pattern' }" type="button" @click="tab = 'pattern'">
              形态
            </button>
            <button :class="{ on: tab === 'peer' }" type="button" @click="tab = 'peer'">
              对标
            </button>
          </div>

          <div v-if="tab === 'condition'" class="block">
            <label>
              Preset
              <select v-model="selectedPreset">
                <option
                  v-for="p in presets"
                  :key="p.name"
                  :value="p.name"
                  :disabled="!p.implemented"
                >
                  {{ p.name }}{{ p.implemented ? '' : '（未实现）' }}
                </option>
              </select>
            </label>
            <div v-if="isCustom" class="custom-grid">
              <label>
                涨幅% ≥
                <input v-model.number="minChange" type="number" step="0.1" placeholder="不限" />
              </label>
              <label>
                涨幅% ≤
                <input v-model.number="maxChange" type="number" step="0.1" placeholder="不限" />
              </label>
              <label>
                换手% ≥
                <input v-model.number="minTurnover" type="number" step="0.1" placeholder="不限" />
              </label>
              <label>
                换手% ≤
                <input v-model.number="maxTurnover" type="number" step="0.1" placeholder="不限" />
              </label>
            </div>
          </div>
          <div v-else-if="tab === 'recipe'" class="block">
            <label>
              内置配方
              <select v-model="selectedRecipe">
                <option
                  v-for="r in recipes"
                  :key="r.recipe_id"
                  :value="r.recipe_id"
                  :disabled="!r.implemented"
                >
                  {{ r.name }}
                </option>
              </select>
            </label>
            <label v-if="isRadarLeader">
              变体
              <select v-model="leaderVariant">
                <option value="mainline">主线龙头</option>
                <option value="all_market">全市场龙头</option>
              </select>
            </label>
            <div v-if="isWeightEditable" class="weight-block">
              <div class="weight-head">
                <strong>因子权重</strong>
                <button class="ghost tiny-btn" type="button" @click="weightOpen = !weightOpen">
                  {{ weightOpen ? '收起' : '展开' }}
                </button>
              </div>
              <div v-if="weightOpen" class="weight-panel">
                <div v-for="item in weightItems" :key="item.key" class="weight-row">
                  <label :for="`rw-${item.key}`">{{ item.label }}</label>
                  <input
                    :id="`rw-${item.key}`"
                    v-model.number="weightDraft[item.key]"
                    type="number"
                    min="0"
                    max="5"
                    step="0.01"
                    :disabled="weightBusy"
                  />
                </div>
                <p v-if="weightErr" class="weight-err">{{ weightErr }}</p>
                <div class="weight-actions">
                  <button
                    class="primary tiny-primary"
                    type="button"
                    :disabled="weightBusy || weightItems.length === 0"
                    @click="saveRecipeWeights"
                  >
                    保存
                  </button>
                  <button
                    class="ghost"
                    type="button"
                    :disabled="weightBusy"
                    @click="resetRecipeWeights"
                  >
                    恢复默认
                  </button>
                </div>
                <p class="hint muted">保存后按比例归一化；空值不会清空已存权重</p>
              </div>
            </div>
          </div>
          <div v-else-if="tab === 'pattern'" class="block">
            <label>
              形态
              <select v-model="selectedPattern">
                <option v-for="p in patterns" :key="p.pattern_id" :value="p.pattern_id">
                  {{ p.name }}
                </option>
              </select>
            </label>
            <p class="hint muted">
              {{
                patterns.find((p) => p.pattern_id === selectedPattern)?.description ||
                'Redis 行情池 ∩ 日 K'
              }}
            </p>
            <label>
              扫描上限
              <input v-model.number="maxScan" type="number" min="50" max="1200" />
            </label>
          </div>
          <div v-else-if="tab === 'peer'" class="block">
            <label>
              标杆代码
              <input v-model="peerSymbol" placeholder="600519.SSE" @keyup.enter="runScreen" />
            </label>
            <p class="hint muted">
              同业 30% + 估值 25% + 近5日动量 15% + 近20日动量 15% + 换手 15%（需 Tushare）
            </p>
          </div>

          <button class="primary run-btn" type="button" :disabled="running" @click="runScreen">
            {{ running ? '运行中…' : '运行选股' }}
          </button>
        </div>

        <div class="cfg-card">
          <div class="card-title">
            <strong>硬过滤</strong>
            <span class="muted">{{ activeTemplate?.name || '—' }}</span>
          </div>
          <label>
            过滤模板
            <select v-model="hardTemplate">
              <option v-for="t in templates" :key="t.id" :value="t.id">{{ t.name }}</option>
            </select>
          </label>
          <p v-if="activeTemplate" class="hint muted">
            成交额 ≥ {{ activeTemplate.prefs.min_amount_wan }} 万 · 市值 ≥
            {{ activeTemplate.prefs.min_total_mv_yi }} 亿
            <template v-if="activeTemplate.prefs.exclude_limit_board"> · 排除连板≥2</template>
          </p>
          <div class="industry-block">
            <div class="industry-head">
              <strong>行业白名单</strong>
              <button class="ghost tiny-btn" type="button" @click="industryOpen = !industryOpen">
                {{ industryOpen ? '收起' : '展开' }}
              </button>
            </div>
            <div v-if="industryOpen" class="industry-panel">
              <p v-if="industryErr" class="industry-err">{{ industryErr }}</p>
              <p v-else-if="!industryOptions.length" class="hint muted">
                暂无行业数据，请先同步行业映射
              </p>
              <label v-for="name in industryOptions" :key="name" class="industry-check">
                <input
                  type="checkbox"
                  :checked="isIndustrySelected(name)"
                  @change="toggleIndustry(name)"
                />
                <span>{{ name }}</span>
              </label>
              <p v-if="selectedIndustries.length" class="hint muted">
                已选 {{ selectedIndustries.length }} 个行业；全不选则不限制
              </p>
            </div>
          </div>
          <label>
            Top N
            <input v-model.number="topN" type="number" min="1" max="500" />
          </label>
        </div>

        <div class="cfg-card">
          <div class="card-title">
            <strong>方案</strong>
            <span class="muted">{{ schemes.length }} 个</span>
          </div>
          <div class="row">
            <input v-model="schemeName" placeholder="方案名称" @keyup.enter="saveScheme" />
            <button type="button" class="ghost" @click="saveScheme">保存</button>
          </div>
          <button
            v-for="s in schemes"
            :key="s.id"
            type="button"
            class="hist"
            :class="{ on: selectedSchemeId === s.id }"
            @click="applyScheme(s)"
          >
            <span>{{ s.name }}</span>
            <span class="muted">{{ fmtDateTime(s.updated_at) }}</span>
            <span class="del" @click.stop="deleteScheme(s.id)">删</span>
          </button>
          <p v-if="!schemes.length" class="muted">保存当前配置后可一键加载复跑</p>
        </div>
      </section>

      <section class="middle">
        <div class="cfg-card">
          <div class="history-head">
            <strong>运行历史</strong>
            <span class="muted">{{ historyTotal ? `${historyTotal} 条` : '' }}</span>
            <button
              type="button"
              class="ghost tiny-btn"
              :disabled="historyBusy"
              @click="loadHistory"
            >
              {{ historyBusy ? '刷新中…' : '刷新' }}
            </button>
          </div>
          <p v-if="historyErr" class="err">{{ historyErr }}</p>
          <p v-else-if="!historyBusy && !history.length" class="muted">
            暂无运行记录，点左侧「运行」生成
          </p>
          <button
            v-for="h in history"
            :key="h.id"
            type="button"
            class="hist"
            :class="{ on: current?.id === h.id }"
            :disabled="runBusy"
            @click="openRun(h.id)"
          >
            <span>{{ h.condition }}</span>
            <span class="muted">{{ h.row_count }} 只 · {{ fmtDateTime(h.created_at) }}</span>
          </button>
          <PagerBar
            :page="historyPage"
            :pages="historyPages"
            :total="historyTotal"
            :disabled="historyBusy"
            @change="goHistoryPage"
          />
        </div>
      </section>

      <section class="right">
        <div class="run-status">
          <p v-if="statusText" class="status">{{ statusText }}</p>
          <p v-if="error" class="err">{{ error }}</p>
          <p v-if="!statusText && !error" class="hint muted">
            配置左侧参数后运行；点击表格行「自选 / 找同类」快速操作
          </p>
        </div>

        <div v-if="current" class="toolbar">
          <strong>{{ current.condition }}</strong>
          <span class="muted">扫描 {{ current.total_scanned }} · 命中 {{ current.row_count }}</span>
          <span class="spacer"></span>
          <button type="button" class="ghost" @click="exportCsv">导出 CSV</button>
          <button
            type="button"
            class="ghost"
            :disabled="batchBusy || selectedCount === 0"
            @click="addSelectedToWatchlist"
          >
            {{ batchBusy ? '加入中…' : `加入自选 (${selectedCount})` }}
          </button>
        </div>
        <div v-if="current" class="row filter-row">
          <input v-model="resultFilter" placeholder="过滤代码/名称/行业" />
          <button v-if="sortKey" type="button" class="ghost" @click="clearSort">默认序</button>
        </div>

        <div v-if="diff" class="diff">
          <div class="diff-summary">
            <span class="chip">新增 {{ diff.added.length }}</span>
            <span class="chip">移除 {{ diff.removed.length }}</span>
            <span class="chip">保留 {{ diff.kept.length }}</span>
            <button type="button" class="link" @click="toggleDiffDetail">
              {{ showDiffDetail ? '收起' : '详情' }}
            </button>
          </div>
          <div v-if="showDiffDetail" class="diff-detail">
            <div v-if="diff.added.length" class="diff-group">
              <strong>新增</strong>
              <div class="chips">
                <button
                  v-for="vt in diff.added"
                  :key="'a-' + vt"
                  type="button"
                  class="chip-link mono"
                  @click="applyDiffFilter(vt)"
                >
                  {{ vt }}
                </button>
              </div>
            </div>
            <div v-if="diff.removed.length" class="diff-group">
              <strong>移除</strong>
              <div class="chips">
                <button
                  v-for="vt in diff.removed"
                  :key="'r-' + vt"
                  type="button"
                  class="chip-link mono"
                  @click="applyDiffFilter(vt)"
                >
                  {{ vt }}
                </button>
              </div>
            </div>
            <p v-if="!diff.added.length && !diff.removed.length" class="muted tip">无新增或移除</p>
          </div>
        </div>

        <div class="table-wrap">
          <table>
            <thead>
              <tr class="group-row">
                <th class="sel-col" colspan="2"></th>
                <th v-for="g in COL_GROUPS" :key="g.label" :class="g.cls" :colspan="g.cols.length">
                  {{ g.label }}
                </th>
                <th class="ops-col"></th>
              </tr>
              <tr class="col-row">
                <th class="sel-col">
                  <input
                    type="checkbox"
                    :checked="allDisplayedSelected"
                    :disabled="!displayedRows.length"
                    @change="toggleSelectAllDisplayed"
                  />
                </th>
                <th class="sel-col">#</th>
                <template v-for="c in flatCols" :key="c.key">
                  <th v-if="c.sortable" class="sortable" @click="toggleColSort(c.key)">
                    {{ c.label }}{{ colSortMark(c.key) }}
                  </th>
                  <th v-else :class="{ 'hint-cell': c.hint }">{{ c.label }}</th>
                </template>
                <th class="ops-col"></th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(row, i) in displayedRows" :key="String(row.symbol)">
                <td class="sel-col" @click.stop>
                  <input
                    type="checkbox"
                    :checked="isSelected(rowVt(row))"
                    @change="toggleVt(rowVt(row))"
                  />
                </td>
                <td class="sel-col">{{ i + 1 }}</td>
                <td class="mono">{{ row.vt_symbol || row.symbol }}</td>
                <td>{{ row.name }}</td>
                <td>{{ String(row.industry || '').trim() || '—' }}</td>
                <td class="g-quote">{{ Number(row.last_price || 0).toFixed(2) }}</td>
                <td
                  class="g-quote"
                  :class="{ up: Number(row.change_pct) > 0, down: Number(row.change_pct) < 0 }"
                >
                  {{ Number(row.change_pct || 0).toFixed(2) }}
                </td>
                <td class="g-quote">{{ Number(row.turnover_rate || 0).toFixed(2) }}</td>
                <td class="g-quote">{{ Number(row.volume_ratio || 0).toFixed(2) }}</td>
                <td class="g-tape">
                  {{ row.limit_times != null ? Number(row.limit_times).toFixed(0) : '—' }}
                  <span v-if="rowSealLabel(row)" class="muted seal-tag">
                    · {{ rowSealLabel(row) }}</span
                  >
                </td>
                <td class="g-tape">{{ row.leader_tier_label || row.leader_tier || '—' }}</td>
                <td class="g-fund">
                  {{ row.pe_ttm != null ? Number(row.pe_ttm).toFixed(2) : '—' }}
                </td>
                <td class="g-fund">
                  {{
                    row.total_mv_yi != null
                      ? Number(row.total_mv_yi).toFixed(1)
                      : row.total_mv
                        ? (Number(row.total_mv) / 10000).toFixed(1)
                        : '—'
                  }}
                </td>
                <td class="g-flow">
                  {{
                    row.net_mf_wan != null
                      ? Number(row.net_mf_wan).toFixed(0)
                      : row.net_mf_amount
                        ? Number(row.net_mf_amount).toFixed(0)
                        : '—'
                  }}
                </td>
                <td class="g-score">
                  {{
                    row.similarity_score != null
                      ? Number(row.similarity_score).toFixed(1)
                      : row.pattern_score != null
                        ? Number(row.pattern_score).toFixed(1)
                        : row.leader_score != null
                          ? Number(row.leader_score).toFixed(1)
                          : row.score != null
                            ? Number(row.score).toFixed(3)
                            : '—'
                  }}
                </td>
                <td
                  class="g-score hint-cell"
                  :title="
                    [
                      row.pattern_hint || row.hit_reason || '',
                      isRadarLeader ? rowSealLabel(row) : '',
                    ]
                      .filter(Boolean)
                      .join(' · ') || ''
                  "
                >
                  <template v-if="row.pattern_hint || row.hit_reason">
                    {{ row.pattern_hint || row.hit_reason }}
                  </template>
                  <template v-else-if="isRadarLeader && rowSealLabel(row)">{{
                    rowSealLabel(row)
                  }}</template>
                  <template v-else>—</template>
                </td>
                <td class="ops-col row-actions">
                  <button type="button" class="link" @click="addToWatchlist(row)">自选</button>
                  <button type="button" class="link" @click="findPeers(row)">找同类</button>
                </td>
              </tr>
              <tr v-if="!displayedRows.length">
                <td :colspan="flatCols.length + 3" class="empty">
                  {{ rows.length === 0 ? '运行选股后在此显示结果' : '无匹配结果' }}
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        <div v-if="industry.length" class="industry">
          <h3>行业分布</h3>
          <div class="chips">
            <span v-for="item in industry.slice(0, 12)" :key="item.industry" class="chip">
              {{ item.industry }} {{ item.count }}
            </span>
          </div>
        </div>
      </section>
    </div>
  </AppShell>
</template>

<style scoped>
.workspace {
  display: grid;
  grid-template-columns: 280px 280px minmax(0, 1fr);
  grid-template-areas: 'left middle right';
  height: 100%;
  min-height: 0;
  background: var(--surface-muted);
}
.left {
  grid-area: left;
  border-right: 1px solid var(--line);
  padding: 14px;
  overflow: auto;
  display: grid;
  gap: 12px;
  align-content: start;
  background: var(--surface-muted);
}
.middle {
  grid-area: middle;
  border-right: 1px solid var(--line);
  padding: 14px;
  overflow: auto;
  display: grid;
  gap: 12px;
  align-content: start;
  background: var(--surface-muted);
}
.cfg-card {
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: 0.75rem;
  box-shadow: var(--shadow-card);
  padding: 12px 14px;
  display: grid;
  gap: 10px;
  align-content: start;
}
.cfg-card > .primary.run-btn {
  margin-top: 2px;
}
.card-title {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  gap: 8px;
  padding-bottom: 8px;
  border-bottom: 1px solid var(--line-soft);
}
.card-title strong {
  font-size: 0.85rem;
  font-weight: 600;
}
.run-btn {
  position: sticky;
  bottom: 0;
  z-index: 2;
  box-shadow:
    0 1px 2px rgba(0, 0, 0, 0.05),
    0 -4px 12px rgba(0, 0, 0, 0.04);
}
.right {
  grid-area: right;
  padding: 16px 24px 24px;
  overflow: auto;
  display: grid;
  gap: 12px;
  align-content: start;
}
.run-status {
  min-height: 20px;
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
  padding: 8px 12px;
  border: 1px solid var(--line);
  border-radius: 0.75rem;
  background: var(--surface);
  box-shadow: var(--shadow-card);
}
.run-status p {
  margin: 0;
}
.tabs {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 6px;
  padding: 4px;
  border-radius: 0.75rem;
  background: var(--surface-muted);
  border: 1px solid var(--line-soft);
}
.tabs button {
  background: transparent;
  border: 1px solid transparent;
  color: var(--ink-muted);
  border-radius: 0.5rem;
  padding: 8px;
  font-size: 0.8125rem;
  transition:
    background 0.15s ease,
    color 0.15s ease;
}
.tabs button:hover {
  color: var(--ink);
}
.tabs button.on {
  background: var(--surface);
  color: var(--brand);
  border-color: var(--brand-soft);
  font-weight: 500;
  box-shadow: var(--shadow-card);
}
.block {
  display: grid;
  gap: 10px;
}
.custom-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
}
.row {
  display: grid;
  grid-template-columns: 1fr auto;
  gap: 8px;
}
.filter-row {
  grid-template-columns: 1fr auto;
}
label {
  display: grid;
  gap: 6px;
  font-size: 0.8rem;
  color: var(--muted);
}
select,
input {
  background: var(--bg-elevated);
  border: 1px solid var(--border);
  border-radius: 0.5rem;
  color: var(--text);
  padding: 8px 10px;
}
.hint {
  margin: 0;
  font-size: 0.75rem;
  line-height: 1.4;
}
.hint-cell {
  max-width: 180px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 0.78rem;
  color: var(--muted);
}
.seal-tag {
  font-size: 0.75rem;
}
.primary {
  background: var(--brand);
  color: var(--brand-foreground);
  border: none;
  border-radius: 0.5rem;
  padding: 10px;
  font-weight: 600;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.05);
}
.primary:disabled {
  opacity: 0.6;
}
.ghost {
  background: transparent;
  border: 1px solid var(--border);
  color: var(--text);
  border-radius: 0.5rem;
  padding: 6px 10px;
}
.link {
  background: none;
  border: none;
  color: var(--accent);
  padding: 0;
}
.row-actions {
  display: flex;
  gap: 8px;
}
.status {
  margin: 0;
  color: var(--muted);
  font-size: 0.85rem;
}
.err {
  margin: 0;
  color: var(--danger);
  font-size: 0.85rem;
}
.history-head h3,
.industry h3 {
  margin: 0 0 8px;
  font-size: 0.9rem;
}
.history-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding-bottom: 8px;
  border-bottom: 1px solid var(--line-soft);
}
.hist {
  width: 100%;
  text-align: left;
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: 0.5rem;
  color: var(--ink);
  padding: 8px 10px;
  display: grid;
  gap: 2px;
  margin-bottom: 6px;
  position: relative;
  transition:
    background 0.15s ease,
    border-color 0.15s ease;
}
.hist:hover {
  border-color: var(--brand-soft);
}
.hist.on {
  background: var(--brand-light);
  border-color: var(--brand-soft);
  color: var(--brand);
}
.del {
  position: absolute;
  right: 8px;
  top: 8px;
  color: var(--muted);
  font-size: 0.75rem;
}
.muted {
  color: var(--muted);
  font-size: 0.75rem;
}
.toolbar {
  display: flex;
  gap: 12px;
  align-items: center;
  flex-wrap: wrap;
}
.toolbar .spacer {
  flex: 1;
}
.diff {
  color: var(--muted);
  font-size: 0.85rem;
}
.diff-summary {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  align-items: center;
}
.diff-detail {
  margin-top: 8px;
  display: grid;
  gap: 8px;
}
.diff-group {
  display: grid;
  gap: 6px;
}
.diff-group strong {
  font-size: 0.8rem;
  color: var(--text);
}
.chip-link {
  background: var(--bg-panel);
  border: 1px solid var(--border);
  border-radius: 999px;
  padding: 4px 10px;
  font-size: 0.8rem;
  color: var(--text);
  cursor: pointer;
}
.chip-link:hover {
  border-color: var(--brand-soft);
  color: var(--brand);
}
.tip {
  margin: 0;
}
.table-wrap {
  border: 1px solid var(--line);
  border-radius: 0.75rem;
  overflow: auto;
  background: var(--surface);
  box-shadow: var(--shadow-card);
}
th,
td {
  padding: 8px 10px;
  border-bottom: 1px solid var(--border);
  font-size: 0.85rem;
  text-align: left;
  white-space: nowrap;
}
th {
  color: var(--muted);
  font-weight: 500;
  background: var(--surface-muted);
  position: sticky;
  top: 0;
}
th.sortable {
  cursor: pointer;
  user-select: none;
}
th.sortable:hover {
  color: var(--text);
}
.group-row th {
  padding: 4px 10px;
  font-size: 0.72rem;
  color: var(--ink-faint);
  background: var(--surface-muted);
  border-bottom: 1px solid var(--line);
  letter-spacing: 0.02em;
}
.col-row th {
  top: 24px;
  padding: 7px 10px;
}
.sel-col {
  text-align: center;
  width: 34px;
}
.ops-col {
  width: 96px;
}
.group-row th.g-quote,
.g-quote {
  background: rgba(230, 100, 50, 0.04);
}
.col-row th.g-quote {
  background: rgba(230, 100, 50, 0.06);
  color: var(--brand);
}
.group-row th.g-tape,
.g-tape {
  background: rgba(22, 163, 74, 0.03);
}
.col-row th.g-tape {
  background: rgba(22, 163, 74, 0.06);
  color: var(--ok);
}
.group-row th.g-fund,
.g-fund {
  background: rgba(115, 115, 115, 0.03);
}
.col-row th.g-fund {
  color: var(--ink-muted);
}
.group-row th.g-flow,
.g-flow {
  background: rgba(59, 130, 246, 0.04);
}
.col-row th.g-flow {
  background: rgba(59, 130, 246, 0.07);
  color: #2563eb;
}
.group-row th.g-score,
.g-score {
  background: rgba(230, 100, 50, 0.05);
}
.col-row th.g-score {
  background: rgba(230, 100, 50, 0.08);
  color: var(--brand);
}
.group-row th.g-quote,
.group-row th.g-tape,
.group-row th.g-fund,
.group-row th.g-flow,
.group-row th.g-score,
.col-row th.g-quote,
.col-row th.g-tape,
.col-row th.g-fund,
.col-row th.g-flow,
.col-row th.g-score,
td.g-quote,
td.g-tape,
td.g-fund,
td.g-flow,
td.g-score {
  border-left: 1px solid var(--line-soft);
}
td.g-flow {
  font-variant-numeric: tabular-nums;
}
td.g-score {
  font-weight: 500;
}
.mono {
  font-family: var(--mono);
}
.up {
  color: var(--danger);
}
.down {
  color: var(--ok);
}
.empty {
  text-align: center;
  color: var(--muted);
  padding: 28px !important;
}
.chips {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.chip {
  background: var(--bg-panel);
  border: 1px solid var(--border);
  border-radius: 999px;
  padding: 4px 10px;
  font-size: 0.8rem;
}
.weight-block {
  display: grid;
  gap: 8px;
}
.weight-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
  font-size: 0.85rem;
}
.tiny-btn {
  padding: 4px 8px;
  font-size: 0.75rem;
}
.weight-panel {
  border: 1px solid var(--border);
  border-radius: 0.5rem;
  padding: 8px;
  display: grid;
  gap: 8px;
  background: var(--bg-panel, var(--bg-elevated));
}
.weight-row {
  display: grid;
  grid-template-columns: 1fr 72px;
  gap: 8px;
  align-items: center;
  font-size: 0.8rem;
}
.weight-row label {
  display: block;
  margin: 0;
  color: var(--text);
}
.weight-row input {
  width: 100%;
  box-sizing: border-box;
  padding: 4px 6px;
  font-variant-numeric: tabular-nums;
}
.weight-actions {
  display: flex;
  gap: 8px;
}
.weight-actions .tiny-primary,
.weight-actions .ghost {
  flex: 1;
  padding: 6px 8px;
  font-size: 0.8rem;
}
.weight-err {
  margin: 0;
  font-size: 0.78rem;
  color: var(--danger);
}
.industry-block {
  display: grid;
  gap: 8px;
}
.industry-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
  font-size: 0.85rem;
}
.industry-panel {
  border: 1px solid var(--border);
  border-radius: 0.5rem;
  padding: 8px;
  display: grid;
  gap: 6px;
  max-height: 220px;
  overflow: auto;
  background: var(--bg-panel, var(--bg-elevated));
}
.industry-check {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 0.8rem;
  color: var(--text);
  cursor: pointer;
}
.industry-check input {
  width: auto;
  margin: 0;
  padding: 0;
}
.industry-err {
  margin: 0;
  font-size: 0.78rem;
  color: var(--danger);
}
@media (max-width: 1200px) {
  .workspace {
    grid-template-columns: 280px 1fr;
    grid-template-areas:
      'left middle'
      'right right';
  }
}
@media (max-width: 900px) {
  .workspace {
    grid-template-columns: 1fr;
    grid-template-areas:
      'left'
      'middle'
      'right';
  }
}
</style>
