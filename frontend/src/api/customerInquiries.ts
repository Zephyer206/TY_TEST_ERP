import { callApi, type ApiParams } from './client'

export type TechnicalReviewStatus = '待评审' | '评审中' | '待补充' | '已完成'

export interface InquiryPressSelection {
  pressTonnage: string
  pressTonnageSource: 'type' | 'manual'
  pressTypeKey: string | null
  pressTypeLabel: string
  pressIsDualAxis: boolean | null
}

/** Legacy machine references are accepted only for compatibility, never assigned by the picker. */
export type CustomerInquiryTechnicalData = Record<string, unknown> & Omit<Partial<InquiryPressSelection>, 'pressTonnageSource'> & {
  pressTonnageSource?: 'type' | 'manual' | 'machine'
  pressMachineId?: number | null
  pressMachineLabel?: string
}

export interface CustomerInquiryAttachment {
  id: number
  name: string
  size: number
  status: 'ready' | 'reviewing' | string
  url: string
  content_type?: string | null
}

export interface CustomerInquiryRecord {
  id: number
  inquiry_no: string
  customer_id: number
  customer: string
  project_name: string
  due_date?: string | null
  status: string
  technical_review: TechnicalReviewStatus
  technical_review_note?: string | null
  technical_data?: CustomerInquiryTechnicalData[]
  owner_name: string
  received_at?: string | null
  created_at?: string | null
  attachments: CustomerInquiryAttachment[]
}

export interface CustomerInquiryListParams extends ApiParams {
  technical_review?: TechnicalReviewStatus | string
  search?: string
}

export interface CreateCustomerInquiryInput {
  customer_id: number | string
  project_name?: string
  due_date?: string
  technical_review_note?: string
  files: File[] | FileList
}

export interface TechnicalReviewInput {
  /** Omit to persist technical data without changing the review status. */
  status?: '待补充' | '已完成'
  note?: string
  technical_data?: CustomerInquiryTechnicalData[]
}

function createInquiryForm(input: CreateCustomerInquiryInput): FormData {
  const form = new FormData()
  form.append('customer_id', String(input.customer_id))
  if (input.project_name?.trim()) form.append('project_name', input.project_name.trim())
  if (input.due_date) form.append('due_date', input.due_date)
  if (input.technical_review_note?.trim()) form.append('technical_review_note', input.technical_review_note.trim())
  for (const file of Array.from(input.files || [])) form.append('files', file)
  return form
}

export const customerInquiriesApi = {
  list: (params: CustomerInquiryListParams = {}) => callApi<CustomerInquiryRecord[]>('customerInquiries.list', { params }),
  detail: (id: number | string) => callApi<CustomerInquiryRecord>('customerInquiries.detail', { pathParams: { inquiry_id: id } }),
  create: (input: CreateCustomerInquiryInput) => callApi<CustomerInquiryRecord>('customerInquiries.create', { data: createInquiryForm(input) }),
  technicalReview: (id: number | string, payload: TechnicalReviewInput) => callApi<CustomerInquiryRecord>('customerInquiries.technicalReview', { pathParams: { inquiry_id: id }, data: payload }),
}
