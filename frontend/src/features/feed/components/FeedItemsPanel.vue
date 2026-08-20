<script setup lang="ts">
import { computed, ref } from 'vue'
import PagerBar from '../../../components/PagerBar.vue'
import { fmtDateTime } from '../../../lib/format'
import type { FeedItem } from '../../../api/content'

const props = defineProps<{
  items: FeedItem[]
  itemsPage: number
  itemsPages: number
  itemsTotal: number
  hasSubs: boolean
  loading: boolean
}>()

const emit = defineEmits<{
  refresh: []
  select: [item: FeedItem]
  'page-change': [page: number]
}>()

const listFilter = ref('')
const unreadOnly = ref(false)

const ITEM_TYPE_LABELS: Record<string, string> = {
  video: '视频',
  dynamic: '动态',
}

const displayedItems = computed(() => {
  const q = listFilter.value.trim().toLowerCase()
  let list = props.items
  if (q) {
    list = list.filter((it) => {
      const t = (it.title || '').toLowerCase()
      const a = (it.author_name || '').toLowerCase()
      const s = (it.summary || '').toLowerCase()
      return t.includes(q) || a.includes(q) || s.includes(q)
    })
  }
  if (unreadOnly.value) {
    list = list.filter((it) => !it.is_read)
  }
  return list
})

function itemTypeLabel(t: string): string {
  return ITEM_TYPE_LABELS[t] || ''
}
</script>

<template>
  <section class="feed">
    <div class="right-head">
      <div class="right-title-row">
        <h2 class="right-title">动态</h2>
        <span class="count muted">{{ displayedItems.length }}</span>
      </div>
      <button class="ghost" type="button" :disabled="loading" @click="emit('refresh')">刷新</button>
    </div>

    <div v-if="items.length" class="filter-row">
      <input v-model="listFilter" placeholder="过滤标题 / 作者 / 摘要" />
      <label class="check-label">
        <input v-model="unreadOnly" type="checkbox" />
        <span>仅看未读</span>
      </label>
    </div>

    <div class="feed-list">
      <p v-if="loading" class="empty muted">加载中…</p>
      <template v-else>
        <p v-if="!hasSubs" class="empty muted">暂无订阅</p>
        <p v-else-if="!items.length" class="empty muted">
          暂无动态。可到「调度」执行 B 站订阅同步。
          <RouterLink to="/scheduler" class="link">去调度</RouterLink>
        </p>
        <p v-else-if="!displayedItems.length" class="empty muted">无匹配动态</p>
        <article
          v-for="(item, i) in displayedItems"
          :key="item.id"
          class="item"
          :class="{ unread: !item.is_read }"
          :style="{ '--i': i }"
          @click="emit('select', item)"
        >
          <div class="item-head">
            <div class="item-byline">
              <span class="item-author">{{ item.author_name || '未知作者' }}</span>
              <span class="item-time">{{ fmtDateTime(item.published_at) }}</span>
            </div>
            <span v-if="itemTypeLabel(item.item_type)" class="item-type">{{
              itemTypeLabel(item.item_type)
            }}</span>
            <span v-if="!item.is_read" class="unread-dot" title="未读"></span>
          </div>
          <h3 class="item-title">{{ item.title || '(无标题)' }}</h3>
          <p v-if="item.summary" class="item-summary">{{ item.summary }}</p>
          <span class="item-open">打开 ↗</span>
        </article>
        <PagerBar
          :page="itemsPage"
          :pages="itemsPages"
          :total="itemsTotal"
          @change="emit('page-change', $event)"
        />
      </template>
    </div>
  </section>
</template>

<style scoped>
.feed {
  grid-area: feed;
  min-height: 0;
  border: 1px solid var(--line);
  border-radius: 0.9rem;
  background: var(--surface);
  box-shadow: var(--shadow-card);
  display: flex;
  flex-direction: column;
  padding: 14px 16px;
  overflow: hidden;
}
.right-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}
.right-title-row {
  display: flex;
  align-items: baseline;
  gap: 8px;
}
.right-title {
  margin: 0;
  font-size: 1rem;
  font-weight: 600;
  color: var(--ink);
}
.count {
  font-size: 0.75rem;
}
.ghost {
  border: 1px solid var(--line);
  background: var(--surface);
  color: var(--ink-muted);
  border-radius: 0.5rem;
  padding: 8px 12px;
  white-space: nowrap;
}
.ghost:hover:not(:disabled) {
  background: var(--brand-light);
  color: var(--brand);
  border-color: var(--brand-soft);
}
.ghost:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}
.check-label {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 0.8125rem;
  color: var(--ink-muted);
  cursor: pointer;
  user-select: none;
}
.check-label input {
  accent-color: var(--brand);
}
.filter-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
  padding: 10px 0;
  border-bottom: 1px solid var(--line-soft);
  margin-bottom: 4px;
}
.filter-row input {
  flex: 1;
  min-width: 160px;
  background: var(--surface);
  border: 1px solid var(--line);
  color: var(--ink);
  border-radius: 0.5rem;
  padding: 8px 10px;
}

.feed-list {
  display: grid;
  gap: 10px;
  padding-top: 6px;
  flex: 1;
  min-height: 0;
  overflow: auto;
  align-content: start;
}
.empty {
  text-align: center;
  padding: 32px 16px;
  margin: 0;
  color: var(--ink-muted);
}
.link {
  color: var(--brand);
  margin-left: 4px;
}
.link:hover {
  text-decoration: underline;
}

.item {
  position: relative;
  border: 1px solid var(--line);
  border-radius: 0.8rem;
  padding: 12px 14px;
  cursor: pointer;
  background: var(--surface);
  transition:
    border-color 0.15s ease,
    box-shadow 0.15s ease,
    transform 0.15s ease;
  animation: rise 0.32s ease both;
  animation-delay: calc(min(var(--i), 14) * 22ms);
}
@keyframes rise {
  from {
    opacity: 0;
    transform: translateY(6px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}
.item:hover {
  border-color: var(--brand-soft);
  box-shadow: var(--shadow-panel);
  transform: translateY(-1px);
}
.item.unread {
  border-color: var(--brand-soft);
  background: linear-gradient(90deg, var(--brand-light), var(--surface) 32%);
}
.item-head {
  display: flex;
  align-items: center;
  gap: 8px;
}
.item-byline {
  display: flex;
  flex-direction: column;
  min-width: 0;
  line-height: 1.2;
}
.item-author {
  font-size: 0.82rem;
  font-weight: 500;
  color: var(--ink);
}
.item-time {
  font-size: 0.72rem;
  color: var(--ink-faint);
}
.item-type {
  margin-left: auto;
  font-size: 0.7rem;
  color: var(--brand-dark);
  background: var(--brand-light);
  border: 1px solid var(--brand-soft);
  border-radius: 999px;
  padding: 1px 8px;
  flex-shrink: 0;
}
.unread-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--brand);
  flex-shrink: 0;
  box-shadow: 0 0 0 3px var(--brand-light);
}
.item-title {
  margin: 8px 0 4px;
  font-size: 1.02rem;
  font-weight: 600;
  color: var(--ink);
  line-height: 1.4;
}
.item-summary {
  margin: 0;
  color: var(--ink-muted);
  font-size: 0.85rem;
  line-height: 1.55;
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.item-open {
  display: inline-block;
  margin-top: 8px;
  font-size: 0.75rem;
  color: var(--ink-faint);
  opacity: 0;
  transform: translateY(2px);
  transition:
    opacity 0.15s ease,
    color 0.15s ease,
    transform 0.15s ease;
}
.item:hover .item-open {
  opacity: 1;
  transform: translateY(0);
  color: var(--brand);
}

@media (max-width: 900px) {
  .feed {
    overflow: visible;
  }
}
</style>
