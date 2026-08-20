<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import AppShell from '../../../components/AppShell.vue'
import type { NavActive } from '../../../components/AppShell.vue'
import ScreenerHistoryPanel from '../components/ScreenerHistoryPanel.vue'
import ScreenerModeFields from '../components/ScreenerModeFields.vue'
import ScreenerResultPanel from '../components/ScreenerResultPanel.vue'
import { getToken } from '../../../api/client'
import { fmtDateTime } from '../../../lib/format'
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
} from '../../../api/screener'
import { watchlistApi } from '../../../api/watchlist'

const WEIGHT_EDITABLE = new Set(['intraday_multi', 'post_close_multi', 'ultra_short_unified'])

type ScreenerTab = 'condition' | 'recipe' | 'pattern' | 'peer'

const MODE_TITLE: Record<ScreenerTab, string> = {
  condition: '条件选股',
  recipe: '多因子配方',
  pattern: '形态选股',
  peer: '对标相似',
}

function parseMode(raw: unknown): ScreenerTab {
  if (raw === 'recipe' || raw === 'pattern' || raw === 'peer' || raw === 'condition') return raw
  return 'condition'
}

const route = useRoute()
const router = useRouter()
const tab = ref<ScreenerTab>(parseMode(route.params.mode))

watch(
  () => route.params.mode,
  (m) => {
    const next = parseMode(m)
    if (next !== tab.value) tab.value = next
  },
)

function setTab(mode: ScreenerTab) {
  tab.value = mode
  if (parseMode(route.params.mode) !== mode) {
    void router.push({ name: 'screener', params: { mode }, query: { ...route.query } })
  }
}

const navActive = computed(() => `screener-${tab.value}` as NavActive)
const pageTitle = computed(() => MODE_TITLE[tab.value])
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
const batchBusy = ref(false)
const weightOpen = ref(true)
const weightItems = ref<RecipeWeightItem[]>([])
const weightDraft = ref<Record<string, number>>({})
const weightBusy = ref(false)
const weightErr = ref('')
const industryOptions = ref<string[]>([])
const selectedIndustries = ref<string[]>([])
const industryOpen = ref(false)
const industryErr = ref('')

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
  setTab(
    tabVal === 'recipe'
      ? 'recipe'
      : tabVal === 'pattern'
        ? 'pattern'
        : tabVal === 'peer'
          ? 'peer'
          : 'condition',
  )
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
  } catch (e) {
    error.value = e instanceof Error ? e.message : '打开运行记录失败'
  } finally {
    runBusy.value = false
  }
}

function rowVt(row: Record<string, unknown>): string {
  return String(row.vt_symbol || row.symbol || '').trim()
}

async function addToWatchlist(row: Record<string, unknown>) {
  const vt = rowVt(row)
  if (!vt) return
  try {
    await watchlistApi.add(vt, String(row.name || ''))
    statusText.value = `已加入自选 ${vt}`
  } catch (e) {
    error.value = e instanceof Error ? e.message : '加入自选失败'
  }
}

async function addSelectedToWatchlist(queue: Record<string, unknown>[]) {
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
  setTab('peer')
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
    if (qRecipe && tab.value === 'recipe') {
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
  <AppShell :title="pageTitle" :subtitle="dataStatus" :active="navActive">
    <div class="workspace">
      <section class="left">
        <div class="cfg-card">
          <ScreenerModeFields
            :mode="tab"
            :presets="presets"
            :recipes="recipes"
            :patterns="patterns"
            :is-custom="isCustom"
            :is-radar-leader="isRadarLeader"
            :is-weight-editable="isWeightEditable"
            :weight-open="weightOpen"
            :weight-items="weightItems"
            :weight-draft="weightDraft"
            :weight-busy="weightBusy"
            :weight-err="weightErr"
            v-model:selected-preset="selectedPreset"
            v-model:min-change="minChange"
            v-model:max-change="maxChange"
            v-model:min-turnover="minTurnover"
            v-model:max-turnover="maxTurnover"
            v-model:selected-recipe="selectedRecipe"
            v-model:leader-variant="leaderVariant"
            v-model:selected-pattern="selectedPattern"
            v-model:max-scan="maxScan"
            v-model:peer-symbol="peerSymbol"
            @update:weight-open="weightOpen = $event"
            @save-weights="saveRecipeWeights"
            @reset-weights="resetRecipeWeights"
            @run="runScreen"
          />

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
        <ScreenerHistoryPanel
          :history="history"
          :current-id="current?.id"
          :page="historyPage"
          :pages="historyPages"
          :total="historyTotal"
          :busy="historyBusy"
          :err="historyErr"
          :run-busy="runBusy"
          @refresh="loadHistory"
          @open="openRun"
          @page="goHistoryPage"
        />
      </section>

      <section class="right">
        <ScreenerResultPanel
          :current="current"
          :status-text="statusText"
          :error="error"
          :is-radar-leader="isRadarLeader"
          :batch-busy="batchBusy"
          @export-csv="exportCsv"
          @add-selected="addSelectedToWatchlist"
          @add-watchlist="addToWatchlist"
          @find-peers="findPeers"
        />
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
