import { createApp } from 'vue'
import { createRouter, createWebHistory } from 'vue-router'
import Vant from 'vant'
import 'vant/lib/index.css'
import '@vant/touch-emulator'

import App from './App.vue'
import './style.css'

const routes = [
  { path: '/login', name: 'Login', component: () => import('./views/Login.vue') },
  { path: '/', redirect: '/query' },
  { path: '/dashboard', redirect: '/query' },
  { path: '/query', name: 'Query', component: () => import('./views/Query.vue'), meta: { requiresAuth: true } },
  { path: '/production', name: 'Production', component: () => import('./views/Production.vue'), meta: { requiresAuth: true } },
  { path: '/delivery', name: 'Delivery', component: () => import('./views/Delivery.vue'), meta: { requiresAuth: true } },
  { path: '/scan', name: 'Scan', component: () => import('./views/Scan.vue'), meta: { requiresAuth: true } },
  { path: '/report', name: 'Report', component: () => import('./views/Report.vue'), meta: { requiresAuth: true } },
  { path: '/parts', redirect: '/query?tab=parts' },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.beforeEach((to) => {
  if (to.meta.requiresAuth && !localStorage.getItem('access_token')) return '/login'
  if (to.path === '/login' && localStorage.getItem('access_token')) return '/query'
  return true
})

window.addEventListener('mobile-auth-expired', () => {
  if (router.currentRoute.value.path !== '/login') router.replace('/login')
})

createApp(App).use(router).use(Vant).mount('#app')
