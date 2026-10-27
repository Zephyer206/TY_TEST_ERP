import { callApi } from './client'
import type {
  QrGenerateRequest, QrGenerateResponse, QrLookupParams, QrLookupResponse,
  QrMachineResponse, QrMaterialResponse, QrPartResponse, QrProcessFlowResponse,
} from '@/types/legacyQr'

export const qrApi = {
  lookup: (params: QrLookupParams) => callApi<QrLookupResponse>('qr.lookup', { params: { ...params } }),
  generate: (data: QrGenerateRequest) => callApi<QrGenerateResponse>('qr.generate', { data }),
  material: (batchId: number) => callApi<QrMaterialResponse>('qr.material', { pathParams: { batch_id: batchId } }),
  machine: (machineId: number) => callApi<QrMachineResponse>('qr.machine', { pathParams: { machine_id: machineId } }),
  processFlow: (cardId: number) => callApi<QrProcessFlowResponse>('qr.processFlow', { pathParams: { card_id: cardId } }),
  part: (partId: number) => callApi<QrPartResponse>('qr.part', { pathParams: { part_id: partId } }),
}
