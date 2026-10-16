import { callApi, type ApiParams } from './client'

export const partNamesApi = {
  list: <T = unknown>(params: ApiParams = {}) => callApi<T>('partNames.list', { params }),
  create: <T = unknown>(payload: unknown) => callApi<T>('partNames.create', { data: payload }),
  update: <T = unknown>(id: number | string, payload: unknown) => callApi<T>('partNames.update', { pathParams: { item_id: id }, data: payload }),
  remove: <T = unknown>(id: number | string) => callApi<T>('partNames.delete', { pathParams: { item_id: id } }),
}

export const materialsApi = {
  list: <T = unknown>(params: ApiParams = {}) => callApi<T>('materials.list', { params }),
  create: <T = unknown>(payload: unknown) => callApi<T>('materials.create', { data: payload }),
  update: <T = unknown>(id: number | string, payload: unknown) => callApi<T>('materials.update', { pathParams: { item_id: id }, data: payload }),
  remove: <T = unknown>(id: number | string) => callApi<T>('materials.delete', { pathParams: { item_id: id } }),
}

export const machineTonnagesApi = {
  list: <T = unknown>(params: ApiParams = {}) => callApi<T>('machineTonnages.list', { params }),
  create: <T = unknown>(payload: unknown) => callApi<T>('machineTonnages.create', { data: payload }),
  update: <T = unknown>(id: number | string, payload: unknown) => callApi<T>('machineTonnages.update', { pathParams: { item_id: id }, data: payload }),
  remove: <T = unknown>(id: number | string) => callApi<T>('machineTonnages.delete', { pathParams: { item_id: id } }),
}

export const moldTypesApi = {
  list: <T = unknown>(params: ApiParams = {}) => callApi<T>('moldTypes.list', { params }),
  create: <T = unknown>(payload: unknown) => callApi<T>('moldTypes.create', { data: payload }),
  update: <T = unknown>(id: number | string, payload: unknown) => callApi<T>('moldTypes.update', { pathParams: { item_id: id }, data: payload }),
  remove: <T = unknown>(id: number | string) => callApi<T>('moldTypes.delete', { pathParams: { item_id: id } }),
}
