<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import AppShell from '../components/AppShell.vue'
import PagerBar from '../components/PagerBar.vue'
import { confirmDialog } from '../lib/dialog'
import { contentApi, type BilibiliUserHit, type FeedItem, type FeedSub } from '../api/content'

const subs = ref<FeedSub[]>([])
const subId = ref('')
const items = ref<FeedItem[]>([])
const itemsPage = ref(1)
const itemsPages = ref(0)
const itemsTotal = ref(0)
const newMid = ref('')
const syncOnAdd = ref(false)
const adding = ref(false)
const error = ref('')
const loading = ref(false)
const searchQ = ref('')
const searchHits = ref<BilibiliUserHit[]>([])
const searching = ref(false)
const searchTried = ref(false)
const listFilter = ref('')
const unreadOnly = ref(false)
const subFilter = ref('')
const enabledOnly = ref(false)
const manageOpen = ref(false)

const subtitle = computed(() => `${subs.value.length} 订阅 · ${itemsTotal.value} 条`)

const ITEM_TYPE_LABELS: Record<string, string> = {
  video: '视频',
  dynamic: '动态',
}

const displayedSubs = computed(() => {
  let list = subs.value
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

const displayedItems = computed(() => {
  const q = listFilter.value.trim().toLowerCase()
  let list = items.value
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

async function load() {
  loading.value = true
  error.value = ''
  itemsPage.value = 1
  try {
    await Promise.all([loadSubs(), loadItems()])
  } catch (e) {
    error.value = e instanceof Error ? e.message : '加载失败'
  } finally {
    loading.value = false
  }
}

async function loadSubs() {
  subs.value = await contentApi.feedSubs()
}

async function loadItems() {
  const p = await contentApi.feedItemsPage(subId.value || undefined, itemsPage.value, 20)
  items.value = p.items
  itemsTotal.value = p.total
  itemsPages.value = p.pages
}

async function goItemsPage(p: number) {
  itemsPage.value = p
  await loadItems()
}

function selectItem(item: FeedItem) {
  if (!item.is_read) {
    item.is_read = true
    void contentApi.markRead(item.id)
  }
  window.open(item.url, '_blank', 'noopener,noreferrer')
}

async function toggleSub(s: FeedSub) {
  await contentApi.setFeedEnabled(s.id, !s.enabled)
  await load()
}

async function runSearch() {
  const q = searchQ.value.trim()
  searching.value = true
  error.value = ''
  searchTried.value = true
  try {
    const res = await contentApi.searchBilibiliUps(q)
    searchHits.value = res.results
  } catch (e) {
    searchHits.value = []
    error.value = e instanceof Error ? e.message : '搜索失败'
  } finally {
    searching.value = false
  }
}

async function addFromHit(hit: BilibiliUserHit) {
  adding.value = true
  error.value = ''
  try {
    const sub = await contentApi.addFeedSub({ mid: hit.mid, sync_now: syncOnAdd.value })
    const syncErr = sub.sync_error
    await load()
    if (syncErr) {
      error.value = `已添加，但同步失败：${syncErr}`
    }
  } catch (e) {
    error.value = e instanceof Error ? e.message : '添加失败'
  } finally {
    adding.value = false
  }
}

async function addSub() {
  const mid = newMid.value.trim()
  if (!mid) return
  adding.value = true
  error.value = ''
  try {
    const sub = await contentApi.addFeedSub({ mid, sync_now: syncOnAdd.value })
    newMid.value = ''
    const syncErr = sub.sync_error
    await load()
    // load() 会清空 error；同步失败提示须在刷新后再写
    if (syncErr) {
      error.value = `已添加，但同步失败：${syncErr}`
    }
  } catch (e) {
    error.value = e instanceof Error ? e.message : '添加失败'
  } finally {
    adding.value = false
  }
}

async function removeSub(s: FeedSub) {
  const name = s.display_name || s.source_id
  const ok = await confirmDialog({
    title: '删除订阅',
    message: `确定删除订阅「${name}」？`,
    danger: true,
  })
  if (!ok) return
  error.value = ''
  try {
    await contentApi.removeFeedSub(s.id)
    if (subId.value === s.id) subId.value = ''
    await load()
  } catch (e) {
    error.value = e instanceof Error ? e.message : '删除失败'
  }
}

watch(subId, () => {
  void load()
})

onMounted(() => {
  void load()
})
</script>

<template>
  <AppShell title="信息流" :subtitle="subtitle" active="feed">
    <div class="page">
      <div class="page-head">
        <p class="hint">
          添加 B 站 UP 订阅后可自动拉取动态；批量同步走
          <code>sync_bilibili_feed</code>（需 <code>BILIBILI_COOKIES</code>）。
        </p>
        <p v-if="error" class="err">{{ error }}</p>
      </div>

      <div class="workspace">
        <section class="mid">
          <div class="side-title-row">
            <h2 class="side-title">我的订阅</h2>
            <span class="count muted">{{ subs.length }}</span>
            <span class="spacer"></span>
            <button type="button" class="ghost small" @click="manageOpen = true">+ 添加订阅</button>
          </div>

          <input v-model="subFilter" class="sub-filter" placeholder="过滤订阅名 / mid" />
          <label class="check-label">
            <input v-model="enabledOnly" type="checkbox" />
            <span>仅看启用</span>
          </label>

          <button type="button" class="sub all" :class="{ on: !subId }" @click="subId = ''">
            全部动态
          </button>

          <p v-if="subs.length && !displayedSubs.length" class="muted tiny-text">无匹配订阅</p>
          <p v-if="!subs.length && !loading" class="muted tiny-text sub-hint">
            点击「+ 添加订阅」搜索关键词或填写 mid 添加订阅。
          </p>

          <div class="sub-list">
            <div
              v-for="s in displayedSubs"
              :key="s.id"
              class="sub-row"
              :class="{ on: subId === s.id, off: !s.enabled }"
            >
              <button type="button" class="sub-name" :title="s.source_id" @click="subId = s.id">
                {{ s.display_name || s.source_id }}
              </button>
              <button
                type="button"
                class="icon-btn"
                :class="{ on: s.enabled }"
                :title="s.enabled ? '停用' : '启用'"
                @click="toggleSub(s)"
              >
                {{ s.enabled ? '开' : '关' }}
              </button>
              <button type="button" class="icon-btn danger" title="删除" @click="removeSub(s)">
                删
              </button>
            </div>
          </div>
        </section>

        <section class="feed">
          <div class="right-head">
            <div class="right-title-row">
              <h2 class="right-title">动态</h2>
              <span class="count muted">{{ displayedItems.length }}</span>
            </div>
            <button class="ghost" type="button" :disabled="loading" @click="load">刷新</button>
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
              <p v-if="!subs.length" class="empty muted">暂无订阅</p>
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
                @click="selectItem(item)"
              >
                <div class="item-head">
                  <div class="item-byline">
                    <span class="item-author">{{ item.author_name || '未知作者' }}</span>
                    <span class="item-time">{{ item.published_at }}</span>
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
                @change="goItemsPage"
              />
            </template>
          </div>
        </section>
      </div>
    </div>
  </AppShell>

  <Teleport to="body">
    <Transition name="fade">
      <div
        v-if="manageOpen"
        class="overlay"
        @click.self="manageOpen = false"
        @keydown.esc="manageOpen = false"
      >
        <div class="manager" role="dialog" aria-modal="true" aria-label="添加订阅">
          <h3 class="manager-title">添加订阅</h3>
          <p v-if="error" class="err">{{ error }}</p>

          <div class="row">
            <input v-model="newMid" placeholder="输入 UP 的 mid" @keyup.enter="addSub" />
            <button type="button" class="primary" :disabled="adding" @click="addSub">添加</button>
          </div>
          <label class="check-label">
            <input v-model="syncOnAdd" type="checkbox" />
            <span>添加后立即同步</span>
          </label>

          <div class="divider"></div>

          <div class="row">
            <input v-model="searchQ" placeholder="搜索 UP 主（关键词）" @keyup.enter="runSearch" />
            <button type="button" class="ghost" :disabled="searching" @click="runSearch">
              {{ searching ? '搜索中' : '搜索' }}
            </button>
          </div>

          <div v-if="searchHits.length" class="hits">
            <div v-for="h in searchHits" :key="h.mid" class="hit-row">
              <div class="hit-meta">
                <div class="hit-name">{{ h.name || h.mid }}</div>
                <div class="muted tiny-text">mid {{ h.mid }}</div>
              </div>
              <button type="button" class="tiny" :disabled="adding" @click="addFromHit(h)">
                添加
              </button>
            </div>
          </div>
          <p v-else-if="searchTried && !searching" class="muted tiny-text">无搜索结果</p>

          <div class="manager-actions">
            <button type="button" class="ghost" @click="manageOpen = false">关闭</button>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.page {
  display: flex;
  flex-direction: column;
  gap: 12px;
  height: 100%;
  padding: 16px 24px 24px;
}
.page-head {
  display: grid;
  gap: 6px;
}
.hint {
  margin: 0;
  font-size: 0.8125rem;
  color: var(--ink-muted);
}
.hint code {
  font-family: var(--mono);
  font-size: 0.78rem;
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: 4px;
  padding: 1px 4px;
  color: var(--brand-dark);
}
.err {
  margin: 0;
  color: var(--danger);
  font-size: 0.85rem;
}

.workspace {
  display: grid;
  grid-template-columns: 264px minmax(0, 1fr);
  grid-template-areas: 'mid feed';
  gap: 14px;
  flex: 1;
  min-height: 0;
}

/* ---------- 中栏 · 订阅列表 ---------- */
.mid,
.feed {
  min-height: 0;
  overflow: auto;
  border: 1px solid var(--line);
  border-radius: 0.9rem;
  background: var(--surface);
  box-shadow: var(--shadow-card);
}
.mid {
  grid-area: mid;
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 14px;
}
.mid .sub-list {
  flex: 1;
  min-height: 0;
}
.spacer {
  flex: 1;
}
.ghost.small {
  padding: 4px 10px;
  font-size: 0.78rem;
}
.side-title {
  margin: 0;
  font-size: 0.72rem;
  font-weight: 600;
  letter-spacing: 0.08em;
  color: var(--ink-faint);
}
.side-title-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
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
.sub-hint {
  margin: 0;
}
.sub.all {
  width: 100%;
  text-align: left;
  font-weight: 500;
  color: var(--ink);
}
.sub-list {
  display: grid;
  gap: 2px;
  margin-top: 2px;
  overflow: auto;
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

/* ---------- 右栏 · 动态列表 ---------- */
.feed {
  grid-area: feed;
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

/* ---------- 添加订阅弹窗 ---------- */
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

@media (max-width: 900px) {
  .workspace {
    grid-template-columns: 1fr;
    grid-template-areas:
      'mid'
      'feed';
  }
  .mid,
  .feed {
    overflow: visible;
  }
  .mid .sub-list {
    max-height: 320px;
  }
}
</style>
