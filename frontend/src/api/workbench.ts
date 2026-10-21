import { callApi } from './client'

export type TaskScope = 'mine' | 'team' | 'created'
export type TaskModule = 'production' | 'shipping'
export type DueFilter = 'all' | 'today' | 'overdue' | 'undated'

export interface WorkbenchTask {
  key: string
  scope: TaskScope
  module: TaskModule
  document_no: string
  title: string
  summary: string
  customer: string | null
  role: string
  due_date: string | null
  urgent: boolean
  updated_at: string | null
  route: string
  action_label: string
}

export interface WorkbenchPage {
  identity: { id: number; name: string; department: string; position: string | null; administrator: boolean; acceptance_mode: boolean }
  today: string
  generated_at: string
  counts: Record<TaskScope, number>
  stats: { pending: number; today: number; overdue: number }
  items: WorkbenchTask[]
  total: number
  page: number
  page_size: number
}

export interface WorkbenchQuery {
  scope: TaskScope
  module?: TaskModule
  search: string
  due: DueFilter
  page: number
  page_size: number
}

export const workbenchApi = {
  list: (query: WorkbenchQuery) => callApi<WorkbenchPage>('workbench.list', { params: { ...query } }),
}
