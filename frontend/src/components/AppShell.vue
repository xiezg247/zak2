<script setup lang="ts">
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import BrandLogo from './BrandLogo.vue'
import NavIcon from './NavIcon.vue'

defineProps<{
  title: string
  subtitle?: string
  active:
    | 'screener'
    | 'watchlist'
    | 'board'
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
}>()

const auth = useAuthStore()
const router = useRouter()

type NavKey =
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

type NavItem = {
  key: NavKey
  label: string
  to: string
  enabled: boolean
}

const navGroups: { title: string; items: NavItem[] }[] = [
  {
    title: '交易',
    items: [
      { key: 'playbook', label: '守则', to: '/playbook', enabled: true },
      { key: 'watchlist', label: '自选', to: '/watchlist', enabled: true },
      { key: 'board', label: '看板', to: '/board', enabled: true },
      { key: 'strategies', label: '策略', to: '/strategies', enabled: true },
      { key: 'market', label: '市场', to: '/market', enabled: true },
      { key: 'sectors', label: '板块资金', to: '/sectors', enabled: true },
      { key: 'radar', label: '雷达', to: '/radar', enabled: true },
      { key: 'screener', label: '选股', to: '/screener', enabled: true },
      { key: 'backtest', label: '回测', to: '/backtest', enabled: true },
    ],
  },
  {
    title: '内容',
    items: [
      { key: 'feed', label: '信息流', to: '/feed', enabled: true },
      { key: 'notes', label: '笔记', to: '/notes', enabled: true },
      { key: 'ai', label: 'AI', to: '/ai', enabled: true },
    ],
  },
  {
    title: '系统',
    items: [
      { key: 'ops', label: '运维', to: '/ops', enabled: true },
      { key: 'scheduler', label: '调度', to: '/scheduler', enabled: true },
      { key: 'notify', label: '通知', to: '/notify', enabled: true },
      { key: 'channels', label: '消息渠道', to: '/channels', enabled: true },
      { key: 'auto-schedule', label: '自动任务', to: '/auto-schedule', enabled: true },
    ],
  },
]

const displayName = computed(() => auth.user?.display_name || auth.user?.username || '')
const initial = computed(() => {
  const name = displayName.value
  return name ? name.slice(0, 1).toUpperCase() : '?'
})

function logout() {
  auth.logout()
  void router.push('/login')
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
        <div
          v-for="(group, gi) in navGroups"
          :key="group.title"
          class="nav-group"
          :class="{ spaced: gi > 0 }"
        >
          <p class="nav-group-title">{{ group.title }}</p>
          <ul class="nav-list">
            <li v-for="item in group.items" :key="item.key">
              <RouterLink
                class="nav-item"
                :class="{ 'nav-item-active': active === item.key, muted: !item.enabled }"
                :to="item.enabled ? item.to : '#'"
                @click="
                  (e) => {
                    if (!item.enabled) e.preventDefault()
                  }
                "
              >
                <span class="nav-main">
                  <NavIcon :name="item.key" />
                  <span class="nav-label">{{ item.label }}</span>
                </span>
                <span v-if="!item.enabled" class="soon">稍后</span>
              </RouterLink>
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
  overflow-y: auto;
  padding: 16px 12px 12px;
  scrollbar-width: thin;
  scrollbar-color: var(--line) transparent;
}
.side-nav::-webkit-scrollbar {
  width: 6px;
}
.side-nav::-webkit-scrollbar-thumb {
  background: var(--line);
  border-radius: 999px;
}
.nav-group.spaced {
  margin-top: 1.25rem;
}
.nav-group-title {
  margin: 0 0 0.5rem;
  padding: 0 0.75rem;
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.06em;
  text-transform: none;
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
.soon {
  font-size: 0.7rem;
  opacity: 0.7;
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
