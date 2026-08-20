<script setup lang="ts">
import { computed, ref } from 'vue'
import type { BilibiliUserHit, FeedSub } from '../../../api/content'

const props = defineProps<{
  open: boolean
  subs: FeedSub[]
  subId: string
  error: string
  adding: boolean
  searching: boolean
  searchHits: BilibiliUserHit[]
  searchTried: boolean
  newMid: string
  syncOnAdd: boolean
  searchQ: string
}>()

const emit = defineEmits<{
  'update:open': [value: boolean]
  'update:newMid': [value: string]
  'update:syncOnAdd': [value: boolean]
  'update:searchQ': [value: string]
  select: [sub: FeedSub]
  toggle: [sub: FeedSub]
  remove: [sub: FeedSub]
  add: []
  'add-hit': [hit: BilibiliUserHit]
  search: []
}>()

const subFilter = ref('')
const enabledOnly = ref(false)

const displayedSubs = computed(() => {
  let list = props.subs
  if (enabledOnly.value) {
    list = list.filter((s) => s.enabled)
  }
  const q = subFilter.value.trim().toLowerCase()
  if (!q) return list
  return list.filter((s) => {
    const name = (s.display_name || '').toLowerCase()
    const mid = (s.source_id || '').toLowerCase()
    return name.includes(q) || mid.includes(q)
  })
})

function close() {
  emit('update:open', false)
}
</script>

<template>
  <Teleport to="body">
    <Transition name="fade">
      <div
        v-if="open"
        class="overlay"
        @click.self="close"
        @keydown.esc="close"
      >
        <div class="manager" role="dialog" aria-modal="true" aria-label="订阅管理">
          <h3 class="manager-title">订阅管理</h3>
          <p v-if="error" class="err">{{ error }}</p>

          <div class="manager-block">
            <div class="manager-sub-head">
              <strong class="manager-label">订阅列表</strong>
              <span class="count muted">{{ subs.length }}</span>
            </div>
            <input v-model="subFilter" class="sub-filter" placeholder="过滤订阅名 / mid" />
            <label class="check-label">
              <input v-model="enabledOnly" type="checkbox" />
              <span>仅看启用</span>
            </label>
            <p v-if="subs.length && !displayedSubs.length" class="muted tiny-text">无匹配订阅</p>
            <p v-if="!subs.length" class="muted tiny-text">暂无订阅，可从下方添加</p>
            <div class="sub-list">
              <div
                v-for="s in displayedSubs"
                :key="s.id"
                class="sub-row"
                :class="{ on: subId === s.id, off: !s.enabled }"
              >
                <button
                  type="button"
                  class="sub-name"
                  :title="s.source_id"
                  @click="emit('select', s)"
                >
                  {{ s.display_name || s.source_id }}
                </button>
                <button
                  type="button"
                  class="icon-btn"
                  :class="{ on: s.enabled }"
                  :title="s.enabled ? '停用' : '启用'"
                  @click="emit('toggle', s)"
                >
                  {{ s.enabled ? '开' : '关' }}
                </button>
                <button type="button" class="icon-btn danger" title="删除" @click="emit('remove', s)">
                  删
                </button>
              </div>
            </div>
          </div>

          <div class="divider"></div>

          <strong class="manager-label">添加订阅</strong>
          <div class="row">
            <input
              :value="newMid"
              placeholder="输入 UP 的 mid"
              @input="emit('update:newMid', ($event.target as HTMLInputElement).value)"
              @keyup.enter="emit('add')"
            />
            <button type="button" class="primary" :disabled="adding" @click="emit('add')">添加</button>
          </div>
          <label class="check-label">
            <input
              type="checkbox"
              :checked="syncOnAdd"
              @change="emit('update:syncOnAdd', ($event.target as HTMLInputElement).checked)"
            />
            <span>添加后立即同步</span>
          </label>

          <div class="divider"></div>

          <div class="row">
            <input
              :value="searchQ"
              placeholder="搜索 UP 主（关键词）"
              @input="emit('update:searchQ', ($event.target as HTMLInputElement).value)"
              @keyup.enter="emit('search')"
            />
            <button type="button" class="ghost" :disabled="searching" @click="emit('search')">
              {{ searching ? '搜索中' : '搜索' }}
            </button>
          </div>

          <div v-if="searchHits.length" class="hits">
            <div v-for="h in searchHits" :key="h.mid" class="hit-row">
              <div class="hit-meta">
                <div class="hit-name">{{ h.name || h.mid }}</div>
                <div class="muted tiny-text">mid {{ h.mid }}</div>
              </div>
              <button type="button" class="tiny" :disabled="adding" @click="emit('add-hit', h)">
                添加
              </button>
            </div>
          </div>
          <p v-else-if="searchTried && !searching" class="muted tiny-text">无搜索结果</p>

          <div class="manager-actions">
            <button type="button" class="ghost" @click="close">关闭</button>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.err {
  margin: 0;
  color: var(--danger);
  font-size: 0.85rem;
}
.count {
  font-size: 0.75rem;
}
.row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 6px;
}
.row input {
  min-width: 0;
  background: var(--surface);
  border: 1px solid var(--line);
  color: var(--ink);
  border-radius: 0.5rem;
  padding: 8px 10px;
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
.primary {
  background: var(--brand);
  border: none;
  color: var(--brand-foreground);
  border-radius: 0.5rem;
  padding: 8px 12px;
  font-weight: 500;
  white-space: nowrap;
}
.primary:disabled {
  opacity: 0.55;
  cursor: not-allowed;
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

.hits {
  display: grid;
  gap: 4px;
  border: 1px solid var(--line-soft);
  border-radius: 0.6rem;
  padding: 6px;
  background: var(--surface-muted);
}
.hit-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 8px;
  align-items: center;
}
.hit-meta {
  min-width: 0;
}
.hit-name {
  font-size: 0.85rem;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.tiny-text {
  font-size: 0.72rem;
}
.tiny {
  background: transparent;
  border: 1px solid var(--line);
  color: var(--brand);
  border-radius: 0.5rem;
  padding: 2px 8px;
  font-size: 0.75rem;
}
.tiny:hover:not(:disabled) {
  background: var(--brand-light);
}
.tiny:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.sub-filter {
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: 0.5rem;
  color: var(--ink);
  padding: 8px 10px;
  width: 100%;
}
.sub-list {
  display: grid;
  gap: 2px;
  overflow: auto;
  max-height: 180px;
}
.sub-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto auto;
  gap: 6px;
  align-items: center;
  border-radius: 0.5rem;
  padding: 4px 4px;
}
.sub-row:hover {
  background: var(--surface-muted);
}
.sub-row.on {
  background: var(--brand-light);
}
.sub-row.off .sub-name {
  color: var(--ink-faint);
}
.sub-name {
  min-width: 0;
  text-align: left;
  background: transparent;
  border: none;
  color: var(--ink);
  padding: 6px 4px;
  font-size: 0.85rem;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.icon-btn {
  background: transparent;
  border: 1px solid var(--line);
  color: var(--ink-muted);
  border-radius: 0.4rem;
  padding: 2px 7px;
  font-size: 0.72rem;
}
.icon-btn:hover {
  background: var(--surface);
}
.icon-btn.on {
  color: var(--ok);
  border-color: #86efac;
  background: #ecfdf5;
}
.icon-btn.danger {
  color: var(--danger);
}
.icon-btn.danger:hover {
  background: #fff1f2;
  border-color: var(--danger);
}

.overlay {
  position: fixed;
  inset: 0;
  z-index: 1000;
  display: grid;
  place-items: center;
  background: rgba(0, 0, 0, 0.4);
  padding: 24px;
}
.manager {
  width: 100%;
  max-width: 420px;
  max-height: min(620px, calc(100vh - 48px));
  overflow: auto;
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: 0.875rem;
  box-shadow: var(--shadow-panel);
  padding: 20px;
  display: grid;
  gap: 12px;
  align-content: start;
}
.manager-title {
  margin: 0;
  font-size: 1.05rem;
  font-weight: 600;
  color: var(--ink);
}
.manager-block {
  display: grid;
  gap: 8px;
  padding: 10px 12px;
  border: 1px solid var(--line-soft);
  border-radius: 0.6rem;
  background: var(--surface-muted);
}
.manager-sub-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 8px;
}
.manager-label {
  font-size: 0.82rem;
  font-weight: 600;
  color: var(--ink);
}
.divider {
  height: 1px;
  background: var(--line-soft);
  margin: 2px 0;
}
.manager-actions {
  display: flex;
  justify-content: flex-end;
  padding-top: 4px;
}
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.18s ease;
}
.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>
