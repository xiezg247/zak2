import { createRouter, createWebHistory } from 'vue-router'
import { getToken } from '../api/client'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', redirect: '/playbook' },
    {
      path: '/login',
      name: 'login',
      component: () => import('../features/auth/pages/LoginPage.vue'),
      meta: { public: true },
    },
    { path: '/playbook', name: 'playbook', component: () => import('../features/playbook/pages/PlaybookPage.vue') },
    {
      path: '/watchlist',
      name: 'watchlist',
      component: () => import('../features/watchlist/pages/WatchlistListPage.vue'),
    },
    {
      path: '/watchlist/signals',
      name: 'watchlist-signals',
      component: () => import('../features/watchlist/pages/WatchlistSignalsPage.vue'),
    },
    {
      path: '/strategies',
      name: 'strategies',
      component: () => import('../features/strategy/pages/StrategyPage.vue'),
    },
    { path: '/market', name: 'market', component: () => import('../features/market/pages/MarketPage.vue') },
    { path: '/sectors', name: 'sectors', component: () => import('../features/sector/pages/SectorPage.vue') },
    { path: '/radar', name: 'radar', component: () => import('../features/radar/pages/RadarPage.vue') },
    { path: '/screener', redirect: '/screener/condition' },
    {
      path: '/screener/:mode(condition|recipe|pattern|peer)',
      name: 'screener',
      component: () => import('../features/screener/pages/ScreenerHubPage.vue'),
    },
    { path: '/backtest', name: 'backtest', component: () => import('../features/backtest/pages/BacktestPage.vue') },
    { path: '/feed', name: 'feed', component: () => import('../features/feed/pages/FeedPage.vue') },
    { path: '/notes', name: 'notes', component: () => import('../features/notes/pages/NotesPage.vue') },
    { path: '/ai', name: 'ai', component: () => import('../features/ai/pages/AiPage.vue') },
    { path: '/ops', name: 'ops', component: () => import('../features/system/pages/OpsPage.vue') },
    {
      path: '/scheduler',
      name: 'scheduler',
      component: () => import('../features/system/pages/SchedulerPage.vue'),
    },
    { path: '/notify', name: 'notify', component: () => import('../features/system/pages/NotifyPage.vue') },
    { path: '/channels', name: 'channels', component: () => import('../features/system/pages/ChannelsPage.vue') },
    {
      path: '/auto-schedule',
      name: 'auto-schedule',
      component: () => import('../features/system/pages/AutoSchedulePage.vue'),
    },
  ],
})

router.beforeEach((to) => {
  if (to.meta.public) return true
  if (!getToken()) return { name: 'login', query: { redirect: to.fullPath } }
  return true
})

export default router
