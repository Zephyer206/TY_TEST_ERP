import { callApi, type ApiParams } from './client'

export const customersApi = {
  list: <T = unknown>(params: ApiParams = {}) => callApi<T>('customers.list', { params }),
  create: <T = unknown>(payload: unknown) => callApi<T>('customers.create', { data: payload }),
  update: <T = unknown>(id: number | string, payload: unknown) => callApi<T>('customers.update', { pathParams: { customer_id: id }, data: payload }),
  remove: <T = unknown>(id: number | string) => callApi<T>('customers.delete', { pathParams: { customer_id: id } }),
}
