<script setup lang="ts">
import { nextTick, ref, watch } from 'vue'
import { marketApi, type EmotionThresholds } from '../../../api/market'

const emit = defineEmits<{
  saved: []
}>()

const thresholdsOpen = ref(false)
const thresholdsSectionEl = ref<HTMLElement | null>(null)
const thresholdsDraft = ref<EmotionThresholds | null>(null)
const thresholdsBusy = ref(false)
const thresholdsErr = ref('')
const thresholdsMsg = ref('')

const thresholdFields: {
  key: keyof Omit<EmotionThresholds, 'is_default'>
  label: string
  step?: number
  min?: number
  max?: number
  kind?: 'bool'
}[] = [
  { key: 'recession_limit_down', label: '衰退跌停数', step: 1, min: 0 },
  { key: 'ice_limit_down', label: '冰点跌停数', step: 1, min: 0 },
  { key: 'ice_max_boards', label: '冰点最高板', step: 1, min: 0 },
  { key: 'ice_up_ratio_max', label: '冰点上涨比上限', step: 0.01, min: 0, max: 1 },
  { key: 'climax_limit_up', label: '高潮涨停数', step: 1, min: 0 },
  { key: 'climax_ladder_depth', label: '高潮梯队深度', step: 1, min: 0 },
  { key: 'startup_limit_up', label: '启动涨停数', step: 1, min: 0 },
  { key: 'startup_max_boards', label: '启动最高板', step: 1, min: 0 },
  { key: 'divergence_limit_up_min', label: '分歧涨停下限', step: 1, min: 0 },
  { key: 'divergence_limit_spread', label: '分歧板差', step: 1, min: 0 },
  { key: 'fear_greed_overheat', label: '恐贪过热', step: 1, min: 0, max: 100 },
  { key: 'recession_break_rate', label: '衰退炸板率', step: 0.01, min: 0, max: 1 },
  { key: 'amount_floor_yuan', label: '成交额下限(元)', step: 1e8, min: 0 },
  { key: 'hysteresis_enabled', label: '滞回', kind: 'bool' },
]

function applyThresholds(t: EmotionThresholds) {
  thresholdsDraft.value = { ...t }
}

async function loadThresholds() {
  thresholdsErr.value = ''
  thresholdsMsg.value = ''
  try {
    applyThresholds(await marketApi.emotionThresholds())
  } catch (e) {
    thresholdsErr.value = e instanceof Error ? e.message : '阈值加载失败'
  }
}

async function saveThresholds() {
  if (!thresholdsDraft.value) return
  thresholdsBusy.value = true
  thresholdsErr.value = ''
  thresholdsMsg.value = ''
  const { is_default: _, ...body } = thresholdsDraft.value
  try {
    const out = await marketApi.putEmotionThresholds(body)
    applyThresholds(out)
    thresholdsMsg.value = '阈值已保存'
    emit('saved')
  } catch (e) {
    thresholdsErr.value = e instanceof Error ? e.message : '保存失败'
  } finally {
    thresholdsBusy.value = false
  }
}

async function resetThresholds() {
  thresholdsBusy.value = true
  thresholdsErr.value = ''
  thresholdsMsg.value = ''
  try {
    const out = await marketApi.resetEmotionThresholds()
    applyThresholds(out)
    thresholdsMsg.value = '已恢复默认阈值'
    emit('saved')
  } catch (e) {
    thresholdsErr.value = e instanceof Error ? e.message : '恢复失败'
  } finally {
    thresholdsBusy.value = false
  }
}

function openFromCard() {
  thresholdsOpen.value = true
  void nextTick(() => {
    thresholdsSectionEl.value?.scrollIntoView({ behavior: 'smooth', block: 'nearest' })
  })
}

watch(thresholdsOpen, (open) => {
  if (open) void loadThresholds()
})

defineExpose({ openFromCard })
</script>

<template>
  <section ref="thresholdsSectionEl" class="thresholds-section">
    <div class="thresholds-head">
      <div>
        <strong>判定阈值</strong>
        <span v-if="thresholdsDraft" class="muted tag">
          {{ thresholdsDraft.is_default ? '默认' : '已自定义' }}
        </span>
      </div>
      <button class="ghost tiny-btn" type="button" @click="thresholdsOpen = !thresholdsOpen">
        {{ thresholdsOpen ? '收起' : '展开' }}
      </button>
    </div>
    <div v-if="thresholdsOpen" class="thresholds-panel">
      <p class="muted thresholds-hint">
        全局 meta 持久化；保存后失效短 TTL 缓存并刷新情绪周期。
      </p>
      <div v-if="thresholdsDraft" class="thresholds-grid">
        <div v-for="f in thresholdFields" :key="f.key" class="threshold-row">
          <label :for="`th-${f.key}`">{{ f.label }}</label>
          <input
            v-if="f.kind === 'bool'"
            :id="`th-${f.key}`"
            v-model="thresholdsDraft[f.key]"
            type="checkbox"
            :disabled="thresholdsBusy"
          />
          <input
            v-else
            :id="`th-${f.key}`"
            v-model.number="thresholdsDraft[f.key]"
            type="number"
            :step="f.step ?? 1"
            :min="f.min"
            :max="f.max"
            :disabled="thresholdsBusy"
          />
        </div>
      </div>
      <p v-else-if="!thresholdsErr" class="muted">加载中…</p>
      <p v-if="thresholdsErr" class="err">{{ thresholdsErr }}</p>
      <p v-if="thresholdsMsg" class="ok">{{ thresholdsMsg }}</p>
      <div class="thresholds-actions">
        <button
          class="primary"
          type="button"
          :disabled="thresholdsBusy || !thresholdsDraft"
          @click="saveThresholds"
        >
          保存
        </button>
        <button class="ghost" type="button" :disabled="thresholdsBusy" @click="resetThresholds">
          恢复默认
        </button>
      </div>
    </div>
  </section>
</template>

<style scoped>
.thresholds-section {
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: 0.75rem;
  box-shadow: var(--shadow-card);
  padding: 12px 16px;
  display: grid;
  gap: 10px;
}
.thresholds-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
}
.thresholds-head strong {
  font-size: 0.9rem;
  font-weight: 600;
}
.tag {
  margin-left: 8px;
  font-size: 0.75rem;
}
.thresholds-panel {
  display: grid;
  gap: 10px;
}
.thresholds-hint {
  margin: 0;
  font-size: 0.8rem;
}
.thresholds-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: 8px 14px;
}
.threshold-row {
  display: grid;
  grid-template-columns: 1fr auto;
  align-items: center;
  gap: 8px;
}
.threshold-row label {
  font-size: 0.8rem;
  color: var(--muted);
}
.threshold-row input[type='number'] {
  width: 100px;
  background: var(--bg-elevated, var(--surface-muted));
  border: 1px solid var(--border, var(--line));
  border-radius: 0.4rem;
  color: var(--text, var(--ink));
  padding: 4px 8px;
  font-size: 0.85rem;
}
.threshold-row input[type='checkbox'] {
  width: 16px;
  height: 16px;
  justify-self: end;
}
.thresholds-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.ghost,
.primary {
  border-radius: 0.5rem;
  padding: 6px 10px;
  border: 1px solid var(--border);
  cursor: pointer;
}
.ghost {
  background: transparent;
  color: var(--text);
}
.ghost:disabled,
.primary:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
.primary {
  background: var(--accent);
  border-color: transparent;
  color: var(--brand-foreground);
  font-weight: 600;
}
.tiny-btn {
  padding: 2px 8px;
  font-size: 0.75rem;
}
.err {
  margin: 0;
  color: var(--danger);
  font-size: 0.85rem;
}
.ok {
  margin: 0;
  color: var(--ok);
  font-size: 0.85rem;
}
.muted {
  color: var(--muted);
}
</style>
