import { request } from './request'

export const listParts = (params = {}) => request('parts.list', { params })
