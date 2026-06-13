/**
 * 前端权限控制模块
 * 提供基于 role_level 的动态按钮权限控制
 */

import { computed, Ref } from 'vue'
import { useUserStore } from '@/stores/user'
import { usePermissionStore } from '@/stores/permission'

// 角色级别定义
export enum RoleLevel {
  WORKER = 1,           // 操作工
  TECHNICIAN = 2,       // 技术员/模具工程师
  SUPERVISOR = 3,       // 组长/主管
  ENGINEER = 4,         // 工程师
  MANAGER = 5,          // 经理/业务经理
  SENIOR_MANAGER = 7,   // 高级经理
  BOSS = 9,             // 老板
  ADMIN = 10,           // 超级管理员
}

// 角色名称映射
export const RoleNames: Record<number, string> = {
  [RoleLevel.WORKER]: '操作工',
  [RoleLevel.TECHNICIAN]: '技术员',
  [RoleLevel.SUPERVISOR]: '主管',
  [RoleLevel.ENGINEER]: '工程师',
  [RoleLevel.MANAGER]: '经理',
  [RoleLevel.SENIOR_MANAGER]: '高级经理',
  [RoleLevel.BOSS]: '老板',
  [RoleLevel.ADMIN]: '管理员',
}

// 权限配置
export interface PermissionConfig {
  // 基础权限
  canView: boolean           // 查看权限
  canCreate: boolean         // 创建权限
  canEdit: boolean           // 编辑权限
  canDelete: boolean         // 删除权限
  canApprove: boolean        // 审批权限
  canExport: boolean         // 导出权限
  canImport: boolean         // 导入权限

  // 业务权限
  canSubmitQuote: boolean    // 提交报价
  canApproveQuote: boolean   // 审批报价
  canCreatePlan: boolean      // 创建生产计划
  canReportProduction: boolean // 生产报工
  canInspect: boolean         // 质量检验
  canManageStock: boolean     // 库存管理
  canManageUser: boolean     // 用户管理
  canViewCost: boolean        // 查看成本
  canViewReports: boolean     // 查看报表
}

// 获取基础权限配置
export function getBasePermissions(roleLevel: number): PermissionConfig {
  const isAdmin = roleLevel >= RoleLevel.ADMIN
  const isBoss = roleLevel >= RoleLevel.BOSS
  const isManager = roleLevel >= RoleLevel.MANAGER
  const isSupervisor = roleLevel >= RoleLevel.SUPERVISOR
  const isTechnician = roleLevel >= RoleLevel.TECHNICIAN
  const isWorker = roleLevel >= RoleLevel.WORKER

  return {
    // 基础权限
    canView: isWorker,
    canCreate: isSupervisor,
    canEdit: isSupervisor,
    canDelete: isSupervisor,
    canApprove: isBoss,
    canExport: isSupervisor,
    canImport: isManager,

    // 业务权限
    canSubmitQuote: isManager,
    canApproveQuote: isBoss,
    canCreatePlan: isSupervisor,
    canReportProduction: isWorker,
    canInspect: isTechnician,
    canManageStock: isSupervisor,
    canManageUser: isAdmin,
    canViewCost: isManager,
    canViewReports: isSupervisor,
  }
}

// 获取报价审批权限
export function canApproveQuote(roleLevel: number): boolean {
  return roleLevel >= RoleLevel.BOSS
}

// 获取生产报工权限
export function canReportProduction(roleLevel: number): boolean {
  return roleLevel >= RoleLevel.WORKER
}

// 获取质量检验权限
export function canInspect(roleLevel: number): boolean {
  return roleLevel >= RoleLevel.TECHNICIAN
}

// 获取用户管理权限
export function canManageUser(roleLevel: number): boolean {
  return roleLevel >= RoleLevel.ADMIN
}

// 获取成本查看权限
export function canViewCost(roleLevel: number): boolean {
  return roleLevel >= RoleLevel.MANAGER
}

// 检查是否应该隐藏老板按钮
export function shouldHideBossButton(roleLevel: number, isSwitched: boolean): boolean {
  // 当超级管理员切换到其他视角时，隐藏老板按钮
  if (isSwitched && roleLevel >= RoleLevel.ADMIN) {
    return true
  }
  return roleLevel < RoleLevel.BOSS
}

// Vue 组合式 API 权限钩子
export function usePermission() {
  const userStore = useUserStore()
  const permissionStore = usePermissionStore()

  // 获取当前有效的角色级别
  const effectiveRoleLevel = computed(() => {
    return permissionStore.effectiveRoleLevel || userStore.userInfo?.role_level || 0
  })

  // 获取当前是否切换视角
  const isSwitched = computed(() => permissionStore.isSwitched)

  // 获取权限配置
  const permissions = computed(() => getBasePermissions(effectiveRoleLevel.value))

  // 检查是否有指定级别的权限
  const hasPermission = (minLevel: number): boolean => {
    return effectiveRoleLevel.value >= minLevel
  }

  // 检查特定权限
  const can = (permission: keyof PermissionConfig): boolean => {
    return permissions.value[permission]
  }

  // 检查是否应该显示老板按钮
  const showBossButton = computed(() => {
    return !shouldHideBossButton(effectiveRoleLevel.value, isSwitched.value)
  })

  // 检查是否应该显示管理员按钮
  const showAdminButton = computed(() => {
    return effectiveRoleLevel.value >= RoleLevel.ADMIN && !isSwitched.value
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

// 权限指令
export const permissionDirective = {
  mounted(el: HTMLElement, binding: any) {
    const { value } = binding
    const userStore = useUserStore()
    const roleLevel = userStore.userInfo?.role_level || 0

    // value 可以是数字(最低角色级别)或权限键名
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

// 导出权限检查工具
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
