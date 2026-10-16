import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

interface User {
  id: number
  username: string
  real_name?: string | null
  dept: string
  role_level: number  // Canonical LV1-LV4
  position?: string | null
  is_tech: boolean
  created_at?: string | null
}

// The frontend is temporarily running without the login workflow. Keep the
// default identity in one place so the router, layout, and future auth flow
// can switch back to server-provided user data without changing page code.
export const DEFAULT_ADMIN_USER: User = {
  id: 1,
  username: 'admin',
  real_name: '管理员',
  dept: 'admin',
  role_level: 4,
  position: '系统管理员',
  is_tech: true,
}

export const AUTH_DISABLED = true
export const DEFAULT_ADMIN_TOKEN = 'temporary-admin-session'

export const useUserStore = defineStore('user', () => {
  const token = ref(AUTH_DISABLED ? DEFAULT_ADMIN_TOKEN : (localStorage.getItem('token') || ''))

  // Restore user info from localStorage
  let savedUserInfo = null
  try {
    const saved = localStorage.getItem('userInfo')
    if (saved) {
      savedUserInfo = JSON.parse(saved)
    }
  } catch (e) {
    console.error('Failed to parse user info:', e)
  }

  const userInfo = ref<User>(AUTH_DISABLED ? DEFAULT_ADMIN_USER : (savedUserInfo || DEFAULT_ADMIN_USER))

  // Persist the temporary admin session so a refresh stays inside the app.
  if (AUTH_DISABLED) {
    localStorage.setItem('token', DEFAULT_ADMIN_TOKEN)
    localStorage.setItem('userInfo', JSON.stringify(DEFAULT_ADMIN_USER))
  }

  const isLoggedIn = computed(() => !!token.value)
  const isSuperAdmin = computed(() => userInfo.value?.role_level === 4)  // LV4
  const isBoss = computed(() => (userInfo.value?.role_level ?? 0) >= 3)  // LV3+
  const isManager = computed(() => (userInfo.value?.role_level ?? 0) >= 2)  // LV2+
  const isOrdinaryStaff = computed(() => (userInfo.value?.role_level ?? 0) >= 1)  // LV1+

  const setToken = (newToken: string) => {
    token.value = newToken
    localStorage.setItem('token', newToken)
  }

  const setUserInfo = (info: User) => {
    userInfo.value = info
    // Save to localStorage for restore after refresh
    localStorage.setItem('userInfo', JSON.stringify(info))
  }

  const logout = () => {
    // Login is intentionally disabled for this frontend phase. Resetting the
    // session keeps the user in the fixed administrator workspace.
    token.value = DEFAULT_ADMIN_TOKEN
    userInfo.value = DEFAULT_ADMIN_USER
    localStorage.setItem('token', DEFAULT_ADMIN_TOKEN)
    localStorage.setItem('userInfo', JSON.stringify(DEFAULT_ADMIN_USER))
  }

  return {
    token,
    userInfo,
    isLoggedIn,
    isSuperAdmin,
    isBoss,
    isManager,
    isOrdinaryStaff,
    setToken,
    setUserInfo,
    logout,
  }
})
