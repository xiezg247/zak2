<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import AppShell from '../components/AppShell.vue'
import { getToken } from '../api/client'
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
    ? `Redis 行情 ${count} 只 · 更新 ${ds.redis.updated_at || '—'}`
    : 'Redis 不可用'
}

async function loadHistory() {
  history.value = await screenerApi.runs()
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
  current.value = await screenerApi.run(id)
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
        <div class="tabs">
          <button :class="{ on: tab === 'condition' }" type="button" @click="tab = 'condition'">条件选股</button>
          <button :class="{ on: tab === 'recipe' }" type="button" @click="tab = 'recipe'">多因子配方</button>
          <button :class="{ on: tab === 'pattern' }" type="button" @click="tab = 'pattern'">形态</button>
          <button :class="{ on: tab === 'peer' }" type="button" @click="tab = 'peer'">对标</button>
        </div>

        <div v-if="tab === 'condition'" class="block">
          <label>
            Preset
            <select v-model="selectedPreset">
              <option v-for="p in presets" :key="p.name" :value="p.name" :disabled="!p.implemented">
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
              <option v-for="r in recipes" :key="r.recipe_id" :value="r.recipe_id" :disabled="!r.implemented">
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
                <button class="ghost" type="button" :disabled="weightBusy" @click="resetRecipeWeights">
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
            {{ patterns.find((p) => p.pattern_id === selectedPattern)?.description || 'Redis 行情池 ∩ 日 K' }}
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
          <p class="hint muted">同业 30% + 估值 25% + 近5日动量 15% + 近20日动量 15% + 换手 15%（需 Tushare）</p>
        </div>

        <div class="block">
          <label>
            硬过滤模板
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
              <label
                v-for="name in industryOptions"
                :key="name"
                class="industry-check"
              >
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

        <button class="primary" type="button" :disabled="running" @click="runScreen">
          {{ running ? '运行中…' : '运行' }}
        </button>

        <div class="block scheme">
          <h3>方案</h3>
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
            <span class="muted">{{ s.updated_at }}</span>
            <span class="del" @click.stop="deleteScheme(s.id)">删</span>
          </button>
          <p v-if="!schemes.length" class="muted">保存当前配置后可一键加载复跑</p>
        </div>

        <p v-if="statusText" class="status">{{ statusText }}</p>
        <p v-if="error" class="err">{{ error }}</p>

        <div class="block history">
          <h3>运行历史</h3>
          <button v-for="h in history" :key="h.id" type="button" class="hist" @click="openRun(h.id)">
            <span>{{ h.condition }}</span>
            <span class="muted">{{ h.row_count }} 只 · {{ h.created_at }}</span>
          </button>
        </div>
      </section>

      <section class="right">
        <div class="toolbar" v-if="current">
          <strong>{{ current.condition }}</strong>
          <span class="muted">扫描 {{ current.total_scanned }} · 命中 {{ current.row_count }}</span>
          <button class="ghost" type="button" @click="exportCsv">导出 CSV</button>
        </div>

        <div v-if="diff" class="diff">
          <span>新增 {{ diff.added.length }}</span>
          <span>移除 {{ diff.removed.length }}</span>
          <span>保留 {{ diff.kept.length }}</span>
        </div>

        <div class="table-wrap">
          <table>
            <thead>
              <tr>
                <th>#</th>
                <th>代码</th>
                <th>名称</th>
                <th>现价</th>
                <th>涨幅%</th>
                <th>换手%</th>
                <th>连板</th>
                <th>分层</th>
                <th>PE</th>
                <th>市值亿</th>
                <th>净流入万</th>
                <th>量比</th>
                <th>得分</th>
                <th>形态说明</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(row, i) in rows" :key="String(row.symbol)">
                <td>{{ i + 1 }}</td>
                <td class="mono">{{ row.vt_symbol || row.symbol }}</td>
                <td>{{ row.name }}</td>
                <td>{{ Number(row.last_price || 0).toFixed(2) }}</td>
                <td :class="{ up: Number(row.change_pct) > 0, down: Number(row.change_pct) < 0 }">
                  {{ Number(row.change_pct || 0).toFixed(2) }}
                </td>
                <td>{{ Number(row.turnover_rate || 0).toFixed(2) }}</td>
                <td>
                  {{ row.limit_times != null ? Number(row.limit_times).toFixed(0) : '—' }}
                  <span v-if="rowSealLabel(row)" class="muted seal-tag"> · {{ rowSealLabel(row) }}</span>
                </td>
                <td>{{ row.leader_tier_label || row.leader_tier || '—' }}</td>
                <td>{{ row.pe_ttm != null ? Number(row.pe_ttm).toFixed(2) : '—' }}</td>
                <td>
                  {{
                    row.total_mv_yi != null
                      ? Number(row.total_mv_yi).toFixed(1)
                      : row.total_mv
                        ? (Number(row.total_mv) / 10000).toFixed(1)
                        : '—'
                  }}
                </td>
                <td>
                  {{
                    row.net_mf_wan != null
                      ? Number(row.net_mf_wan).toFixed(0)
                      : row.net_mf_amount
                        ? Number(row.net_mf_amount).toFixed(0)
                        : '—'
                  }}
                </td>
                <td>{{ Number(row.volume_ratio || 0).toFixed(2) }}</td>
                <td>
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
                  class="hint-cell"
                  :title="
                    [row.pattern_hint || row.hit_reason || '', isRadarLeader ? rowSealLabel(row) : '']
                      .filter(Boolean)
                      .join(' · ') || ''
                  "
                >
                  <template v-if="row.pattern_hint || row.hit_reason">
                    {{ row.pattern_hint || row.hit_reason }}
                  </template>
                  <template v-else-if="isRadarLeader && rowSealLabel(row)">{{ rowSealLabel(row) }}</template>
                  <template v-else>—</template>
                </td>
                <td class="row-actions">
                  <button type="button" class="link" @click="addToWatchlist(row)">自选</button>
                  <button type="button" class="link" @click="findPeers(row)">找同类</button>
                </td>
              </tr>
              <tr v-if="!rows.length">
                <td colspan="15" class="empty">运行选股后在此显示结果</td>
              </tr>
            </tbody>
          </table>
        </div>

        <div class="industry" v-if="industry.length">
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
  grid-template-columns: 300px 1fr;
  height: 100%;
  min-height: 0;
}
.left {
  border-right: 1px solid var(--border);
  padding: 16px;
  overflow: auto;
  display: grid;
  gap: 14px;
  align-content: start;
}
.right {
  padding: 16px 20px;
  overflow: auto;
  display: grid;
  gap: 12px;
  align-content: start;
}
.tabs {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 6px;
}
.tabs button {
  background: var(--bg-elevated);
  border: 1px solid var(--border);
  color: var(--muted);
  border-radius: 0.5rem;
  padding: 8px;
}
.tabs button.on {
  color: var(--text);
  border-color: var(--accent);
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
  background: var(--accent);
  color: var(--brand-foreground);
  border: none;
  border-radius: 0.5rem;
  padding: 10px;
  font-weight: 600;
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
.history h3,
.scheme h3 {
  margin: 0 0 8px;
  font-size: 0.9rem;
}
.hist {
  width: 100%;
  text-align: left;
  background: var(--bg-elevated);
  border: 1px solid var(--border);
  border-radius: 0.5rem;
  color: var(--text);
  padding: 8px 10px;
  display: grid;
  gap: 2px;
  margin-bottom: 6px;
  position: relative;
}
.hist.on {
  border-color: var(--accent);
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
}
.diff {
  display: flex;
  gap: 16px;
  color: var(--muted);
  font-size: 0.85rem;
}
.table-wrap {
  border: 1px solid var(--border);
  border-radius: 0.75rem;
  overflow: auto;
  background: var(--bg-elevated);
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
.industry h3 {
  margin: 0 0 8px;
  font-size: 0.9rem;
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
@media (max-width: 900px) {
  .workspace {
    grid-template-columns: 1fr;
  }
}
</style>
