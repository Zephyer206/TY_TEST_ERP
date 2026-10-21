import { callApi, type ApiParams } from './client'
import type { CompanyKey } from '@/stores/company'

export type PpapStatus = 'preparing' | 'submitted' | 'supplement' | 'temporary' | 'approved' | 'rejected'
export const ppapStatusLabels: Record<PpapStatus, string> = { preparing: '准备中', submitted: '已提交', supplement: '需补充', temporary: '临时批准', approved: '已批准', rejected: '未批准' }
export interface PpapLink {
  key: string; kind: 'part' | 'requirement' | 'package'; source_id?: number
  part_no: string; name: string; tooling_no: string; mold_type: string; drawing_version: string
  composition?: Record<string, unknown>[]
}
export interface PpapFolder { id: string; parent_id: string | null; name: string }
export interface PpapVersion { id: string; document_id: string; version: number; sha256: string; size: number; extension: string; sheets: string[]; created_at: string; created_by: string }
export interface PpapDocument { id: string; name: string; folder_id: string | null; linked_key: string | null; current_version: number; versions: PpapVersion[] }
export interface PpapSnapshotDocument { id: string; name: string; folder_id: string | null; linked_key: string | null; version: PpapVersion }
export interface PpapSubmission {
  id: string; round_no: number; submitted_date: string | null; status: Exclude<PpapStatus, 'preparing'>
  feedback: string; approved_date: string | null; valid_until: string | null; conditions: string
  evidence_version_id: string | null; updated_by: string; updated_at: string
  snapshot: { name: string; customer_name: string; links: PpapLink[]; folders: PpapFolder[]; documents: PpapSnapshotDocument[]; remark: string }
}
export interface PpapRow {
  id: string; company: CompanyKey; record_no: string; name: string; customer_key: string; customer_name: string; owner: string
  planned_date: string | null; remark: string; links: PpapLink[]; revision: number; updated_at: string; created_at: string
  status: PpapStatus; submitted_date?: string | null; approved_date?: string | null; valid_until?: string | null; round_no?: number
}
export interface PpapDetail extends PpapRow {
  can_write: boolean; acceptance_mode: boolean; folders: PpapFolder[]; documents: PpapDocument[]; submissions: PpapSubmission[]
  audit: { id: string; action: string; detail: Record<string, unknown>; actor_name: string; created_at: string }[]
}
export interface PpapLedger { items: PpapRow[]; total: number; can_write: boolean; acceptance_mode: boolean; identity: { name: string; dept: string } }
export interface PpapOptions { customers: { key: string; name: string }[]; references: PpapLink[] }
export interface PpapArchiveInput { name: string; customer_key: string; owner: string; planned_date: string | null; remark: string; links: Pick<PpapLink, 'key' | 'drawing_version' | 'tooling_no' | 'mold_type'>[] }
export interface PpapFeedbackInput {
  revision: number; status: Exclude<PpapStatus, 'preparing'>; feedback: string; approved_date: string | null; valid_until: string | null; conditions: string; evidence_version_id: string | null
}

const scoped = (company: CompanyKey, archiveId: string) => ({ company, archive_id: archiveId })
async function blob(key: string, company: CompanyKey, archiveId: string, versionId: string) {
  try {
    return await callApi<Blob>(key, { pathParams: { ...scoped(company, archiveId), version_id: versionId }, config: { responseType: 'blob', timeout: 120000 } })
  } catch (error: unknown) {
    const data = (error as { response?: { data?: Blob } }).response?.data
    if (data instanceof Blob) {
      let message = ''
      try { message = JSON.parse(await data.text()).detail } catch { /* keep request-client error */ }
      if (message) throw new Error(message)
    }
    throw error
  }
}
export const ppapApi = {
  list: (params: ApiParams) => callApi<PpapLedger>('ppap.list', { params }),
  options: (params: ApiParams) => callApi<PpapOptions>('ppap.options', { params }),
  create: (company: CompanyKey, data: PpapArchiveInput) => callApi<PpapDetail>('ppap.create', { pathParams: { company }, data }),
  detail: (company: CompanyKey, archiveId: string) => callApi<PpapDetail>('ppap.detail', { pathParams: scoped(company, archiveId) }),
  update: (company: CompanyKey, archiveId: string, data: PpapArchiveInput & { revision: number }) => callApi<PpapDetail>('ppap.update', { pathParams: scoped(company, archiveId), data }),
  createFolder: (company: CompanyKey, archiveId: string, data: { revision: number; parent_id: string | null; name: string }) => callApi<PpapDetail>('ppap.folderCreate', { pathParams: scoped(company, archiveId), data }),
  renameFolder: (company: CompanyKey, archiveId: string, folderId: string, data: { revision: number; name: string }) => callApi<PpapDetail>('ppap.folderRename', { pathParams: { ...scoped(company, archiveId), folder_id: folderId }, data }),
  upload: (company: CompanyKey, archiveId: string, data: FormData) => callApi<PpapDetail>('ppap.upload', { pathParams: scoped(company, archiveId), data, config: { timeout: 120000 } }),
  preview: (company: CompanyKey, archiveId: string, versionId: string) => blob('ppap.preview', company, archiveId, versionId),
  original: (company: CompanyKey, archiveId: string, versionId: string) => blob('ppap.original', company, archiveId, versionId),
  submit: (company: CompanyKey, archiveId: string, data: { revision: number; submitted_date: string | null; remark: string }) => callApi<PpapDetail>('ppap.submit', { pathParams: scoped(company, archiveId), data }),
  feedback: (company: CompanyKey, archiveId: string, submissionId: string, data: PpapFeedbackInput) => callApi<PpapDetail>('ppap.feedback', { pathParams: { ...scoped(company, archiveId), submission_id: submissionId }, data }),
}
