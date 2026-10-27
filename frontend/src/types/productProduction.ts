import type { ProductBox, QrCapability, QrId } from './productBox'

export interface ProductionContext {
  id: QrId; machine_id: number; state_id: QrId | null; order_id: number | null
  order_product_id: QrId | null; assignment_id: number | null; process_code: string | null
  expires_at: string; closed_at: string | null; completion_scan_at: string | null
}
export interface OutputAllocation {
  id: QrId; source_quantity_id: QrId; box_id: QrId; order_id: number; order_product_id: QrId
  available_qty: number; order_qty: number; stock_qty: number; remaining_order_qty_snapshot: number
  manually_adjusted: boolean; version: number; has_downstream: boolean; allowed_actions: Array<'allocate'>
  origin_allocation_id: QrId | null
}
export interface ProcessQuantity {
  id: QrId; state_id: QrId; box_id: QrId; current_qty: number; input_qty: number
  source_quantity_id: QrId | null; version: number; updated_by: number; updated_at: string
  material_batch_id: number | null
}
export interface ProductionBox extends ProcessQuantity {
  quantity_id: QrId; box_no: string; box_version: number; product_name: string
  customer_part_no: string | null; allocation: OutputAllocation | null
  can_correct: boolean; quantity_locked: boolean
}
export interface ProductionState {
  id: QrId; assignment_id: number; machine_id: number; machine_no: string; machine_name: string
  order_id: number; plan_no: string; part_id: number; part_name: string | null; customer_part_no: string | null
  order_product_id: QrId; product_code: 'B' | 'C'; route_revision_id: QrId; route_code: string; route_revision: number; process_code: string
  target_qty: number; current_qty: number; difference_qty: number
  production_status: 'pending' | 'in_progress' | 'completed'; version: number
  completed_at: string | null; completed_by: number | null; blocked: boolean
  allowed_actions: Array<'quantity' | 'complete' | 'bind' | 'correct'>; boxes: ProductionBox[]
}
export interface ProductionSelection { context: ProductionContext; state: ProductionState }
export interface MachineScan {
  machine: { id: number; machine_no: string; name: string }
  actor: { id: number; dept: string; role_level: number }; capabilities: QrCapability[]
  scan_ticket: string | null; context: ProductionContext | null; state: ProductionState | null
  assignments: ProductionState[]; completion_intent: boolean
}
export interface ProductionQuantityResult {
  context: ProductionContext | null; state: ProductionState; box: ProductBox
  quantity: ProcessQuantity; allocation: OutputAllocation | null
}
export interface RouteConfiguration {
  route_code: string; revision: number
  steps: Array<{code: string; name?: string; machine_ids?: number[]; machine_types?: string[]}>
  first_output_process_code: string
}
export interface SaveOrderQrConfiguration {
  business_owner_id: number; expected_version: number; idempotency_key: string
  products: Array<{key: string; id?: QrId; part_id: number; product_code: 'B' | 'C'; target_qty: number
    binding_allowed?: boolean; conversion_source_key?: string; route: RouteConfiguration
    pre_authorized_conversions?: Array<{target_key: string; difference_process_codes: string[]}>}>
  machine_process_targets: Array<{product_key: string; assignment_id: number; process_code: string; target_qty: number}>
}
