import { request } from './request'

export const listCustomers = (params = {}) => request('customers.list', { params })
