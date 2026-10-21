<template>
  <div class="ppap-page" :aria-busy="loading">
    <header class="ppap-heading">
      <div><el-button v-if="archiveId" link :icon="ArrowLeft" @click="backToList">返回台账</el-button><h1>{{ archiveId ? (detail?.name || 'PPAP档案') : 'PPAP台账' }}</h1><p>{{ companyName }} · {{ archiveId ? detail?.record_no : '客户提交资料、文件归档与批准记录' }}</p></div>
      <div class="ppap-actions"><el-tag v-if="detail && archiveId" :type="statusType(detail.status)">{{ ppapStatusLabels[detail.status] }}</el-tag><el-tag v-if="!loading && !canWrite" type="info">只读</el-tag><el-button :icon="Refresh" :loading="loading" @click="refresh">刷新</el-button><el-button v-if="!archiveId && canWrite" type="primary" :icon="Plus" @click="editArchive = null; formOpen = true">新建PPAP</el-button></div>
    </header>
    <el-alert v-if="error" :title="error" type="error" show-icon :closable="false" />
    <template v-if="!archiveId">
      <form class="ppap-filters" @submit.prevent="page = 1; loadLedger()"><el-input v-model="search" clearable :prefix-icon="Search" aria-label="搜索PPAP" placeholder="搜索模具号、件号、产品名或客户" @clear="page = 1; loadLedger()" /><el-select v-model="statusFilter" clearable placeholder="全部状态" aria-label="PPAP状态筛选" @change="page = 1; loadLedger()"><el-option v-for="(label, value) in ppapStatusLabels" :key="value" :label="label" :value="value" /></el-select><el-button native-type="submit">查询</el-button></form>
      <div class="ppap-section-line ppap-table-caption"><span>共 {{ total }} 份档案</span><el-button v-if="sourceFiltered" link @click="clearSourceFilter">清除关联筛选</el-button><span>{{ canWrite ? '质量部门维护' : '可查询及在线查看' }}</span></div>
      <el-table v-loading="loading" :data="rows" stripe empty-text="暂无PPAP档案" @row-dblclick="openArchive">
        <el-table-column label="档案名称" min-width="300"><template #default="{ row }"><button class="ppap-name-button" @click="openArchive(row)">{{ row.name }}</button><small class="ppap-subtext">{{ row.record_no }}</small></template></el-table-column>
        <el-table-column prop="customer_name" label="客户" min-width="150" />
        <el-table-column label="关联对象" min-width="190"><template #default="{ row }"><span>{{ row.links.map((i: PpapLink) => i.part_no || i.name).join('、') || '尚未关联' }}</span><small class="ppap-subtext">{{ row.links.length }} 项</small></template></el-table-column>
        <el-table-column label="状态" width="130"><template #default="{ row }"><el-tag :type="statusType(row.status)">{{ ppapStatusLabels[row.status as PpapStatus] }}</el-tag><small v-if="expired(row.status, row.valid_until)" class="ppap-expired">临时批准已到期</small></template></el-table-column>
        <el-table-column prop="owner" label="负责人" width="110" /><el-table-column prop="planned_date" label="计划提交" width="120" /><el-table-column prop="submitted_date" label="最近提交" width="120" /><el-table-column prop="approved_date" label="批准日期" width="120" />
        <el-table-column label="操作" width="90" fixed="right"><template #default="{ row }"><el-button link type="primary" @click="openArchive(row)">查看</el-button></template></el-table-column>
      </el-table>
      <el-pagination v-model:current-page="page" :page-size="30" :total="total" layout="prev, pager, next, total" @current-change="loadLedger" />
    </template>
    <div v-else-if="loading && !detail" class="ppap-loading"><el-skeleton :rows="8" animated /></div>
    <template v-else-if="detail">
      <div class="ppap-summary"><span><small>客户</small>{{ detail.customer_name }}</span><span><small>负责人</small>{{ detail.owner }}</span><span><small>关联对象</small>{{ detail.links.length }} 项</span><span><small>提交轮次</small>{{ detail.submissions.length }} 次</span><span><small>计划提交</small>{{ detail.planned_date || '未设置' }}</span><el-button v-if="canWrite" @click="editArchive = detail; formOpen = true">编辑档案</el-button></div>
      <el-alert v-if="expired(detail.status, detail.submissions[0]?.valid_until)" title="临时批准已到期，请质量部门跟进客户后续结论。" type="warning" :closable="false" show-icon />
      <el-tabs v-model="activeTab" class="ppap-detail-tabs">
        <el-tab-pane label="文件资料" name="files">
          <div class="ppap-file-toolbar"><el-select v-model="snapshotId" aria-label="资料版本" placeholder="当前工作资料" @change="folderId = null"><el-option label="当前工作资料" value="" /><el-option v-for="s in detail.submissions" :key="s.id" :label="`第${s.round_no}次提交 · ${s.submitted_date || '日期未记录'}`" :value="s.id" /></el-select><div v-if="canWrite && !snapshotId" class="ppap-actions"><el-button :icon="FolderAdd" :disabled="busy" @click="openFolderDialog()">新建文件夹</el-button><el-button type="primary" :icon="Upload" :disabled="busy" @click="openUpload()">上传文档</el-button></div></div>
          <el-alert v-if="snapshot" :title="`正在查看第${selectedSubmission?.round_no}次提交的归档资料 · ${snapshot.name}`" type="info" :closable="false" />
          <div class="ppap-file-browser">
            <aside class="ppap-tree" aria-label="资料目录"><h2>资料目录</h2><el-tree :data="folderTree" node-key="id" :current-node-key="folderId || 'root'" :expand-on-click-node="false" highlight-current default-expand-all @node-click="(node: TreeNode) => folderId = node.id === 'root' ? null : node.id"><template #default="{ data }"><el-icon><Folder /></el-icon><span :title="data.label">{{ data.label }}</span></template></el-tree></aside>
            <section class="ppap-folder-content">
              <nav class="ppap-breadcrumb" aria-label="当前文件夹"><button @click="folderId = null">资料根目录</button><template v-for="f in breadcrumbs" :key="f.id"><span>/</span><button @click="folderId = f.id">{{ f.name }}</button></template></nav>
              <el-table :data="fileRows" empty-text="当前文件夹暂无资料" @row-dblclick="activateFile">
                <el-table-column label="名称" min-width="240"><template #default="{ row }"><button class="ppap-file-name" @click="activateFile(row)"><el-icon><Folder v-if="row.isFolder" /><Document v-else /></el-icon><span>{{ row.name }}</span></button><small v-if="row.linked_key" class="ppap-subtext">关联：{{ linkLabel(row.linked_key) }}</small></template></el-table-column>
                <el-table-column label="版本 / 大小" width="135"><template #default="{ row }"><span v-if="row.version">V{{ row.version.version }} · {{ fileSize(row.version.size) }}</span><span v-else>文件夹</span></template></el-table-column>
                <el-table-column label="上传人 / 时间" min-width="160"><template #default="{ row }"><span>{{ row.version?.created_by || '—' }}</span><small class="ppap-subtext">{{ row.version ? formatTime(row.version.created_at) : '' }}</small></template></el-table-column>
                <el-table-column label="操作" width="170" fixed="right"><template #default="{ row }"><template v-if="row.isFolder"><el-button link type="primary" @click="activateFile(row)">打开</el-button><el-button v-if="canWrite && !snapshotId" link @click="openFolderDialog(row)">重命名</el-button></template><template v-else><el-button link type="primary" @click="activateFile(row)">预览</el-button><el-dropdown v-if="row.versions && row.versions.length > 1" trigger="click"><el-button link>历史版本<el-icon><ArrowDown /></el-icon></el-button><template #dropdown><el-dropdown-menu><el-dropdown-item v-for="v in row.versions" :key="v.id" @click="showPreview(row.name, v)">V{{ v.version }} · {{ formatTime(v.created_at) }}</el-dropdown-item></el-dropdown-menu></template></el-dropdown></template></template></el-table-column>
              </el-table>
            </section>
          </div>
        </el-tab-pane>
        <el-tab-pane label="关联明细" name="links">
          <p class="ppap-muted">{{ snapshot ? `第${selectedSubmission?.round_no}次提交时的关联明细` : '当前档案关联明细' }} · 批准结果对整份PPAP统一生效</p>
          <el-table :data="visibleLinks" stripe><el-table-column label="类型" width="100"><template #default="{ row }">{{ row.kind === 'package' ? '安装包' : '零件' }}</template></el-table-column><el-table-column prop="part_no" label="件号 / 包号" min-width="170" /><el-table-column prop="name" label="产品名" min-width="160" /><el-table-column prop="tooling_no" label="模具号" min-width="170" /><el-table-column prop="mold_type" label="模具类型" min-width="120" /><el-table-column prop="drawing_version" label="图纸版本" width="110" /></el-table>
          <el-collapse v-for="link in visibleLinks.filter(l => l.composition?.length)" :key="link.key"><el-collapse-item :title="`${link.part_no} 安装包组成（${link.composition?.length}项）`"><div v-for="(item, i) in link.composition" :key="i" class="ppap-component">{{ item.unlinked_customer_part_number || item.tianyue_internal_composition || `关联单件 #${item.requirement_id}` }} · 数量 {{ item.quantity }}</div></el-collapse-item></el-collapse>
          <p v-if="detail.remark" class="ppap-remark">备注：{{ detail.remark }}</p>
        </el-tab-pane>
        <el-tab-pane label="提交与批准" name="submissions">
          <div class="ppap-section-line"><p class="ppap-muted">每轮提交保留独立的资料与客户结论</p><el-button v-if="canWrite" type="primary" :disabled="busy" @click="submissionOpen = true; submissionDate = today(); submissionRemark = ''; dialogError = ''">登记客户提交</el-button></div>
          <el-empty v-if="!detail.submissions.length" description="尚未登记客户提交" />
          <article v-for="s in detail.submissions" :key="s.id" class="ppap-submission-card"><div class="ppap-section-line"><h2>第{{ s.round_no }}次提交 <small>{{ s.submitted_date || '提交日期未记录' }}</small></h2><el-tag :type="statusType(s.status)">{{ ppapStatusLabels[s.status] }}</el-tag></div><p>{{ s.snapshot.documents.length }} 份文件 · {{ s.snapshot.links.length }} 项关联对象</p><p v-if="s.snapshot.remark">提交备注：{{ s.snapshot.remark }}</p><p v-if="s.feedback">客户反馈：{{ s.feedback }}</p><p v-if="s.approved_date">批准日期：{{ s.approved_date }}</p><p v-if="s.conditions">批准条件：{{ s.conditions }}</p><p v-if="s.valid_until" :class="{ 'ppap-expired': expired(s.status, s.valid_until) }">有效截止：{{ s.valid_until }}{{ expired(s.status, s.valid_until) ? ' · 已到期' : '' }}</p><div class="ppap-actions"><el-button @click="snapshotId = s.id; folderId = null; activeTab = 'files'">查看当次资料</el-button><el-button v-if="s.evidence_version_id" @click="previewEvidence(s.evidence_version_id)">查看批准凭证</el-button><el-button v-if="canWrite" @click="openFeedback(s)">登记客户反馈</el-button></div></article>
        </el-tab-pane>
        <el-tab-pane label="操作记录" name="audit"><el-timeline class="ppap-audit"><el-timeline-item v-for="entry in detail.audit" :key="entry.id" :timestamp="formatTime(entry.created_at)"><strong>{{ entry.action }}</strong> · {{ entry.actor_name }}<span v-if="entry.detail.name"> · {{ entry.detail.name }}</span><el-collapse><el-collapse-item title="查看记录详情"><pre class="ppap-audit-detail">{{ JSON.stringify(entry.detail, null, 2) }}</pre></el-collapse-item></el-collapse></el-timeline-item></el-timeline></el-tab-pane>
      </el-tabs>
    </template>

    <ArchiveForm v-model="formOpen" :company="company" :archive="editArchive" :default-owner="identityName" @saved="archiveSaved" />
    <PreviewDialog v-model="previewOpen" :company="company" :archive-id="archiveId" :version="previewVersion" :name="previewName" :can-write="canWrite" />
    <el-dialog v-model="folderOpen" :title="renamingFolder ? '重命名文件夹' : '新建文件夹'" width="440px" :close-on-click-modal="false" :show-close="!busy"><el-alert v-if="dialogError" :title="dialogError" type="error" :closable="false" /><el-form label-position="top" @submit.prevent="saveFolder"><el-form-item label="文件夹名称" required><el-input v-model="folderName" maxlength="200" aria-label="文件夹名称" :disabled="busy" /></el-form-item></el-form><template #footer><el-button :disabled="busy" @click="folderOpen = false">取消</el-button><el-button type="primary" :loading="busy" @click="saveFolder">保存文件夹</el-button></template></el-dialog>
    <el-dialog v-model="uploadOpen" title="上传文档" width="560px" :close-on-click-modal="false" :show-close="!busy"><el-alert v-if="dialogError" :title="dialogError" type="error" :closable="false" /><el-form label-position="top"><el-form-item label="选择文件" required><input type="file" accept=".pdf,.xls,.xlsx" aria-label="选择PPAP文档" :disabled="busy" @change="chooseFile" /></el-form-item><p class="ppap-muted">支持PDF、XLS、XLSX，单个文件最大100MB</p><el-form-item label="保存文件名" required><el-input v-model="uploadName" aria-label="保存文件名" :disabled="busy" /></el-form-item><el-form-item label="关联明细"><el-select v-model="uploadLink" :disabled="busy" aria-label="文件关联明细" placeholder="整份PPAP资料"><el-option label="整份PPAP资料" value="" /><el-option v-for="l in detail?.links || []" :key="l.key" :label="`${l.part_no} · ${l.name}`" :value="l.key" /></el-select></el-form-item><el-form-item label="文件保存方式"><el-radio-group v-model="uploadMode" :disabled="busy"><el-radio label="new">新增文件</el-radio><el-radio label="version">更新同名文件版本</el-radio></el-radio-group></el-form-item><el-alert v-if="uploadCollision" title="当前目录已有同名文件，可修改文件名，或明确选择更新同名文件版本。" type="warning" :closable="false" /></el-form><template #footer><el-button :disabled="busy" @click="uploadOpen = false">取消</el-button><el-button type="primary" :loading="busy" @click="saveUpload">确认上传</el-button></template></el-dialog>
    <el-dialog v-model="submissionOpen" title="登记客户提交" width="520px" :close-on-click-modal="false" :show-close="!busy"><el-alert v-if="dialogError" :title="dialogError" type="error" :closable="false" /><p>本次会归档当前目录及其全部文件版本、关联零件和安装包组成。</p><el-form label-position="top"><el-form-item label="实际提交日期"><el-date-picker v-model="submissionDate" type="date" value-format="YYYY-MM-DD" aria-label="实际提交日期" :disabled="busy" clearable /></el-form-item><el-form-item label="本次提交备注"><el-input v-model="submissionRemark" type="textarea" :rows="3" maxlength="6000" :disabled="busy" /></el-form-item></el-form><template #footer><el-button :disabled="busy" @click="submissionOpen = false">取消</el-button><el-button type="primary" :loading="busy" @click="saveSubmission">保存提交记录</el-button></template></el-dialog>
    <el-dialog v-model="feedbackOpen" :title="`第${feedbackTarget?.round_no || ''}次提交 · 客户反馈`" width="620px" :close-on-click-modal="false" :show-close="!busy"><el-alert v-if="dialogError" :title="dialogError" type="error" :closable="false" /><el-form label-position="top"><el-form-item label="整包处理结果"><el-select v-model="feedbackDraft.status" aria-label="客户处理结果" :disabled="busy" @change="feedbackStatusChanged"><el-option v-for="s in feedbackStatuses" :key="s" :label="ppapStatusLabels[s]" :value="s" /></el-select></el-form-item><el-form-item label="客户反馈"><el-input v-model="feedbackDraft.feedback" type="textarea" :rows="2" maxlength="6000" :disabled="busy" /></el-form-item><template v-if="['temporary', 'approved'].includes(feedbackDraft.status)"><div class="ppap-form-grid"><el-form-item label="批准日期"><el-date-picker v-model="feedbackDraft.approved_date" type="date" value-format="YYYY-MM-DD" aria-label="客户批准日期" :disabled="busy" /></el-form-item><el-form-item v-if="feedbackDraft.status === 'temporary'" label="临时批准有效截止"><el-date-picker v-model="feedbackDraft.valid_until" type="date" value-format="YYYY-MM-DD" aria-label="临时批准有效截止" :disabled="busy" /></el-form-item></div><el-form-item label="批准条件" :required="feedbackDraft.status === 'temporary'"><el-input v-model="feedbackDraft.conditions" type="textarea" :rows="3" maxlength="6000" aria-label="批准条件" :disabled="busy" /></el-form-item></template><el-form-item label="批准 / 反馈凭证"><el-select v-model="feedbackDraft.evidence_version_id" clearable aria-label="批准凭证" :disabled="busy"><el-option v-for="v in evidenceOptions" :key="v.id" :label="v.label" :value="v.id" /></el-select><small class="ppap-muted">凭证可先上传至“客户反馈”等文件夹，再在此选择。</small></el-form-item></el-form><template #footer><el-button :disabled="busy" @click="feedbackOpen = false">取消</el-button><el-button type="primary" :loading="busy" @click="saveFeedback">保存客户反馈</el-button></template></el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ArrowDown, ArrowLeft, Document, Folder, FolderAdd, Plus, Refresh, Search, Upload } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { useCompanyStore } from '@/stores/company'
import { ppapApi, ppapStatusLabels, type PpapDetail, type PpapFeedbackInput, type PpapFolder, type PpapLink, type PpapRow, type PpapStatus, type PpapSubmission, type PpapVersion } from '@/api/ppap'
import ArchiveForm from './ArchiveForm.vue'
import PreviewDialog from './PreviewDialog.vue'
import './ppap.css'

interface TreeNode { id: string; label: string; children: TreeNode[] }
interface FileRow { id: string; name: string; isFolder: boolean; linked_key?: string | null; version?: PpapVersion; versions?: PpapVersion[] }
const router = useRouter(), route = useRoute(), companyStore = useCompanyStore()
const company = computed(() => companyStore.selectedCompany), companyName = computed(() => company.value === 'tianyue' ? '天越' : '盖博')
const archiveId = computed(() => String(route.params.archiveId || ''))
const rows = ref<PpapRow[]>([]), total = ref(0), canWrite = ref(false), identityName = ref(''), detail = ref<PpapDetail | null>(null)
const search = ref(''), statusFilter = ref<PpapStatus | ''>(''), page = ref(1), loading = ref(false), error = ref(''), busy = ref(false), dialogError = ref('')
const activeTab = ref('files'), folderId = ref<string | null>(null), snapshotId = ref('')
const formOpen = ref(false), editArchive = ref<PpapDetail | null>(null)
const previewOpen = ref(false), previewVersion = ref<PpapVersion | null>(null), previewName = ref('')
const folderOpen = ref(false), folderName = ref(''), renamingFolder = ref<FileRow | null>(null)
const uploadOpen = ref(false), selectedFile = ref<File | null>(null), uploadName = ref(''), uploadLink = ref(''), uploadMode = ref<'new' | 'version'>('new')
const submissionOpen = ref(false), submissionDate = ref<string | null>(null), submissionRemark = ref('')
const feedbackOpen = ref(false), feedbackTarget = ref<PpapSubmission | null>(null)
const feedbackStatuses: Exclude<PpapStatus, 'preparing'>[] = ['submitted', 'supplement', 'temporary', 'approved', 'rejected']
const feedbackDraft = ref<PpapFeedbackInput>({ revision: 1, status: 'submitted', feedback: '', approved_date: null, valid_until: null, conditions: '', evidence_version_id: null })
let loadRequest = 0
const sourceFiltered = computed(() => Boolean(route.query.part_id || route.query.requirement_id || route.query.package_id))
const selectedSubmission = computed(() => detail.value?.submissions.find(s => s.id === snapshotId.value))
const snapshot = computed(() => selectedSubmission.value?.snapshot)
const visibleFolders = computed(() => snapshot.value?.folders || detail.value?.folders || [])
const visibleLinks = computed(() => snapshot.value?.links || detail.value?.links || [])
const folderTree = computed<TreeNode[]>(() => {
  const makeChildren = (parent: string | null): TreeNode[] => visibleFolders.value.filter(f => f.parent_id === parent).map(f => ({ id: f.id, label: f.name, children: makeChildren(f.id) }))
  return [{ id: 'root', label: '资料根目录', children: makeChildren(null) }]
})
const breadcrumbs = computed(() => {
  const chain: PpapFolder[] = [], visited = new Set<string>(); let id = folderId.value
  while (id && !visited.has(id)) { visited.add(id); const f = visibleFolders.value.find(item => item.id === id); if (!f) break; chain.unshift(f); id = f.parent_id }
  return chain
})
const fileRows = computed<FileRow[]>(() => {
  const folders: FileRow[] = visibleFolders.value.filter(f => f.parent_id === folderId.value).map(f => ({ id: f.id, name: f.name, isFolder: true }))
  const docs: FileRow[] = snapshot.value ? snapshot.value.documents.filter(d => d.folder_id === folderId.value).map(d => ({ ...d, isFolder: false })) : (detail.value?.documents || []).filter(d => d.folder_id === folderId.value).map(d => ({ id: d.id, name: d.name, linked_key: d.linked_key, isFolder: false, version: d.versions.find(v => v.version === d.current_version), versions: d.versions }))
  return [...folders, ...docs]
})
const uploadCollision = computed(() => detail.value?.documents.some(d => d.folder_id === folderId.value && d.name.toLowerCase() === uploadName.value.toLowerCase()))
const evidenceOptions = computed(() => (detail.value?.documents || []).flatMap(d => d.versions.map(v => ({ id: v.id, label: `${d.name} · V${v.version}` }))))
function today() { return new Intl.DateTimeFormat('en-CA', { timeZone: 'Asia/Shanghai', year: 'numeric', month: '2-digit', day: '2-digit' }).format(new Date()) }
function expired(status: PpapStatus, until?: string | null) { return status === 'temporary' && Boolean(until && until < today()) }
function statusType(status: PpapStatus) { return status === 'approved' ? 'success' : status === 'rejected' ? 'danger' : ['temporary', 'supplement'].includes(status) ? 'warning' : 'info' }
function fileSize(bytes: number) { return bytes >= 1024 * 1024 ? `${(bytes / 1024 / 1024).toFixed(1)} MB` : `${Math.max(1, Math.round(bytes / 1024))} KB` }
function formatTime(value: string) { return new Date(value.endsWith('Z') ? value : `${value}Z`).toLocaleString('zh-CN', { timeZone: 'Asia/Shanghai', hour12: false }) }
function linkLabel(key: string) { const l = visibleLinks.value.find(i => i.key === key); return l ? `${l.part_no} ${l.name}` : key }
async function loadLedger() {
  const request = ++loadRequest; loading.value = true; error.value = ''
  try { const result = await ppapApi.list({ company: company.value, search: search.value, status: statusFilter.value || undefined, page: page.value, part_id: route.query.part_id || undefined, requirement_id: route.query.requirement_id || undefined, package_id: route.query.package_id || undefined }); if (request === loadRequest) { rows.value = result.items; total.value = result.total; canWrite.value = result.can_write; identityName.value = result.identity.name } } catch (e) { if (request === loadRequest) { rows.value = []; total.value = 0; error.value = (e as Error).message } } finally { if (request === loadRequest) loading.value = false }
}
async function loadDetail() {
  const request = ++loadRequest; loading.value = true; error.value = ''; detail.value = null; canWrite.value = false
  try { const result = await ppapApi.detail(company.value, archiveId.value); if (request === loadRequest) { detail.value = result; canWrite.value = result.can_write; identityName.value = result.owner } } catch (e) { if (request === loadRequest) error.value = (e as Error).message } finally { if (request === loadRequest) loading.value = false }
}
function refresh() { if (archiveId.value) return loadDetail(); return loadLedger() }
function openArchive(row: PpapRow) { void router.push({ path: `/ppap/${row.id}`, query: { company: company.value } }) }
function backToList() { void router.push({ path: '/ppap', query: { company: company.value } }) }
function clearSourceFilter() { void router.replace({ path: '/ppap', query: { company: company.value } }) }
function resetDetailView() { folderId.value = null; snapshotId.value = ''; activeTab.value = 'files'; previewOpen.value = false; formOpen.value = false; folderOpen.value = false; uploadOpen.value = false; submissionOpen.value = false; feedbackOpen.value = false }
watch(() => route.fullPath, () => { const c = route.query.company; if ((c === 'gaibo' || c === 'tianyue') && c !== company.value) { companyStore.setCompany(c); return } resetDetailView(); void refresh() })
watch(company, () => { loadRequest++; rows.value = []; detail.value = null; canWrite.value = false; page.value = 1; resetDetailView(); if (route.query.company === company.value) void refresh(); else void router.replace({ path: '/ppap', query: { company: company.value } }) })
onMounted(() => { const c = route.query.company; if ((c === 'gaibo' || c === 'tianyue') && c !== company.value) companyStore.setCompany(c); else void refresh() })
function archiveSaved(result: PpapDetail) { if (archiveId.value === result.id) { detail.value = result; canWrite.value = result.can_write } else openArchive(result) }
function showPreview(name: string, version: PpapVersion) { previewName.value = name; previewVersion.value = version; previewOpen.value = true }
function activateFile(row: FileRow) { if (row.isFolder) folderId.value = row.id; else if (row.version) showPreview(row.name, row.version) }
function previewEvidence(id: string) { for (const d of detail.value?.documents || []) { const v = d.versions.find(v => v.id === id); if (v) { showPreview(d.name, v); return } } ElMessage.error('凭证文件版本未找到，请刷新重试') }
function openFolderDialog(folder?: FileRow) { renamingFolder.value = folder || null; folderName.value = folder?.name || ''; dialogError.value = ''; folderOpen.value = true }
async function mutate(operation: () => Promise<PpapDetail>, done: () => void) {
  if (busy.value) return
  busy.value = true; dialogError.value = ''
  const requestedCompany = company.value, requestedArchive = archiveId.value
  try { const result = await operation(); if (company.value === requestedCompany && archiveId.value === requestedArchive) { detail.value = result; canWrite.value = result.can_write; done(); ElMessage.success('已保存') } } catch (e) { dialogError.value = (e as Error).message } finally { busy.value = false }
}
function saveFolder() {
  const d = detail.value; if (!d) return
  return mutate(() => renamingFolder.value ? ppapApi.renameFolder(company.value, d.id, renamingFolder.value.id, { revision: d.revision, name: folderName.value }) : ppapApi.createFolder(company.value, d.id, { revision: d.revision, name: folderName.value, parent_id: folderId.value }), () => folderOpen.value = false)
}
function openUpload() { selectedFile.value = null; uploadName.value = ''; uploadLink.value = ''; uploadMode.value = 'new'; dialogError.value = ''; uploadOpen.value = true }
function chooseFile(event: Event) { const file = (event.target as HTMLInputElement).files?.[0]; selectedFile.value = file || null; uploadName.value = file?.name || ''; dialogError.value = '' }
function saveUpload() {
  const d = detail.value, file = selectedFile.value; if (!d) return
  if (!file || !uploadName.value.trim()) { dialogError.value = '请选择文件并填写保存文件名'; return }
  if (file.size > 100 * 1024 * 1024) { dialogError.value = '单个文件不能超过100MB'; return }
  if (uploadCollision.value && uploadMode.value === 'new') { dialogError.value = '请选择更新同名文件版本，或修改保存文件名'; return }
  const data = new FormData(); data.append('file', file, uploadName.value); data.append('revision', String(d.revision)); data.append('mode', uploadMode.value)
  if (folderId.value) data.append('folder_id', folderId.value)
  if (uploadLink.value) data.append('linked_key', uploadLink.value)
  return mutate(() => ppapApi.upload(company.value, d.id, data), () => uploadOpen.value = false)
}
function saveSubmission() { const d = detail.value; if (!d) return; return mutate(() => ppapApi.submit(company.value, d.id, { revision: d.revision, submitted_date: submissionDate.value || null, remark: submissionRemark.value }), () => submissionOpen.value = false) }
function openFeedback(s: PpapSubmission) { feedbackTarget.value = s; feedbackDraft.value = { revision: detail.value!.revision, status: s.status, feedback: s.feedback, approved_date: s.approved_date, valid_until: s.valid_until, conditions: s.conditions, evidence_version_id: s.evidence_version_id }; dialogError.value = ''; feedbackOpen.value = true }
function feedbackStatusChanged() { if (!['temporary', 'approved'].includes(feedbackDraft.value.status)) { feedbackDraft.value.approved_date = null; feedbackDraft.value.conditions = '' }; if (feedbackDraft.value.status !== 'temporary') feedbackDraft.value.valid_until = null }
function saveFeedback() { const d = detail.value, s = feedbackTarget.value; if (!d || !s) return; return mutate(() => ppapApi.feedback(company.value, d.id, s.id, { ...feedbackDraft.value, revision: d.revision, evidence_version_id: feedbackDraft.value.evidence_version_id || null }), () => feedbackOpen.value = false) }
</script>
