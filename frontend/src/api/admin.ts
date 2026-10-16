import { callApi } from './client'

export const adminApi = {
  contextInfo: <T = unknown>() => callApi<T>('admin.contextInfo'),
  departments: <T = unknown>() => callApi<T>('admin.departments'),
  switchContext: <T = unknown>(department: string) => callApi<T>('admin.switchContext', { data: { department } }),
  switchBack: <T = unknown>() => callApi<T>('admin.switchBack'),
}

