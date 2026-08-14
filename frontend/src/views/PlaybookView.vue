<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import AppShell from '../components/AppShell.vue'
import { confirmDialog } from '../lib/dialog'
import {
  contentApi,
  type DisciplineCheck,
  type Plan,
  type PlaybookSection,
} from '../api/content'

const sections = ref<PlaybookSection[]>([])
const activeId = ref('')
const checks = ref<DisciplineCheck[]>([])
const plans = ref<Plan[]>([])
const editing = ref(false)
const draft = ref('')
const error = ref('')
const saving = ref(false)
const msg = ref('')
const historyOpen = ref(false)
const editingId = ref('')
const editNotes = ref('')
const editMaxPct = ref(30)
const editSymbols = ref<string[]>([])
const symbolDraft = ref('')
const acting = ref(false)

const active = computed(() => sections.value.find((s) => s.section_id === activeId.value) || sections.value[0])
const livePlans = computed(() => plans.value.filter((p) => p.status !== 'abandoned'))
const historyPlans = computed(() => plans.value.filter((p) => p.status === 'abandoned'))

async function load() {
  error.value = ''
  try {
    const [secs, disc, pls] = await Promise.all([
      contentApi.sections(),
      contentApi.discipline(),
      contentApi.plans(),
    ])
    sections.value = secs
    checks.value = disc
    plans.value = pls
    if (!activeId.value && secs.length) activeId.value = secs[0].section_id
    draft.value = active.value?.body_md || ''
  } catch (e) {
    error.value = e instanceof Error ? e.message : '加载失败'
  }
}

async function reloadPlans() {
  plans.value = await contentApi.plans()
}

function selectSection(id: string) {
  activeId.value = id
  editing.value = false
  draft.value = sections.value.find((s) => s.section_id === id)?.body_md || ''
}

async function toggleCheck(c: DisciplineCheck) {
  try {
    const updated = await contentApi.setDiscipline(c.check_id, !c.checked)
    checks.value = checks.value.map((x) => (x.check_id === updated.check_id ? updated : x))
  } catch (e) {
    error.value = e instanceof Error ? e.message : '更新失败'
  }
}

async function saveSection() {
  if (!active.value) return
  saving.value = true
  try {
    const updated = await contentApi.updateSection(active.value.section_id, { body_md: draft.value })
    sections.value = sections.value.map((s) => (s.section_id === updated.section_id ? updated : s))
    editing.value = false
  } catch (e) {
    error.value = e instanceof Error ? e.message : '保存失败'
  } finally {
    saving.value = false
  }
}

function startEdit(p: Plan) {
  editingId.value = p.id
  editNotes.value = p.notes || ''
  editMaxPct.value = Math.round((p.max_position_pct || 0) * 100)
  editSymbols.value = p.symbols.map((s) => s.vt_symbol)
  symbolDraft.value = ''
  msg.value = ''
}

function cancelEdit() {
  editingId.value = ''
}

function addSymbol() {
  const t = symbolDraft.value.trim()
  if (!t) return
  if (editSymbols.value.length >= 20) {
    error.value = '标的最多 20 只'
    return
  }
  if (!editSymbols.value.includes(t)) editSymbols.value = [...editSymbols.value, t]
  symbolDraft.value = ''
}

function removeSymbol(vt: string) {
  editSymbols.value = editSymbols.value.filter((x) => x !== vt)
}

async function saveEdit(id: string) {
  acting.value = true
  error.value = ''
  msg.value = ''
  try {
    const plan = plans.value.find((p) => p.id === id)
    const current = plan?.symbols.map((s) => s.vt_symbol) ?? []
    const next = [...editSymbols.value]
    const symbolsChanged =
      current.length !== next.length || current.some((vt, i) => vt !== next[i])
    const pct = Math.min(100, Math.max(1, Number(editMaxPct.value) || 1))
    editMaxPct.value = pct
    const body: { notes: string; max_position_pct: number; symbols?: string[] } = {
      notes: editNotes.value,
      max_position_pct: pct / 100,
    }
    if (symbolsChanged) body.symbols = next
    await contentApi.patchPlan(id, body)
    await reloadPlans()
    editingId.value = ''
    msg.value = '已保存'
  } catch (e) {
    error.value = e instanceof Error ? e.message : '保存失败'
  } finally {
    acting.value = false
  }
}

async function activate(id: string) {
  acting.value = true
  error.value = ''
  msg.value = ''
  try {
    await contentApi.activatePlan(id)
    await reloadPlans()
    msg.value = '已激活，回自选可看计划外'
  } catch (e) {
    error.value = e instanceof Error ? e.message : '激活失败'
  } finally {
    acting.value = false
  }
}

async function abandon(id: string) {
  const ok = await confirmDialog({
    title: '废弃计划',
    message: '确认废弃该计划？',
    danger: true,
  })
  if (!ok) return
  acting.value = true
  error.value = ''
  msg.value = ''
  try {
    await contentApi.abandonPlan(id)
    await reloadPlans()
    msg.value = '已废弃'
    if (editingId.value === id) editingId.value = ''
  } catch (e) {
    error.value = e instanceof Error ? e.message : '废弃失败'
  } finally {
    acting.value = false
  }
}

onMounted(() => {
  void load()
})
</script>

<template>
  <AppShell title="守则" subtitle="Playbook · 纪律 · 计划" active="playbook">
    <div class="page">
      <p v-if="error" class="err">{{ error }}</p>
      <p v-if="msg" class="ok">{{ msg }}</p>

      <section class="discipline">
        <h2>今日纪律</h2>
        <label v-for="c in checks" :key="c.check_id" class="check">
          <input type="checkbox" :checked="c.checked" @change="toggleCheck(c)" />
          <span>{{ c.label }}</span>
        </label>
      </section>

      <div class="main">
        <aside class="toc">
          <button
            v-for="s in sections"
            :key="s.section_id"
            type="button"
            :class="{ on: active?.section_id === s.section_id }"
            @click="selectSection(s.section_id)"
          >
            {{ s.title }}
          </button>
        </aside>
        <article class="body" v-if="active">
          <div class="head">
            <h2>{{ active.title }}</h2>
            <button class="ghost" type="button" @click="editing = !editing">{{ editing ? '取消' : '编辑' }}</button>
            <button v-if="editing" class="primary" type="button" :disabled="saving" @click="saveSection">
              保存
            </button>
          </div>
          <textarea v-if="editing" v-model="draft" rows="18" />
          <pre v-else class="md">{{ active.body_md }}</pre>
        </article>
      </div>

      <section class="plans" v-if="livePlans.length || historyPlans.length">
        <h2>交易计划</h2>
        <div
          class="plan"
          v-for="p in livePlans"
          :key="p.id"
          :class="{ active: p.status === 'active' }"
        >
          <div class="plan-head">
            <strong>{{ p.trade_date }}</strong>
            <span class="badge" :data-status="p.status">{{ p.status }}</span>
            <span class="muted">仓位上限 {{ (p.max_position_pct * 100).toFixed(0) }}%</span>
            <span v-if="p.status === 'active'" class="tip">自选计划外以此为准</span>
          </div>

          <template v-if="editingId === p.id">
            <label class="field">
              仓位上限 %
              <input type="number" v-model.number="editMaxPct" min="1" max="100" step="1" />
            </label>
            <label class="field">
              备注
              <input type="text" v-model="editNotes" />
            </label>
            <div class="syms">
              <span v-for="vt in editSymbols" :key="vt" class="chip">
                {{ vt }}
                <button type="button" class="chip-x" @click="removeSymbol(vt)">×</button>
              </span>
            </div>
            <div class="add-row">
              <input v-model="symbolDraft" placeholder="代码 如 600519.SSE" @keydown.enter.prevent="addSymbol" />
              <button type="button" class="ghost" @click="addSymbol">添加</button>
            </div>
            <div class="actions">
              <button type="button" class="primary" :disabled="acting" @click="saveEdit(p.id)">保存</button>
              <button type="button" class="ghost" :disabled="acting" @click="cancelEdit">取消</button>
            </div>
          </template>

          <template v-else>
            <div class="syms">
              <span v-for="s in p.symbols" :key="s.vt_symbol" class="chip">{{ s.vt_symbol }}</span>
            </div>
            <p v-if="p.notes" class="muted">{{ p.notes }}</p>
            <div class="actions">
              <button
                v-if="p.status === 'draft'"
                type="button"
                class="primary"
                :disabled="acting"
                @click="activate(p.id)"
              >
                激活
              </button>
              <button type="button" class="ghost" :disabled="acting" @click="startEdit(p)">编辑</button>
              <button type="button" class="ghost" :disabled="acting" @click="abandon(p.id)">废弃</button>
            </div>
          </template>
        </div>

        <div v-if="historyPlans.length" class="history">
          <button type="button" class="ghost" @click="historyOpen = !historyOpen">
            {{ historyOpen ? '收起历史' : `历史（${historyPlans.length}）` }}
          </button>
          <template v-if="historyOpen">
            <div class="plan muted-block" v-for="p in historyPlans" :key="p.id">
              <strong>{{ p.trade_date }}</strong>
              <span class="badge" data-status="abandoned">abandoned</span>
              <div class="syms">
                <span v-for="s in p.symbols" :key="s.vt_symbol" class="chip">{{ s.vt_symbol }}</span>
              </div>
              <p v-if="p.notes" class="muted">{{ p.notes }}</p>
            </div>
          </template>
        </div>
      </section>
    </div>
  </AppShell>
</template>

<style scoped>
.page {
  display: grid;
  gap: 16px;
}
.err {
  margin: 0;
  color: var(--danger);
}
.ok {
  margin: 0;
  color: var(--success, #2a9d6e);
}
.discipline {
  background: var(--bg-elevated);
  border: 1px solid var(--border);
  border-radius: 0.75rem;
  padding: 12px 14px;
  display: grid;
  gap: 8px;
}
.discipline h2,
.plans h2 {
  margin: 0 0 4px;
  font-size: 1rem;
}
.check {
  display: flex;
  gap: 8px;
  align-items: center;
  font-size: 0.9rem;
}
.main {
  display: grid;
  grid-template-columns: 220px 1fr;
  gap: 12px;
  min-height: 360px;
}
.toc {
  display: grid;
  gap: 6px;
  align-content: start;
}
.toc button {
  text-align: left;
  background: var(--surface);
  border: 1px solid var(--line);
  color: var(--ink-muted);
  border-radius: 0.5rem;
  padding: 8px 10px;
  transition: background 0.15s ease, color 0.15s ease, border-color 0.15s ease;
}
.toc button:hover {
  color: var(--ink);
  border-color: var(--brand-soft);
}
.toc button.on {
  background: var(--brand-light);
  color: var(--brand);
  border-color: var(--brand-soft);
  font-weight: 500;
}
.body {
  border: 1px solid var(--line);
  border-radius: 0.75rem;
  background: var(--surface);
  box-shadow: var(--shadow-card);
  padding: 16px 18px;
}
.head {
  display: flex;
  gap: 8px;
  align-items: center;
  margin-bottom: 10px;
}
.head h2 {
  margin: 0;
  flex: 1;
  font-size: 1.1rem;
}
.ghost,
.primary {
  border-radius: 0.5rem;
  padding: 6px 10px;
}
.ghost {
  background: transparent;
  border: 1px solid var(--border);
  color: var(--text);
}
.primary {
  background: var(--accent);
  border: none;
  color: var(--brand-foreground);
}
.primary:disabled,
.ghost:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}
textarea,
.md {
  width: 100%;
  background: var(--bg);
  border: 1px solid var(--border);
  border-radius: 0.5rem;
  color: var(--text);
  padding: 12px;
  font-family: var(--mono);
  font-size: 0.85rem;
  white-space: pre-wrap;
  line-height: 1.5;
  margin: 0;
}
.plan {
  border: 1px solid var(--border);
  border-radius: 0.75rem;
  padding: 10px 12px;
  margin-top: 8px;
  background: var(--bg-elevated);
  display: grid;
  gap: 4px;
}
.plan.active {
  border-color: var(--brand-soft, var(--accent));
  box-shadow: 0 0 0 1px var(--brand-soft, transparent);
}
.plan-head {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
}
.badge {
  font-size: 0.75rem;
  padding: 2px 8px;
  border-radius: 999px;
  border: 1px solid var(--border);
  background: var(--bg-panel);
  color: var(--muted);
  text-transform: lowercase;
}
.badge[data-status='active'] {
  color: var(--brand, var(--accent));
  border-color: var(--brand-soft, var(--accent));
  background: var(--brand-light, var(--bg-panel));
}
.badge[data-status='draft'] {
  color: var(--ink-muted, var(--muted));
}
.badge[data-status='abandoned'] {
  opacity: 0.8;
}
.tip {
  font-size: 0.8rem;
  color: var(--brand, var(--accent));
}
.field {
  display: grid;
  gap: 4px;
  font-size: 0.85rem;
  color: var(--muted);
}
.field input {
  background: var(--bg);
  border: 1px solid var(--border);
  border-radius: 0.5rem;
  color: var(--text);
  padding: 6px 10px;
}
.add-row {
  display: flex;
  gap: 8px;
  align-items: center;
}
.add-row input {
  flex: 1;
  background: var(--bg);
  border: 1px solid var(--border);
  border-radius: 0.5rem;
  color: var(--text);
  padding: 6px 10px;
}
.actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 4px;
}
.syms {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.chip {
  background: var(--bg-panel);
  border: 1px solid var(--border);
  border-radius: 999px;
  padding: 2px 8px;
  font-size: 0.8rem;
  display: inline-flex;
  align-items: center;
  gap: 4px;
}
.chip-x {
  border: none;
  background: transparent;
  color: var(--muted);
  cursor: pointer;
  padding: 0 2px;
  line-height: 1;
  font-size: 0.95rem;
}
.history {
  margin-top: 12px;
  display: grid;
  gap: 8px;
}
.muted-block {
  opacity: 0.75;
}
.muted {
  color: var(--muted);
  font-size: 0.85rem;
}
@media (max-width: 900px) {
  .main {
    grid-template-columns: 1fr;
  }
}
</style>
