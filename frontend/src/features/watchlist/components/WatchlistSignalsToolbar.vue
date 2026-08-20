<script setup lang="ts">
defineProps<{
  signalMode: string
  strategyOptions: { value: string; label: string }[]
  riskForm: {
    total_capital: string
    stop_loss_pct: string
    caution_float_pct: string
  }
  prefsReady: boolean
  riskSaving: boolean
  riskError: string
  riskMsg: string
  enqueueing: boolean
  autoRefresh: boolean
}>()

const emit = defineEmits<{
  'update:signalMode': [value: string]
  'update:autoRefresh': [value: boolean]
  'mode-change': []
  'save-risk': []
  'open-backtest': []
  'enqueue-backtest': []
  refresh: []
}>()
</script>

<template>
  <div class="toolbar-wrap">
    <div class="topbar">
      <div class="mode-select">
        <span>策略</span>
        <select
          :value="signalMode"
          @change="
            emit('update:signalMode', ($event.target as HTMLSelectElement).value);
            emit('mode-change')
          "
        >
          <option v-for="m in strategyOptions" :key="m.value" :value="m.value">
            {{ m.label }}
          </option>
        </select>
      </div>

      <div class="risk-form">
        <label>
          总资金
          <input
            v-model="riskForm.total_capital"
            type="number"
            step="1000"
            min="0"
            placeholder="可选"
            :disabled="!prefsReady || riskSaving"
          />
        </label>
        <label>
          止损%
          <input
            v-model="riskForm.stop_loss_pct"
            type="number"
            step="0.1"
            min="0.1"
            max="50"
            :disabled="!prefsReady || riskSaving"
          />
        </label>
        <label>
          浮亏警戒
          <input
            v-model="riskForm.caution_float_pct"
            type="number"
            step="0.5"
            max="-0.1"
            :disabled="!prefsReady || riskSaving"
          />
        </label>
        <button
          type="button"
          class="primary"
          :disabled="!prefsReady || riskSaving"
          @click="emit('save-risk')"
        >
          {{ riskSaving ? '保存中…' : '保存风控' }}
        </button>
      </div>

      <div class="actions">
        <button type="button" class="ghost" @click="emit('open-backtest')">同参回测</button>
        <button
          type="button"
          class="ghost"
          :disabled="enqueueing"
          @click="emit('enqueue-backtest')"
        >
          {{ enqueueing ? '入队中…' : '入队回测' }}
        </button>
        <button type="button" class="ghost" @click="emit('refresh')">刷新看板</button>
        <label class="auto">
          <input
            type="checkbox"
            :checked="autoRefresh"
            @change="emit('update:autoRefresh', ($event.target as HTMLInputElement).checked)"
          />
          自动刷新
        </label>
      </div>
    </div>

    <div class="topbar-feedback">
      <p v-if="!prefsReady" class="muted">加载风控偏好…</p>
      <p v-else-if="riskError" class="err">{{ riskError }}</p>
      <p v-else-if="riskMsg" class="muted">{{ riskMsg }}</p>
      <p class="muted tip">止损按百分数（如 5 = 5%）；浮亏警戒为负数（如 -5）。</p>
    </div>
  </div>
</template>

<style scoped>
.toolbar-wrap {
  display: grid;
  gap: 14px;
}
.topbar {
  display: flex;
  align-items: flex-end;
  gap: 16px;
  flex-wrap: wrap;
  padding: 10px 12px;
  border: 1px solid var(--line);
  border-radius: 0.75rem;
  background: var(--surface);
  box-shadow: var(--shadow-card);
}
.mode-select {
  display: grid;
  gap: 4px;
  font-size: 0.78rem;
  color: var(--muted);
}
.mode-select select {
  min-width: 130px;
  background: var(--bg-elevated);
  border: 1px solid var(--border);
  border-radius: 0.5rem;
  color: var(--text);
  padding: 6px 8px;
}
.mode-select select:focus {
  border-color: var(--brand);
  box-shadow: 0 0 0 3px rgba(230, 100, 50, 0.15);
  outline: none;
}
.risk-form {
  display: flex;
  align-items: flex-end;
  gap: 10px;
  flex-wrap: wrap;
}
.risk-form label {
  display: grid;
  gap: 4px;
  font-size: 0.78rem;
  color: var(--muted);
}
.risk-form input {
  width: 110px;
  background: var(--bg-elevated);
  border: 1px solid var(--border);
  border-radius: 0.5rem;
  color: var(--text);
  padding: 6px 8px;
}
.risk-form input:focus {
  border-color: var(--brand);
  box-shadow: 0 0 0 3px rgba(230, 100, 50, 0.15);
  outline: none;
}
.topbar .actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  align-items: center;
  margin-left: auto;
}
.auto {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 0.8125rem;
  color: var(--ink-muted);
}
.topbar-feedback {
  display: flex;
  align-items: center;
  gap: 16px;
  flex-wrap: wrap;
}
.topbar-feedback p {
  margin: 0;
}
.tip {
  margin: 0;
  font-size: 0.75rem;
}
</style>
