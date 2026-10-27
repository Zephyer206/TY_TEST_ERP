import { callApi, type ApiParams } from './client'
import type { MachineQrResponse, MachineRepairScanParams, MachineResponse, MachineScanResponse } from '@/types/legacyQr'

export interface PressTypeOption {
  key: string
  label: string
  tonnage: number
  is_dual_axis: boolean
  machine_count: number
}

export const machinesApi = {
  pressTypes: () => callApi<PressTypeOption[]>('machines.pressTypes'),
  list: <T = unknown>(params: ApiParams = {}) => callApi<T>('machines.list', { params }),
  detail: <T = unknown>(id: number | string) => callApi<T>('machines.detail', { pathParams: { machine_id: id } }),
  update: <T = unknown>(id: number | string, payload: unknown) =>
    callApi<T>('machines.update', { pathParams: { machine_id: id }, data: payload }),
  /** Existing fault/repair scan workflow; this does not complete a production order. */
  repairScan: (machineId: number, params: MachineRepairScanParams) =>
    callApi<MachineResponse>('machines.repairScan', { pathParams: { machine_id: machineId }, config: { params } }),
  generateQr: (machineId: number) =>
    callApi<MachineQrResponse>('machines.generateQr', { pathParams: { machine_id: machineId } }),
  scanQr: (machineId: number) =>
    callApi<MachineScanResponse>('machines.scanQr', { pathParams: { machine_id: machineId } }),
}
