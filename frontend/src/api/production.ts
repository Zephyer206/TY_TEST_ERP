import { callApi, type ApiParams } from './client'
import type {
  MaterialMatchResult, ProcessFlowCardResponse, ProcessFlowInboundRequest,
  ProcessFlowListParams, ProcessFlowReprintResponse, ProcessFlowReverseTraceResponse,
  ProcessFlowScanResponse, ProductionPlanListParams, ProductionPlanResponse,
  ProductionSessionResponse, SessionStartRequest, VerifyMaterialParams,
} from '@/types/legacyQr'

interface ProductionWorkbenchParams extends ApiParams { plan_id?: number; limit?: number }

export const productionApi = {
  listPlans: (params: ProductionPlanListParams = {}) => callApi<ProductionPlanResponse[]>('production.plans', { params: { ...params } }),
  workbench: <T = unknown>(params: ProductionWorkbenchParams = {}) => callApi<T>('production.workbench', { params }),
  planningPartOptions: <T = unknown>(params: ApiParams = {}) => callApi<T>('production.planningPartOptions', { params }),
  plansCount: <T = unknown>(params: ApiParams = {}) => callApi<T>('production.plansCount', { params }),
  createBatch: <T = unknown>(payload: unknown) => callApi<T>('production.plansBatch', { data: payload }),
  confirmMaterials: <T = unknown>(payload: unknown) => callApi<T>('production.materialConfirmations', { data: payload }),
  updatePlan: <T = unknown>(id: number | string, payload: unknown) => callApi<T>('production.planUpdate', { pathParams: { plan_id: id }, data: payload }),
  cancelPlan: <T = unknown>(id: number | string, payload: unknown) => callApi<T>('production.planCancel', { pathParams: { plan_id: id }, data: payload }),
  schedulingWorkbench: <T = unknown>() => callApi<T>('production.schedulingWorkbench'),
  schedule: <T = unknown>(id: number | string, payload: unknown) => callApi<T>('production.schedule', { pathParams: { plan_id: id }, data: payload }),
  unschedule: <T = unknown>(id: number | string) => callApi<T>('production.unschedule', { pathParams: { plan_id: id } }),
  reorder: <T = unknown>(payload: unknown) => callApi<T>('production.reorder', { data: payload }),
  verifyMaterial: (params: VerifyMaterialParams) => callApi<MaterialMatchResult>('production.verifyMaterial', { config: { params } }),
  startSession: (data: SessionStartRequest) => callApi<ProductionSessionResponse>('production.startSession', { data }),
  closeSession: (sessionId: number) => callApi<ProductionSessionResponse>('production.closeSession', { pathParams: { session_id: sessionId } }),
  processFlowCards: (params: ProcessFlowListParams = {}) => callApi<ProcessFlowCardResponse[]>('production.processFlowCards', { params: { ...params } }),
  scanProcessFlow: (cardId: number) => callApi<ProcessFlowScanResponse>('production.scanProcessFlow', { pathParams: { card_id: cardId } }),
  reverseTraceProcessFlow: (cardId: number) => callApi<ProcessFlowReverseTraceResponse>('production.reverseTraceProcessFlow', { pathParams: { card_id: cardId } }),
  inboundProcessFlow: (cardId: number, data: ProcessFlowInboundRequest = {}) => callApi<ProcessFlowReverseTraceResponse>('production.inboundProcessFlow', { pathParams: { card_id: cardId }, data }),
  reprintProcessFlow: (cardId: number) => callApi<ProcessFlowReprintResponse>('production.reprintProcessFlow', { pathParams: { card_id: cardId } }),
}
