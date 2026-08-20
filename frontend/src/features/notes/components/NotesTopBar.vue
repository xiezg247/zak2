<script setup lang="ts">
import { ref } from 'vue'
import type { NoteSymbol } from '../../../api/content'

defineProps<{
  symbols: NoteSymbol[]
  displayedSymbols: NoteSymbol[]
  selected: string
  listFilter: string
  loading: boolean
}>()

const emit = defineEmits<{
  'update:listFilter': [value: string]
  select: [vt: string]
  open: [vt: string]
}>()

const newSymbol = ref('')

function openOrCreate() {
  const vt = newSymbol.value.trim()
  if (!vt) return
  emit('open', vt)
  newSymbol.value = ''
}
</script>

<template>
  <section class="topbar">
    <div class="topbar-head">
      <div class="open-group">
        <input v-model="newSymbol" placeholder="600519.SSE" @keyup.enter="openOrCreate" />
        <button class="primary" type="button" @click="openOrCreate">打开</button>
      </div>
      <input
        v-if="symbols.length"
        :value="listFilter"
        class="filter"
        placeholder="过滤代码 / 备忘"
        @input="emit('update:listFilter', ($event.target as HTMLInputElement).value)"
      />
      <span class="count muted">{{ symbols.length }} 个标的</span>
    </div>

    <div class="sym-strip">
      <button
        v-for="s in displayedSymbols"
        :key="s.vt_symbol"
        type="button"
        class="sym"
        :class="{ on: selected === s.vt_symbol }"
        :title="s.memo_preview || '无备忘'"
        @click="emit('select', s.vt_symbol)"
      >
        <span class="mono">{{ s.vt_symbol }}</span>
        <span class="badge">{{ s.entry_count }}</span>
      </button>
      <p v-if="loading" class="empty muted">加载中…</p>
      <p v-else-if="!symbols.length" class="hint muted">输入代码打开笔记</p>
      <p v-else-if="!displayedSymbols.length" class="empty muted">无匹配标的</p>
    </div>
  </section>
</template>

<style scoped>
.topbar {
  border: 1px solid var(--line);
  border-radius: 0.9rem;
  background: var(--surface);
  box-shadow: var(--shadow-card);
  padding: 12px 14px;
  display: grid;
  gap: 10px;
}
.topbar-head {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}
.open-group {
  display: grid;
  grid-template-columns: 220px auto;
  gap: 6px;
}
.open-group input {
  min-width: 0;
  background: var(--surface);
  border: 1px solid var(--line);
  color: var(--ink);
  border-radius: 0.5rem;
  padding: 8px 10px;
}
.filter {
  flex: 1;
  min-width: 160px;
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: 0.5rem;
  color: var(--ink);
  padding: 8px 10px;
}
.count {
  font-size: 0.75rem;
}

.sym-strip {
  display: flex;
  align-items: center;
  gap: 6px;
  overflow-x: auto;
  padding-bottom: 2px;
}
.sym {
  flex-shrink: 0;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: 999px;
  color: var(--ink);
  padding: 5px 12px;
  font-size: 0.82rem;
  transition:
    background 0.15s ease,
    border-color 0.15s ease,
    color 0.15s ease;
}
.sym:hover {
  border-color: var(--brand-soft);
  background: var(--surface-muted);
}
.sym.on {
  background: var(--brand);
  border-color: var(--brand);
  color: var(--brand-foreground);
}
.sym.on .badge {
  background: var(--brand-foreground);
  color: var(--brand);
  border-color: transparent;
}
.badge {
  font-size: 0.7rem;
  background: var(--brand-light);
  color: var(--brand-dark);
  border: 1px solid var(--brand-soft);
  border-radius: 999px;
  padding: 0 7px;
  line-height: 1.5;
}
.hint,
.empty {
  margin: 0;
  font-size: 0.85rem;
}

.primary {
  background: var(--brand);
  border: none;
  color: var(--brand-foreground);
  border-radius: 0.5rem;
  padding: 8px 12px;
  font-weight: 500;
  white-space: nowrap;
}

.mono {
  font-family: var(--mono);
}
.muted {
  color: var(--ink-muted);
  font-size: 0.8rem;
}
</style>
