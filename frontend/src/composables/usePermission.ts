/**
 * Frontend permission control module with canonical LV1-LV4 system
 * Based on specs/001-erp-system-architecture/plan.md lines 198-202
 */

import { computed } from 'vue'
import { useUserStore } from '@/stores/user'
import { usePermissionStore } from '@/stores/permission'

// Canonical 4-level role system
export enum RoleLevel {
  ORDINARY_STAFF = 1,      // LV1: operators, warehouse, QC, spray workers, maintenance
  MANAGER_TECHNICAL = 2,   // LV2: managers, business staff, technical staff, supervisors
  BOSS = 3,                // LV3: boss - final approval, global visibility
  SUPER_ADMIN = 4,         // LV4: super administrator - system management, context switching
}

// Role names mapping
export const RoleNames: Record<number, string> = {
  [RoleLevel.ORDINARY_STAFF]: '普通员工',
  [RoleLevel.MANAGER_TECHNICAL]: '管理人员/业务技术',
  [RoleLevel.BOSS]: '老板',
  [RoleLevel.SUPER_ADMIN]: '超级管理员',
}

// Permission configuration
export interface PermissionConfig {
  // Basic permissions
  canView: boolean           // View permission
  canCreate: boolean         // Create permission
  canEdit: boolean           // Edit permission
  canDelete: boolean         // Delete permission
  canApprove: boolean        // Approval permission
  canExport: boolean         // Export permission
  canImport: boolean         // Import permission

  // Business permissions
  canSubmitQuote: boolean    // Submit quote
  canApproveQuote: boolean   // Boss approve quote
  canCreatePlan: boolean      // Create production plan
  canReportProduction: boolean // Production reporting
  canInspect: boolean         // Quality inspection
  canManageStock: boolean     // Stock management
  canManageUser: boolean     // User management
  canViewCost: boolean        // View cost
  canViewReports: boolean     // View reports
}

// Get base permissions configuration
export function getBasePermissions(roleLevel: number): PermissionConfig {
  const isSuperAdmin = roleLevel >= RoleLevel.SUPER_ADMIN
  const isBoss = roleLevel >= RoleLevel.BOSS
  const isManager = roleLevel >= RoleLevel.MANAGER_TECHNICAL
  const isOrdinaryStaff = roleLevel >= RoleLevel.ORDINARY_STAFF

  return {
    // Basic permissions
    canView: isOrdinaryStaff,
    canCreate: isManager,
    canEdit: isManager,
    canDelete: isManager,
    canApprove: isBoss,
    canExport: isManager,
    canImport: isManager,

    // Business permissions
    canSubmitQuote: isManager,
    canApproveQuote: isBoss,
    canCreatePlan: isManager,
    canReportProduction: isOrdinaryStaff,
    canInspect: isOrdinaryStaff,
    canManageStock: isOrdinaryStaff,
    canManageUser: isSuperAdmin,
    canViewCost: isManager,
    canViewReports: isManager,
  }
}

// Get quote approval permission
export function canApproveQuote(roleLevel: number): boolean {
  return roleLevel >= RoleLevel.BOSS
}

// Get production reporting permission
export function canReportProduction(roleLevel: number): boolean {
  return roleLevel >= RoleLevel.ORDINARY_STAFF
}

// Get quality inspection permission
export function canInspect(roleLevel: number): boolean {
  return roleLevel >= RoleLevel.ORDINARY_STAFF
}

// Get user management permission
export function canManageUser(roleLevel: number): boolean {
  return roleLevel >= RoleLevel.SUPER_ADMIN
}

// Get cost view permission
export function canViewCost(roleLevel: number): boolean {
  return roleLevel >= RoleLevel.MANAGER_TECHNICAL
}

// Check if boss button should be hidden
export function shouldHideBossButton(roleLevel: number, isSwitched: boolean): boolean {
  // When super admin switches to other perspective, hide boss buttons
  if (isSwitched && roleLevel >= RoleLevel.SUPER_ADMIN) {
    return true
  }
  return roleLevel < RoleLevel.BOSS
}

// Vue composable permission hook
export function usePermission() {
  const userStore = useUserStore()
  const permissionStore = usePermissionStore()

  // Get current effective role level
  const effectiveRoleLevel = computed(() => {
    return permissionStore.effectiveRoleLevel || userStore.userInfo?.role_level || 0
  })

  // Get current switch status
  const isSwitched = computed(() => permissionStore.isSwitched)

  // Get permission configuration
  const permissions = computed(() => getBasePermissions(effectiveRoleLevel.value))

  // Check if has specified level permission
  const hasPermission = (minLevel: number): boolean => {
    return effectiveRoleLevel.value >= minLevel
  }

  // Check specific permission
  const can = (permission: keyof PermissionConfig): boolean => {
    return permissions.value[permission]
  }

  // Check if should show boss button
  const showBossButton = computed(() => {
    return !shouldHideBossButton(effectiveRoleLevel.value, isSwitched.value)
  })

  // Check if should show admin button
  const showAdminButton = computed(() => {
    return effectiveRoleLevel.value >= RoleLevel.SUPER_ADMIN && !isSwitched.value
  })

  return {
    effectiveRoleLevel,
    isSwitched,
    permissions,
    hasPermission,
    can,
    showBossButton,
    showAdminButton,
    RoleLevel,
    RoleNames,
  }
}

// Permission directive
export const permissionDirective = {
  mounted(el: HTMLElement, binding: any) {
    const { value } = binding
    const userStore = useUserStore()
    const roleLevel = userStore.userInfo?.role_level || 0

    // value can be number (minimum role level) or permission key name
    if (typeof value === 'number') {
      if (roleLevel < value) {
        el.style.display = 'none'
      }
    } else if (typeof value === 'string') {
      const permissions = getBasePermissions(roleLevel)
      if (!permissions[value as keyof PermissionConfig]) {
        el.style.display = 'none'
      }
    }
  },
}

// Export permission check utilities
export default {
  RoleLevel,
  RoleNames,
  getBasePermissions,
  canApproveQuote,
  canReportProduction,
  canInspect,
  canManageUser,
  canViewCost,
  shouldHideBossButton,
  usePermission,
  permissionDirective,
}
