import axios from 'axios'
import type { AxiosInstance, AxiosResponse, InternalAxiosRequestConfig } from 'axios'
import { AUTH_DISABLED } from '@/stores/user'

// 创建 axios 实例
const apiClient: AxiosInstance = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '/api/v1',
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
})

// 请求拦截器
apiClient.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    // Let the browser set the multipart boundary for uploaded inquiry files.
    // The Axios instance has a JSON default header for all other requests.
    if (typeof FormData !== 'undefined' && config.data instanceof FormData && config.headers) {
      delete config.headers['Content-Type']
    }

    // 添加 token
    const token = localStorage.getItem('token')
    if (!AUTH_DISABLED && token && config.headers) {
      config.headers.Authorization = `Bearer ${token}`
    }

    // 添加时间戳防止缓存
    if (config.method === 'get') {
      config.params = {
        ...config.params,
        _t: Date.now(),
      }
    }

    return config
  },
  (error) => {
    return Promise.reject(error)
  }
)

// 响应拦截器
apiClient.interceptors.response.use(
  (response: AxiosResponse) => {
    return response
  },
  async (error) => {
    const originalRequest = error.config
    // Keep the server response available to workflow screens. Shipping-order
    // submission uses structured 409 warnings (code/message/details) to let
    // the operator explicitly confirm a duplicate or unregistered part.
    const attachResponse = (message: string) => {
      const enriched = new Error(message) as Error & { response?: unknown; status?: number }
      enriched.response = error.response
      enriched.status = error.response?.status
      return enriched
    }

    // 401 未授权 - 跳转到登录页
    if (error.response?.status === 401 && !originalRequest._retry && !AUTH_DISABLED) {
      originalRequest._retry = true

      // 清除本地存储
      localStorage.removeItem('token')
      localStorage.removeItem('userInfo')

      // 跳转到登录页
      window.location.href = '/login'

      return Promise.reject(attachResponse('登录已过期，请重新登录'))
    }

    // 403 禁止访问
    if (error.response?.status === 403) {
      if (AUTH_DISABLED) {
        console.warn('验收模式：已跳过前端权限限制，接口返回403')
        return Promise.reject(attachResponse('验收模式下接口暂未返回数据'))
      }
      console.error('权限不足:', error.response.data?.detail || '无权限访问')
      return Promise.reject(attachResponse('权限不足'))
    }

    // 404 未找到
    if (error.response?.status === 404) {
      return Promise.reject(attachResponse('资源不存在'))
    }

    // 500 服务器错误
    if (error.response?.status >= 500) {
      console.error('服务器错误:', error.response?.data)
      return Promise.reject(attachResponse('服务器错误，请稍后重试'))
    }

    // 其他错误
    const errorMessage =
      error.response?.data?.detail ||
      error.response?.data?.message ||
      error.message ||
      '请求失败'

    return Promise.reject(attachResponse(typeof errorMessage === 'string' ? errorMessage : '请求失败'))
  }
)

// Only the registry-aware API client may use this transport instance.
export { apiClient }
export default apiClient
