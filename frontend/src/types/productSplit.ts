import type {ProductBox, QrId} from './productBox'
import type {OutputAllocation} from './productProduction'
import type {TraceRelation} from './productTrace'
export interface SplitRequest {child_qr_payload:string;quantity:number;order_qty:number;stock_qty:number;expected_version:number;allocation_version:number;target_order_product_id?:QrId;target_state_id?:QrId;target_state_version?:number;idempotency_key:string}
export interface SplitResult {parent:ProductBox;child:ProductBox;relation:TraceRelation;parent_allocation:OutputAllocation;child_allocation:OutputAllocation}
