<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import AppShell from '../components/AppShell.vue'
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

const active = computed(() => sections.value.find((s) => s.section_id === activeId.value) || sections.value[0])

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

onMounted(() => {
  void load()
})
</script>

<template>
  <AppShell title="守则" subtitle="Playbook · 纪律 · 计划" active="playbook">
    <div class="page">
      <p v-if="error" class="err">{{ error }}</p>

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

      <section class="plans" v-if="plans.length">
        <h2>交易计划</h2>
        <div class="plan" v-for="p in plans.slice(0, 5)" :key="p.id">
          <strong>{{ p.trade_date }}</strong>
          <span class="muted">{{ p.status }} · 仓位上限 {{ (p.max_position_pct * 100).toFixed(0) }}%</span>
          <div class="syms">
            <span v-for="s in p.symbols" :key="s.vt_symbol" class="chip">{{ s.vt_symbol }}</span>
          </div>
          <p v-if="p.notes" class="muted">{{ p.notes }}</p>
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
