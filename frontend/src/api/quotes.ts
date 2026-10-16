import { callApi, type ApiParams } from './client'

export const quotesApi = {
  list: <T = unknown>(params: ApiParams = {}) => callApi<T>('quotes.list', { params }),
  detail: <T = unknown>(id: number | string) => callApi<T>('quotes.detail', { pathParams: { quote_id: id } }),
  create: <T = unknown>(payload: unknown) => callApi<T>('quotes.create', { data: payload }),
  pricing: <T = unknown>(id: number | string, payload: unknown) => callApi<T>('quotes.pricing', { pathParams: { quote_id: id }, data: payload }),
  submitReview: <T = unknown>(id: number | string) => callApi<T>('quotes.submitReview', { pathParams: { quote_id: id } }),
  submitBoss: <T = unknown>(id: number | string) => callApi<T>('quotes.submitBoss', { pathParams: { quote_id: id } }),
  bossApprove: <T = unknown>(id: number | string, payload: unknown) => callApi<T>('quotes.bossApprove', { pathParams: { quote_id: id }, data: payload }),
  fix: <T = unknown>(id: number | string, payload: unknown) => callApi<T>('quotes.fix', { pathParams: { quote_id: id }, data: payload }),
  revokeNomination: <T = unknown>(id: number | string, payload: unknown) => callApi<T>('quotes.revokeNomination', { pathParams: { quote_id: id }, data: payload }),
}
