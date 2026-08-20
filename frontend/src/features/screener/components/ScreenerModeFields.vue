<script setup lang="ts">
import type { BuiltinRecipe, PatternMeta, Preset, RecipeWeightItem } from '../../../api/screener'

export type ScreenerMode = 'condition' | 'recipe' | 'pattern' | 'peer'

defineProps<{
  mode: ScreenerMode
  presets: Preset[]
  recipes: BuiltinRecipe[]
  patterns: PatternMeta[]
  isCustom: boolean
  isRadarLeader: boolean
  isWeightEditable: boolean
  weightOpen: boolean
  weightItems: RecipeWeightItem[]
  weightDraft: Record<string, number>
  weightBusy: boolean
  weightErr: string
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

const emit = defineEmits<{
  'update:weightOpen': [boolean]
  saveWeights: []
  resetWeights: []
  run: []
}>()
</script>

<template>
  <div v-if="mode === 'condition'" class="block">
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

  <div v-else-if="mode === 'recipe'" class="block">
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
        <button class="ghost tiny-btn" type="button" @click="emit('update:weightOpen', !weightOpen)">
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
            @click="emit('saveWeights')"
          >
            保存
          </button>
          <button class="ghost" type="button" :disabled="weightBusy" @click="emit('resetWeights')">
            恢复默认
          </button>
        </div>
        <p class="hint muted">保存后按比例归一化；空值不会清空已存权重</p>
      </div>
    </div>
  </div>

  <div v-else-if="mode === 'pattern'" class="block">
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

  <div v-else-if="mode === 'peer'" class="block">
    <label>
      标杆代码
      <input v-model="peerSymbol" placeholder="600519.SSE" @keyup.enter="emit('run')" />
    </label>
    <p class="hint muted">
      同业 30% + 估值 25% + 近5日动量 15% + 近20日动量 15% + 换手 15%（需 Tushare）
    </p>
  </div>
</template>

<style scoped>
.block {
  display: grid;
  gap: 10px;
}
.custom-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
}
.hint {
  margin: 0;
  font-size: 0.75rem;
  line-height: 1.4;
}
.weight-block {
  display: grid;
  gap: 8px;
  padding: 8px;
  border: 1px solid var(--line-soft);
  border-radius: 0.5rem;
  background: var(--surface-muted);
}
.weight-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}
.weight-head strong {
  font-size: 0.8125rem;
}
.weight-panel {
  display: grid;
  gap: 8px;
}
.weight-row {
  display: grid;
  grid-template-columns: 1fr 88px;
  gap: 8px;
  align-items: center;
  font-size: 0.8125rem;
}
.weight-actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}
.weight-err {
  margin: 0;
  color: var(--danger);
  font-size: 0.75rem;
}
.tiny-btn {
  padding: 2px 8px;
  font-size: 0.75rem;
}
.tiny-primary {
  padding: 4px 10px;
  font-size: 0.75rem;
}
label {
  display: grid;
  gap: 4px;
  font-size: 0.78rem;
  color: var(--ink-muted);
}
select,
input {
  width: 100%;
  box-sizing: border-box;
}
</style>
