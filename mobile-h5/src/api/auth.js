import { request } from './request'

export const login = (credentials) => request('auth.login', { data: credentials })
export const getCurrentUser = () => request('auth.me')
export const logout = () => request('auth.logout')
