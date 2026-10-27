import {callApi} from './client'
import type {QrId} from '@/types/productBox'
import type {SplitRequest,SplitResult} from '@/types/productSplit'
export const productSplitApi={split:(parentId:QrId,data:SplitRequest)=>callApi<SplitResult>('productBoxes.split',{pathParams:{parent_id:parentId},data})}
