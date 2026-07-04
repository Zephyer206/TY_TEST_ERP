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
        path: 'customers',
        name: 'Customers',
        component: () => import('@/views/customers/index.vue'),
        meta: { roleLevel: 3 },
      },
      {
        path: 'dictionary',
        name: 'Dictionary',
        component: () => import('@/views/dictionary/index.vue'),
        meta: { roleLevel: 4 },
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
      {
        path: 'tooling',
        name: 'Tooling',
        component: () => import('@/views/tooling/index.vue'),
        meta: { roleLevel: 3 },
      },
      {
        path: 'tooling/detail/:id',
        name: 'ToolingDetail',
        component: () => import('@/views/tooling/detail.vue'),
        meta: { roleLevel: 3 },
      },
      {
        path: 'tooling/maintenance/:id',
        name: 'ToolingMaintenance',
        component: () => import('@/views/tooling/maintenance.vue'),
        meta: { roleLevel: 3 },
      },
      {
        path: 'materials',
        name: 'Materials',
        component: () => import('@/views/materials/index.vue'),
        meta: { roleLevel: 3 },
      },
      {
        path: 'materials/batches/:id',
        name: 'MaterialsBatches',
        component: () => import('@/views/materials/batches.vue'),
        meta: { roleLevel: 3 },
      },
      {
        path: 'materials/slitting/:id',
        name: 'MaterialsSlitting',
        component: () => import('@/views/materials/slitting.vue'),
        meta: { roleLevel: 3 },
      },
      {
        path: 'materials/trace',
        name: 'MaterialsTrace',
        component: () => import('@/views/materials/trace.vue'),
        meta: { roleLevel: 3 },
      },
      {
        path: 'packaging',
        name: 'Packaging',
        component: () => import('@/views/packaging/index.vue'),
        meta: { roleLevel: 3 },
      },
      {
        path: 'packaging/create',
        name: 'PackagingCreate',
        component: () => import('@/views/packaging/create.vue'),
        meta: { roleLevel: 3 },
      },
      {
        path: 'packaging/inventory',
        name: 'PackagingInventory',
        component: () => import('@/views/packaging/inventory.vue'),
        meta: { roleLevel: 3 },
      },
      {
        path: 'packaging/inspect/:id',
        name: 'PackagingInspect',
        component: () => import('@/views/packaging/inspect.vue'),
        meta: { roleLevel: 5 },
      },
      {
        path: 'coating/recipes',
        name: 'CoatingRecipes',
        component: () => import('@/views/coating/recipes.vue'),
        meta: { roleLevel: 3 },
      },
      {
        path: 'coating/records',
        name: 'CoatingRecords',
        component: () => import('@/views/coating/records.vue'),
        meta: { roleLevel: 3 },
      },
      {
        path: 'coating/colors',
        name: 'CoatingColors',
        component: () => import('@/views/coating/colors.vue'),
        meta: { roleLevel: 3 },
      },
      {
        path: 'admin/context-switch',
        name: 'AdminContextSwitch',
        component: () => import('@/views/admin/context-switch.vue'),
        meta: { roleLevel: 10 },
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

  // Role level check for route access
  const requiredLevel = to.meta.roleLevel as number | undefined
  if (requiredLevel !== undefined) {
    const userStore = useUserStore()
    const userRoleLevel = userStore.userInfo?.role_level ?? 10 // 默认给管理员权限

    if (userRoleLevel < requiredLevel) {
      console.warn(`Access denied: Route requires role level ${requiredLevel}, user has ${userRoleLevel}`)
      next('/dashboard')
      return
    }
  }

  next()
})

export default router
