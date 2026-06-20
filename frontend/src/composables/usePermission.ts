/**
 * Permission composable for Vue components.
 * Provides reactive permission checking based on admin context switching.
 */

import { computed, onMounted } from 'vue'
import { storeToRefs } from 'pinia'
import { usePermissionStore, ROLE_LEVELS } from './permission'

export function usePermission() {
  const permissionStore = usePermissionStore()
  const {
    effectiveRoleLevel,
    isSwitched,
    isAdmin,
    canSeeBossButtons,
    canAccessBossPages,
    contextStatus,
  } = storeToRefs(permissionStore)

  // Quick permission checks
  const canAccess = (minLevel: number) => {
    return effectiveRoleLevel.value >= minLevel
  }

  const canAccessOperator = () => canAccess(ROLE_LEVELS.OPERATOR)
  const canAccessEngineer = () => canAccess(ROLE_LEVELS.MOLD_ENGINEER)
  const canAccessSupervisor = () => canAccess(ROLE_LEVELS.SUPERVISOR)
  const canAccessDesigner = () => canAccess(ROLE_LEVELS.DESIGN_ENGINEER)
  const canAccessSalesManager = () => canAccess(ROLE_LEVELS.SALES_MANAGER)
  const canAccessBoss = () => canAccess(ROLE_LEVELS.BOSS)
  const canAccessAdmin = () => canAccess(ROLE_LEVELS.ADMIN)

  // Whether to show boss-only buttons
  const showBossButtons = computed(() => canSeeBossButtons.value)

  // Whether to hide admin-specific UI when switched
  const hideAdminUI = computed(() => isSwitched.value)

  // Fetch context status on mount
  onMounted(async () => {
    await permissionStore.fetchContextStatus()
  })

  return {
    // Refs
    effectiveRoleLevel,
    isSwitched,
    isAdmin,
    canAccessBossPages,
    contextStatus,

    // Helpers
    canAccess,
    canAccessOperator,
    canAccessEngineer,
    canAccessSupervisor,
    canAccessDesigner,
    canAccessSalesManager,
    canAccessBoss,
    canAccessAdmin,

    // Computed flags
    showBossButtons,
    hideAdminUI,

    // Store actions
    setSwitchContext: permissionStore.setSwitchContext,
    clearSwitchContext: permissionStore.clearSwitchContext,
    fetchContextStatus: permissionStore.fetchContextStatus,
    getSwitchToken: permissionStore.getSwitchToken,
  }
}

/**
 * Directive for conditional rendering based on role.
 * Usage: v-if="hasRole(3)"
 */
export function hasRole(minLevel: number): boolean {
  const store = usePermissionStore()
  return store.effectiveRoleLevel >= minLevel
}

/**
 * Directive for hiding elements when admin is in switched context.
 * Usage: v-if="!isInSwitchedContext"
 */
export function isInSwitchedContext(): boolean {
  const store = usePermissionStore()
  return store.isSwitched
}
