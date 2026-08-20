<script setup lang="ts">
import { computed, ref } from 'vue'
import ScreenerModeFields from './ScreenerModeFields.vue'
import type { ScreenerMode } from './ScreenerModeFields.vue'
import { fmtDateTime } from '../../../lib/format'
import type {
  BuiltinRecipe,
  HardFilterTemplate,
  PatternMeta,
  Preset,
  RecipeWeightItem,
  Scheme,
} from '../../../api/screener'

const props = defineProps<{
  mode: ScreenerMode
  presets: Preset[]
  recipes: BuiltinRecipe[]
  patterns: PatternMeta[]
  templates: HardFilterTemplate[]
  schemes: Scheme[]
  isCustom: boolean
  isRadarLeader: boolean
  isWeightEditable: boolean
  weightOpen: boolean
  weightItems: RecipeWeightItem[]
  weightDraft: Record<string, number>
  weightBusy: boolean
  weightErr: string
  industryOptions: string[]
  industryErr: string
  running: boolean
  selectedSchemeId: string
}>()

const selectedPreset = defineModel<string>('selectedPreset', { required: true })
const minChange = defineModel<number | null>('minChange', { required: true })
const maxChange = defineModel<number | null>('maxChange', { required: true })
const minTurnover = defineModel<number | null>('minTurnover', { required: true })
const maxTurnover = defineModel<number | null>('maxTurnover', { required: true })
const selectedRecipe = defineModel<string>('selectedRecipe', { required: true })
const leaderVariant = defineModel<'mainline' | 'all_market'>('leaderVariant', { required: true })
const selectedPattern = defineModel<string>('selectedPattern', { required: true })
const maxScan = defineModel<number>('maxScan', { required: true })
const peerSymbol = defineModel<string>('peerSymbol', { required: true })
const hardTemplate = defineModel<string>('hardTemplate', { required: true })
const topN = defineModel<number>('topN', { required: true })
const schemeName = defineModel<string>('schemeName', { required: true })
const selectedIndustries = defineModel<string[]>('selectedIndustries', { required: true })

const emit = defineEmits<{
  'update:weightOpen': [boolean]
  saveWeights: []
  resetWeights: []
  run: []
  saveScheme: []
  applyScheme: [scheme: Scheme]
  deleteScheme: [id: string]
}>()

const industryOpen = ref(false)

const activeTemplate = computed(() => props.templates.find((t) => t.id === hardTemplate.value))

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
</script>

<template>
  <section class="left">
    <div class="cfg-card">
      <ScreenerModeFields
        :mode="mode"
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
        @update:weight-open="emit('update:weightOpen', $event)"
        @save-weights="emit('saveWeights')"
        @reset-weights="emit('resetWeights')"
        @run="emit('run')"
      />

      <button class="primary run-btn" type="button" :disabled="running" @click="emit('run')">
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
        <input v-model="schemeName" placeholder="方案名称" @keyup.enter="emit('saveScheme')" />
        <button type="button" class="ghost" @click="emit('saveScheme')">保存</button>
      </div>
      <button
        v-for="s in schemes"
        :key="s.id"
        type="button"
        class="hist"
        :class="{ on: selectedSchemeId === s.id }"
        @click="emit('applyScheme', s)"
      >
        <span>{{ s.name }}</span>
        <span class="muted">{{ fmtDateTime(s.updated_at) }}</span>
        <span class="del" @click.stop="emit('deleteScheme', s.id)">删</span>
      </button>
      <p v-if="!schemes.length" class="muted">保存当前配置后可一键加载复跑</p>
    </div>
  </section>
</template>

<style scoped>
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
.tiny-btn {
  padding: 4px 8px;
  font-size: 0.75rem;
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
.hist {
  position: relative;
  display: grid;
  gap: 2px;
  text-align: left;
  padding: 8px 28px 8px 10px;
  border: 1px solid var(--line);
  border-radius: 0.5rem;
  background: var(--surface-muted);
  cursor: pointer;
  font-size: 0.8125rem;
}
.hist:hover {
  border-color: var(--brand-soft);
}
.hist.on {
  border-color: var(--brand-soft);
  background: var(--brand-light);
  color: var(--brand-dark);
}
</style>
