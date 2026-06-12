import { createApp } from 'vue'
import { createRouter, createWebHistory } from 'vue-router'
import Vant from 'vant'
import 'vant/lib/index.css'
import '@vant/touch-emulator'

import App from './App.vue'
import './style.css'

const routes = [
  {
    path: '/login',
    name: 'Login',
    component: () => import('./views/Login.vue'),
  },
  {
    path: '/',
    redirect: '/dashboard',
  },
  {
    path: '/dashboard',
    name: 'Dashboard',
    component: () => import('./views/Dashboard.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/scan',
    name: 'Scan',
    component: () => import('./views/Scan.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/report',
    name: 'Report',
    component: () => import('./views/Report.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/parts',
    name: 'Parts',
    component: () => import('./views/Parts.vue'),
    meta: { requiresAuth: true },
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.beforeEach((to, from, next) => {
  const userId = localStorage.getItem('user_id')
  if (to.meta.requiresAuth && !userId) {
    next('/login')
  } else {
    next()
  }
})

const app = createApp(App)
app.use(router)
app.use(Vant)
app.mount('#app')
