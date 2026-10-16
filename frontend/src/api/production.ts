import { callApi, type ApiParams } from './client'

export const productionApi = {
  workbench: <T = unknown>(params: ApiParams = {}) => callApi<T>('production.workbench', { params }),
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
}
