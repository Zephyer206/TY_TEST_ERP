import { request } from './request'

export const listInventory = (params = {}) => request('packaging.inventory', { params })
export const listPackagingRecords = (params = {}) => request('packaging.records', { params })
