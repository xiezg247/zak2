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
      component: () => import('../views/WatchlistView.vue'),
    },
    { path: '/market', name: 'market', component: () => import('../views/MarketView.vue') },
    { path: '/sectors', name: 'sectors', component: () => import('../views/SectorView.vue') },
    { path: '/radar', name: 'radar', component: () => import('../views/RadarView.vue') },
    {
      path: '/screener',
      name: 'screener',
      component: () => import('../views/ScreenerHubView.vue'),
    },
    { path: '/backtest', name: 'backtest', component: () => import('../views/BacktestView.vue') },
    { path: '/feed', name: 'feed', component: () => import('../views/FeedView.vue') },
    { path: '/notes', name: 'notes', component: () => import('../views/NotesView.vue') },
    { path: '/ai', name: 'ai', component: () => import('../views/AiView.vue') },
    { path: '/ops', name: 'ops', component: () => import('../views/OpsView.vue') },
  ],
})

router.beforeEach((to) => {
  if (to.meta.public) return true
  if (!getToken()) return { name: 'login', query: { redirect: to.fullPath } }
  return true
})

export default router
