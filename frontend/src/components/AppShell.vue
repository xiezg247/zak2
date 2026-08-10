<script setup lang="ts">
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'

defineProps<{
  title: string
  subtitle?: string
  active:
    | 'screener'
    | 'watchlist'
    | 'market'
    | 'sectors'
    | 'radar'
    | 'playbook'
    | 'notes'
    | 'feed'
    | 'backtest'
    | 'ai'
    | 'ops'
}>()

const auth = useAuthStore()
const router = useRouter()

const navItems = [
  { key: 'playbook', label: '守则', to: '/playbook', enabled: true },
  { key: 'watchlist', label: '自选', to: '/watchlist', enabled: true },
  { key: 'market', label: '市场', to: '/market', enabled: true },
  { key: 'sectors', label: '板块资金', to: '/sectors', enabled: true },
  { key: 'radar', label: '雷达', to: '/radar', enabled: true },
  { key: 'screener', label: '选股', to: '/screener', enabled: true },
  { key: 'backtest', label: '回测', to: '/backtest', enabled: true },
  { key: 'feed', label: '信息流', to: '/feed', enabled: true },
  { key: 'notes', label: '笔记', to: '/notes', enabled: true },
  { key: 'ai', label: 'AI', to: '/ai', enabled: true },
  { key: 'ops', label: '运维', to: '/ops', enabled: true },
] as const

function logout() {
  auth.logout()
  void router.push('/login')
}
</script>

<template>
  <div class="shell">
    <aside class="side">
      <div class="logo">zak2</div>
      <nav>
        <RouterLink
          v-for="item in navItems"
          :key="item.key"
          class="nav"
          :class="{ active: active === item.key, muted: !item.enabled }"
          :to="item.enabled && 'to' in item ? item.to : '#'"
          @click="(e) => { if (!item.enabled) e.preventDefault() }"
        >
          {{ item.label }}
          <span v-if="!item.enabled" class="soon">稍后</span>
        </RouterLink>
      </nav>
    </aside>
    <div class="main">
      <header class="top">
        <div>
          <h1>{{ title }}</h1>
          <p v-if="subtitle" class="meta">{{ subtitle }}</p>
        </div>
        <div class="user">
          <span>{{ auth.user?.display_name || auth.user?.username }}</span>
          <button class="ghost" type="button" @click="logout">退出</button>
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
  grid-template-columns: 200px 1fr;
  height: 100%;
  background: var(--bg);
}
.side {
  border-right: 1px solid var(--border);
  background: #0c1118;
  padding: 16px 12px;
  display: flex;
  flex-direction: column;
  gap: 18px;
}
.logo {
  font-weight: 700;
  letter-spacing: 0.06em;
  padding: 4px 8px;
}
.nav {
  width: 100%;
  text-align: left;
  background: transparent;
  border: none;
  color: var(--text);
  padding: 10px 10px;
  border-radius: 8px;
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.nav.active {
  background: var(--bg-panel);
}
.nav.muted {
  color: var(--muted);
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
  padding: 16px 20px;
  border-bottom: 1px solid var(--border);
}
.top h1 {
  margin: 0;
  font-size: 1.25rem;
}
.meta {
  margin: 4px 0 0;
  color: var(--muted);
  font-size: 0.85rem;
}
.user {
  display: flex;
  gap: 12px;
  align-items: center;
  color: var(--muted);
}
.ghost {
  background: transparent;
  border: 1px solid var(--border);
  color: var(--text);
  border-radius: 8px;
  padding: 6px 10px;
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
}
</style>
