<script setup lang="ts">
import { RouterLink } from 'vue-router'
import MarkdownView from '../../../components/MarkdownView.vue'
import PagerBar from '../../../components/PagerBar.vue'
import { fmtDateTime } from '../../../lib/format'
import type { TeamReport, TeamReportListItem } from '../../../api/content'

defineProps<{
  selected: string
  reports: TeamReportListItem[]
  displayedReports: TeamReportListItem[]
  reportFilter: string
  activeReport: TeamReport | null
  reportsPage: number
  reportsPages: number
  reportsTotal: number
}>()

const emit = defineEmits<{
  'update:reportFilter': [value: string]
  openReport: [id: number]
  pageChange: [page: number]
}>()
</script>

<template>
  <div class="reports-grid">
    <section class="panel reports-panel">
      <div class="panel-head">
        <h3>
          研报 <span class="count muted">{{ reportsTotal }}</span>
        </h3>
      </div>
      <p v-if="!reports.length" class="empty muted">
        暂无研报。
        <RouterLink :to="{ path: '/ai', query: { symbol: selected } }" class="link">
          去 AI 跑投研团队
        </RouterLink>
      </p>
      <template v-else>
        <input
          :value="reportFilter"
          class="filter"
          placeholder="过滤标题 / 摘要"
          @input="emit('update:reportFilter', ($event.target as HTMLInputElement).value)"
        />
        <p v-if="!displayedReports.length" class="empty muted">无匹配研报</p>
        <div class="report-list">
          <button
            v-for="r in displayedReports"
            :key="r.id"
            type="button"
            class="report-item"
            :class="{ on: activeReport?.id === r.id }"
            @click="emit('openReport', r.id)"
          >
            <div class="report-title">{{ r.title }}</div>
            <div class="report-meta muted">{{ fmtDateTime(r.created_at) }} · {{ r.mode }}</div>
            <div class="report-summary muted">{{ r.summary }}</div>
          </button>
        </div>
        <PagerBar
          :page="reportsPage"
          :pages="reportsPages"
          :total="reportsTotal"
          @change="emit('pageChange', $event)"
        />
      </template>
    </section>

    <article v-if="activeReport" class="panel report-body">
      <h3>{{ activeReport.title }}</h3>
      <MarkdownView :source="activeReport.body" />
    </article>
    <div v-else class="panel report-body empty-state muted">选择一份研报查看详情</div>
  </div>
</template>

<style scoped>
.reports-grid {
  display: grid;
  grid-template-columns: 320px minmax(0, 1fr);
  gap: 12px;
  flex: 1;
  min-height: 0;
}
.panel {
  border: 1px solid var(--line-soft);
  border-radius: 0.8rem;
  background: var(--surface);
  padding: 14px 16px;
  display: flex;
  flex-direction: column;
  gap: 10px;
  min-height: 0;
}
.panel-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-shrink: 0;
}
.panel-head h3 {
  margin: 0;
  font-size: 0.95rem;
  font-weight: 600;
  color: var(--ink);
}
.reports-panel {
  overflow: auto;
}
.filter {
  min-width: 0;
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: 0.5rem;
  color: var(--ink);
  padding: 8px 10px;
}
.report-list {
  display: grid;
  gap: 6px;
  overflow: auto;
  flex: 1;
  align-content: start;
}
.report-item {
  text-align: left;
  background: var(--surface);
  border: 1px solid var(--line-soft);
  border-radius: 0.6rem;
  color: var(--ink);
  padding: 10px 12px;
  display: grid;
  gap: 4px;
  transition:
    border-color 0.15s ease,
    background 0.15s ease;
}
.report-item:hover {
  border-color: var(--brand-soft);
  background: var(--surface-muted);
}
.report-item.on {
  border-color: var(--brand);
  background: var(--brand-light);
}
.report-title {
  font-weight: 600;
  font-size: 0.9rem;
}
.report-meta {
  font-size: 0.75rem;
}
.report-summary {
  font-size: 0.8rem;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.report-body {
  overflow: auto;
  align-content: start;
}
.report-body h3 {
  margin: 0 0 8px;
  font-size: 1.05rem;
}
.count {
  font-size: 0.75rem;
}
.empty {
  margin: 0;
  font-size: 0.85rem;
}
.link {
  background: none;
  border: none;
  color: var(--ink-faint);
  padding: 0;
  font-size: 0.78rem;
}
.link:hover {
  color: var(--danger);
}
.empty-state {
  display: grid;
  place-items: center;
  color: var(--ink-muted);
  font-size: 0.9rem;
  padding: 40px;
}
.muted {
  color: var(--ink-muted);
  font-size: 0.8rem;
}

@media (max-width: 900px) {
  .reports-grid {
    grid-template-columns: 1fr;
  }
}
</style>
