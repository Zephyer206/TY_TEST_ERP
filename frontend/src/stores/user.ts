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
  const userInfo = ref<User | null>(null)

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
  }

  const logout = () => {
    token.value = ''
    userInfo.value = null
    localStorage.removeItem('token')
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
