<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import BrandLogo from './BrandLogo.vue'
import NavIcon from './NavIcon.vue'

export type NavActive =
  | 'screener-condition'
  | 'screener-recipe'
  | 'screener-pattern'
  | 'screener-peer'
  | 'watchlist-list'
  | 'watchlist-signals'
  | 'market'
  | 'strategies'
  | 'sectors'
  | 'radar'
  | 'playbook'
  | 'notes'
  | 'feed'
  | 'backtest'
  | 'ai'
  | 'ops'
  | 'scheduler'
  | 'notify'
  | 'channels'
  | 'auto-schedule'

const props = defineProps<{
  title: string
  subtitle?: string
  active: NavActive
}>()

const auth = useAuthStore()
const router = useRouter()

type IconName =
  | 'playbook'
  | 'watchlist'
  | 'board'
  | 'market'
  | 'strategies'
  | 'sectors'
  | 'radar'
  | 'screener'
  | 'backtest'
  | 'feed'
  | 'notes'
  | 'ai'
  | 'ops'
  | 'scheduler'
  | 'notify'
  | 'channels'
  | 'auto-schedule'

type NavLeaf = {
  kind: 'leaf'
  key: NavActive
  label: string
  to: string
  icon: IconName
  enabled: boolean
}

type NavBranch = {
  kind: 'branch'
  id: string
  label: string
  icon: IconName
  defaultTo: string
  children: NavLeaf[]
}

type NavEntry = NavLeaf | NavBranch

const primaryNavGroups: { title: string; entries: NavEntry[] }[] = [
  {
    title: '工作台',
    entries: [
      { kind: 'leaf', key: 'playbook', label: '守则', to: '/playbook', icon: 'playbook', enabled: true },
      {
        kind: 'branch',
        id: 'watchlist',
        label: '自选',
        icon: 'watchlist',
        defaultTo: '/watchlist',
        children: [
          {
            kind: 'leaf',
            key: 'watchlist-list',
            label: '列表',
            to: '/watchlist',
            icon: 'watchlist',
            enabled: true,
          },
          {
            kind: 'leaf',
            key: 'watchlist-signals',
            label: '策略信号',
            to: '/watchlist/signals',
            icon: 'board',
            enabled: true,
          },
        ],
      },
      {
        kind: 'leaf',
        key: 'strategies',
        label: '策略',
        to: '/strategies',
        icon: 'strategies',
        enabled: true,
      },
    ],
  },
  {
    title: '行情',
    entries: [
      { kind: 'leaf', key: 'market', label: '市场', to: '/market', icon: 'market', enabled: true },
      { kind: 'leaf', key: 'sectors', label: '板块资金', to: '/sectors', icon: 'sectors', enabled: true },
      { kind: 'leaf', key: 'radar', label: '雷达', to: '/radar', icon: 'radar', enabled: true },
    ],
  },
  {
    title: '研究',
    entries: [
      {
        kind: 'branch',
        id: 'screener',
        label: '选股',
        icon: 'screener',
        defaultTo: '/screener/condition',
        children: [
          {
            kind: 'leaf',
            key: 'screener-condition',
            label: '条件选股',
            to: '/screener/condition',
            icon: 'screener',
            enabled: true,
          },
          {
            kind: 'leaf',
            key: 'screener-recipe',
            label: '多因子配方',
            to: '/screener/recipe',
            icon: 'screener',
            enabled: true,
          },
          {
            kind: 'leaf',
            key: 'screener-pattern',
            label: '形态',
            to: '/screener/pattern',
            icon: 'screener',
            enabled: true,
          },
          {
            kind: 'leaf',
            key: 'screener-peer',
            label: '对标',
            to: '/screener/peer',
            icon: 'screener',
            enabled: true,
          },
        ],
      },
      { kind: 'leaf', key: 'backtest', label: '回测', to: '/backtest', icon: 'backtest', enabled: true },
      { kind: 'leaf', key: 'ai', label: 'AI', to: '/ai', icon: 'ai', enabled: true },
    ],
  },
  {
    title: '记录',
    entries: [
      { kind: 'leaf', key: 'feed', label: '信息流', to: '/feed', icon: 'feed', enabled: true },
      { kind: 'leaf', key: 'notes', label: '笔记', to: '/notes', icon: 'notes', enabled: true },
    ],
  },
]

const systemBranch: NavBranch = {
  kind: 'branch',
  id: 'system',
  label: '系统',
  icon: 'ops',
  defaultTo: '/ops',
  children: [
    { kind: 'leaf', key: 'ops', label: '运维', to: '/ops', icon: 'ops', enabled: true },
    { kind: 'leaf', key: 'scheduler', label: '调度', to: '/scheduler', icon: 'scheduler', enabled: true },
    {
      kind: 'leaf',
      key: 'auto-schedule',
      label: '自动任务',
      to: '/auto-schedule',
      icon: 'auto-schedule',
      enabled: true,
    },
    { kind: 'leaf', key: 'notify', label: '通知', to: '/notify', icon: 'notify', enabled: true },
    { kind: 'leaf', key: 'channels', label: '消息渠道', to: '/channels', icon: 'channels', enabled: true },
  ],
}

const expanded = ref<Record<string, boolean>>({})

function isLeafActive(leaf: NavLeaf): boolean {
  return leaf.key === props.active
}

function branchChildActive(branch: NavBranch): boolean {
  return branch.children.some((c) => c.key === props.active)
}

function isBranchOpen(branch: NavBranch): boolean {
  if (expanded.value[branch.id] != null) return expanded.value[branch.id]
  return branchChildActive(branch)
}

function isBranchActive(branch: NavBranch): boolean {
  return branch.children.some((c) => isLeafActive(c))
}

watch(
  () => props.active,
  () => {
    for (const g of primaryNavGroups) {
      for (const e of g.entries) {
        if (e.kind === 'branch' && branchChildActive(e)) {
          expanded.value = { ...expanded.value, [e.id]: true }
        }
      }
    }
    if (branchChildActive(systemBranch)) {
      expanded.value = { ...expanded.value, [systemBranch.id]: true }
    }
  },
  { immediate: true },
)

function onBranchClick(branch: NavBranch) {
  const open = isBranchOpen(branch)
  if (!open) {
    expanded.value = { ...expanded.value, [branch.id]: true }
  }
  if (!isBranchActive(branch)) {
    void router.push(branch.defaultTo)
  } else {
    expanded.value = { ...expanded.value, [branch.id]: !open }
  }
}

const displayName = computed(() => auth.user?.display_name || auth.user?.username || '')
const initial = computed(() => {
  const name = displayName.value
  return name ? name.slice(0, 1).toUpperCase() : '?'
})

function logout() {
  auth.logout()
  void router.push('/login')
}

function onLeafClick(e: MouseEvent, item: NavLeaf) {
  if (!item.enabled) e.preventDefault()
}
</script>

<template>
  <div class="shell">
    <aside class="side">
      <div class="side-brand">
        <RouterLink class="logo" to="/playbook" aria-label="zak2 首页">
          <BrandLogo size="md" />
        </RouterLink>
      </div>

      <nav class="side-nav" aria-label="主导航">
        <div class="nav-primary">
          <div
            v-for="(group, gi) in primaryNavGroups"
            :key="group.title"
            class="nav-group"
            :class="{ spaced: gi > 0 }"
          >
            <p class="nav-group-title">{{ group.title }}</p>
            <ul class="nav-list">
              <template v-for="entry in group.entries" :key="entry.kind === 'leaf' ? entry.key : entry.id">
                <li v-if="entry.kind === 'leaf'">
                  <RouterLink
                    class="nav-item"
                    :class="{ 'nav-item-active': isLeafActive(entry), muted: !entry.enabled }"
                    :to="entry.enabled ? entry.to : '#'"
                    @click="onLeafClick($event, entry)"
                  >
                    <span class="nav-main">
                      <NavIcon :name="entry.icon" />
                      <span class="nav-label">{{ entry.label }}</span>
                    </span>
                  </RouterLink>
                </li>
                <li v-else class="nav-branch">
                  <button
                    type="button"
                    class="nav-item nav-parent"
                    :class="{ 'nav-item-active': isBranchActive(entry), open: isBranchOpen(entry) }"
                    @click="onBranchClick(entry)"
                  >
                    <span class="nav-main">
                      <NavIcon :name="entry.icon" />
                      <span class="nav-label">{{ entry.label }}</span>
                    </span>
                    <span class="nav-chevron" aria-hidden="true">{{ isBranchOpen(entry) ? '▾' : '▸' }}</span>
                  </button>
                  <ul v-show="isBranchOpen(entry)" class="nav-sub">
                    <li v-for="child in entry.children" :key="child.key">
                      <RouterLink
                        class="nav-item nav-sub-item"
                        :class="{ 'nav-item-active': isLeafActive(child), muted: !child.enabled }"
                        :to="child.enabled ? child.to : '#'"
                        @click="onLeafClick($event, child)"
                      >
                        <span class="nav-label">{{ child.label }}</span>
                      </RouterLink>
                    </li>
                  </ul>
                </li>
              </template>
            </ul>
          </div>
        </div>

        <div class="nav-group nav-system">
          <ul class="nav-list">
            <li class="nav-branch">
              <button
                type="button"
                class="nav-item nav-parent"
                :class="{
                  'nav-item-active': isBranchActive(systemBranch),
                  open: isBranchOpen(systemBranch),
                }"
                @click="onBranchClick(systemBranch)"
              >
                <span class="nav-main">
                  <NavIcon :name="systemBranch.icon" />
                  <span class="nav-label">{{ systemBranch.label }}</span>
                </span>
                <span class="nav-chevron" aria-hidden="true">
                  {{ isBranchOpen(systemBranch) ? '▾' : '▸' }}
                </span>
              </button>
              <ul v-show="isBranchOpen(systemBranch)" class="nav-sub">
                <li v-for="child in systemBranch.children" :key="child.key">
                  <RouterLink
                    class="nav-item nav-sub-item"
                    :class="{ 'nav-item-active': isLeafActive(child), muted: !child.enabled }"
                    :to="child.enabled ? child.to : '#'"
                    @click="onLeafClick($event, child)"
                  >
                    <span class="nav-label">{{ child.label }}</span>
                  </RouterLink>
                </li>
              </ul>
            </li>
          </ul>
        </div>
      </nav>
    </aside>

    <div class="main">
      <header class="top">
        <div class="top-title">
          <h1>{{ title }}</h1>
          <p v-if="subtitle" class="meta">{{ subtitle }}</p>
        </div>
        <div class="user">
          <span class="avatar" aria-hidden="true">{{ initial }}</span>
          <span class="user-name">{{ displayName }}</span>
          <button class="btn-ghost" type="button" @click="logout">退出</button>
        </div>
      </header>
      <div class="body">
        <slot />
      </div>
    </div>
  </div>
</template>

<style scoped>
.shell {
  display: grid;
  grid-template-columns: 240px 1fr;
  height: 100%;
  background: var(--surface-muted);
}
.side {
  display: flex;
  flex-direction: column;
  min-height: 0;
  border-right: 1px solid var(--line);
  background: var(--surface);
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.03);
}
.side-brand {
  display: flex;
  align-items: center;
  height: 56px;
  flex-shrink: 0;
  padding: 0 16px;
  border-bottom: 1px solid var(--line);
}
.logo {
  display: flex;
  align-items: center;
  border-radius: 0.5rem;
  padding: 4px 2px;
  transition: opacity 0.15s ease;
}
.logo:hover {
  opacity: 0.85;
}
.side-nav {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  padding: 12px 12px 10px;
  overflow: hidden;
}
.nav-primary {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding-bottom: 8px;
  scrollbar-width: thin;
  scrollbar-color: var(--line) transparent;
}
.nav-primary::-webkit-scrollbar {
  width: 6px;
}
.nav-primary::-webkit-scrollbar-thumb {
  background: var(--line);
  border-radius: 999px;
}
.nav-group.spaced {
  margin-top: 1rem;
  padding-top: 1rem;
  border-top: 1px solid var(--line);
}
.nav-system {
  flex-shrink: 0;
  margin-top: 4px;
  padding-top: 12px;
  border-top: 1px solid var(--line);
}
.nav-group-title {
  margin: 0 0 0.4rem;
  padding: 0 0.75rem;
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.08em;
  color: var(--ink-faint);
}
.nav-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: grid;
  gap: 2px;
}
.nav-main {
  display: inline-flex;
  align-items: center;
  gap: 0.625rem;
  min-width: 0;
}
.nav-label {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.nav-item.muted {
  color: var(--ink-faint);
  pointer-events: none;
}
.nav-parent {
  width: 100%;
  border: none;
  background: transparent;
  cursor: pointer;
  font: inherit;
  text-align: left;
}
.nav-chevron {
  flex-shrink: 0;
  font-size: 0.65rem;
  color: var(--ink-faint);
  margin-left: 0.25rem;
}
.nav-sub {
  list-style: none;
  margin: 2px 0 4px;
  padding: 0 0 0 0.5rem;
  display: grid;
  gap: 1px;
  border-left: 1px solid var(--line);
  margin-left: 1.15rem;
}
.nav-sub-item {
  padding-left: 0.75rem !important;
  font-size: 0.8125rem;
  min-height: 2rem;
}
.main {
  display: flex;
  flex-direction: column;
  min-width: 0;
  min-height: 0;
}
.top {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
  min-height: 56px;
  height: auto;
  padding: 10px 24px;
  border-bottom: 1px solid var(--line);
  background: var(--surface);
  box-shadow: 0 1px 0 rgba(0, 0, 0, 0.02);
}
.top-title {
  min-width: 0;
}
.top h1 {
  margin: 0;
  font-size: 1.125rem;
  font-weight: 600;
  color: var(--ink);
  letter-spacing: -0.01em;
}
.meta {
  margin: 3px 0 0;
  color: var(--ink-muted);
  font-size: 0.8125rem;
  line-height: 1.35;
}
.user {
  display: flex;
  gap: 10px;
  align-items: center;
  flex-shrink: 0;
  color: var(--ink-muted);
  font-size: 0.875rem;
}
.avatar {
  display: inline-grid;
  place-items: center;
  width: 28px;
  height: 28px;
  border-radius: 999px;
  background: var(--brand-light);
  color: var(--brand);
  font-size: 0.75rem;
  font-weight: 600;
  flex-shrink: 0;
}
.user-name {
  max-width: 10rem;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.body {
  flex: 1;
  min-height: 0;
  overflow: auto;
}
@media (max-width: 900px) {
  .shell {
    grid-template-columns: 1fr;
  }
  .side {
    display: none;
  }
  .user-name {
    display: none;
  }
}
</style>
