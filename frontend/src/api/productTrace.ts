import {callApi} from './client'
import type {QrId} from '@/types/productBox'
import type {BoxTrace, EventPage} from '@/types/productTrace'
import type {ProductionQuantityResult} from '@/types/productProduction'

export const productTraceApi = {
  trace: (boxId: QrId, params: {page?: number; page_size?: number} = {}) =>
    callApi<BoxTrace>('productBoxes.trace', {pathParams: {box_id: boxId}, params}),
  events: (boxId: QrId, params: {before_id?: QrId; page_size?: number} = {}) =>
    callApi<EventPage>('productBoxes.events', {pathParams: {box_id: boxId}, params}),
  advance: (boxId: QrId, data: {context_id: QrId; expected_version: number; state_version: number; idempotency_key: string}) =>
    callApi<ProductionQuantityResult>('productBoxes.advance', {pathParams: {box_id: boxId}, data}),
}
