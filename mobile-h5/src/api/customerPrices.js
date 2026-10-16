import { request } from './request'

export const listCustomerYearPrices = (customerId) => request('customerPrices.yearPrices', {
  pathParams: { customer_id: customerId },
})
