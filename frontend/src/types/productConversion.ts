import type {ProductBox,QrId} from './productBox'
import type {TraceRelation} from './productTrace'
export interface ConversionRecord {
  id:QrId;product_box_id:QrId;order_id:number;source_order_product_id:QrId;target_order_product_id:QrId
  source_product_code:string;target_product_code:string;source_process_code:string|null;target_process_code:string|null
  proposed_qty:number|null;actual_qty:number|null;trigger_type:string;confirmation_status:string;version:number
  created_by:number;created_at:string;confirmed_by:number|null;confirmed_at:string|null;cancelled_by:number|null
  cancelled_at:string|null;cancel_reason:string|null;relation_id:QrId|null;child_box_id:QrId|null;remark:string|null;can_cancel:boolean
}
export interface ConversionTarget {order_product_id:QrId;product_code:string;product_name:string|null;customer_part_no:string|null;target_process_code:string;route_code:string;route_revision:number}
export interface ConversionOptions {can_create:boolean;reason:string|null;targets:ConversionTarget[];pending:ConversionRecord[]}
export interface ConversionResult {conversion:ConversionRecord;source_box:ProductBox;converted_box:ProductBox;relation:TraceRelation|null}
