import { callApi, type ApiParams } from './client'

export const packagingApi = {
  inventory: <T = unknown>(params: ApiParams = {}) => callApi<T>('packaging.inventory', { params }),
  records: <T = unknown>(params: ApiParams = {}) => callApi<T>('packaging.records', { params }),
  scan: <T = unknown>(payload: unknown) => callApi<T>('packaging.scan', { data: payload }),
  inspect: <T = unknown>(id: number | string, payload: unknown) => callApi<T>('packaging.inspect', { pathParams: { record_id: id }, data: payload }),
}
