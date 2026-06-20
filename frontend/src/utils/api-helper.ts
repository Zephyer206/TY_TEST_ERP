/**
 * Unified API error handling for frontend.
 * Handles 401 redirects, 403 notifications, and other HTTP errors.
 */

import { ElMessage, ElMessageBox } from 'element-plus'

export interface ApiError {
  status: number
  message: string
  detail?: string | Record<string, any>
}

export interface ApiResponse<T = any> {
  data: T | null
  error: ApiError | null
  loading: boolean
}

/**
 * Handle HTTP response and extract error info.
 */
export async function handleResponse<T>(
  response: Response,
): Promise<{ data: T | null; error: ApiError | null }> {
  const { status, ok } = response

  if (ok) {
    const data = await response.json().catch(() => null)
    return { data, error: null }
  }

  const contentType = response.headers.get('content-type')
  let detail: string | Record<string, any> = ''

  if (contentType?.includes('application/json')) {
    try {
      const json = await response.json()
      detail = json.detail || json.message || json
    } catch {
      detail = await response.text()
    }
  } else {
    detail = await response.text()
  }

  const error: ApiError = {
    status,
    message: getErrorMessage(status),
    detail,
  }

  return { data: null, error }
}

/**
 * Get user-friendly error message for HTTP status code.
 */
function getErrorMessage(status: number): string {
  const messages: Record<number, string> = {
    400: '请求参数错误',
    401: '登录已过期，请重新登录',
    403: '您没有权限执行此操作',
    404: '请求的资源不存在',
    405: '请求方法不允许',
    408: '请求超时，请重试',
    409: '请求冲突，请刷新后重试',
    422: '数据验证失败',
    429: '请求过于频繁，请稍后再试',
    500: '服务器内部错误',
    502: '网关错误',
    503: '服务暂时不可用',
    504: '网关超时',
  }

  return messages[status] || `请求失败 (${status})`
}

/**
 * Global error handler for API calls.
 */
export function handleApiError(error: ApiError | Error, context?: string) {
  // Log error
  console.error(`[API Error${context ? ` - ${context}` : ''}:]`, error)

  // Handle specific status codes
  if (isApiError(error)) {
    switch (error.status) {
      case 401:
        handleUnauthorized()
        return
      case 403:
        ElMessage.error({
          message: error.detail as string || error.message,
          duration: 4000,
        })
        return
      case 404:
        ElMessage.warning({
          message: '资源不存在',
          duration: 3000,
        })
        return
    }
  }

  // Generic error message
  const message = isApiError(error) ? error.message : '网络错误，请重试'
  ElMessage.error({
    message,
    duration: 4000,
  })
}

/**
 * Check if object is an API error.
 */
function isApiError(obj: any): obj is ApiError {
  return obj && typeof obj.status === 'number' && typeof obj.message === 'string'
}

/**
 * Handle 401 Unauthorized - redirect to login.
 */
function handleUnauthorized() {
  // Clear auth data
  localStorage.removeItem('token')
  localStorage.removeItem('user_role_level')
  localStorage.removeItem('switch_context')

  // Show message
  ElMessageBox.alert(
    '您的登录已过期，请重新登录。',
    '登录过期',
    {
      confirmButtonText: '确定',
      type: 'warning',
      showClose: false,
    }
  ).then(() => {
    // Redirect to login
    window.location.href = '/login'
  }).catch(() => {
    window.location.href = '/login'
  })
}

/**
 * Create a fetch wrapper with unified error handling.
 */
export async function apiRequest<T>(
  url: string,
  options: RequestInit = {},
): Promise<T> {
  const token = localStorage.getItem('token')

  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(options.headers as Record<string, string>),
  }

  if (token) {
    headers['Authorization'] = `Bearer ${token}`
  }

  try {
    const response = await fetch(url, {
      ...options,
      headers,
    })

    const { data, error } = await handleResponse<T>(response)

    if (error) {
      handleApiError(error)
      throw error
    }

    return data as T
  } catch (err) {
    // Don't handle again if already handled
    if (!isApiError(err)) {
      console.error('Network error:', err)
      ElMessage.error('网络错误，请检查您的连接')
    }
    throw err
  }
}

/**
 * HTTP method shortcuts.
 */
export const http = {
  get: <T>(url: string, options?: RequestInit) =>
    apiRequest<T>(url, { ...options, method: 'GET' }),

  post: <T>(url: string, body?: any, options?: RequestInit) =>
    apiRequest<T>(url, {
      ...options,
      method: 'POST',
      body: JSON.stringify(body),
    }),

  put: <T>(url: string, body?: any, options?: RequestInit) =>
    apiRequest<T>(url, {
      ...options,
      method: 'PUT',
      body: JSON.stringify(body),
    }),

  patch: <T>(url: string, body?: any, options?: RequestInit) =>
    apiRequest<T>(url, {
      ...options,
      method: 'PATCH',
      body: JSON.stringify(body),
    }),

  delete: <T>(url: string, options?: RequestInit) =>
    apiRequest<T>(url, { ...options, method: 'DELETE' }),
}

/**
 * Confirmation dialog for destructive actions.
 */
export async function confirmDelete(
  title: string = '确认删除',
  message: string = '此操作不可逆，是否继续？',
): Promise<boolean> {
  try {
    await ElMessageBox.confirm(message, title, {
      confirmButtonText: '确认删除',
      cancelButtonText: '取消',
      type: 'warning',
    })
    return true
  } catch {
    return false
  }
}

/**
 * Confirmation dialog for sensitive operations.
 */
export async function confirmSensitive(
  title: string,
  message: string,
  confirmText: string = '确认',
): Promise<boolean> {
  try {
    await ElMessageBox.confirm(message, title, {
      confirmButtonText: confirmText,
      cancelButtonText: '取消',
      type: 'warning',
    })
    return true
  } catch {
    return false
  }
}
