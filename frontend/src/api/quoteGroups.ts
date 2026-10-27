import { callApi, type ApiParams } from './client'

export interface QuoteGroupItem {
  id: number
  sequence: number
  customer_part_no?: string | null
  part_name?: string | null
  pair_key?: string | null
  material_name?: string | null
  thickness?: number | null
  width?: number | null
  pitch?: number | null
  utilization?: number | null
  press_tonnage?: number | null
  press_type_key?: string | null
  press_type_label?: string | null
  press_is_dual_axis?: boolean | null
  press_tonnage_source?: 'type' | 'manual' | null
  cavity_count: number
  tooling_cost: number
  tooling_lead_time: number
  product_price: number
  annual_usage: number
  lifecycle_years?: number | null
}

export interface QuoteGroupRecord {
  id: number
  group_no: string
  inquiry_id: number
  customer_id: number
  customer: string
  project_name: string
  status: string
  quote_path: string
  tooling_type?: string | null
  /** Engineering snapshot total; shared left/right tooling is counted once. */
  development_tooling_cost: number | null
  /** Final customer tooling price, independent of the engineering estimate. */
  tooling_cost: number
  tooling_lead_time: number
  tooling_life: number
  material_name?: string | null
  material_density?: number | null
  material_unit_price: number
  material_scrap_price?: number | null
  surface_treatment_fee: number
  inspection_fee: number
  packaging_fee: number
  freight_fee: number
  management_fee: number
  profit_margin: number
  material_adjustment: number
  quote_note?: string | null
  updated_at: string
  items: QuoteGroupItem[]
}

export interface QuoteGroupUpdate {
  quote_path?: string
  tooling_type?: string
  /** Final customer tooling price; discounts are applied before saving. */
  tooling_cost?: number
  tooling_lead_time?: number
  tooling_life?: number
  material_name?: string | null
  material_density?: number | null
  material_unit_price?: number
  material_scrap_price?: number | null
  surface_treatment_fee?: number
  inspection_fee?: number
  packaging_fee?: number
  freight_fee?: number
  management_fee?: number
  profit_margin?: number
  material_adjustment?: number
  quote_note?: string
  items?: Array<{ product_price: number; annual_usage: number; lifecycle_years?: number | null }>
}

export const quoteGroupsApi = {
  syncPress: (id: number | string) => callApi<QuoteGroupRecord>('quoteGroups.syncPress', { pathParams: { group_id: id } }),
  list: (params: ApiParams = {}) => callApi<QuoteGroupRecord[]>('quoteGroups.list', { params }),
  detail: (id: number | string) => callApi<QuoteGroupRecord>('quoteGroups.detail', { pathParams: { group_id: id } }),
  create: (inquiryId: number | string) => callApi<QuoteGroupRecord>('quoteGroups.create', { data: { inquiry_id: inquiryId } }),
  update: (id: number | string, payload: QuoteGroupUpdate) => callApi<QuoteGroupRecord>('quoteGroups.update', { pathParams: { group_id: id }, data: payload }),
}
