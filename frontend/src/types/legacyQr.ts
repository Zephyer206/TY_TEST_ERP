/** Existing MAT/MCN/PFC/lookup HTTP contracts. IDs remain legacy integer IDs. */
export type BatchStatus = 'pending_iqc' | 'available' | 'in_use' | 'partial' | 'exhausted' | 'rejected' | 'scrapped'
export type IqcResult = 'passed' | 'failed'
export type ScanType = 'MAT' | 'MCN' | 'PFC' | 'PRT' | 'PFB'
export type ScanOperation = 'query' | 'split' | 'consume' | 'report' | 'inbound' | 'bind' | 'qty_save' | 'complete' | 'conversion' | 'exception'
export type MachineState = 'idle' | 'running' | 'fault' | 'pending_check' | 'repairing' | 'offline'
export type SessionStatus = 'pending' | 'active' | 'closed' | 'cancelled'
export type ProcessFlowStatus = 'pending' | 'in_progress' | 'completed' | 'cancelled'
export interface LegacyPagination { skip?: number; limit?: number }
export interface MaterialResponse {
  id: number
  material_no: string
  name: string
  grade: string
  thickness: number | null
  width: number | null
  weight_per_unit: number | null
  unit: string
  supplier_id: number | null
  supplier_name: string | null
  is_active: boolean
  created_at: string
}
export interface SupplierResponse {
  id: number
  supplier_no: string
  name: string
  contact_person: string | null
  contact_phone: string | null
  address: string | null
  notes: string | null
  is_active: boolean
  created_at: string
}
export interface ProductionPlanListParams extends LegacyPagination { status?: string; part_id?: number }
export interface ProductionPlanResponse {
  id: number
  plan_no: string
  part_id: number
  total_qty: number
  planned_start_date: string | null
  planned_end_date: string | null
  priority: number
  notes: string | null
  completed_qty: number
  status: string
  created_by: number | null
  created_at: string
  updated_at: string
}

export interface MaterialBatchCreate {
  material_id?: number | null
  supplier_id?: number | null
  thickness?: number | null
  width?: number | null
  length?: number | null
  gross_weight?: number | null
  po_no?: string | null
}
export interface IqcUpdate { result: IqcResult; notes?: string | null }
export interface BatchSplitRequest { splits: Array<{ width?: number | null; length?: number | null; weight: number }> }
export interface BatchConsumeRequest { weight: number; reference_type?: string | null; reference_id?: number | null; notes?: string | null }
export interface BatchScrapRequest { reason: string }
export interface MaterialBatchListParams extends LegacyPagination { status?: BatchStatus; material_id?: number }
export interface MaterialBatchResponse extends MaterialBatchCreate {
  id: number
  batch_no: string
  qr_code: string | null
  net_weight: number | null
  current_weight: number
  status: BatchStatus
  iqc_result: IqcResult | null
  iqc_time: string | null
  iqc_by: number | null
  iqc_notes: string | null
  parent_batch_id: number | null
  received_at: string | null
  created_at: string
}
/** Detail children also include legacy child-table rows; their IDs are not MaterialBatch IDs. */
export interface MaterialBatchChildResponse {
  id: number
  child_batch_no: string
  child_qr_code: string | null
  width: number | null
  length: number | null
  current_weight: number
  status: BatchStatus
  created_at: string
}
export interface MaterialBatchDetailResponse extends MaterialBatchResponse {
  material_name: string | null
  material_grade: string | null
  supplier_name: string | null
  children: MaterialBatchChildResponse[]
}
export interface BatchTransactionResponse {
  id: number
  batch_id: number
  batch_no: string
  transaction_type: string
  quantity_change: number
  weight_after: number
  reference_type: string | null
  reference_id: number | null
  operator_id: number | null
  notes: string | null
  created_at: string
}
export interface BatchTraceResponse { batch: MaterialBatchDetailResponse; transactions: BatchTransactionResponse[] }
export interface MaterialBatchScanResponse {
  id: number
  batch_no: string
  qr_code: string | null
  qr_image_base64: string | null
  material_id: number | null
  material_name: string | null
  material_grade: string | null
  supplier_name: string | null
  thickness: number | null
  width: number | null
  length: number | null
  gross_weight: number
  current_weight: number
  status: BatchStatus
  iqc_result: IqcResult | null
  iqc_time: string | null
  received_at: string | null
  created_at: string
  parent_batch_id: number | null
  parent_batch_no: string | null
}
export interface MaterialBatchChildScanResponse {
  child_batch: MaterialBatchScanResponse
  parent_batch: MaterialBatchScanResponse
  sibling_batches: MaterialBatchScanResponse[]
}
export interface QrScanLogCreate {
  scan_type: ScanType
  entity_id: number
  entity_no?: string | null
  operation: ScanOperation
  notes?: string | null
}
export interface QrScanLogResponse {
  id: number
  scan_type: ScanType
  entity_id: number
  entity_no: string | null
  operator_id: number | null
  operation: ScanOperation
  notes: string | null
  scanned_at: string
}
export interface ScanHistoryItem {
  id: number
  operation: ScanOperation
  operator_id: number | null
  notes: string | null
  scanned_at: string | null
}
export interface MachineRepairScanParams { scan_type: 'first' | 'second'; action?: 'complete' | 'dismount'; fault_reason?: string }
export interface MachineResponse {
  id: number
  machine_no: string
  name: string
  machine_type: string | null
  tonnage: number | null
  max_stroke: number | null
  bed_size: string | null
  state: MachineState
  current_tooling_id: number | null
  fault_time: string | null
  fault_reported_by: number | null
  fault_reason: string | null
  repair_start_time: string | null
  repairer_id: number | null
  location: string | null
  is_deleted: boolean
  created_at: string
  updated_at: string
}
export interface MachineQrResponse {
  machine_id: number
  machine_no: string
  name: string
  machine_type: string | null
  tonnage: number | null
  location: string | null
  state: string
  qr_content: string
  qr_image_base64: string
}
export interface MachineScanResponse extends MachineQrResponse {
  max_stroke: number | null
  bed_size: string | null
  current_tooling_id: number | null
  fault_time: string | null
  fault_reason: string | null
  repair_start_time: string | null
  repairer_id: number | null
  scan_history: ScanHistoryItem[]
}
export interface VerifyMaterialParams { machine_id: number; part_id: number; material_batch_id: number }
export interface MaterialMatchResult {
  is_match: boolean
  message: string
  tooling_id: number | null
  tooling_number: string | null
  expected_material: string | null
  actual_material: string | null
}
export interface SessionStartRequest extends VerifyMaterialParams { plan_id?: number | null; force_start?: boolean }
export interface ProductionSessionResponse {
  id: number
  session_no: string
  plan_id: number | null
  machine_id: number
  tooling_id: number | null
  part_id: number
  material_batch_id: number | null
  status: SessionStatus
  started_at: string | null
  closed_at: string | null
  total_strokes: number
  total_output: number
  good_qty: number
  reject_qty: number
  process_flow_id: number | null
  operator_id: number | null
  created_at: string
}
export interface ProcessFlowListParams extends LegacyPagination { part_id?: number; machine_id?: number; status?: ProcessFlowStatus }
export interface ProcessFlowCardResponse {
  id: number
  card_no: string
  session_id: number
  part_id: number
  part_no: string | null
  machine_id: number
  machine_no: string | null
  tooling_id: number | null
  tooling_number: string | null
  material_batch_no: string | null
  planned_qty: number
  actual_output: number
  good_qty: number
  reject_qty: number
  status: ProcessFlowStatus
  start_time: string | null
  end_time: string | null
  operator_id: number | null
  qr_code: string | null
  qr_image_base64: string | null
  inbound_time: string | null
  inbound_operator_id: number | null
  inbound_notes: string | null
  created_at: string
}
export interface ProcessFlowScanResponse {
  card_id: number
  card_no: string
  part_id: number
  part_name: string | null
  machine_id: number
  machine_no: string | null
  tooling_id: number | null
  tooling_number: string | null
  material_batch_no: string | null
  planned_qty: number
  actual_output: number
  good_qty: number
  reject_qty: number
  status: string
  start_time: string | null
  end_time: string | null
  operator_id: number | null
  qr_content: string
  qr_image_base64: string
  scan_history: ScanHistoryItem[]
}
export interface ProcessFlowReverseTraceResponse {
  card_id: number
  card_no: string
  status: string
  good_qty: number
  operator_id: number | null
  material_batch_no: string | null
  material_name: string | null
  supplier_name: string | null
  session_id: number | null
  scan_history: ScanHistoryItem[]
}
export interface ProcessFlowInboundRequest { notes?: string | null }
export interface ProcessFlowReprintResponse { card_id: number; card_no: string; qr_content: string; qr_image_base64: string }
export interface QrLookupParams { code: string; manual?: boolean; type?: string }
/** Lookup entity_data is intentionally an open dictionary in the backend contract. */
export interface QrLookupResponse { found: boolean; prefix: string | null; entity_id: number | null; entity_type: string | null; entity_data: Record<string, unknown> | null; error: string | null }
export interface QrGenerateRequest { prefix: string; entity_id: number; extra_data?: Record<string, string> | null }
export interface QrGenerateResponse { content: string; image_base64: string; url: string | null }
export interface QrMaterialResponse { batch_id: number; batch_no: string; qr_content: string; image_base64: string }
export interface QrMachineResponse { machine_id: number; machine_no: string; qr_content: string; image_base64: string }
export interface QrProcessFlowResponse { card_id: number; card_no: string; qr_content: string; image_base64: string }
export interface QrPartResponse { part_id: number; customer_part_no: string; qr_content: string; image_base64: string }
