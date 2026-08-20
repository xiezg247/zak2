<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import AppShell from '../../../components/AppShell.vue'
import type { NavActive } from '../../../components/AppShell.vue'
import ScreenerConfigPanel from '../components/ScreenerConfigPanel.vue'
import ScreenerHistoryPanel from '../components/ScreenerHistoryPanel.vue'
import ScreenerResultPanel from '../components/ScreenerResultPanel.vue'
import { fmtDateTime } from '../../../lib/format'
import {
  screenerApi,
  type BuiltinRecipe,
  type HardFilterTemplate,
  type PatternMeta,
  type Preset,
  type Scheme,
} from '../../../api/screener'
import {
  emptyToNull,
  useScreenerRun,
  type ScreenerTab,
} from '../composables/useScreenerRun'
import { useScreenerWeights } from '../composables/useScreenerWeights'

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
const industryOptions = ref<string[]>([])
const selectedIndustries = ref<string[]>([])
const industryErr = ref('')

const isCustom = computed(() => selectedPreset.value === '自定义筛选')
const isRadarLeader = computed(() => selectedRecipe.value === 'radar_leader')

const {
  current,
  history,
  historyPage,
  historyPages,
  historyTotal,
  historyBusy,
  historyErr,
  runBusy,
  running,
  statusText,
  error,
  batchBusy,
  hardFilterOverride,
  loadHistory,
  goHistoryPage,
  runScreen,
  openRun,
  exportCsv,
  addToWatchlist,
  addSelectedToWatchlist,
} = useScreenerRun({
  tab,
  selectedPreset,
  selectedRecipe,
  selectedPattern,
  peerSymbol,
  leaderVariant,
  hardTemplate,
  topN,
  maxScan,
  minChange,
  maxChange,
  minTurnover,
  maxTurnover,
  selectedIndustries,
  isCustom,
  isRadarLeader,
})

const {
  weightOpen,
  weightItems,
  weightDraft,
  weightBusy,
  weightErr,
  isWeightEditable,
  clearWeights,
  loadRecipeWeights,
  saveRecipeWeights,
  resetRecipeWeights,
} = useScreenerWeights(selectedRecipe, statusText)

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

type ScreenerResultRow = Record<string, unknown>

function findPeers(row: ScreenerResultRow) {
  const vt = String(row.vt_symbol || '').trim() || String(row.symbol || '').trim()
  if (!vt) return
  peerSymbol.value = vt
  setTab('peer')
  void runScreen()
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
    else clearWeights()
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
      <ScreenerConfigPanel
        :mode="tab"
        :presets="presets"
        :recipes="recipes"
        :patterns="patterns"
        :templates="templates"
        :schemes="schemes"
        :is-custom="isCustom"
        :is-radar-leader="isRadarLeader"
        :is-weight-editable="isWeightEditable"
        :weight-open="weightOpen"
        :weight-items="weightItems"
        :weight-draft="weightDraft"
        :weight-busy="weightBusy"
        :weight-err="weightErr"
        :industry-options="industryOptions"
        :industry-err="industryErr"
        :running="running"
        :selected-scheme-id="selectedSchemeId"
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
        v-model:hard-template="hardTemplate"
        v-model:top-n="topN"
        v-model:scheme-name="schemeName"
        v-model:selected-industries="selectedIndustries"
        @update:weight-open="weightOpen = $event"
        @save-weights="saveRecipeWeights"
        @reset-weights="resetRecipeWeights"
        @run="runScreen"
        @save-scheme="saveScheme"
        @apply-scheme="applyScheme"
        @delete-scheme="deleteScheme"
      />

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
.right {
  grid-area: right;
  padding: 16px 24px 24px;
  overflow: auto;
  display: grid;
  gap: 12px;
  align-content: start;
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
