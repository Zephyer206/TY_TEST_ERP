import axios from 'axios'
import { getApiDefinition } from './registry'

const client = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '/api/v1',
  timeout: 20000,
  headers: { 'Content-Type': 'application/json' },
})

const resolvePath = (template, pathParams = {}) => template.replace(/\{([^}]+)\}/g, (_, name) => {
  const value = pathParams[name]
  if (value === undefined || value === null || value === '') {
    throw new Error(`Missing API path parameter: ${name}`)
  }
  return encodeURIComponent(String(value))
})

const formatError = (error) => {
  const detail = error.response?.data?.detail
  return new Error(typeof detail === 'string' ? detail : error.message || '请求失败')
}

export const request = async (key, { pathParams, params, data } = {}) => {
  const definition = getApiDefinition(key)
  const token = localStorage.getItem('access_token')
  const response = await client.request({
    method: definition.method,
    url: resolvePath(definition.path, pathParams),
    params,
    data,
    headers: definition.auth && token ? { Authorization: `Bearer ${token}` } : undefined,
  }).catch((error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('access_token')
      localStorage.removeItem('refresh_token')
      window.dispatchEvent(new CustomEvent('mobile-auth-expired'))
    }
    throw formatError(error)
  })

  return response.data
}
