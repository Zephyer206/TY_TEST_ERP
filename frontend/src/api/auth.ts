import { callApi } from './client'

export const authApi = {
  current: () => callApi<{id:number; username:string; real_name:string|null; dept:string; role_level:number; position:string|null; is_tech:boolean; created_at:string}>('auth.me'),
  login: <T = unknown>(payload: unknown) => callApi<T>('auth.login', { data: payload }),
}

