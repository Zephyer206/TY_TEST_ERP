import { reactive, watch } from 'vue'
import type { QuoteGroupRecord } from '@/api/quoteGroups'

export type ProjectStage = '待启动' | '打样' | '量产模具' | 'PPAP' | '量产导入' | '已移交'
export type ProjectStatus = '待启动' | '进行中' | '暂停' | '已完成'

export interface PartLine {
  id: number
  customerPartNo: string
  name: string
  pairLabel?: string
  annualUsage: number
  price: number
  material?: string
  thickness?: string
  width?: string
  pitch?: string
  utilization?: string
  pressTonnage?: string
  cavityCount?: string
  toolingLeadTime?: string
}

export interface QuoteGroup {
  id: string
  backendId?: number
  inquiryId?: number
  customer: string
  vehicle: string
  projectName: string
  stage: ProjectStage
  status: string
  path: '待确定方案' | '仅打样' | '先打样后开量产模具' | '直接开量产模具'
  toolingType: string
  developmentToolingCost?: number
  toolingCost: number
  toolingLife: number
  material: string
  materialDensity?: number
  materialUnitPrice?: number
  materialScrapPrice?: number
  surfaceTreatmentFee?: number
  inspectionFee?: number
  packagingFee?: number
  freightFee?: number
  managementFee?: number
  profitMargin?: number
  projectMaterialAdjustment?: number
  toolingLeadTime?: number
  quoteNote?: string
  quotedAt?: string
  parts: PartLine[]
  updatedAt: string
}

export function mapQuoteGroup(record: QuoteGroupRecord): QuoteGroup {
  return {
    id: record.group_no,
    backendId: record.id,
    inquiryId: record.inquiry_id,
    customer: record.customer,
    vehicle: record.project_name,
    projectName: record.project_name,
    stage: '待启动',
    status: record.status,
    path: record.quote_path as QuoteGroup['path'],
    toolingType: record.tooling_type || '',
    developmentToolingCost: record.development_tooling_cost == null ? undefined : Number(record.development_tooling_cost),
    toolingCost: Number(record.tooling_cost || 0),
    toolingLife: Number(record.tooling_life || 0),
    material: record.material_name || '',
    // Older quote records stored the one-off adjustment separately. Present it
    // as the final quote price while the UI migrates new saves to adjustment=0.
    materialDensity: record.material_density == null ? undefined : Number(record.material_density),
    materialUnitPrice: Number(record.material_unit_price || 0) + Number(record.material_adjustment || 0),
    materialScrapPrice: record.material_scrap_price == null ? undefined : Number(record.material_scrap_price),
    surfaceTreatmentFee: Number(record.surface_treatment_fee || 0),
    inspectionFee: Number(record.inspection_fee || 0),
    packagingFee: Number(record.packaging_fee || 0),
    freightFee: Number(record.freight_fee || 0),
    managementFee: Number(record.management_fee || 0),
    profitMargin: Number(record.profit_margin || 0),
    projectMaterialAdjustment: 0,
    toolingLeadTime: Number(record.tooling_lead_time || 0),
    quoteNote: record.quote_note || '',
    updatedAt: (record.updated_at || '').slice(0, 10),
    parts: record.items.map(item => ({
      id: item.id,
      customerPartNo: item.customer_part_no || '',
      name: item.part_name || '待命名零件',
      pairLabel: item.pair_key ? '左右件 · 一出二' : undefined,
      annualUsage: Number(item.annual_usage || 0),
      price: Number(item.product_price || 0),
      material: item.material_name || '',
      thickness: item.thickness == null ? '' : String(item.thickness),
      width: item.width == null ? '' : String(item.width),
      pitch: item.pitch == null ? '' : String(item.pitch),
      utilization: item.utilization == null ? '' : String(item.utilization),
      pressTonnage: item.press_tonnage == null ? '' : String(item.press_tonnage),
      cavityCount: String(item.cavity_count || 1),
      toolingLeadTime: String(item.tooling_lead_time || 0),
    })),
  }
}

export interface ProjectRecord {
  id: string
  inquiryId?: number
  name: string
  customer: string
  customerProject: string
  owner: string
  stage: ProjectStage
  status: ProjectStatus
  sop: string
  nominatedAt: string
  quoteGroups: QuoteGroup[]
  milestones: { label: string; date: string; state: 'done' | 'active' | 'pending' }[]
  pending: string[]
}

export const projects = reactive<ProjectRecord[]>([
  {
    id: 'P-2026-001',
    name: '星海后桥支架开发',
    customer: '星海汽车',
    customerProject: 'XH-NEV-2027',
    owner: '陈项目',
    stage: '量产模具',
    status: '进行中',
    sop: '2027-03-15',
    nominatedAt: '2026-08-18',
    quoteGroups: [{
      id: 'QG-2026-014', customer: '星海汽车', vehicle: '星海后桥', projectName: '星海后桥支架开发', stage: '量产模具', status: 'OTS准备中', path: '先打样后开量产模具', toolingType: '连续模', toolingCost: 58500, toolingLife: 10000000, material: 'SUS 301', updatedAt: '2026-09-28',
      parts: [
        { id: 1, customerPartNo: '35721420014', name: '左簧片（星海后桥）', pairLabel: '左右件 · 一出二', annualUsage: 10000, price: 0.87 },
        { id: 2, customerPartNo: '35721420024', name: '右簧片（星海后桥）', pairLabel: '左右件 · 一出二', annualUsage: 10000, price: 0.87 },
      ],
    }],
    milestones: [
      { label: '项目启动', date: '2026-08-18', state: 'done' },
      { label: '样件确认', date: '2026-09-02', state: 'done' },
      { label: '量产模具完成', date: '2026-11-20', state: 'active' },
      { label: 'OTS完成', date: '2026-12-05', state: 'pending' },
      { label: '量产导入', date: '2027-02-20', state: 'pending' },
    ],
    pending: ['连续模试模计划待确认', '图纸 V2.1 已发布，技术需确认工艺影响', '客户样件反馈待归档'],
  },
  {
    id: 'P-2026-002', name: '华岳电池托盘项目', customer: '华岳新能源', customerProject: 'HY-EV-08', owner: '李项目', stage: '打样', status: '进行中', sop: '2027-06-01', nominatedAt: '2026-09-06',
    quoteGroups: [{ id: 'QG-2026-019', customer: '华岳新能源', vehicle: 'HY-EV-08', projectName: '华岳电池托盘项目', stage: '打样', status: '客户样件确认', path: '先打样后开量产模具', toolingType: '激光切割+简易模', toolingCost: 18000, toolingLife: 5000, material: 'SUS 301', updatedAt: '2026-09-25', parts: [{ id: 3, customerPartNo: 'HY-88031', name: '电池托盘支架', annualUsage: 24000, price: 20 }] }],
    milestones: [{ label: '项目启动', date: '2026-09-06', state: 'done' }, { label: '样件确认', date: '2026-10-08', state: 'active' }, { label: '量产模具完成', date: '2027-01-12', state: 'pending' }, { label: '量产导入', date: '2027-05-10', state: 'pending' }],
    pending: ['样件检验报告待上传'],
  },
  {
    id: 'P-2026-003', name: '启明座椅弹片定点', customer: '启明汽车', customerProject: 'QM-Seat-26', owner: '王项目', stage: 'PPAP', status: '进行中', sop: '2026-12-20', nominatedAt: '2026-06-12',
    quoteGroups: [{ id: 'QG-2026-007', customer: '启明汽车', vehicle: 'QM-Seat-26', projectName: '启明座椅弹片定点', stage: 'PPAP', status: '资料整理中', path: '直接开量产模具', toolingType: '连续模', toolingCost: 67500, toolingLife: 10000000, material: 'SUS 301', updatedAt: '2026-09-30', parts: [{ id: 4, customerPartNo: '35721310014', name: '座椅弹片', annualUsage: 18000, price: 0.89 }] }],
    milestones: [{ label: '项目启动', date: '2026-06-12', state: 'done' }, { label: '量产模具完成', date: '2026-08-20', state: 'done' }, { label: 'OTS完成', date: '2026-09-10', state: 'done' }, { label: 'PPAP资料提交', date: '2026-10-10', state: 'active' }, { label: '量产导入', date: '2026-11-22', state: 'pending' }],
    pending: ['PPAP资料包待上传客户模板'],
  },
])

export const quoteGroups = reactive<QuoteGroup[]>(projects.flatMap(project => project.quoteGroups))

export function refreshQuoteGroups() {
  quoteGroups.splice(0, quoteGroups.length, ...projects.flatMap(project => project.quoteGroups))
}

export interface RfqAttachment { name: string; size: number; status: 'ready' | 'reviewing' }
export interface RfqRecord {
  id: string
  projectId?: string
  customer: string
  project: string
  receivedAt: string
  dueAt: string
  parts: number
  status: string
  owner: string
  technicalReview: '待评审' | '评审中' | '待补充' | '已完成'
  attachments: RfqAttachment[]
}

export const rfqs = reactive<RfqRecord[]>([
  { id: 'RFQ-2026-031', customer: '星海汽车', project: 'XH-NEV-2027', receivedAt: '2026-09-22', dueAt: '2026-10-06', parts: 2, status: '报价中', owner: '陈项目', technicalReview: '评审中', attachments: [{ name: 'XH-NEV-2027-询价图纸.zip', size: 2840000, status: 'reviewing' }] },
  { id: 'RFQ-2026-028', customer: '华岳新能源', project: 'HY-EV-08', receivedAt: '2026-09-08', dueAt: '2026-09-25', parts: 1, status: '已提交客户', owner: '李项目', technicalReview: '已完成', attachments: [{ name: 'HY-EV-08-技术要求.pdf', size: 840000, status: 'ready' }] },
  { id: 'RFQ-2026-021', customer: '启明汽车', project: 'QM-Seat-26', receivedAt: '2026-06-05', dueAt: '2026-06-15', parts: 1, status: '已定点', owner: '王项目', technicalReview: '已完成', attachments: [] },
])

const WORKSPACE_STORAGE_KEY = 'zephyr-project-workspace-v1'
export function persistWorkspace() {
  if (typeof window === 'undefined') return
  window.localStorage.setItem(WORKSPACE_STORAGE_KEY, JSON.stringify({ projects, rfqs }))
}

function restoreWorkspace() {
  if (typeof window === 'undefined') return
  try {
    const saved = JSON.parse(window.localStorage.getItem(WORKSPACE_STORAGE_KEY) || 'null') as { projects?: ProjectRecord[]; rfqs?: RfqRecord[] } | null
    if (saved?.projects?.length) projects.splice(0, projects.length, ...saved.projects)
    if (saved?.rfqs?.length) rfqs.splice(0, rfqs.length, ...saved.rfqs)
    refreshQuoteGroups()
  } catch {
    window.localStorage.removeItem(WORKSPACE_STORAGE_KEY)
  }
}

restoreWorkspace()
watch(projects, persistWorkspace, { deep: true })
watch(rfqs, persistWorkspace, { deep: true })

export const samples = reactive([
  { id: 'SP-2026-018', project: 'P-2026-001', quoteGroup: 'QG-2026-014', purpose: '客户确认样件', method: '简易模', qty: 20, planned: '2026-09-02', status: '客户已接收', pair: '左右件 2件' },
  { id: 'SP-2026-019', project: 'P-2026-002', quoteGroup: 'QG-2026-019', purpose: '工程样件', method: '激光切割+简易模', qty: 10, planned: '2026-10-08', status: '检验中', pair: '单件' },
])

export const changes = reactive([
  { id: 'EC-2026-006', project: 'P-2026-001', part: '35721420014 / 024', drawing: 'DWG-XH-014', from: 'V2.0', to: 'V2.1', reason: '客户孔位调整', owner: '文控', tech: '待技术审核', ppap: '不需要', effective: '2026-10-15', status: '技术审核中' },
  { id: 'EC-2026-004', project: 'P-2026-003', part: '35721310014', drawing: 'DWG-QM-014', from: 'V1.2', to: 'V1.3', reason: '标识文字修正', owner: '文控', tech: '无需审核', ppap: '不需要', effective: '2026-09-28', status: '已生效' },
])

export function getProject(id: string) { return projects.find(project => project.id === id) }
