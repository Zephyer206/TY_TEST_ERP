import { callApi, type ApiParams } from './client'

export const machinesApi = {
  list: <T = unknown>(params: ApiParams = {}) => callApi<T>('machines.list', { params }),
  detail: <T = unknown>(id: number | string) => callApi<T>('machines.detail', { pathParams: { machine_id: id } }),
  update: <T = unknown>(id: number | string, payload: unknown) =>
    callApi<T>('machines.update', { pathParams: { machine_id: id }, data: payload }),
}
