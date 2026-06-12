import { createRouter, createWebHistory, RouteRecordRaw } from 'vue-router'

const routes: RouteRecordRaw[] = [
  {
    path: '/login',
    name: 'Login',
    component: () => import('@/views/login/index.vue'),
  },
  {
    path: '/',
    component: () => import('@/views/layout/index.vue'),
    redirect: '/dashboard',
    children: [
      {
        path: 'dashboard',
        name: 'Dashboard',
        component: () => import('@/views/dashboard/index.vue'),
      },
      {
        path: 'quotes',
        name: 'Quotes',
        component: () => import('@/views/quotes/index.vue'),
      },
      {
        path: 'parts',
        name: 'Parts',
        component: () => import('@/views/parts/index.vue'),
      },
      {
        path: 'production',
        name: 'Production',
        component: () => import('@/views/production/index.vue'),
      },
      {
        path: 'machines',
        name: 'Machines',
        component: () => import('@/views/machines/index.vue'),
      },
      {
        path: 'warehouse',
        name: 'Warehouse',
        component: () => import('@/views/warehouse/index.vue'),
      },
      {
        path: 'quality',
        name: 'Quality',
        component: () => import('@/views/quality/index.vue'),
      },
    ],
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.beforeEach((to, from, next) => {
  const token = localStorage.getItem('token')
  if (!token && to.path !== '/login') {
    next('/login')
  } else {
    next()
  }
})

export default router
