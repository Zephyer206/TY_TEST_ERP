/**
 * 统一 API 错误处理模块
 * 提供错误提示、401重定向、403提示等功能
 */

import { ElMessage, ElMessageBox, ElNotification } from 'element-plus'
import router from '@/router'
import { AUTH_DISABLED } from '@/stores/user'

// 错误类型
export enum ApiErrorType {
  NETWORK = 'NETWORK',
  UNAUTHORIZED = 'UNAUTHORIZED',
  FORBIDDEN = 'FORBIDDEN',
  NOT_FOUND = 'NOT_FOUND',
  VALIDATION = 'VALIDATION',
  SERVER = 'SERVER',
  UNKNOWN = 'UNKNOWN',
}

// 错误配置
export interface ErrorConfig {
  type: ApiErrorType
  message: string
  title?: string
  duration?: number
  showNotification?: boolean
  redirectToLogin?: boolean
}

// 获取错误类型
export function getErrorType(error: any): ApiErrorType {
  if (!error.response) {
    return ApiErrorType.NETWORK
  }

  switch (error.response.status) {
    case 401:
      return ApiErrorType.UNAUTHORIZED
    case 403:
      return ApiErrorType.FORBIDDEN
    case 404:
      return ApiErrorType.NOT_FOUND
    case 422:
      return ApiErrorType.VALIDATION
    case 500:
    case 502:
    case 503:
      return ApiErrorType.SERVER
    default:
      return ApiErrorType.UNKNOWN
  }
}

// 获取错误消息
export function getErrorMessage(error: any): string {
  // 优先使用后端返回的 detail
  if (error.response?.data?.detail) {
    const detail = error.response.data.detail
    // 如果是数组，取第一个元素的消息
    if (Array.isArray(detail)) {
      return detail.map((d: any) => d.msg || d.message || String(d)).join(', ')
    }
    return String(detail)
  }

  // 其次使用 message
  if (error.response?.data?.message) {
    return String(error.response.data.message)
  }

  // 使用 error.message
  if (error.message) {
    return error.message
  }

  // 根据状态码返回默认消息
  switch (error.response?.status) {
    case 401:
      return '登录已过期，请重新登录'
    case 403:
      return '您没有权限执行此操作'
    case 404:
      return '请求的资源不存在'
    case 422:
      return '数据验证失败，请检查输入'
    case 500:
      return '服务器内部错误'
    case 502:
      return '网关错误'
    case 503:
      return '服务暂时不可用'
    default:
      return '请求失败，请稍后重试'
  }
}

// 处理 API 错误
export function handleApiError(error: any, customMessage?: string): void {
  const type = getErrorType(error)
  const message = customMessage || getErrorMessage(error)

  switch (type) {
    case ApiErrorType.UNAUTHORIZED:
      if (AUTH_DISABLED) {
        ElMessage.warning({
          message: '当前为临时管理员模式，后端登录校验暂未启用',
          duration: 3000,
        })
        break
      }
      // 401 错误：清除本地存储并跳转登录
      localStorage.removeItem('token')
      localStorage.removeItem('userInfo')
      ElMessage.error({
        message: '登录已过期，请重新登录',
        duration: 3000,
        onClose: () => {
          router.push('/login')
        },
      })
      break

    case ApiErrorType.FORBIDDEN:
      if (AUTH_DISABLED) {
        ElMessage.info({
          message: '验收模式已跳过权限校验',
          duration: 2200,
        })
        break
      }
      // 403 错误：显示权限不足提示
      ElMessage.warning({
        message: message || '您没有权限执行此操作',
        duration: 3000,
      })
      break

    case ApiErrorType.NETWORK:
      // 网络错误
      ElNotification.error({
        title: '网络错误',
        message: '网络连接失败，请检查您的网络',
        duration: 5000,
      })
      break

    case ApiErrorType.VALIDATION:
      // 验证错误
      ElMessage.warning({
        message: message,
        duration: 5000,
      })
      break

    case ApiErrorType.NOT_FOUND:
      // 404 错误
      ElMessage.warning({
        message: '请求的资源不存在',
        duration: 3000,
      })
      break

    case ApiErrorType.SERVER:
      // 服务器错误
      ElNotification.error({
        title: '服务器错误',
        message: message || '服务器处理失败，请稍后重试',
        duration: 5000,
      })
      break

    default:
      // 其他错误
      ElMessage.error({
        message: message,
        duration: 3000,
      })
  }

  // 在控制台输出完整错误信息
  console.error('API Error:', {
    type,
    message,
    error,
  })
}

// 显示成功消息
export function showSuccess(message: string, duration = 3000): void {
  ElMessage.success({
    message,
    duration,
  })
}

// 显示警告消息
export function showWarning(message: string, duration = 3000): void {
  ElMessage.warning({
    message,
    duration,
  })
}

// 显示确认对话框
export function showConfirm(
  message: string,
  title = '确认'
): Promise<'confirm' | 'cancel' | 'close'> {
  return new Promise((resolve) => {
    ElMessageBox.confirm(message, title, {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning',
    })
      .then(() => {
        resolve('confirm')
      })
      .catch((action) => {
        resolve(action === 'close' ? 'close' : 'cancel')
      })
  })
}

// 导出请求方法（带统一错误处理）
export async function apiRequest<T>(
  request: () => Promise<T>,
  options?: {
    successMessage?: string
    errorMessage?: string
    showSuccess?: boolean
    showError?: boolean
  }
): Promise<T | null> {
  try {
    const result = await request()

    if (options?.showSuccess !== false && options?.successMessage) {
      showSuccess(options.successMessage)
    }

    return result
  } catch (error: any) {
    if (options?.showError !== false) {
      handleApiError(error, options?.errorMessage)
    }
    return null
  }
}

export default {
  ApiErrorType,
  getErrorType,
  getErrorMessage,
  handleApiError,
  showSuccess,
  showWarning,
  showConfirm,
  apiRequest,
}
