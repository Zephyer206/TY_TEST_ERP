import type {QrId} from './productBox'
export interface CoilSpec {material_name:string|null;thickness:string|null;width:string|null}
export type CoilResolution='accept_continue'|'pause'|'reconfirm_coil'
export interface CoilException {
  id:QrId;state_id:QrId;order_id:number;plan_no:string;product_name:string|null;process_code:string
  product_box_id:QrId|null;material_batch_id:number;batch_no:string|null;expected_spec:CoilSpec;actual_spec:CoilSpec
  status:'pending_confirmation'|'confirmed';resolution:CoilResolution|null;remark:string|null;version:number
  spec_incomplete:boolean
  created_by:number;created_at:string;confirmed_by:number|null;confirmed_at:string|null;released_by:number|null;released_at:string|null
  resume_reason:string|null;rechecked_material_batch_id:number|null;blocked:boolean;allowed_actions:Array<'confirm'|'resume'>
  recipient_groups:Array<{group_type:'supervisor'|'business_owner';resolution_status:'pending_configuration'|'resolved';recipient_ids:number[];missing_reason:string|null}>
  delivery_summary:{pending:number;sent:number;failed:number}
}
export interface CoilCheckRequest {context_id:QrId;material_batch_id:number;product_box_id?:QrId;continue_production:boolean;idempotency_key:string}
export interface CoilCheckResult {matches:boolean;requires_confirmation:boolean;production_allowed:boolean;expected_spec:CoilSpec;actual_spec:CoilSpec;exception:CoilException|null;state_version:number}
export type DeliveryStatus='pending'|'sent'|'failed'
export interface NotificationAttempt {retry_batch:number;attempt_no:number;trigger_type:'automatic'|'manual';result:'sent'|'failed';safe_error_code:string|null;created_at:string}
export interface NotificationDelivery {
  id:QrId;recipient_user_id:number;delivery_status:DeliveryStatus;attempts:number;retry_batch:number;version:number
  next_retry_at:string;last_error:string|null;sent_at:string|null;created_at:string;notification_id:QrId|null;read_at:string|null
  exception:CoilException;attempt_history:NotificationAttempt[]
}
export interface NotificationPage {items:NotificationDelivery[];total:number;page:number;page_size:number;can_manage_deliveries:boolean}
export interface NotificationFilter {delivery_status?:DeliveryStatus;unread_only?:boolean;page?:number;page_size?:number}
