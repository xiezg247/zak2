import { createRouter, createWebHistory } from 'vue-router'
import { getToken } from '../api/client'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', redirect: '/playbook' },
    {
      path: '/login',
      name: 'login',
      component: () => import('../views/LoginView.vue'),
      meta: { public: true },
    },
    { path: '/playbook', name: 'playbook', component: () => import('../views/PlaybookView.vue') },
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
      component: () => import('../views/StrategyView.vue'),
    },
    { path: '/market', name: 'market', component: () => import('../features/market/pages/MarketPage.vue') },
    { path: '/sectors', name: 'sectors', component: () => import('../views/SectorView.vue') },
    { path: '/radar', name: 'radar', component: () => import('../features/radar/pages/RadarPage.vue') },
    { path: '/screener', redirect: '/screener/condition' },
    {
      path: '/screener/:mode(condition|recipe|pattern|peer)',
      name: 'screener',
      component: () => import('../features/screener/pages/ScreenerHubPage.vue'),
    },
    { path: '/backtest', name: 'backtest', component: () => import('../views/BacktestView.vue') },
    { path: '/feed', name: 'feed', component: () => import('../views/FeedView.vue') },
    { path: '/notes', name: 'notes', component: () => import('../views/NotesView.vue') },
    { path: '/ai', name: 'ai', component: () => import('../features/ai/pages/AiPage.vue') },
    { path: '/ops', name: 'ops', component: () => import('../views/OpsView.vue') },
    {
      path: '/scheduler',
      name: 'scheduler',
      component: () => import('../views/SchedulerView.vue'),
    },
    { path: '/notify', name: 'notify', component: () => import('../views/NotifyView.vue') },
    { path: '/channels', name: 'channels', component: () => import('../views/ChannelsView.vue') },
    {
      path: '/auto-schedule',
      name: 'auto-schedule',
      component: () => import('../views/AutoScheduleView.vue'),
    },
  ],
})

router.beforeEach((to) => {
  if (to.meta.public) return true
  if (!getToken()) return { name: 'login', query: { redirect: to.fullPath } }
  return true
})

export default router
