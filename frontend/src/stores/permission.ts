/**
 * Permission store for dynamic button and route access control.
 * Handles admin context switching to hide boss-only buttons.
 */

import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export interface ContextStatus {
  is_switched: boolean
  current_role_level: number
  current_role_name: string
  original_role_level?: number
  original_role_name?: string
  switched_at?: string
  expires_at?: string
  remaining_minutes?: number
}

const SWITCH_TOKEN_KEY = 'switch_token'
const SWITCH_CONTEXT_KEY = 'switch_context'

export const usePermissionStore = defineStore('permission', () => {
  // Admin context switch state
  const switchToken = ref<string | null>(localStorage.getItem(SWITCH_TOKEN_KEY) || null)
  const contextStatus = ref<ContextStatus | null>(
    JSON.parse(localStorage.getItem(SWITCH_CONTEXT_KEY) || 'null')
  )

  // Computed: effective role level (switched or original)
  const effectiveRoleLevel = computed(() => {
    if (contextStatus.value?.is_switched) {
      return contextStatus.value.current_role_level
    }
    // Fall back to user store (will be set by auth)
    const stored = localStorage.getItem('user_role_level')
    return stored ? parseInt(stored) : 10
  })

  // Computed: whether in switched context
  const isSwitched = computed(() => contextStatus.value?.is_switched ?? false)

  // Computed: whether admin (role_level >= 9 for boss审批权限)
  const isAdmin = computed(() => effectiveRoleLevel.value === 10)

  // Computed: whether can see boss-only buttons
  // Admin in switched context should NOT see boss buttons
  const canSeeBossButtons = computed(() => {
    // If switched, hide boss buttons
    if (isSwitched.value) {
      return false
    }
    // Otherwise use original role level check
    return effectiveRoleLevel.value >= 9
  })

  // Computed: whether can access boss pages (quotes approval, etc.)
  const canAccessBossPages = computed(() => {
    // If switched, block access
    if (isSwitched.value) {
      return false
    }
    return effectiveRoleLevel.value >= 9
  })

  // Permission check helpers
  const canAccess = (minLevel: number): boolean => {
    return effectiveRoleLevel.value >= minLevel
  }

  const canAccessDept = (dept: string): boolean => {
    if (effectiveRoleLevel.value === 10 && !isSwitched.value) {
      return true // Admin can access all
    }
    // Check department match (simplified)
    const stored = localStorage.getItem('user_dept')
    if (!stored) return true
    return stored === dept
  }

  // Context switch operations
  const setSwitchContext = (token: string, status: ContextStatus) => {
    switchToken.value = token
    contextStatus.value = status
    localStorage.setItem(SWITCH_TOKEN_KEY, token)
    localStorage.setItem(SWITCH_CONTEXT_KEY, JSON.stringify(status))
  }

  const clearSwitchContext = () => {
    switchToken.value = null
    contextStatus.value = null
    localStorage.removeItem(SWITCH_TOKEN_KEY)
    localStorage.removeItem(SWITCH_CONTEXT_KEY)
  }

  // Fetch current context status from server
  const fetchContextStatus = async () => {
    if (!switchToken.value) {
      contextStatus.value = null
      return null
    }

    try {
      const response = await fetch('/api/v1/admin/context-status', {
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('token')}`,
        },
      })

      if (response.ok) {
        const data = await response.json()
        if (data.is_switched) {
          contextStatus.value = data
          localStorage.setItem(SWITCH_CONTEXT_KEY, JSON.stringify(data))
        } else {
          clearSwitchContext()
        }
        return data
      } else {
        clearSwitchContext()
        return null
      }
    } catch {
      clearSwitchContext()
      return null
    }
  }

  // Get switch token for API calls
  const getSwitchToken = (): string | null => {
    return switchToken.value
  }

  return {
    // State
    switchToken,
    contextStatus,

    // Computed
    effectiveRoleLevel,
    isSwitched,
    isAdmin,
    canSeeBossButtons,
    canAccessBossPages,

    // Helpers
    canAccess,
    canAccessDept,

    // Context operations
    setSwitchContext,
    clearSwitchContext,
    fetchContextStatus,
    getSwitchToken,
  }
})

// Role level constants
export const ROLE_LEVELS = {
  OPERATOR: 1,
  MOLD_ENGINEER: 2,
  SUPERVISOR: 3,
  DESIGN_ENGINEER: 4,
  SALES_MANAGER: 5,
  BOSS: 9,
  ADMIN: 10,
} as const

// Role name mapping
export const ROLE_NAMES: Record<number, string> = {
  1: '操作工',
  2: '模具工程师',
  3: '组长/主管',
  4: '设计工程师',
  5: '业务经理',
  9: '老板',
  10: '超级管理员',
}
