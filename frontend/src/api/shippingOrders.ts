import { callApi, type ApiParams } from './client'

export const listShippingOrders = (params: ApiParams = {}) => callApi<any>('shippingOrders.list', { params })
export const createShippingOrder = (payload: unknown) => callApi<any>('shippingOrders.create', { data: payload })
export const updateShippingOrder = (id: number, payload: unknown) => callApi<any>('shippingOrders.update', { pathParams: { order_id: id }, data: payload })
export const submitShippingOrder = (id: number, payload: unknown) => callApi<any>('shippingOrders.submit', { pathParams: { order_id: id }, data: payload })
export const getShippingOrder = (id: number) => callApi<any>('shippingOrders.detail', { pathParams: { order_id: id } })
export const searchCustomerParts = (customerId: number, q: string) => callApi<any>('shippingOrders.customerParts', { params: { customer_id: customerId, q } })
export const confirmLabel = (lineId: number, payload: unknown = {}) => callApi<any>('shippingOrders.labelConfirm', { pathParams: { line_id: lineId }, data: payload })
export const cancelLine = (lineId: number, payload: unknown) => callApi<any>('shippingOrders.cancelLine', { pathParams: { line_id: lineId }, data: payload })
export const cancellationConsent = (lineId: number, payload: { consent: boolean }) => callApi<any>('shippingOrders.cancellationConsent', { pathParams: { line_id: lineId }, data: payload })
export const confirmShipment = (id: number, payload: unknown) => callApi<any>('shippingOrders.confirmShipment', { pathParams: { order_id: id }, data: payload })
export const getShippingHistory = (id: number) => callApi<any>('shippingOrders.history', { pathParams: { order_id: id } })
export const updateShipmentLogistics = (shipmentId: number, payload: unknown) => callApi<any>('shippingOrders.shipmentLogistics', { pathParams: { shipment_id: shipmentId }, data: payload })
