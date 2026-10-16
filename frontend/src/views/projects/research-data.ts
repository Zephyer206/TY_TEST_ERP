import { reactive, watch } from 'vue'

export type ResearchProjectType = '新产品研发' | '工艺改良' | '技术迭代'
export type ResearchStage = '诊断规划' | '制度搭建' | '费用落地' | '验收交付'
export type EvidenceStatus = '齐全' | '待补' | '不适用'

export interface ResearchDocument {
  name: string
  category: '立项' | '执行' | '结项' | '委外'
  status: EvidenceStatus
  updatedAt: string
}

export interface ResearchCost {
  category: string
  amount: number
  sourceNo: string
  voucherNo: string
  allocation: string
  eligible: boolean
}

export interface ResearchProject {
  id: string
  name: string
  type: ResearchProjectType
  owner: string
  department: string
  stage: ResearchStage
  status: '进行中' | '待验收' | '已结项' | '已终止'
  startDate: string
  endDate: string
  budget: number
  spent: number
  evidenceRate: number
  taxRate: number
  documents: ResearchDocument[]
  costs: ResearchCost[]
}

export const stagePlan = [
  { name: '诊断规划' as ResearchStage, weeks: '第 1-4 周', state: 'done', standards: ['研发与生产项目边界确认', '重点项目清单经管理层批准', '立项资料完整性首次诊断'] },
  { name: '制度搭建' as ResearchStage, weeks: '第 5-10 周', state: 'done', standards: ['研发费用科目与四口径映射完成', '工时、领料与设备使用制度发布', '委外成果归属与验收模板启用'] },
  { name: '费用落地' as ResearchStage, weeks: '第 11-18 周', state: 'active', standards: ['业务单据与凭证逐笔关联', '共用资源按工时或实际时长分摊', '项目费用台账月度四口径核对'] },
  { name: '验收交付' as ResearchStage, weeks: '第 19-24 周', state: 'pending', standards: ['项目档案包完整率不低于 95%', '高新六项量化指标复核通过', '抽样穿透至业务单据和财务凭证'] },
]

const seedProjects: ResearchProject[] = [
  {
    id: 'RD-2026-001', name: '高强度弹片耐久性提升', type: '新产品研发', owner: '周明', department: '研发中心', stage: '费用落地', status: '进行中', startDate: '2026-01-08', endDate: '2026-11-30', budget: 1280000, spent: 836420, evidenceRate: 94, taxRate: 100,
    documents: [
      { name: '项目立项计划书', category: '立项', status: '齐全', updatedAt: '2026-01-08' },
      { name: '科技查新报告', category: '立项', status: '齐全', updatedAt: '2026-01-15' },
      { name: '内部立项审批文件', category: '立项', status: '齐全', updatedAt: '2026-01-18' },
      { name: '实验记录与阶段报告', category: '执行', status: '齐全', updatedAt: '2026-09-30' },
      { name: '成果鉴定与知识产权证明', category: '结项', status: '待补', updatedAt: '2026-10-08' },
      { name: '委外疲劳测试验收记录', category: '委外', status: '齐全', updatedAt: '2026-08-22' },
    ],
    costs: [
      { category: '人工费用', amount: 368200, sourceNo: 'WH-RD-2609-018', voucherNo: '记-2026-09-0321', allocation: '项目工时', eligible: true },
      { category: '直接投入', amount: 286540, sourceNo: 'LL-RD-2609-044', voucherNo: '记-2026-09-0356', allocation: '研发专用', eligible: true },
      { category: '设备折旧', amount: 98680, sourceNo: 'EQ-RD-2609-009', voucherNo: '记-2026-09-0380', allocation: '实际机时', eligible: true },
      { category: '委外费用', amount: 83000, sourceNo: 'OS-RD-2608-003', voucherNo: '记-2026-08-0288', allocation: '合同验收', eligible: true },
    ],
  },
  {
    id: 'RD-2026-002', name: '连续模高速冲压工艺改良', type: '工艺改良', owner: '陈工', department: '工艺工程部', stage: '费用落地', status: '进行中', startDate: '2026-03-01', endDate: '2026-12-15', budget: 760000, spent: 492880, evidenceRate: 88, taxRate: 96,
    documents: [
      { name: '项目立项计划书', category: '立项', status: '齐全', updatedAt: '2026-03-01' },
      { name: '科技查新报告', category: '立项', status: '待补', updatedAt: '2026-03-04' },
      { name: '内部立项审批文件', category: '立项', status: '齐全', updatedAt: '2026-03-06' },
      { name: '试制参数与专题会议纪要', category: '执行', status: '齐全', updatedAt: '2026-09-28' },
      { name: '工艺变更图纸', category: '执行', status: '齐全', updatedAt: '2026-09-18' },
      { name: '成果鉴定报告', category: '结项', status: '待补', updatedAt: '2026-10-01' },
    ],
    costs: [
      { category: '人工费用', amount: 186400, sourceNo: 'WH-RD-2609-026', voucherNo: '记-2026-09-0338', allocation: '项目工时', eligible: true },
      { category: '直接投入', amount: 174260, sourceNo: 'LL-RD-2609-051', voucherNo: '记-2026-09-0372', allocation: '研发专用', eligible: true },
      { category: '设备折旧', amount: 132220, sourceNo: 'EQ-RD-2609-014', voucherNo: '记-2026-09-0391', allocation: '实际机时', eligible: false },
    ],
  },
  {
    id: 'RD-2026-003', name: '表面涂层抗盐雾技术迭代', type: '技术迭代', owner: '许岚', department: '技术质量部', stage: '验收交付', status: '待验收', startDate: '2025-11-15', endDate: '2026-10-31', budget: 520000, spent: 501300, evidenceRate: 97, taxRate: 100,
    documents: [
      { name: '项目立项计划书', category: '立项', status: '齐全', updatedAt: '2025-11-15' },
      { name: '科技查新报告', category: '立项', status: '齐全', updatedAt: '2025-11-20' },
      { name: '内部立项审批文件', category: '立项', status: '齐全', updatedAt: '2025-11-22' },
      { name: '实验记录与检测报告', category: '执行', status: '齐全', updatedAt: '2026-09-26' },
      { name: '成果鉴定报告', category: '结项', status: '齐全', updatedAt: '2026-10-06' },
      { name: '软著登记证明', category: '结项', status: '齐全', updatedAt: '2026-10-09' },
    ],
    costs: [
      { category: '人工费用', amount: 206800, sourceNo: 'WH-RD-2609-031', voucherNo: '记-2026-09-0347', allocation: '项目工时', eligible: true },
      { category: '直接投入', amount: 218500, sourceNo: 'PO-RD-2608-017', voucherNo: '记-2026-08-0306', allocation: '研发采购', eligible: true },
      { category: '检测费用', amount: 76000, sourceNo: 'QA-RD-2609-012', voucherNo: '记-2026-09-0401', allocation: '项目专属', eligible: true },
    ],
  },
]

const STORAGE_KEY = 'zephyr-research-compliance-v1'

function loadProjects() {
  if (typeof window === 'undefined') return seedProjects
  try {
    const saved = JSON.parse(window.localStorage.getItem(STORAGE_KEY) || 'null')
    return Array.isArray(saved) && saved.length ? saved as ResearchProject[] : seedProjects
  } catch {
    return seedProjects
  }
}

export const researchProjects = reactive<ResearchProject[]>(loadProjects())

if (typeof window !== 'undefined') {
  watch(researchProjects, value => window.localStorage.setItem(STORAGE_KEY, JSON.stringify(value)), { deep: true })
}

export const peopleLedger = [
  { name: '周明', role: '项目研发人员', department: '研发中心', project: 'RD-2026-001', hours: 156, totalHours: 168, evidence: '劳动合同 / 社保 / 岗位说明齐全' },
  { name: '陈工', role: '项目研发人员', department: '工艺工程部', project: 'RD-2026-002', hours: 132, totalHours: 168, evidence: '劳动合同 / 社保 / 岗位说明齐全' },
  { name: '许岚', role: '项目研发人员', department: '技术质量部', project: 'RD-2026-003', hours: 148, totalHours: 168, evidence: '劳动合同 / 社保 / 岗位说明齐全' },
  { name: '郭航', role: '跨部门共用管理人员', department: '设备部', project: 'RD-2026-001 / 002', hours: 62, totalHours: 168, evidence: '工时占比已公示' },
  { name: '刘检', role: '量产测试人员', department: '质量部', project: '-', hours: 0, totalHours: 168, evidence: '不可计入研发人工' },
]

export const sourceDocuments = [
  { no: 'LL-RD-2609-044', type: '研发试制领料单', project: 'RD-2026-001', department: '生产', status: '已关联凭证', trace: '领料单 → 试制记录 → 凭证' },
  { no: 'PO-RD-2608-017', type: '研发物资采购订单', project: 'RD-2026-003', department: '采购', status: '已关联凭证', trace: '采购单 → 入库单 → 发票 → 凭证' },
  { no: 'QA-RD-2609-012', type: '研发样品检测报告', project: 'RD-2026-003', department: '质量', status: '已归档', trace: '样品批次 → 检测报告 → 结项材料' },
  { no: 'EQ-RD-2609-014', type: '共用设备使用登记', project: 'RD-2026-002', department: '设备', status: '待复核', trace: '设备记录 → 实际机时 → 折旧分摊' },
  { no: 'OS-RD-2608-003', type: '委外研发验收记录', project: 'RD-2026-001', department: '采购', status: '已归档', trace: '合同 → 成果文档 → 验收 → 发票' },
]

export const complianceMetrics = [
  { name: '研发费用占营业收入比例', value: '4.18%', target: '不低于 3%', status: '达标' },
  { name: '高新技术产品收入占比', value: '68.4%', target: '不低于 60%', status: '达标' },
  { name: '科技人员占职工总数比例', value: '13.2%', target: '不低于 10%', status: '达标' },
  { name: '境内研发费用占比', value: '96.8%', target: '不低于 60%', status: '达标' },
  { name: '近三年研发费用增长率', value: '9.6%', target: '持续稳定', status: '达标' },
  { name: '项目档案包完整率', value: '93.0%', target: '不低于 95%', status: '关注' },
]
