/** New bigint identities are decimal strings; legacy ERP identities stay numbers. */
export type QrId = string
export type QrCapability = 'qr.trace' | 'qr.production' | 'qr.split' | 'qr.print' | 'qr.bind'
  | 'qr.supervise' | 'qr.generate' | 'qr.metadata' | 'qr.configure' | 'qr.admin'

export interface ProductQrPoolItem {
  id: QrId
  public_code: string
  qr_payload: string
  payload_version: 'v1'
  pool_status: 'unused' | 'bound' | 'void'
  print_batch_no: string | null
  print_count: number
  printed_at: string | null
  created_at: string
  bound_box_id: QrId | null
}

export interface ProductBox {
  id: QrId
  qr_pool_item_id: QrId
  box_no: string
  order_id: number
  order_product_id: QrId
  part_id: number
  product_code: 'B' | 'C'
  product_name_snapshot: string
  customer_id: number | null
  customer_name_snapshot: string | null
  customer_part_no: string | null
  route_revision_id: QrId
  current_process_code: string | null
  next_process_code: string | null
  current_qty: number
  version: number
  lifecycle_status: 'active' | 'empty' | 'closed' | 'scrapped'
  bound_by: number
  bound_at: string
  public_code: string
  qr_payload: string
}

export interface PoolPage {
  items: ProductQrPoolItem[]
  total: number
  page: number
  page_size: number
  actor: { id: number; dept: string; role_level: number }
  capabilities: QrCapability[]
  batch_limit: number
}

export interface PoolFilter {
  pool_status?: ProductQrPoolItem['pool_status']
  print_batch_no?: string
  page?: number
  page_size?: number
}

export interface GenerateQrBatch {
  count: number
  print_batch_no?: string
  idempotency_key: string
}

export interface GeneratedQrBatch {
  print_batch_no: string
  count: number
  items: ProductQrPoolItem[]
}

export interface BindProductBox {
  qr_payload: string
  order_product_id: QrId
  context_id?: QrId
  idempotency_key: string
}

export interface ProductBoxScan {
  pool_item: ProductQrPoolItem
  box: ProductBox | null
  allowed_actions: Array<'bind' | 'trace'>
  latest_event?: import('./productTrace').FlowEvent | null
  conversion?: import('./productConversion').ConversionOptions | null
}

export interface QrPrintTemplate {
  code: 'a4_3x7_v1'
  paper_width_mm: number
  paper_height_mm: number
  margin_mm: number
  columns: number
  rows: number
  label_width_mm: number
  label_height_mm: number
  gap_mm: number
  quiet_zone_modules: number
}

export interface QrPrintLabel extends ProductQrPoolItem {
  qr_image_base64: string
  box: ProductBox | null
}

export interface QrPrintJob {
  print_job_id: QrId
  template: QrPrintTemplate
  items: QrPrintLabel[]
}

export interface QrPrintDataRequest {
  item_ids: QrId[]
  template_code?: 'a4_3x7_v1'
  idempotency_key: string
}

export interface QrReprintRequest {
  template_code?: 'a4_3x7_v1'
  idempotency_key: string
}

export interface QrPrintConfirmationRequest {
  print_job_id: QrId
  confirmed_item_ids: QrId[]
  idempotency_key: string
}

export interface QrPrintConfirmation {
  print_job_id: QrId
  items: ProductQrPoolItem[]
}

export interface QrCapabilities {
  user_id: number
  version: number
  capabilities: QrCapability[]
}

export interface QrCapabilitiesItem extends QrCapabilities {
  dept: string
  role_level: 1 | 2 | 3 | 4
}

export interface QrCapabilitiesPage {
  items: QrCapabilitiesItem[]
  page: number
  page_size: number
}

export interface UpdateQrCapabilities {
  capabilities: QrCapability[]
  expected_version: number
  idempotency_key: string
}

export interface QrDomainError {
  code: string
  message: string
  details?: { current_version?: number; maximum?: number; missing_configuration?: string[] }
}

export interface ProductBoxMetadata {
  customer_name_snapshot?: string | null
  customer_part_no?: string | null
  next_process_code?: string | null
  expected_version: number
  idempotency_key: string
}

export interface ProductQrContext {
  order_id: number
  part_id: number | null
  paired_part_id: number | null
  is_left_right_pair: boolean
  status: string | null
  total_qty: number | null
  business_owner_id: number | null
  version: number
  missing_configuration: string[]
  products: Array<{
    id: QrId; part_id: number; product_code: 'B' | 'C'; target_qty: number
    route_revision_id: QrId; binding_allowed: boolean; conversion_source_id: QrId | null
    version: number; part_name: string | null; customer_part_no: string | null
    route: { id: QrId; route_code: string; revision: number; product_code: 'B' | 'C'
      steps: Array<{ code: string; name?: string; machine_ids?: number[]; machine_types?: string[] }>
      first_output_process_code: string; is_published: boolean } | null
    machine_process_targets: Array<{ state_id: QrId; assignment_id: number; machine_id: number
      process_code: string; target_qty: number; production_status: string; version: number; is_active: boolean }>
    missing_configuration: string[]; can_bind: boolean
  }>
}
