import { callApi } from './client'
import type { ProductQrContext, QrId } from '@/types/productBox'
import type { MachineScan, OutputAllocation, ProductionQuantityResult, ProductionSelection, SaveOrderQrConfiguration } from '@/types/productProduction'

export const productProductionApi = {
  scanMachine: (data: {machine_qr: string; context_id?: QrId}) => callApi<MachineScan>('machines.scanProduction', {data}),
  select: (data: {scan_ticket: string; assignment_id: number; order_product_id: QrId; process_code: string; state_id?: QrId; idempotency_key: string}) =>
    callApi<ProductionSelection>('machines.selectProduction', {data}),
  saveQuantity: (boxId: QrId, data: {context_id: QrId; current_qty: number; expected_version: number; state_version: number; idempotency_key: string; material_batch_id?: number}) =>
    callApi<ProductionQuantityResult>('productBoxes.saveQuantity', {pathParams: {box_id: boxId}, data}),
  complete: (machineId: number, data: {context_id: QrId; confirm_quantity_difference: boolean; expected_version: number; idempotency_key: string}) =>
    callApi<ProductionSelection>('machines.productionComplete', {pathParams: {machine_id: machineId}, data}),
  correct: (boxId: QrId, data: {state_id: QrId; current_qty: number; reason: string; expected_version: number; state_version: number; idempotency_key: string}) =>
    callApi<ProductionQuantityResult>('productBoxes.correctQuantity', {pathParams: {box_id: boxId}, data}),
  allocate: (data: {source_quantity_id: QrId; order_qty: number; stock_qty: number; expected_version: number; idempotency_key: string}) =>
    callApi<OutputAllocation>('production.allocateOutput', {data}),
  saveConfiguration: (orderId: number, data: SaveOrderQrConfiguration) =>
    callApi<ProductQrContext>('production.saveQrContext', {pathParams: {order_id: orderId}, data}),
}
