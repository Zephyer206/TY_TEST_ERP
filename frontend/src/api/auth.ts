import { callApi } from './client'

export const authApi = {
  login: <T = unknown>(payload: unknown) => callApi<T>('auth.login', { data: payload }),
}

