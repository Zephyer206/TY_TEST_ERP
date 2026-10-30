import {callApi} from './client'
import type {QrId} from '@/types/productBox'
import type {CoilCheckRequest,CoilCheckResult,CoilException,CoilResolution,NotificationDelivery,NotificationFilter,NotificationPage} from '@/types/coilException'
export const coilExceptionsApi={
  check:(data:CoilCheckRequest)=>callApi<CoilCheckResult>('coilSpecExceptions.create',{data}),
  confirm:(id:QrId,data:{resolution:CoilResolution;remark?:string|null;expected_version:number;idempotency_key:string})=>callApi<CoilException>('coilSpecExceptions.confirm',{pathParams:{exception_id:id},data}),
  resume:(id:QrId,data:{rechecked_material_batch_id:number;reason:string;expected_version:number;idempotency_key:string})=>callApi<CoilException>('coilSpecExceptions.resume',{pathParams:{exception_id:id},data}),
  notifications:(params:NotificationFilter={})=>callApi<NotificationPage>('notifications.list',{params:{...params}}),
  deliveries:(params:NotificationFilter={})=>callApi<NotificationPage>('qrAdmin.deliveries',{params:{...params}}),
  retry:(id:QrId,data:{expected_version:number;idempotency_key:string})=>callApi<NotificationDelivery>('qrAdmin.retryDelivery',{pathParams:{delivery_id:id},data}),
}
