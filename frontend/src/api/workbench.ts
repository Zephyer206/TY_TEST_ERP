import { callApi } from './client'
import type { CompanyKey } from '@/stores/company'

export type TaskScope = 'mine' | 'team' | 'created'
export type TaskModule = 'production' | 'shipping' | 'inquiry' | 'quote' | 'nonconforming'
export type DueFilter = 'all' | 'today' | 'overdue' | 'undated' | 'blocked'

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
  source_type: string
  source_id: string
  source_line_id: string | null
  step_key: string
  source_revision: string
  company: CompanyKey | null
  owner_department: string
  owner_role: string
  source_assignee: string | null
  actionable: boolean
  assignee_id: number | null
  assignee_name: string | null
  assignment_state: 'unassigned' | 'claimed' | 'assigned'
  assignment_version: number
  can_claim: boolean
  can_release: boolean
  can_assign: boolean
  blocked_reason: string | null
  completion_requirements: string[]
  next_role: string | null
}

export interface WorkbenchCoverage {
  key: string
  label: string
  status: 'active' | 'not_connected'
  description: string
}

export interface WorkbenchPage {
  identity: { id: number; name: string; department: string; position: string | null; administrator: boolean; acceptance_mode: boolean; is_switched?: boolean }
  today: string
  generated_at: string
  counts: Record<TaskScope, number>
  stats: { pending: number; today: number; overdue: number; blocked: number }
  items: WorkbenchTask[]
  total: number
  page: number
  page_size: number
  coverage: WorkbenchCoverage[]
}

export interface WorkbenchQuery {
  scope: TaskScope
  module?: TaskModule
  search: string
  due: DueFilter
  page: number
  page_size: number
  company: CompanyKey
}

export interface TaskAssignmentInput {
  task_key: string
  source_revision: string
  expected_version: number
  company: CompanyKey
}

export interface TaskAssignmentResult {
  task_key: string
  version: number
  assignee_id: number | null
  assignee_name: string | null
  assignment_state: 'unassigned' | 'claimed' | 'assigned'
}

export interface TaskAssignee { id: number; name: string; department: string; position: string | null }

export const workbenchApi = {
  list: (query: WorkbenchQuery) => callApi<WorkbenchPage>('workbench.list', { params: { ...query } }),
  claim: (data: TaskAssignmentInput) => callApi<TaskAssignmentResult>('workbench.claim', { data }),
  release: (data: TaskAssignmentInput) => callApi<TaskAssignmentResult>('workbench.release', { data }),
  assign: (data: TaskAssignmentInput & { assignee_id: number | null }) => callApi<TaskAssignmentResult>('workbench.assign', { data }),
  assignees: (task_key: string, company: CompanyKey) => callApi<{ items: TaskAssignee[] }>('workbench.assignees', { params: { task_key, company } }),
}
