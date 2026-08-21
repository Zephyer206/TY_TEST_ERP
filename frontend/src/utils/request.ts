import axios from 'axios'
import type { AxiosInstance, AxiosRequestConfig, AxiosResponse, InternalAxiosRequestConfig } from 'axios'

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
    // 添加 token
    const token = localStorage.getItem('token')
    if (token && config.headers) {
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

    // 401 未授权 - 跳转到登录页
    if (error.response?.status === 401 && !originalRequest._retry) {
      originalRequest._retry = true

      // 清除本地存储
      localStorage.removeItem('token')
      localStorage.removeItem('userInfo')

      // 跳转到登录页
      window.location.href = '/login'

      return Promise.reject(new Error('登录已过期，请重新登录'))
    }

    // 403 禁止访问
    if (error.response?.status === 403) {
      console.error('权限不足:', error.response.data?.detail || '无权限访问')
      return Promise.reject(new Error('权限不足'))
    }

    // 404 未找到
    if (error.response?.status === 404) {
      return Promise.reject(new Error('资源不存在'))
    }

    // 500 服务器错误
    if (error.response?.status >= 500) {
      console.error('服务器错误:', error.response?.data)
      return Promise.reject(new Error('服务器错误，请稍后重试'))
    }

    // 其他错误
    const errorMessage =
      error.response?.data?.detail ||
      error.response?.data?.message ||
      error.message ||
      '请求失败'

    return Promise.reject(new Error(errorMessage))
  }
)

// 通用 GET 请求
export const get = <T = any>(
  url: string,
  params?: Record<string, any>,
  config?: AxiosRequestConfig
): Promise<T> => {
  return apiClient.get(url, { params, ...config }).then((res) => res.data)
}

// 通用 POST 请求
export const post = <T = any>(
  url: string,
  data?: any,
  config?: AxiosRequestConfig
): Promise<T> => {
  return apiClient.post(url, data, config).then((res) => res.data)
}

// 通用 PUT 请求
export const put = <T = any>(
  url: string,
  data?: any,
  config?: AxiosRequestConfig
): Promise<T> => {
  return apiClient.put(url, data, config).then((res) => res.data)
}

// 通用 PATCH 请求
export const patch = <T = any>(
  url: string,
  data?: any,
  config?: AxiosRequestConfig
): Promise<T> => {
  return apiClient.patch(url, data, config).then((res) => res.data)
}

// 通用 DELETE 请求
export const del = <T = any>(
  url: string,
  config?: AxiosRequestConfig
): Promise<T> => {
  return apiClient.delete(url, config).then((res) => res.data)
}

// 导出实例和快捷方法
export { apiClient }
export default apiClient
