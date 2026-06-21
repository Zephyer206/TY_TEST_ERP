import { createRouter, createWebHistory, RouteRecordRaw } from 'vue-router'
import { useUserStore } from '@/stores/user'

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
        meta: { roleLevel: 5 },
      },
      {
        path: 'parts',
        name: 'Parts',
        component: () => import('@/views/parts/index.vue'),
        meta: { roleLevel: 3 },
      },
      {
        path: 'production',
        name: 'Production',
        component: () => import('@/views/production/index.vue'),
        meta: { roleLevel: 3 },
      },
      {
        path: 'machines',
        name: 'Machines',
        component: () => import('@/views/machines/index.vue'),
        meta: { roleLevel: 1 },
      },
      {
        path: 'warehouse',
        name: 'Warehouse',
        component: () => import('@/views/warehouse/index.vue'),
        meta: { roleLevel: 3 },
      },
      {
        path: 'quality',
        name: 'Quality',
        component: () => import('@/views/quality/index.vue'),
        meta: { roleLevel: 3 },
      },
      {
        path: 'sampling',
        name: 'Sampling',
        component: () => import('@/views/sampling/index.vue'),
        meta: { roleLevel: 3 },
      },
      {
        path: 'sampling/detail/:id',
        name: 'SamplingDetail',
        component: () => import('@/views/sampling/detail.vue'),
        meta: { roleLevel: 3 },
      },
      {
        path: 'sampling/review/:id',
        name: 'SamplingReview',
        component: () => import('@/views/sampling/review.vue'),
        meta: { roleLevel: 5 },
      },
    ],
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

// Routes that should be blocked when admin is in context-switched mode
const ADMIN_ONLY_ROUTES = ['quotes-boss-approval', 'admin-settings']

router.beforeEach(async (to, from, next) => {
  const token = localStorage.getItem('token')

  // Login check
  if (!token && to.path !== '/login') {
    next('/login')
    return
  }

  if (to.path === '/login') {
    next()
    return
  }

  // Get permission store context info if token exists
  let isSwitched = false
  let effectiveRoleLevel = 0

  try {
    const userStore = useUserStore()
    // If user is admin, check for context switch
    if (userStore.isAdmin) {
      const response = await fetch('/api/admin/context-info', {
        headers: {
          'Authorization': `Bearer ${token}`,
        },
      })
      if (response.ok) {
        const contextInfo = await response.json()
        isSwitched = contextInfo.is_switched
        effectiveRoleLevel = contextInfo.current_role_level
      }
    }
  } catch (error) {
    console.error('Failed to check context switch:', error)
  }

  // Block admin-only routes when switched
  if (isSwitched) {
    const routeName = to.name as string
    if (ADMIN_ONLY_ROUTES.some(route => routeName.includes(route))) {
      console.warn('Access denied: Admin-only route blocked during context switch')
      next('/dashboard')
      return
    }
  }

  // Role level check for route access
  const requiredLevel = to.meta.roleLevel as number | undefined
  if (requiredLevel !== undefined) {
    const userStore = useUserStore()
    const userRoleLevel = isSwitched ? effectiveRoleLevel : (userStore.userInfo?.role_level ?? 0)

    if (userRoleLevel < requiredLevel) {
      console.warn(`Access denied: Route requires role level ${requiredLevel}`)
      next('/dashboard')
      return
    }
  }

  next()
})

export default router
