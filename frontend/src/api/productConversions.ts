import {callApi} from './client'
import type {QrId} from '@/types/productBox'
import type {ConversionRecord,ConversionResult} from '@/types/productConversion'
export const productConversionsApi={
  create:(data:{box_id:QrId;target_order_product_id:QrId;proposed_qty?:number;expected_version:number;idempotency_key:string})=>callApi<ConversionRecord>('productConversions.create',{data}),
  confirm:(id:QrId,data:{context_id:QrId;actual_qty:number;confirm:true;child_qr_payload?:string;expected_version:number;conversion_version:number;idempotency_key:string})=>callApi<ConversionResult>('productConversions.confirm',{pathParams:{conversion_id:id},data}),
  cancel:(id:QrId,data:{context_id?:QrId;conversion_version:number;reason?:string;idempotency_key:string})=>callApi<ConversionRecord>('productConversions.cancel',{pathParams:{conversion_id:id},data}),
}
