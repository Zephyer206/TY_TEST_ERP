import type {ProductBox, QrId} from './productBox'
import type {ProcessQuantity} from './productProduction'

export interface FlowEvent {
  id: QrId; event_type: string; process_code: string | null; state_id: QrId | null
  operator_id: number; operator_name: string | null; machine_id: number | null; machine_no: string | null
  material_batch_id: number | null; before_qty: number; after_qty: number
  before_snapshot: Record<string, unknown>; after_snapshot: Record<string, unknown>
  remark: string | null; occurred_at: string
}
export interface EventPage {items: FlowEvent[]; next_cursor: QrId | null; total: number}
export interface TraceQuantity extends ProcessQuantity {process_code: string; machine_id: number; machine_no: string; operator_name: string | null}
export interface TraceMaterial {
  id: number; batch_no: string; parent_batch_id: number | null; qr_code: string | null
  current_weight: number | null; thickness: number | null; width: number | null
  status: string | null; iqc_result: string | null; material_name: string | null; grade: string | null; depth: number
}
export interface TraceRelation {
  id: QrId; relation_type: string; parent_box_id: QrId; child_box_id: QrId
  source_order_id: number; target_order_id: number; quantity: number; order_qty: number; stock_qty: number; created_by: number; created_at: string
  source_snapshot: Record<string, unknown>; parent_box_no: string | null; child_box_no: string | null
  parent_current_qty: number | null; child_current_qty: number | null
}
export interface TraceException {id: QrId; status: string; resolution: string | null; material_batch_id: number; created_by: number; confirmed_by: number | null; remark: string | null; created_at: string}
export interface TraceConversion {id: QrId; source_product_code: string; target_product_code: string; confirmation_status: string; actual_qty: number | null; created_by: number; confirmed_by: number | null; remark: string | null; created_at: string}
export interface BoxTrace {
  box: ProductBox; order: {id: number; plan_no: string; business_owner_id: number | null}
  route: {route_code: string; revision: number; steps: Array<{code: string; name?: string | null}>; first_output_process_code: string}
  quantities: TraceQuantity[]; quantities_total: number; materials: TraceMaterial[]
  missing_material_source: boolean; material_lineage_incomplete: boolean; latest_event: FlowEvent | null; events: EventPage
  relations: TraceRelation[]; relations_total: number; exceptions: TraceException[]; exceptions_total: number
  conversions: TraceConversion[]; conversions_total: number; page: number; page_size: number
  split: SplitInfo | null
}

export interface SplitTarget {order_product_id: QrId; state_id: QrId; state_version: number; order_id: number; plan_no: string; product_name: string | null; customer_part_no: string | null; process_code: string; machine_no: string; remaining_qty: number}
export interface SplitInfo {allowed_actions: Array<'split'|'cross_order_split'>; reason: string | null; available_qty: number; order_qty: number; stock_qty: number; allocation_version: number | null; targets: SplitTarget[]; targets_total: number; page: number; page_size: number}
