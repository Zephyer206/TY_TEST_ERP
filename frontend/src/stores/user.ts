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

export const useUserStore = defineStore('user', () => {
  const token = ref(localStorage.getItem('token') || '')

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

  const userInfo = ref<User | null>(savedUserInfo)

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
    token.value = ''
    userInfo.value = null
    localStorage.removeItem('token')
    localStorage.removeItem('userInfo')
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
