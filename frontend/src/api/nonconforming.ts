import { callApi } from './client'
import type { Actor, Company, DefectDraft, DefectRecord, ReworkMold } from '@/domain/nonconforming'
import type { WorkbookBundle } from '@/domain/nonconformingImport'

export interface NonconformingWorkspace {
  records: DefectRecord[]; molds: ReworkMold[]; workbook: Omit<WorkbookBundle, 'records'> | null;
  actor: Actor; serverTime: string; createdId?: string | null;
}
export type RecordCommand = 'edit' | 'confirm' | 'return' | 'prepare' | 'start' | 'finish_step' | 'submit' | 'inspect' | 'move'
export const nonconformingApi = {
  list: (company: Company) => callApi<NonconformingWorkspace>('nonconforming.workspace', { params: { company } }),
  create: (company: Company, draft: DefectDraft) => callApi<NonconformingWorkspace>('nonconforming.create', { pathParams: { company }, data: draft }),
  action: (company: Company, id: string, revision: number, action: RecordCommand, payload: Record<string, unknown>) => callApi<NonconformingWorkspace>('nonconforming.action', { pathParams: { company, record_id: id }, data: { revision, action, payload } }),
  saveMold: (company: Company, draft: ReworkMold) => callApi<NonconformingWorkspace>('nonconforming.saveMold', { pathParams: { company }, data: draft }),
}
