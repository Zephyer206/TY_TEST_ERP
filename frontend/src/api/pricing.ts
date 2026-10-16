import { callApi, type ApiParams } from './client'

export const customerPricesApi = {
  yearPrices: <T = unknown>(customerId: number | string) => callApi<T>('customerPrices.yearPrices', { pathParams: { customer_id: customerId } }),
  priceHistory: <T = unknown>(customerId: number | string, partId: number | string) => callApi<T>('customerPrices.priceHistory', { pathParams: { customer_id: customerId, part_id: partId } }),
}

export const priceAdjustmentsApi = {
  list: <T = unknown>(params: ApiParams = {}) => callApi<T>('priceAdjustments.list', { params }),
  create: <T = unknown>(payload: unknown) => callApi<T>('priceAdjustments.create', { data: payload }),
  approve: <T = unknown>(id: number | string, payload: unknown) => callApi<T>('priceAdjustments.approve', { pathParams: { adjustment_id: id }, data: payload }),
}

export const treatmentsApi = {
  list: <T = unknown>() => callApi<T>('treatments.list'),
  create: <T = unknown>(payload: unknown) => callApi<T>('treatments.create', { data: payload }),
  update: <T = unknown>(id: number | string, payload: unknown) => callApi<T>('treatments.update', { pathParams: { treatment_id: id }, data: payload }),
}
