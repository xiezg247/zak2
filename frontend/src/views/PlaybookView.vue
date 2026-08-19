<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import AppShell from '../components/AppShell.vue'
import MarkdownView from '../components/MarkdownView.vue'
import { contentApi, type DisciplineCheck, type PlaybookSection } from '../api/content'

const sections = ref<PlaybookSection[]>([])
const activeId = ref('')
const checks = ref<DisciplineCheck[]>([])
const editing = ref(false)
const draft = ref('')
const error = ref('')
const saving = ref(false)
const msg = ref('')

const active = computed(
  () => sections.value.find((s) => s.section_id === activeId.value) || sections.value[0],
)
const doneCount = computed(() => checks.value.filter((c) => c.checked).length)
const donePct = computed(() =>
  checks.value.length ? Math.round((doneCount.value / checks.value.length) * 100) : 0,
)

async function load() {
  error.value = ''
  try {
    const [secs, disc] = await Promise.all([contentApi.sections(), contentApi.discipline()])
    sections.value = secs
    checks.value = disc
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
    const updated = await contentApi.updateSection(active.value.section_id, {
      body_md: draft.value,
    })
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
  <AppShell title="守则" subtitle="Playbook · 纪律" active="playbook">
    <div class="page">
      <p v-if="error" class="banner err">{{ error }}</p>
      <p v-if="msg" class="banner ok">{{ msg }}</p>

      <div class="top">
        <aside class="discipline">
          <div class="discipline-head">
            <h2>今日纪律</h2>
            <span class="count mono">{{ doneCount }}/{{ checks.length }}</span>
          </div>
          <p class="sub">开盘前的自我检查</p>
          <div v-if="checks.length" class="progress" aria-hidden="true">
            <span class="progress-fill" :style="{ width: donePct + '%' }"></span>
          </div>

          <div v-if="checks.length" class="check-list">
            <label v-for="c in checks" :key="c.check_id" class="check" :class="{ done: c.checked }">
              <input type="checkbox" :checked="c.checked" @change="toggleCheck(c)" />
              <span class="check-box" aria-hidden="true"></span>
              <span class="check-label">{{ c.label }}</span>
            </label>
          </div>
          <p v-else class="empty muted">暂无纪律项</p>
        </aside>

        <article class="manual">
          <nav v-if="sections.length" class="tabs" aria-label="守则章节">
            <button
              v-for="s in sections"
              :key="s.section_id"
              type="button"
              :class="{ on: active?.section_id === s.section_id }"
              @click="selectSection(s.section_id)"
            >
              {{ s.title }}
            </button>
          </nav>
          <template v-if="active">
            <div class="manual-head">
              <h2>{{ active.title }}</h2>
              <button class="ghost" type="button" @click="editing = !editing">
                {{ editing ? '取消' : '编辑' }}
              </button>
              <button
                v-if="editing"
                class="primary"
                type="button"
                :disabled="saving"
                @click="saveSection"
              >
                {{ saving ? '保存中…' : '保存' }}
              </button>
            </div>
            <textarea v-if="editing" v-model="draft" rows="16" />
            <MarkdownView v-else :source="active.body_md" />
          </template>
          <p v-else class="empty muted">暂无守则内容</p>
        </article>
      </div>
    </div>
  </AppShell>
</template>

<style scoped>
.page {
  display: grid;
  gap: 20px;
  padding: 20px 24px 28px;
}

.banner {
  margin: 0;
  padding: 10px 14px;
  border-radius: 0.5rem;
  font-size: 0.875rem;
  border: 1px solid transparent;
}
.banner.err {
  color: var(--danger);
  background: #fef2f2;
  border-color: #fecaca;
}
.banner.ok {
  color: var(--ok);
  background: #f0fdf4;
  border-color: #bbf7d0;
}

/* ── 顶部：纪律侧栏 + 守则手册 ─────────────────────────── */
.top {
  display: grid;
  grid-template-columns: 280px 1fr;
  gap: 16px;
  align-items: start;
}

.discipline,
.manual {
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: 0.875rem;
  box-shadow: var(--shadow-card);
}

.discipline {
  position: sticky;
  top: 16px;
  padding: 16px 16px 14px;
  display: grid;
  gap: 10px;
}
.discipline-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 8px;
}
.discipline-head h2 {
  margin: 0;
  font-size: 1rem;
  font-weight: 600;
  letter-spacing: -0.01em;
}
.discipline .sub {
  margin: -4px 0 0;
  font-size: 0.75rem;
  color: var(--ink-faint);
}
.count {
  font-size: 1.05rem;
  font-weight: 600;
  color: var(--brand);
  font-variant-numeric: tabular-nums;
}
.progress {
  height: 6px;
  border-radius: 999px;
  background: var(--line-soft);
  overflow: hidden;
}
.progress-fill {
  display: block;
  height: 100%;
  border-radius: 999px;
  background: linear-gradient(90deg, var(--brand), #f5936a);
  transition: width 0.3s ease;
}

.check-list {
  display: grid;
  gap: 2px;
}
.check {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 10px;
  border-radius: 0.5rem;
  cursor: pointer;
  transition: background 0.15s ease;
}
.check:hover {
  background: var(--surface-muted);
}
.check input {
  position: absolute;
  opacity: 0;
  width: 1px;
  height: 1px;
}
.check-box {
  flex-shrink: 0;
  width: 18px;
  height: 18px;
  border-radius: 6px;
  border: 1.5px solid var(--line);
  background: var(--surface);
  position: relative;
  transition:
    background 0.15s ease,
    border-color 0.15s ease;
}
.check-box::after {
  content: '';
  position: absolute;
  left: 5px;
  top: 1.5px;
  width: 5px;
  height: 9px;
  border: solid #fff;
  border-width: 0 2px 2px 0;
  transform: rotate(45deg) scale(0);
  transition: transform 0.15s ease;
}
.check.done .check-box {
  background: var(--brand);
  border-color: var(--brand);
}
.check.done .check-box::after {
  transform: rotate(45deg) scale(1);
}
.check-label {
  font-size: 0.875rem;
  line-height: 1.4;
  transition:
    color 0.15s ease,
    opacity 0.15s ease;
}
.check.done .check-label {
  color: var(--ink-faint);
  text-decoration: line-through;
  text-decoration-color: var(--line);
}

/* ── 守则手册 ─────────────────────────── */
.manual {
  padding: 16px 20px 20px;
  display: grid;
  gap: 14px;
  min-height: 360px;
}
.tabs {
  display: flex;
  gap: 4px;
  flex-wrap: wrap;
  padding-bottom: 12px;
  border-bottom: 1px solid var(--line-soft);
}
.tabs button {
  border-radius: 0.5rem;
  border: 1px solid transparent;
  background: transparent;
  color: var(--ink-muted);
  padding: 7px 12px;
  font-size: 0.8125rem;
  transition:
    background 0.15s ease,
    color 0.15s ease;
}
.tabs button:hover {
  color: var(--ink);
  background: var(--surface-muted);
}
.tabs button.on {
  background: var(--brand-light);
  color: var(--brand);
  font-weight: 500;
}
.manual-head {
  display: flex;
  align-items: center;
  gap: 8px;
}
.manual-head h2 {
  margin: 0;
  flex: 1;
  font-size: 1.15rem;
  font-weight: 600;
  letter-spacing: -0.01em;
}

textarea {
  width: 100%;
  background: var(--surface-muted);
  border: 1px solid var(--line);
  border-radius: 0.625rem;
  color: var(--ink);
  padding: 14px;
  font-family: var(--mono);
  font-size: 0.85rem;
  white-space: pre-wrap;
  line-height: 1.7;
  margin: 0;
  resize: vertical;
}
textarea:focus {
  border-color: var(--brand);
  box-shadow: 0 0 0 3px rgba(230, 100, 50, 0.15);
  outline: none;
}

/* ── 按钮 ─────────────────────────── */
.ghost,
.primary {
  border-radius: 0.5rem;
  padding: 7px 12px;
  font-size: 0.8125rem;
  font-weight: 500;
  transition:
    background 0.15s ease,
    color 0.15s ease,
    border-color 0.15s ease,
    opacity 0.15s ease;
}
.ghost {
  background: var(--surface);
  border: 1px solid var(--line);
  color: var(--ink-muted);
}
.ghost:hover:not(:disabled) {
  background: var(--brand-light);
  color: var(--brand);
  border-color: var(--brand-soft);
}
.primary {
  background: var(--brand);
  border: none;
  color: var(--brand-foreground);
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.05);
}
.primary:hover:not(:disabled) {
  background: var(--brand-dark);
}
.primary:disabled,
.ghost:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

.mono {
  font-family: var(--mono);
}
.muted {
  color: var(--ink-muted);
}
.empty {
  margin: 0;
  font-size: 0.85rem;
  padding: 12px 0;
  text-align: center;
}

@media (max-width: 900px) {
  .top {
    grid-template-columns: 1fr;
  }
  .discipline {
    position: static;
  }
}
</style>
