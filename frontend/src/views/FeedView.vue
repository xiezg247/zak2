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

const subtitle = computed(() => `${subs.value.length} 订阅 · ${itemsTotal.value} 条`)

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

async function openItem(item: FeedItem) {
  if (!item.is_read) {
    try {
      await contentApi.markRead(item.id)
      item.is_read = true
    } catch {
      /* ignore */
    }
  }
  window.open(item.url, '_blank', 'noopener,noreferrer')
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
      <p class="hint muted">
        左侧可 mid 直填，或关键词搜索后点选添加 UP 订阅；可选「并同步」立即拉取动态。批量同步仍可由 Ops「B站订阅同步」或内嵌定时（`sync_bilibili_feed`，需
        <code>BILIBILI_COOKIES</code>）。
      </p>
      <p v-if="error" class="err">{{ error }}</p>

      <div class="workspace">
        <aside class="left">
          <div class="row">
            <input v-model="newMid" placeholder="UP mid" @keyup.enter="addSub" />
            <button type="button" class="primary" :disabled="adding" @click="addSub">添加</button>
          </div>
          <label class="sync-label">
            <input v-model="syncOnAdd" type="checkbox" />
            并同步
          </label>
          <div class="row">
            <input v-model="searchQ" placeholder="关键词搜 UP" @keyup.enter="runSearch" />
            <button type="button" class="ghost" :disabled="searching" @click="runSearch">搜索</button>
          </div>
          <div v-if="searchHits.length" class="hits">
            <div v-for="h in searchHits" :key="h.mid" class="hit-row">
              <img v-if="h.avatar" class="avatar" :src="h.avatar" alt="" />
              <span v-else class="avatar avatar-ph" aria-hidden="true"></span>
              <div class="hit-meta">
                <div class="hit-name">{{ h.name || h.mid }}</div>
                <div class="muted tiny-text">mid {{ h.mid }}</div>
              </div>
              <button type="button" class="tiny" :disabled="adding" @click="addFromHit(h)">添加</button>
            </div>
          </div>
          <p v-else-if="searchTried && !searching" class="muted tiny-text">无搜索结果</p>
          <p v-if="!subs.length && !loading" class="muted tiny-text sub-hint">
            先搜索关键词或填写 mid 添加订阅。
          </p>
          <input
            v-if="subs.length"
            v-model="subFilter"
            class="sub-filter"
            placeholder="过滤订阅名/mid"
          />
          <label v-if="subs.length" class="enabled-label">
            <input v-model="enabledOnly" type="checkbox" />
            仅启用
          </label>
          <button type="button" class="sub" :class="{ on: !subId }" @click="subId = ''">全部</button>
          <p v-if="subs.length && !displayedSubs.length" class="muted tiny-text">无匹配订阅</p>
          <div v-for="s in displayedSubs" :key="s.id" class="sub-row">
            <button type="button" class="sub" :class="{ on: subId === s.id }" @click="subId = s.id">
              {{ s.display_name || s.source_id }}
            </button>
            <button type="button" class="tiny" @click="toggleSub(s)">{{ s.enabled ? '开' : '关' }}</button>
            <button type="button" class="tiny danger" @click="removeSub(s)">删</button>
          </div>
        </aside>
        <section class="right">
          <div class="right-tools">
            <button class="ghost" type="button" :disabled="loading" @click="load">刷新</button>
            <div v-if="items.length" class="filter-row">
              <input v-model="listFilter" placeholder="过滤标题/作者" />
              <label class="unread-label">
                <input v-model="unreadOnly" type="checkbox" />
                仅未读
              </label>
            </div>
          </div>

          <p v-if="loading" class="muted">加载中…</p>
          <template v-else>
            <p v-if="!subs.length" class="empty muted">暂无订阅</p>
            <p v-else-if="!items.length" class="empty muted">
              暂无动态。可到 Ops 执行 sync_bilibili_feed。
              <RouterLink to="/ops" class="draft-link">去 Ops</RouterLink>
            </p>
            <p v-else-if="!displayedItems.length" class="empty muted">无匹配动态</p>
            <article
              v-for="item in displayedItems"
              :key="item.id"
              class="item"
              :class="{ unread: !item.is_read }"
              @click="openItem(item)"
            >
              <div class="meta muted">
                {{ item.author_name }} · {{ item.published_at }}
                <span v-if="!item.is_read">· 未读</span>
              </div>
              <h3>{{ item.title || '(无标题)' }}</h3>
              <p class="summary">{{ item.summary }}</p>
            </article>
            <PagerBar
              :page="itemsPage"
              :pages="itemsPages"
              :total="itemsTotal"
              @change="goItemsPage"
            />
          </template>
        </section>
      </div>
    </div>
  </AppShell>
</template>

<style scoped>
.page {
  display: grid;
  gap: 12px;
  height: 100%;
  padding: 16px 24px 24px;
}
.hint {
  margin: 0;
  font-size: 0.85rem;
}
.err {
  margin: 0;
  color: var(--danger);
}
.workspace {
  display: grid;
  grid-template-columns: 240px 1fr;
  gap: 12px;
  min-height: 0;
  flex: 1;
}
.left,
.right {
  border: 1px solid var(--border);
  border-radius: 0.75rem;
  background: var(--bg-elevated);
  padding: 12px;
  overflow: auto;
  display: grid;
  gap: 8px;
  align-content: start;
}
.row {
  display: grid;
  grid-template-columns: 1fr auto;
  gap: 6px;
}
.row input {
  background: var(--bg);
  border: 1px solid var(--border);
  color: var(--text);
  border-radius: 0.5rem;
  padding: 8px 10px;
}
.sync-label {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 0.85rem;
  color: var(--muted);
}
.primary {
  background: var(--accent);
  border: none;
  color: var(--brand-foreground);
  border-radius: 0.5rem;
  padding: 8px 12px;
}
.primary:disabled {
  opacity: 0.6;
}
.sub-row {
  display: grid;
  grid-template-columns: 1fr auto auto;
  gap: 6px;
}
.tiny.danger {
  color: var(--danger);
}
.sub {
  text-align: left;
  background: var(--bg);
  border: 1px solid var(--border);
  color: var(--text);
  border-radius: 0.5rem;
  padding: 8px 10px;
}
.sub.on {
  border-color: var(--accent);
}
.tiny {
  background: transparent;
  border: 1px solid var(--border);
  color: var(--muted);
  border-radius: 0.5rem;
  padding: 0 8px;
}
.ghost {
  justify-self: start;
  background: transparent;
  border: 1px solid var(--border);
  color: var(--text);
  border-radius: 0.5rem;
  padding: 6px 10px;
}
.right-tools {
  display: grid;
  gap: 8px;
}
.filter-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
}
.filter-row input {
  background: var(--bg);
  border: 1px solid var(--border);
  color: var(--text);
  border-radius: 0.5rem;
  padding: 6px 10px;
  min-width: 140px;
  flex: 1;
}
.unread-label {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 0.85rem;
  color: var(--muted);
  white-space: nowrap;
}
.enabled-label {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 0.85rem;
  color: var(--muted);
  white-space: nowrap;
}
.draft-link {
  color: var(--brand);
  margin-left: 4px;
}
.sub-hint {
  margin: 0;
}
.sub-filter {
  background: var(--bg);
  border: 1px solid var(--border);
  border-radius: 0.5rem;
  color: var(--text);
  padding: 8px 10px;
  width: 100%;
  box-sizing: border-box;
}
.item {
  border: 1px solid var(--border);
  border-radius: 0.75rem;
  padding: 10px 12px;
  cursor: pointer;
  background: var(--bg);
}
.item.unread {
  border-color: var(--brand-soft);
}
.item h3 {
  margin: 4px 0;
  font-size: 1rem;
}
.summary {
  margin: 0;
  color: var(--muted);
  font-size: 0.85rem;
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.meta {
  font-size: 0.8rem;
}
.muted {
  color: var(--muted);
}
.empty {
  text-align: center;
  padding: 24px;
}
.hits {
  display: grid;
  gap: 6px;
}
.hit-row {
  display: grid;
  grid-template-columns: auto 1fr auto;
  gap: 8px;
  align-items: center;
}
.avatar {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  object-fit: cover;
}
.avatar-ph {
  display: inline-block;
  background: var(--border);
  flex-shrink: 0;
}
.hit-name {
  font-size: 0.9rem;
}
.tiny-text {
  font-size: 0.75rem;
}
@media (max-width: 900px) {
  .workspace {
    grid-template-columns: 1fr;
  }
}
</style>
