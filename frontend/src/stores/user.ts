import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

interface User {
  id: number
  username: string
  real_name: string
  role_level: number
  department_id: number
}

export const useUserStore = defineStore('user', () => {
  const token = ref(localStorage.getItem('token') || '')

  // 从 localStorage 恢复用户信息
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
  const isAdmin = computed(() => userInfo.value?.role_level === 10)
  const isBoss = computed(() => userInfo.value?.role_level >= 7)
  const isManager = computed(() => userInfo.value?.role_level >= 5)
  const isWorker = computed(() => userInfo.value?.role_level <= 2)

  const setToken = (newToken: string) => {
    token.value = newToken
    localStorage.setItem('token', newToken)
  }

  const setUserInfo = (info: User) => {
    userInfo.value = info
    // 同时保存到 localStorage 以便刷新后恢复
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
    isAdmin,
    isBoss,
    isManager,
    isWorker,
    setToken,
    setUserInfo,
    logout,
  }
})
