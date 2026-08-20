<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import AppShell from '../../../components/AppShell.vue'
import { confirmDialog } from '../../../lib/dialog'
import { contentApi, type BilibiliUserHit, type FeedItem, type FeedSub } from '../../../api/content'
import FeedSubsChipBar from '../components/FeedSubsChipBar.vue'
import FeedItemsPanel from '../components/FeedItemsPanel.vue'
import FeedManageModal from '../components/FeedManageModal.vue'

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
const manageOpen = ref(false)

const subtitle = computed(() => `${subs.value.length} 订阅 · ${itemsTotal.value} 条`)

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

function selectSubInManage(s: FeedSub) {
  subId.value = s.id
  manageOpen.value = false
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
        <FeedSubsChipBar
          v-model:sub-id="subId"
          :subs="subs"
          :loading="loading"
          @manage="manageOpen = true"
        />
        <FeedItemsPanel
          :items="items"
          :items-page="itemsPage"
          :items-pages="itemsPages"
          :items-total="itemsTotal"
          :has-subs="!!subs.length"
          :loading="loading"
          @refresh="load"
          @select="selectItem"
          @page-change="goItemsPage"
        />
      </div>
    </div>
  </AppShell>

  <FeedManageModal
    v-model:open="manageOpen"
    v-model:new-mid="newMid"
    v-model:sync-on-add="syncOnAdd"
    v-model:search-q="searchQ"
    :subs="subs"
    :sub-id="subId"
    :error="error"
    :adding="adding"
    :searching="searching"
    :search-hits="searchHits"
    :search-tried="searchTried"
    @select="selectSubInManage"
    @toggle="toggleSub"
    @remove="removeSub"
    @add="addSub"
    @add-hit="addFromHit"
    @search="runSearch"
  />
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
  grid-template-columns: 220px minmax(0, 1fr);
  grid-template-areas: 'mid feed';
  gap: 14px;
  flex: 1;
  min-height: 0;
}

@media (max-width: 900px) {
  .workspace {
    grid-template-columns: 1fr;
    grid-template-areas:
      'mid'
      'feed';
  }
}
</style>
