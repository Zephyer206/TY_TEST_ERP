import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { sendApiRequest } from '../api'

interface ContextSwitch {
  user_id: number
  original_role_level: number
  original_dept: string | null
  current_role_level: number
  current_dept: string
  is_switched: boolean
  switch_type: string | null
  switched_at: string | null
  expires_at: string | null
}

interface DeptRoleMapping {
  department: string
  role_level: number
  role_name: string
}

export const usePermissionStore = defineStore('permission', () => {
  // Context switch state
  const contextSwitch = ref<ContextSwitch | null>(null)
  const availableDepartments = ref<DeptRoleMapping[]>([])

  // Computed: effective role after context switch
  const effectiveRoleLevel = computed(() => {
    return contextSwitch.value?.current_role_level ?? 0
  })

  const effectiveDept = computed(() => {
    return contextSwitch.value?.current_dept ?? ''
  })

  const isSwitched = computed(() => {
    return contextSwitch.value?.is_switched ?? false
  })

  // Check if current user can access boss buttons
  // Boss buttons should be hidden when admin is in context-switched mode
  const canAccessBossButtons = computed(() => {
    if (!contextSwitch.value) {
      // No switch, use original role from user store
      return true
    }
    // When switched, boss buttons (LV3) should be hidden
    return contextSwitch.value.current_role_level >= 3
  })

  // Fetch current context info
  const fetchContextInfo = async () => {
    try {
      const data = await sendApiRequest('GET', '/api/admin/context-info')
      contextSwitch.value = data
      return data
    } catch (error) {
      console.error('Failed to fetch context info:', error)
      return null
    }
  }

  // Fetch available departments
  const fetchDepartments = async () => {
    try {
      const data = await sendApiRequest('GET', '/api/admin/departments')
      availableDepartments.value = data
      return data
    } catch (error) {
      console.error('Failed to fetch departments:', error)
      return []
    }
  }

  // Switch context to a department
  const switchContext = async (department: string) => {
    try {
      const data = await sendApiRequest('POST', '/api/admin/switch-context', { department })
      await fetchContextInfo()
      return data
    } catch (error) {
      console.error('Failed to switch context:', error)
      throw error
    }
  }

  // Switch back to admin
  const switchBack = async () => {
    try {
      const data = await sendApiRequest('POST', '/api/admin/switch-back')
      contextSwitch.value = null
      return data
    } catch (error) {
      console.error('Failed to switch back:', error)
      throw error
    }
  }

  // Check if user has minimum role level
  const hasRoleLevel = (minLevel: number): boolean => {
    return effectiveRoleLevel.value >= minLevel
  }

  // Check if user can perform action (requires specific role)
  const canPerformAction = (requiredLevel: number): boolean => {
    return effectiveRoleLevel.value >= requiredLevel
  }

  // Check if route should be accessible
  const canAccessRoute = (routeName: string, requiredRoleLevel: number = 1): boolean => {
    // When switched, certain admin routes should be blocked
    if (isSwitched.value && routeName.startsWith('admin-')) {
      return false
    }
    return hasRoleLevel(requiredRoleLevel)
  }

  // Check if button should be visible based on role
  const isButtonVisible = (buttonRoleLevel: number): boolean => {
    // When switched, hide buttons requiring LV3 or higher
    if (isSwitched.value && buttonRoleLevel >= 3) {
      return false
    }
    return effectiveRoleLevel.value >= buttonRoleLevel
  }

  // Reset context (e.g., on logout)
  const resetContext = () => {
    contextSwitch.value = null
    availableDepartments.value = []
  }

  return {
    // State
    contextSwitch,
    availableDepartments,

    // Computed
    effectiveRoleLevel,
    effectiveDept,
    isSwitched,
    canAccessBossButtons,

    // Actions
    fetchContextInfo,
    fetchDepartments,
    switchContext,
    switchBack,
    hasRoleLevel,
    canPerformAction,
    canAccessRoute,
    isButtonVisible,
    resetContext,
  }
})
