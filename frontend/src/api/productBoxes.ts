import { callApi } from './client'
import type {
  BindProductBox, GeneratedQrBatch, GenerateQrBatch, PoolFilter, PoolPage, ProductBoxScan,
  ProductBox, ProductBoxMetadata, ProductQrContext,
  QrCapabilities, QrCapabilitiesPage, QrId, QrPrintConfirmation, QrPrintConfirmationRequest,
  QrPrintDataRequest, QrPrintJob, QrReprintRequest, UpdateQrCapabilities,
} from '@/types/productBox'

export const productBoxesApi = {
  listPool: (params: PoolFilter = {}) => callApi<PoolPage>('productQrPool.list', { params: { ...params } }),
  generateBatch: (data: GenerateQrBatch) => callApi<GeneratedQrBatch>('productQrPool.generateBatch', { data }),
  printData: (data: QrPrintDataRequest) => callApi<QrPrintJob>('productQrPool.printData', { data }),
  confirmPrint: (data: QrPrintConfirmationRequest) =>
    callApi<QrPrintConfirmation>('productQrPool.confirmPrint', { data }),
  reprint: (id: QrId, data: QrReprintRequest) =>
    callApi<QrPrintJob>('productQrPool.reprint', { pathParams: { item_id: id }, data }),
  bind: (data: BindProductBox) => callApi<ProductBoxScan>('productBoxes.bind', { data }),
  scan: (qr_payload: string, split_parent_id?: QrId) => callApi<ProductBoxScan>('productBoxes.scan', { data: { qr_payload, ...(split_parent_id ? {split_parent_id} : {}) } }),
  qrContext: (orderId: number) => callApi<ProductQrContext>('production.qrContext', { pathParams: { order_id: orderId } }),
  updateMetadata: (boxId: QrId, data: ProductBoxMetadata) =>
    callApi<ProductBox>('productBoxes.metadata', { pathParams: { box_id: boxId }, data }),
  capabilities: (params: { user_id?: number; page?: number; page_size?: number } = {}) =>
    callApi<QrCapabilitiesPage>('qrAdmin.capabilities', { params }),
  saveCapabilities: (userId: number, data: UpdateQrCapabilities) =>
    callApi<QrCapabilities>('qrAdmin.saveCapabilities', { pathParams: { user_id: userId }, data }),
}
