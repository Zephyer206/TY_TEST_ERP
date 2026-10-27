import { callApi } from './client'
import { qrApi } from './qr'
import type {
  BatchConsumeRequest, BatchScrapRequest, BatchSplitRequest, BatchTraceResponse,
  IqcUpdate, LegacyPagination, MaterialBatchChildScanResponse, MaterialBatchCreate,
  MaterialBatchDetailResponse, MaterialBatchListParams, MaterialBatchResponse,
  MaterialBatchScanResponse, MaterialResponse, QrScanLogCreate, QrScanLogResponse,
  ScanType, SupplierResponse,
} from '@/types/legacyQr'

/** Existing warehouse QR endpoints; all paths and transport stay in the shared API layer. */
export const materialQrApi = {
  listMaterials: (params: LegacyPagination & { grade?: string; include_inactive?: boolean } = {}) =>
    callApi<MaterialResponse[]>('warehouse.qrMaterials', { params: { ...params } }),
  listSuppliers: (params: LegacyPagination & { is_active?: boolean } = {}) =>
    callApi<SupplierResponse[]>('warehouse.qrSuppliers', { params: { ...params } }),
  listBatches: (params: MaterialBatchListParams = {}) =>
    callApi<MaterialBatchResponse[]>('materialQr.list', { params: { ...params } }),
  getBatch: (batchId: number) =>
    callApi<MaterialBatchDetailResponse>('materialQr.detail', { pathParams: { batch_id: batchId } }),
  getBatchByNo: (batchNo: string) =>
    callApi<MaterialBatchDetailResponse>('materialQr.byNo', { pathParams: { batch_no: batchNo } }),
  createInbound: (data: MaterialBatchCreate) =>
    callApi<MaterialBatchResponse>('materialQr.create', { data }),
  updateIqc: (batchId: number, data: IqcUpdate) =>
    callApi<MaterialBatchResponse>('materialQr.iqc', { pathParams: { batch_id: batchId }, data }),
  split: (batchId: number, data: BatchSplitRequest) =>
    callApi<MaterialBatchScanResponse[]>('materialQr.split', { pathParams: { batch_id: batchId }, data }),
  consume: (batchId: number, data: BatchConsumeRequest) =>
    callApi<MaterialBatchResponse>('materialQr.consume', { pathParams: { batch_id: batchId }, data }),
  scrap: (batchId: number, data: BatchScrapRequest) =>
    callApi<MaterialBatchResponse>('materialQr.scrap', { pathParams: { batch_id: batchId }, data }),
  getTraceability: (batchId: number) =>
    callApi<BatchTraceResponse>('materialQr.trace', { pathParams: { batch_id: batchId } }),
  scanQr: (batchId: number) =>
    callApi<MaterialBatchScanResponse>('materialQr.scan', { pathParams: { batch_id: batchId } }),
  scanChild: (childId: number) =>
    callApi<MaterialBatchChildScanResponse>('materialQr.childScan', { pathParams: { child_id: childId } }),
  listChildren: (batchId: number) =>
    callApi<MaterialBatchScanResponse[]>('materialQr.children', { pathParams: { batch_id: batchId } }),
  createScanLog: (data: QrScanLogCreate) =>
    callApi<QrScanLogResponse>('qrScans.create', { data }),
  listScanLogs: (entityType: ScanType, entityId: number, params: LegacyPagination = {}) =>
    callApi<QrScanLogResponse[]>('qrScans.list', { pathParams: { entity_type: entityType, entity_id: entityId }, params: { ...params } }),
  reprintQr: (batchId: number) =>
    callApi<MaterialBatchScanResponse>('materialQr.reprint', { pathParams: { batch_id: batchId } }),
  lookup: qrApi.lookup,
}
