import { createRouter, createWebHistory, RouteRecordRaw } from 'vue-router'

// Route meta for permission requirements
export interface RouteMeta {
  requiresAuth?: boolean
  minRoleLevel?: number
  bossOnly?: boolean
  adminOnly?: boolean
}

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
        meta: { requiresAuth: true },
      },
      {
        path: 'quotes',
        name: 'Quotes',
        component: () => import('@/views/quotes/index.vue'),
        meta: { requiresAuth: true, minRoleLevel: 4 },
      },
      {
        path: 'parts',
        name: 'Parts',
        component: () => import('@/views/parts/index.vue'),
        meta: { requiresAuth: true },
      },
      {
        path: 'production',
        name: 'Production',
        component: () => import('@/views/production/index.vue'),
        meta: { requiresAuth: true, minRoleLevel: 1 },
      },
      {
        path: 'machines',
        name: 'Machines',
        component: () => import('@/views/machines/index.vue'),
        meta: { requiresAuth: true },
      },
      {
        path: 'warehouse',
        name: 'Warehouse',
        component: () => import('@/views/warehouse/index.vue'),
        meta: { requiresAuth: true },
      },
      {
        path: 'quality',
        name: 'Quality',
        component: () => import('@/views/quality/index.vue'),
        meta: { requiresAuth: true, minRoleLevel: 2 },
      },
      // Boss-only routes (blocked when admin is in switched context)
      {
        path: 'boss/approvals',
        name: 'BossApprovals',
        component: () => import('@/views/boss/approvals.vue'),
        meta: { requiresAuth: true, minRoleLevel: 9, bossOnly: true },
      },
      {
        path: 'boss/price-cards',
        name: 'PriceCards',
        component: () => import('@/views/boss/price-cards.vue'),
        meta: { requiresAuth: true, minRoleLevel: 5 },
      },
      // Admin routes
      {
        path: 'admin/users',
        name: 'AdminUsers',
        component: () => import('@/views/admin/users.vue'),
        meta: { requiresAuth: true, adminOnly: true },
      },
      {
        path: 'admin/audit-logs',
        name: 'AdminAuditLogs',
        component: () => import('@/views/admin/audit-logs.vue'),
        meta: { requiresAuth: true, adminOnly: true },
      },
      {
        path: 'admin/context-switch',
        name: 'AdminContextSwitch',
        component: () => import('@/views/admin/context-switch.vue'),
        meta: { requiresAuth: true, adminOnly: true },
      },
    ],
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

// Route guard
router.beforeEach(async (to, _from, next) => {
  const token = localStorage.getItem('token')
  const userRoleLevel = parseInt(localStorage.getItem('user_role_level') || '0')
  const switchContext = localStorage.getItem('switch_context')
  const isSwitched = switchContext ? JSON.parse(switchContext).is_switched : false

  // Check auth requirement
  if (to.meta.requiresAuth !== false && !token && to.path !== '/login') {
    next('/login')
    return
  }

  // Skip further checks for login page
  if (to.path === '/login') {
    next()
    return
  }

  // Get effective role level
  let effectiveRoleLevel = userRoleLevel
  if (userRoleLevel === 10 && isSwitched && switchContext) {
    const ctx = JSON.parse(switchContext)
    effectiveRoleLevel = ctx.current_role_level
  }

  // Check admin-only routes
  if (to.meta.adminOnly) {
    if (effectiveRoleLevel !== 10) {
      next('/dashboard')
      return
    }
  }

  // Check boss-only routes
  if (to.meta.bossOnly) {
    // Block if admin is in switched context
    if (isSwitched) {
      alert('切换视角期间无法访问老板专属页面')
      next('/dashboard')
      return
    }
    // Check role level
    if ((to.meta.minRoleLevel || 0) > effectiveRoleLevel) {
      next('/dashboard')
      return
    }
  }

  // Check min role level
  if (to.meta.minRoleLevel !== undefined) {
    if (effectiveRoleLevel < to.meta.minRoleLevel) {
      next('/dashboard')
      return
    }
  }

  next()
})

export default router
