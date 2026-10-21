import { emptyDefectDraft, normalizeDefect, type DefectRecord, type PreviewData } from './nonconforming.ts'

export interface WorkbookBundle {
  batchId: string; fileName: string; sha256: string; sourceRows: number; uniqueRows: number;
  mergedDuplicateRows: number; splitRows: number; sheets: Record<string, number>;
  records: Array<Partial<DefectRecord> & Pick<DefectRecord, 'id' | 'no' | 'customer' | 'partNo' | 'partName' | 'quantity' | 'importInfo'>>;
}
/** Preview placement is explicit; sheet names describe provenance, not company ownership. */
export function mergeWorkbookPreview(data: PreviewData, bundle: WorkbookBundle): PreviewData {
  const existing = new Set(data.records.map(record => record.id))
  let priority = Math.max(0, ...data.records.map(record => record.priority))
  const at = new Date().toISOString()
  const added = bundle.records.filter(row => !existing.has(row.id)).map(row => normalizeDefect({
    ...emptyDefectDraft(), ...JSON.parse(JSON.stringify(row)), company: 'tianyue', priority: ++priority,
    status: 'pending_confirmation', moldReady: false, paused: false,
    acceptedQty: 0, scrappedQty: 0, otherQty: 0, submission: null, actualDate: '', createdAt: at,
    history: [{ id: `${row.id}-import`, at, actor: 'Excel 导入', action: '原表导入待确认', detail: `${bundle.fileName}；${row.importInfo?.sources.map(item => `${item.sheet}第${item.row}行`).join('、')}。原表进度及完成日期保留作历史参考，未自动生成验收结果。` }],
  } as DefectRecord))
  return { ...data, records: [...data.records, ...added] }
}
export const originalProgressLabels = { reported_completed: '原表记完成', reported_processing: '原表在处理', unrecorded: '原表进度未明' }
