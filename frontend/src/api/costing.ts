import { callApi, type ApiParams } from './client'
import type { SurfaceTreatment, CostingTask, CostingItem, CostingRevision, Candidate, MaterialPrice, ChargeRule, ImportRow } from '@/types/costing'

export const partTreatmentsApi = {
  detail: (id: number | string) => callApi<{part_id: number; surface_treatment: SurfaceTreatment}>('partTreatments.detail', { pathParams: { part_id: id } }),
  save: (id: number | string, data: unknown) => callApi<{part_id: number; surface_treatment: SurfaceTreatment}>('partTreatments.save', { pathParams: { part_id: id }, data }),
}
export const costingApi = {
  catalog: () => callApi<{materials: MaterialPrice[]; treatments: ChargeRule[]}>('costing.catalog'),
  materialPreview: (data: unknown) => callApi<any>('costing.materialPreview', { data }),
  quotationPreview: (data: unknown) => callApi<any>('costing.quotationPreview', { data }),
  candidates: (params: ApiParams) => callApi<{total: number; items: Candidate[]}>('costing.candidates', { params }),
  tasks: (params: ApiParams = {}) => callApi<CostingTask[]>('costing.tasks.list', { params }),
  createTask: (data: unknown) => callApi<CostingTask>('costing.tasks.create', { data }),
  task: (id: number) => callApi<CostingTask & {items: CostingItem[]}>('costing.tasks.detail', { pathParams: { task_id: id } }),
  addItem: (id: number, data: unknown) => callApi<CostingItem>('costing.tasks.addItem', { pathParams: { task_id: id }, data }),
  context: (id: number) => callApi<any>('costing.context', { pathParams: { item_id: id } }),
  preview: (id: number, data: unknown) => callApi<any>('costing.preview', { pathParams: { item_id: id }, data }),
  save: (id: number, data: unknown) => callApi<CostingRevision>('costing.revisions.create', { pathParams: { item_id: id }, data }),
  revisions: (id: number) => callApi<CostingRevision[]>('costing.revisions.list', { pathParams: { item_id: id } }),
  importPreview: (customerId: number, file: File) => {
    const data = new FormData(); data.append('file', file)
    return callApi<{sheet: string; rows: ImportRow[]}>('costing.importPreview', { data, config: { params: { customer_id: customerId } } })
  },
  export: async (id: number) => {
    const blob = await callApi<Blob>('costing.export', { pathParams: { task_id: id }, config: { responseType: 'blob' } })
    const url = URL.createObjectURL(blob); const a = document.createElement('a')
    a.href = url; a.download = `简易成本核算-${id}.csv`; a.click(); URL.revokeObjectURL(url)
  },
}
export function costingError(error: any): string {
  const detail = error?.response?.data?.detail
  return typeof detail === 'string' ? detail : detail?.message || error?.message || '操作失败，请重试'
}
