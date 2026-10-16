import type { AxiosRequestConfig, AxiosResponse } from 'axios'
import apiClient from '@/utils/request'
import { getApiDefinition } from './registry'

export type ApiParams = Record<string, unknown>

export interface ApiCallOptions {
  params?: ApiParams
  data?: unknown
  pathParams?: Record<string, string | number>
  config?: AxiosRequestConfig
}

export interface ApiRawCallOptions extends ApiCallOptions {
  allowErrorResponse?: boolean
}

function resolvePath(template: string, pathParams: Record<string, string | number> = {}): string {
  return template.replace(/\{([^}]+)\}/g, (_match, key: string) => {
    const value = pathParams[key]
    if (value === undefined || value === null || value === '') throw new Error(`Missing API path parameter: ${key}`)
    return encodeURIComponent(String(value))
  })
}

function makeRequestConfig(key: string, options: ApiCallOptions = {}): AxiosRequestConfig {
  const definition = getApiDefinition(key)
  if (definition.lifecycle === 'removed') throw new Error(`API endpoint has been removed: ${key}`)
  const url = resolvePath(definition.path, options.pathParams)
  const method = definition.method.toLowerCase() as AxiosRequestConfig['method']
  return {
    method,
    url,
    params: definition.method === 'GET' || definition.method === 'DELETE' ? options.params : undefined,
    data: definition.method === 'GET' || definition.method === 'DELETE' ? undefined : options.data,
    ...options.config,
  }
}

export async function callApi<T = unknown>(key: string, options: ApiCallOptions = {}): Promise<T> {
  const response = await apiClient.request<T>(makeRequestConfig(key, options))
  return response.data
}

/** Return the Axios response for flows that intentionally inspect 409/status. */
export async function callApiRaw<T = unknown>(key: string, options: ApiRawCallOptions = {}): Promise<AxiosResponse<T>> {
  const config = makeRequestConfig(key, options)
  if (options.allowErrorResponse) config.validateStatus = () => true
  return apiClient.request<T>(config)
}
