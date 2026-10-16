import { callApi, type ApiParams } from './client'

export const warehouseApi = {
  finishedGoods: <T = unknown>(params: ApiParams = {}) =>
    callApi<T>('warehouse.finishedGoods', { params }),
  finishedGoodsReview: <T = unknown>(params: ApiParams = {}) =>
    callApi<T>('warehouse.finishedGoodsReview', { params }),
  finishedGoodsLedger: <T = unknown>(inventoryId: number, params: ApiParams = {}) =>
    callApi<T>('warehouse.finishedGoodsLedger', { pathParams: { inventory_id: inventoryId }, params }),
  createFinishedGoodsLedgerEntry: <T = unknown>(inventoryId: number, payload: unknown) =>
    callApi<T>('warehouse.finishedGoodsLedgerEntry', { pathParams: { inventory_id: inventoryId }, data: payload }),
  reconcileFinishedGoodsLedger: <T = unknown>(inventoryId: number, payload: unknown) =>
    callApi<T>('warehouse.finishedGoodsLedgerReconcile', { pathParams: { inventory_id: inventoryId }, data: payload }),
  updateLocation: <T = unknown>(inventoryId: number, payload: unknown) =>
    callApi<T>('warehouse.finishedGoodsLocation', { pathParams: { inventory_id: inventoryId }, data: payload }),
  adjust: <T = unknown>(inventoryId: number, payload: unknown) =>
    callApi<T>('warehouse.finishedGoodsAdjust', { pathParams: { inventory_id: inventoryId }, data: payload }),
  resolveReview: <T = unknown>(rowId: number, payload: unknown) =>
    callApi<T>('warehouse.finishedGoodsReviewResolve', { pathParams: { row_id: rowId }, data: payload }),
}
