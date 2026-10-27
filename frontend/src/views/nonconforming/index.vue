<template>
  <div v-loading="store.loading || store.busy" class="quality-v1">
    <header class="quality-page-header">
      <div><p class="quality-eyebrow">不良品 / 异常处置</p><h1>不良品处理</h1><p class="quality-caption">从讨论方案到品质验收，跟踪每一批不良品的处理结果。</p></div>
      <el-button v-if="store.can('create')" type="primary" :icon="Plus" @click="openCreate">新增不良记录</el-button>
    </header>
    <el-alert v-if="store.loadError" :title="store.loadError" type="error" :closable="false" show-icon><el-button @click="store.reload">重试读取台账</el-button></el-alert>
    <section class="quality-stats" aria-label="不良品概览">
      <article><span>待确认</span><strong>{{ pendingRows.length }}<small>条</small></strong><p>讨论方案与处理顺序</p></article>
      <article><span>处理中</span><strong>{{ scopedRecords.filter(row => row.status === 'processing').length }}<small>条</small></strong><p>跟进执行进度</p></article>
      <article><span>已完成</span><strong>{{ scopedRecords.filter(row => row.status === 'closed').length }}<small>条</small></strong><p>查看处理结果与完成时间</p></article>
      <article :class="{ 'is-overdue': overdueRows.length }"><span>已逾期</span><strong>{{ overdueRows.length }}<small>条</small></strong><p>计划时间已过，尚未完成</p></article>
    </section>
    <section class="quality-panel">
      <el-tabs v-model="activeTab" class="quality-tabs">
        <el-tab-pane label="不良品台账" name="ledger">
          <div class="quality-toolbar">
            <el-input v-model="filters.search" :prefix-icon="Search" clearable aria-label="搜索不良记录" placeholder="搜索客户、零件号、异常或批次" />
            <el-select v-model="filters.disposition" clearable placeholder="处置方式" aria-label="筛选处置方式"><el-option v-for="key in dispositions" :key="key" :label="dispositionLabels[key]" :value="key" /></el-select>
            <el-select v-model="filters.source" clearable placeholder="发现来源" aria-label="筛选发现来源"><el-option v-for="source in sourceOptions" :key="source" :label="source" :value="source" /></el-select>
            <el-checkbox v-model="filters.overdue">仅看逾期</el-checkbox>
            <el-button :aria-expanded="advancedFilters" @click="advancedFilters = !advancedFilters">更多筛选{{ filters.quantityReview || dataScope !== 'all' ? ' · 已筛选' : '' }}</el-button>
            <span class="quality-toolbar-total">共 {{ filteredRows.length }} 条</span>
          </div>
          <div v-if="advancedFilters" class="quality-import-filters"><el-select v-model="dataScope" aria-label="数据范围"><el-option label="全部记录" value="all" /><el-option label="批量录入" value="imported" /><el-option label="手工新增" value="manual" /></el-select><el-checkbox v-model="filters.quantityReview">仅看数量待核对</el-checkbox></div>
          <div class="quality-status-filters" aria-label="按处理状态筛选">
            <button type="button" :class="{ active: !filters.status }" :aria-pressed="!filters.status" @click="filters.status = ''">全部 <b>{{ scopedRecords.length }}</b></button>
            <button v-for="status in statuses" :key="status" type="button" :class="{ active: filters.status === status }" :aria-pressed="filters.status === status" @click="filters.status = filters.status === status ? '' : status">{{ statusLabels[status] }} <b>{{ scopedRecords.filter(row => row.status === status).length }}</b></button>
          </div>
          <el-table :data="pagedRows" class="quality-ledger" row-key="id" :row-class-name="rowClass" @row-click="openDetail">
            <el-table-column label="顺序" width="65" align="center"><template #default="{ row }"><span class="quality-rank">{{ row.priority }}</span></template></el-table-column>
            <el-table-column label="产品 / 客户" min-width="195"><template #default="{ row }"><button type="button" class="quality-part-link" @click.stop="openDetail(row)">{{ row.partNo }}</button><div class="quality-secondary">{{ row.customer }} · {{ row.partName }}<span v-if="row.trace.stockForm"> · {{ row.trace.stockForm === 'single' ? '单件' : '成品' }}</span></div></template></el-table-column>
            <el-table-column label="异常描述" min-width="220"><template #default="{ row }"><div class="quality-description">{{ row.description || '未填写异常描述' }}</div><div v-if="row.source || row.batchNo || row.trace.productState" class="quality-secondary">{{ row.source }}<span v-if="row.batchNo"> · 批次 {{ row.batchNo }}</span><span v-if="row.trace.productState"> · {{ row.trace.productState }}</span></div></template></el-table-column>
            <el-table-column label="不良 / 待处理" width="140" align="right"><template #default="{ row }"><strong class="quality-number">{{ row.quantity > 0 ? number(row.quantity) : '待核对' }}</strong><div v-if="!row.quantityVerified" class="quality-secondary quality-warning">数量待核对</div><div v-else-if="row.status === 'closed'" class="quality-secondary">已完成</div><div v-else class="quality-secondary">剩余 {{ number(remainingQty(row)) }}</div></template></el-table-column>
            <el-table-column label="处理方案" min-width="155"><template #default="{ row }"><span class="quality-plan-label">{{ planLabel(row) }}</span><div v-if="row.status === 'processing' && activeStep(row)" class="quality-secondary">当前：{{ stepLabels[activeStep(row)!.kind] }}</div></template></el-table-column>
            <el-table-column label="状态 / 模具" width="133"><template #default="{ row }"><el-tag :type="statusType(row.status)" size="small" effect="light">{{ statusLabels[row.status as DefectStatus] }}</el-tag><div v-if="row.paused" class="quality-secondary quality-warning">原任务已暂停</div><div v-else-if="hasRework(row) && row.status !== 'closed'" class="quality-secondary" :class="{ 'quality-warning': !row.moldReady }">{{ row.moldReady ? '模具已就绪' : '模具未就绪' }}</div></template></el-table-column>
            <el-table-column label="计划 / 实际完成" width="165"><template #default="{ row }"><span class="quality-number" :class="{ 'quality-danger': isOverdue(row) }">{{ row.plannedDate || '待安排' }}</span><div class="quality-secondary">实际 {{ row.actualDate || '—' }}</div></template></el-table-column>
            <el-table-column label="操作" fixed="right" width="75"><template #default="{ row }"><el-button link type="primary" @click.stop="openDetail(row)">详情</el-button></template></el-table-column>
            <template #empty><el-empty description="没有符合条件的不良记录"><el-button @click="clearFilters">清除筛选</el-button></el-empty></template>
          </el-table>
          <div v-if="filteredRows.length > pageSize" class="quality-pagination"><el-pagination v-model:current-page="page" v-model:page-size="pageSize" :total="filteredRows.length" :page-sizes="[20, 50, 100]" layout="total, prev, pager, next, sizes" small /></div>
          <div class="quality-table-footer"><span>不良数量按整批登记，处理结果分次留痕。</span><span>品质统一管理 · 业务参与排序</span></div>
        </el-tab-pane>
        <el-tab-pane label="每周处理计划" name="weekly">
          <div class="quality-week-toolbar"><div><h2>本周执行，下周准备</h2><p>按计划完成日期安排整条任务，跟进本周执行与下周准备。</p></div><div class="quality-week-controls"><el-button :icon="ArrowLeft" aria-label="查看上一周" @click="shiftWeek(-1)" /><el-button @click="anchorWeek = mondayOf(today)">回到本周</el-button><el-button :icon="ArrowRight" aria-label="查看下一周" @click="shiftWeek(1)" /></div></div>
          <div class="quality-week-grid">
            <section v-for="(week, index) in displayedWeeks" :key="week" class="quality-week-column" :aria-label="`${index ? '下周准备' : '本周执行'} ${week}`">
              <header><div><span class="quality-eyebrow">{{ index ? '下周准备' : '本周执行' }}</span><h3>{{ weekRange(week) }}</h3></div><b>{{ weekRows(week).length }} 条</b></header>
              <div v-if="!weekRows(week).length" class="quality-week-empty"><el-icon><Calendar /></el-icon><p>这一周还没有任务</p><span>在待确认记录中填写计划完成时间。</span></div>
              <button v-for="row in weekRows(week)" :key="row.id" class="quality-week-card" type="button" @click="openDetail(row)">
                <div class="quality-card-top"><span class="quality-card-rank">{{ String(row.priority).padStart(2, '0') }}</span><strong>{{ row.partNo }}</strong><el-tag :type="statusType(row.status)" size="small">{{ statusLabels[row.status] }}</el-tag></div>
                <p>{{ row.customer }} · {{ row.partName }} <span>{{ number(row.quantity) }} 件</span></p>
                <div class="quality-card-bottom"><span>{{ planLabel(row) }} · {{ row.assignee || '负责人待定' }}</span><span :class="{ 'quality-danger': isOverdue(row) }">{{ row.plannedDate }} 完成</span></div>
                <div v-if="row.paused" class="quality-card-note quality-warning">原任务暂停，等待重新确认</div><div v-else-if="hasRework(row) && row.status !== 'closed'" class="quality-card-note">{{ row.moldReady ? '返工模具已就绪' : '开发准备：返工模具未就绪' }}</div>
              </button>
            </section>
          </div>
          <div class="quality-backlog"><h3>需重新安排 <span>{{ backlog.length }} 条</span></h3><p>未安排日期或计划已过期的记录，供周会讨论；确认后需先退回再调整。</p><div class="quality-backlog-items"><button v-for="row in backlog" :key="row.id" type="button" @click="openDetail(row)"><strong>{{ row.partNo }}</strong><span>{{ row.customer }} · {{ number(remainingQty(row)) }} 件</span><el-tag size="small" :type="statusType(row.status)">{{ statusLabels[row.status] }}</el-tag></button><span v-if="!backlog.length" class="quality-muted">当前没有待安排记录。</span></div></div>
        </el-tab-pane>
        <el-tab-pane label="排序与确认" name="priority">
          <div class="quality-section-intro"><h2>先讨论怎么处理，再确认执行顺序</h2><p>业务可调整待确认记录的相对顺序。确认后顺序锁定，品质、开发、业务填写原因后可退回。</p></div>
          <el-table :data="pendingRows" row-key="id" empty-text="当前没有待确认记录">
            <el-table-column label="顺序" width="75" align="center"><template #default="{ row }"><b class="quality-number">{{ row.priority }}</b></template></el-table-column>
            <el-table-column label="产品 / 客户" min-width="190"><template #default="{ row }"><button type="button" class="quality-part-link" @click="openDetail(row)">{{ row.partNo }}</button><div class="quality-secondary">{{ row.customer }} · {{ number(row.quantity) }} 件</div></template></el-table-column>
            <el-table-column label="讨论方案" min-width="240"><template #default="{ row }"><span>{{ planLabel(row) }}</span><div class="quality-description quality-secondary">{{ row.treatment || '尚未填写处理要求' }}</div></template></el-table-column>
            <el-table-column prop="plannedDate" label="计划完成" width="135" />
            <el-table-column label="调整顺序" width="135"><template #default="{ row, $index }"><el-button :icon="ArrowUp" :disabled="!store.can('priority') || $index === 0" :aria-label="`上移 ${row.partNo}`" @click="perform(() => store.move(row.id, -1, pendingRows.map(item => item.id)))" /><el-button :icon="ArrowDown" :disabled="!store.can('priority') || $index === pendingRows.length - 1" :aria-label="`下移 ${row.partNo}`" @click="perform(() => store.move(row.id, 1, pendingRows.map(item => item.id)))" /></template></el-table-column>
            <el-table-column label="操作" width="140"><template #default="{ row }"><el-button link type="primary" @click="openDetail(row)">讨论详情</el-button><el-button v-if="store.can('confirm')" link type="primary" @click="confirmRow(row)">确认</el-button></template></el-table-column>
          </el-table>
        </el-tab-pane>
      </el-tabs>
    </section>

    <el-drawer v-model="detailVisible" :title="selected ? `${selected.partNo} · 不良处理详情` : '不良处理详情'" size="min(760px, 100vw)" class="quality-drawer" @closed="clearDetailQuery">
      <template v-if="selected">
        <div class="quality-detail-heading"><span class="quality-muted">{{ selected.no }}</span><el-tag :type="statusType(selected.status)">{{ statusLabels[selected.status] }}</el-tag></div>
        <ol v-if="!selected.historicalCompletion" class="quality-flow" aria-label="处理流程"><li v-for="(status, index) in statuses" :key="status" :class="{ current: selected.status === status, complete: statuses.indexOf(selected.status) > index }"><span>{{ index + 1 }}</span>{{ statusLabels[status] }}</li></ol>
        <el-alert v-if="selected.paused" title="任务已暂停，重新讨论并确认后才可继续执行。已发生的处理记录保留。" type="warning" :closable="false" />
        <p v-else-if="selected.status !== 'pending_confirmation' && selected.status !== 'closed' && !needsPlanReview(selected)" class="quality-lock-note"><el-icon><Lock /></el-icon>确认内容和顺序已锁定，变更需填写原因并退回待确认。</p>
        <section class="quality-detail-section"><h3>不良信息</h3><dl class="quality-details-grid"><div><dt>客户</dt><dd>{{ selected.customer }}</dd></div><div><dt>零件号</dt><dd class="quality-number">{{ selected.partNo }}</dd></div><div><dt>零件名称</dt><dd>{{ selected.partName }}</dd></div><div><dt>生产批次</dt><dd>{{ selected.batchNo || '未填写' }}</dd></div><div><dt>发现来源</dt><dd>{{ selected.source || '待核对' }}</dd></div><div><dt>不良数量</dt><dd><b class="quality-number">{{ selected.quantity > 0 ? number(selected.quantity) + ' 件' : '待核对' }}</b><span v-if="!selected.quantityVerified" class="quality-warning"> · 数量未核实</span></dd></div></dl><p class="quality-detail-description">{{ selected.description || '异常描述未填写。' }}</p></section>
        <section class="quality-detail-section"><h3>处理方案</h3><p v-if="needsPlanReview(selected)" class="quality-warning">处理方案待完善，请退回待确认后补齐处理要求和验收标准。</p><dl class="quality-details-grid"><div><dt>处置方式</dt><dd>{{ selected.disposition ? dispositionLabels[selected.disposition] : '待讨论' }}</dd></div><div><dt>执行负责人</dt><dd>{{ selected.assignee || '待安排' }}</dd></div><div><dt>计划完成时间</dt><dd>{{ selected.plannedDate || '待安排' }}</dd></div><div><dt>实际完成时间</dt><dd>{{ selected.actualDate || '尚未完成' }}</dd></div></dl><p class="quality-detail-description">{{ selected.treatment || '等待讨论处理要求。' }}</p>
          <div v-if="hasRework(selected) && !selected.historicalCompletion" class="quality-mold-readiness"><div><el-icon><Tools /></el-icon><span>返工模具</span><strong :class="selected.moldReady ? 'quality-success' : 'quality-warning'">{{ selected.moldReady ? '已就绪' : '未就绪' }}</strong></div><el-button v-if="['pending', 'processing'].includes(selected.status) && store.can('prepare') && selected.planSteps.some(step => step.kind === 'rework' && !step.completedAt)" size="small" @click="perform(() => store.prepare(selected!.id, !selected!.moldReady), '已更新模具就绪情况')">{{ selected.moldReady ? '改为未就绪' : '标记已就绪' }}</el-button><router-link to="/tooling/rework">查看返工模档案 <el-icon><ArrowRight /></el-icon></router-link></div>
        </section>
        <DefectSupplementDetails :record="selected" :can-complete="store.can('submit') && !needsPlanReview(selected)" @complete="openStep" />
        <section class="quality-detail-section"><h3>处理数量 <small>品质验收后计入结果</small></h3><p v-if="selected.historicalCompletion" class="quality-muted">处理已完成，合格、报废等结果分项未登记。</p><p v-else-if="selected.importInfo && !selected.importInfo.reviewed" class="quality-muted">处理结果尚未登记。</p><p v-if="!selected.quantityVerified" class="quality-warning">实际数量待核对，暂不计入数量合计。</p><div v-if="!selected.importInfo || selected.importInfo.reviewed" class="quality-result-grid" :class="{ 'has-other': selected.otherQty }"><div><span>已验收合格</span><strong>{{ number(selected.acceptedQty) }}</strong></div><div><span>已确认报废</span><strong>{{ number(selected.scrappedQty) }}</strong></div><div v-if="selected.otherQty"><span>其他处置完成</span><strong>{{ number(selected.otherQty) }}</strong></div><div><span>剩余待处理</span><strong>{{ selected.quantityVerified ? number(remainingQty(selected)) : '待核对' }}</strong></div></div><div v-if="selected.submission" class="quality-submission"><b>本次待验收</b><span>合格 {{ number(selected.submission.good) }} 件 / 报废 {{ number(selected.submission.scrap) }} 件<span v-if="selected.submission.other"> / 其他处置 {{ number(selected.submission.other) }} 件</span></span><p>{{ selected.submission.note }}</p></div></section>
        <details class="quality-detail-section quality-record-history"><summary>处理历史 <small>共 {{ selected.history.length }} 条</small></summary><el-timeline class="quality-history"><el-timeline-item v-for="entry in selected.history" :key="entry.id" :timestamp="`${formatDateTime(entry.at)} · ${entry.actor}`" placement="top"><strong>{{ entry.action }}</strong><p>{{ entry.detail }}</p><details v-if="entry.snapshot"><summary>查看当时的方案与验收明细</summary><DefectHistorySnapshot :value="entry.snapshot" /></details></el-timeline-item></el-timeline></details>
        <details v-if="selected.importInfo" class="quality-detail-section quality-source-archive"><summary>来源资料</summary><WorkbookOriginDetails :origin="selected.importInfo" /></details>
      </template>
      <template #footer><div v-if="selected" class="quality-detail-actions"><el-button v-if="canReturn(selected)" type="warning" plain @click="openReturn">退回待确认</el-button><span class="quality-action-spacer" /><template v-if="selected.status === 'pending_confirmation'"><el-button v-if="store.can('edit')" @click="openEdit(selected)">编辑与讨论</el-button><el-button v-if="store.can('confirm')" type="primary" @click="confirmRow(selected)">确认方案</el-button></template><el-button v-if="selected.status === 'pending' && store.can('start')" type="primary" :disabled="(activeStep(selected)?.kind || selected.disposition) === 'rework' && !selected.moldReady" @click="perform(() => store.start(selected!.id), '任务已开始')">开始处理</el-button><el-button v-if="selected.status === 'processing' && store.can('submit')" type="primary" :disabled="!!activeStep(selected) || needsPlanReview(selected)" @click="openResult">提交品质验收</el-button><el-button v-if="selected.status === 'inspection' && store.can('inspect')" type="primary" @click="openInspection">品质验收</el-button><el-button v-if="selected.status === 'closed'" @click="detailVisible = false">关闭详情</el-button></div></template>
    </el-drawer>

    <el-dialog v-model="formVisible" :title="editingId ? '编辑待确认记录' : '新增不良记录'" width="min(760px, 94vw)" class="quality-dialog" :close-on-click-modal="false">
      <el-form ref="formRef" :model="form" :rules="formRules" label-position="top" @submit.prevent="saveForm">
        <div class="quality-form-grid"><el-form-item label="客户" prop="customer"><el-input v-model="form.customer" placeholder="客户名称" /></el-form-item><el-form-item label="零件号" prop="partNo"><el-input v-model="form.partNo" placeholder="客户零件号" /></el-form-item><el-form-item label="零件名称" prop="partName"><el-input v-model="form.partName" placeholder="零件名称" /></el-form-item><el-form-item label="生产批次"><el-input v-model="form.batchNo" placeholder="可稍后补充" /></el-form-item><el-form-item label="发现来源" prop="source"><el-select v-model="form.source"><el-option v-for="source in sourceOptions" :key="source" :label="source" :value="source" /></el-select></el-form-item><el-form-item label="不良数量（件）" prop="quantity"><el-input-number v-model="form.quantity" :min="editingOrigin ? 0 : 1" :max="1000000000" :precision="0" controls-position="right" /></el-form-item></div>
        <el-form-item label="异常描述" prop="description"><el-input v-model="form.description" type="textarea" :rows="3" maxlength="2000" show-word-limit placeholder="填写标准要求及发现时的实测情况" /></el-form-item>
        <div v-if="editingOrigin && editingOrigin.quantityNote" class="quality-quantity-review"><p>{{ editingOrigin.quantityNote }}</p><el-checkbox v-model="form.quantityVerified">已核实本条实际不良数量，排除预计退货与重复数量</el-checkbox></div>
        <DefectTraceFields :draft="form" />
        <div class="quality-form-divider"><strong>讨论方案与计划</strong><span>新增时可暂不填写，确认前须补齐。</span></div>
        <div class="quality-form-grid"><el-form-item label="处置方式"><el-select v-model="form.disposition" clearable placeholder="讨论后选择" @change="syncDisposition"><el-option v-for="key in dispositions" :key="key" :label="dispositionLabels[key]" :value="key" /></el-select></el-form-item><el-form-item label="执行负责人"><el-input v-model="form.assignee" placeholder="姓名或执行班组" maxlength="80" /></el-form-item></div>
        <el-form-item label="处理要求"><el-input v-model="form.treatment" type="textarea" :rows="3" maxlength="2000" show-word-limit placeholder="明确怎么处理，以及品质验收要求" /></el-form-item>
        <div class="quality-form-grid"><el-form-item label="计划完成时间"><el-date-picker v-model="form.plannedDate" type="date" value-format="YYYY-MM-DD" placeholder="选择计划完成日期" @change="syncWeek" /></el-form-item><el-form-item label="任务周"><div class="quality-form-readonly">{{ form.plannedDate ? weekRange(mondayOf(form.plannedDate)) : '选择计划日期后自动归入对应周' }}</div></el-form-item></div>
        <DefectPlanFields :draft="form" />
        <el-alert v-if="formError" :title="formError" type="error" :closable="false" show-icon />
      </el-form>
      <template #footer><el-button @click="formVisible = false">取消</el-button><el-button type="primary" :loading="saving" @click="saveForm">保存待确认记录</el-button></template>
    </el-dialog>
    <el-dialog v-model="returnVisible" title="退回待确认" width="min(500px, 94vw)" class="quality-dialog" :close-on-click-modal="false"><p class="quality-modal-description">原执行任务将暂停。已发生的处理数量、模具就绪情况及确认历史会保留。</p><el-form label-position="top"><el-form-item label="退回原因" required><el-input v-model="returnReason" type="textarea" :rows="4" maxlength="500" show-word-limit placeholder="说明方案、数量或执行顺序为何需要重新讨论" /></el-form-item></el-form><el-alert v-if="actionError" :title="actionError" type="error" :closable="false" /><template #footer><el-button @click="returnVisible = false">取消</el-button><el-button type="warning" @click="submitReturn">确认退回</el-button></template></el-dialog>
    <el-dialog v-model="resultVisible" title="提交处理结果" width="min(530px, 94vw)" class="quality-dialog" :close-on-click-modal="false"><p class="quality-modal-description">剩余待处理 {{ number(selected ? remainingQty(selected) : 0) }} 件。填写本次完成数量，品质验收后计入结果。</p><el-form label-position="top"><el-form-item v-if="selected?.disposition !== 'scrap' && selected?.disposition !== 'other'" label="本次处理合格数量（件）" required><el-input-number v-model="result.good" :min="0" :precision="0" :max="selected ? remainingQty(selected) : 0" /></el-form-item><el-form-item v-else-if="selected?.disposition === 'scrap'" label="本次报废数量（件）" required><el-input-number v-model="result.scrap" :min="0" :precision="0" :max="selected ? remainingQty(selected) : 0" /></el-form-item><el-form-item v-else label="本次按方案完成数量（件）" required><el-input-number v-model="result.other" :min="0" :precision="0" :max="selected ? remainingQty(selected) : 0" /></el-form-item><el-form-item label="处理结果说明" required><el-input v-model="result.note" type="textarea" :rows="3" maxlength="1000" placeholder="填写实际处理情况及需要品质核实的事项" /></el-form-item></el-form><p class="quality-modal-description">剩余产品需改用其他方式处理时，请先退回待确认。</p><el-alert v-if="actionError" :title="actionError" type="error" :closable="false" /><template #footer><el-button @click="resultVisible = false">取消</el-button><el-button type="primary" @click="submitExecution">提交验收</el-button></template></el-dialog>
    <el-dialog v-model="inspectionVisible" title="品质验收" width="min(660px, 94vw)" class="quality-dialog" :close-on-click-modal="false"><div v-if="selected?.submission" class="quality-submission"><b>本次提交</b><span>合格 {{ number(selected.submission.good) }} 件 / 报废 {{ number(selected.submission.scrap) }} 件<span v-if="selected.submission.other"> / 其他处置 {{ number(selected.submission.other) }} 件</span></span><p>{{ selected.submission.note }}</p></div><el-form label-position="top"><DefectInspectionFields v-if="selected" :record="selected" :evidence="inspectionEvidence" /><el-form-item label="验收结论"><el-radio-group v-model="inspectionPassed"><el-radio :value="true">通过</el-radio><el-radio :value="false">不通过，继续处理</el-radio></el-radio-group></el-form-item><el-form-item label="品质验收意见" required><el-input v-model="inspectionNote" type="textarea" :rows="3" maxlength="1000" placeholder="记录验收依据、结果或不通过原因" /></el-form-item></el-form><p class="quality-modal-description">{{ !inspectionPassed ? '本次结果不计入已验收数量，返回处理中，重新记录处理步骤。' : willClose ? '数量核对及全部项目通过后关闭记录，填写实际完成日期。' : '本次通过后保留已验收数量；剩余数量继续执行本方案，处理步骤重新记录。' }}</p><el-alert v-if="actionError" :title="actionError" type="error" :closable="false" /><template #footer><el-button @click="inspectionVisible = false">取消</el-button><el-button type="primary" @click="submitInspection">{{ willClose && inspectionPassed ? '验收通过并关闭' : '保存验收结果' }}</el-button></template></el-dialog>
    <el-dialog v-model="stepVisible" title="记录本步完成" width="min(500px, 94vw)" class="quality-dialog" :close-on-click-modal="false"><p class="quality-modal-description">{{ currentStep ? `${stepLabels[currentStep.kind]}：${currentStep.requirement}` : '' }}</p><el-form label-position="top"><el-form-item label="本步实际处理情况" required><el-input v-model="stepNote" type="textarea" :rows="4" maxlength="1000" placeholder="记录执行情况；完成步骤后继续下一步，数量在品质验收后确认" /></el-form-item></el-form><el-alert v-if="actionError" :title="actionError" type="error" :closable="false" /><template #footer><el-button @click="stepVisible = false">取消</el-button><el-button type="primary" @click="submitStep">保存本步完成</el-button></template></el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox, type FormInstance, type FormRules } from 'element-plus'
import { ArrowDown, ArrowLeft, ArrowRight, ArrowUp, Calendar, Lock, Plus, Search, Tools } from '@element-plus/icons-vue'
import DefectTraceFields from './DefectTraceFields.vue'
import DefectPlanFields from './DefectPlanFields.vue'
import DefectSupplementDetails from './DefectSupplementDetails.vue'
import DefectHistorySnapshot from './DefectHistorySnapshot.vue'
import DefectInspectionFields from './DefectInspectionFields.vue'
import WorkbookOriginDetails from './WorkbookOriginDetails.vue'
import { useNonconformingPreview } from '@/stores/nonconformingPreview'
import { useCompanyStore } from '@/stores/company'
import { activeStep, businessDate, dispositionLabels, dispositions, draftFrom, emptyDefectDraft, hasRework, makeInspectionItem, makeStep, mondayOf, planLabel, remainingQty, stepLabels, submittedQty, sourceOptions, statuses, statusLabels, type DefectDraft, type DefectRecord, type DefectStatus, type InspectionEvidence } from '@/domain/nonconforming'
import '@/styles/nonconforming.css'

const route = useRoute(); const router = useRouter()
const company = useCompanyStore()
const linkedCompany = route.query.company
if (linkedCompany === 'tianyue' || linkedCompany === 'gaibo') company.setCompany(linkedCompany)
const store = useNonconformingPreview()
watch(() => route.query.company, value => {
  if ((value === 'tianyue' || value === 'gaibo') && value !== company.selectedCompany) company.setCompany(value)
}, { flush: 'sync' })
onMounted(() => { void store.reload() })
const today = businessDate(); const activeTab = ref('ledger'); const anchorWeek = ref(mondayOf(today))
const dataScope = ref(route.query.scope === 'manual' ? 'manual' : route.query.scope === 'imported' ? 'imported' : 'all')
const advancedFilters = ref(false)
const scopedRecords = computed(() => store.records.filter(row => dataScope.value === 'all' || (dataScope.value === 'imported' ? !!row.importInfo : !row.importInfo)))
const filters = reactive({ search: '', status: '' as DefectStatus | '', disposition: '', source: '', overdue: false, quantityReview: false })
const number = (value: number) => new Intl.NumberFormat('zh-CN').format(value || 0)
const statusType = (status: DefectStatus) => ({ pending_confirmation: 'warning', pending: 'info', processing: 'primary', inspection: 'warning', closed: 'success' })[status] as 'warning' | 'info' | 'primary' | 'success'
const isOverdue = (record: DefectRecord) => record.status !== 'closed' && !!record.plannedDate && record.plannedDate < today
const openRecords = computed(() => scopedRecords.value.filter(row => row.status !== 'closed'))
const pendingRows = computed(() => scopedRecords.value.filter(row => row.status === 'pending_confirmation'))
const overdueRows = computed(() => scopedRecords.value.filter(isOverdue))
const filteredRows = computed(() => scopedRecords.value.filter(row => {
  const text = `${row.customer} ${row.partNo} ${row.partName} ${row.description} ${row.batchNo} ${row.no} ${Object.values(row.trace).join(' ')} ${row.quantityLots.map(lot => `${lot.batch} ${lot.container}`).join(' ')} ${row.release.destination} ${row.release.outputPartNo}`.toLowerCase()
  return (!filters.search || text.includes(filters.search.trim().toLowerCase())) && (!filters.status || row.status === filters.status) && (!filters.disposition || row.disposition === filters.disposition || row.planSteps.some(step => step.kind === filters.disposition)) && (!filters.source || row.source === filters.source) && (!filters.overdue || isOverdue(row)) && (!filters.quantityReview || !row.quantityVerified)
}))
const page = ref(1); const pageSize = ref(20)
const pagedRows = computed(() => filteredRows.value.slice((page.value - 1) * pageSize.value, page.value * pageSize.value))
watch([filters, dataScope, pageSize], () => { page.value = 1 }, { deep: true })
watch(() => store.records, () => { if ((page.value - 1) * pageSize.value >= filteredRows.value.length) page.value = 1 })
const rowClass = ({ row }: { row: DefectRecord }) => row.status === 'closed' ? 'quality-row-closed' : ''
const clearFilters = () => Object.assign(filters, { search: '', status: '', disposition: '', source: '', overdue: false, quantityReview: false })
const displayedWeeks = computed(() => [anchorWeek.value, mondayOf(anchorWeek.value, 1)])
const weekRows = (week: string) => scopedRecords.value.filter(row => row.status !== 'closed' && row.week === week)
const backlog = computed(() => openRecords.value.filter(row => !row.week || row.week < mondayOf(today)))
const shiftWeek = (offset: number) => { anchorWeek.value = mondayOf(anchorWeek.value, offset) }
function weekRange(week: string) { const end = new Date(`${week}T12:00:00Z`); end.setUTCDate(end.getUTCDate() + 6); return `${week.slice(5).replace('-', '/')} — ${end.toISOString().slice(5, 10).replace('-', '/')}` }
function formatDateTime(value: string) { return new Intl.DateTimeFormat('zh-CN', { timeZone: 'Asia/Shanghai', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' }).format(new Date(value)) }
async function perform(action: () => void | Promise<void>, message = '') { try { await action(); if (message) ElMessage.success(message); return true } catch (error) { ElMessage.error(error instanceof Error ? error.message : '操作未保存，请重试'); return false } }

const detailVisible = ref(false); const selectedId = ref('')
const selected = computed(() => store.records.find(row => row.id === selectedId.value))
watch(() => company.selectedCompany, () => { detailVisible.value = false; selectedId.value = '' }, { flush: 'sync' })
function openDetail(row: DefectRecord) { selectedId.value = row.id; detailVisible.value = true; void router.replace({ query: { ...route.query, company: company.selectedCompany, record: row.id } }) }
function clearDetailQuery() { if (route.query.record) { const query = { ...route.query }; delete query.record; void router.replace({ query }) } }
watch(() => [route.query.record, store.records] as const, ([id]) => { if (typeof id === 'string') { const row = store.records.find(item => item.id === id); if (row) { selectedId.value = row.id; detailVisible.value = true } } }, { immediate: true })
const needsPlanReview = (row: DefectRecord) => !!row.importedProgress && !row.importInfo?.reviewed
const canReturn = (row: DefectRecord) => store.can('return') && ['pending', 'processing', 'inspection'].includes(row.status)

const emptyDraft = emptyDefectDraft
const form = reactive<DefectDraft>(emptyDraft()); const formRef = ref<FormInstance>(); const formVisible = ref(false); const editingId = ref(''); const formError = ref(''); const saving = ref(false)
const editingOrigin = computed(() => store.records.find(row => row.id === editingId.value)?.importInfo)
const formRules: FormRules = Object.fromEntries(['customer', 'partNo', 'partName', 'description', 'source'].map(key => [key, [{ required: true, whitespace: true, message: '请填写此项', trigger: 'blur' }]]))
function openCreate() { editingId.value = ''; formError.value = ''; Object.assign(form, emptyDraft()); formVisible.value = true; void nextTick(() => formRef.value?.clearValidate()) }
function openEdit(row: DefectRecord) { editingId.value = row.id; formError.value = ''; Object.assign(form, draftFrom(row)); formVisible.value = true; void nextTick(() => formRef.value?.clearValidate()) }
function syncDisposition() {
  if (form.disposition && form.planSteps.length <= 1) form.planSteps = [makeStep(form.disposition, form.planSteps[0]?.requirement || '')]
  if (form.disposition && !form.inspectionItems.length) form.inspectionItems = [makeInspectionItem('处置结果', '')]
}
const syncWeek = () => { form.week = form.plannedDate ? mondayOf(form.plannedDate) : '' }
async function saveForm() {
  if (!await formRef.value?.validate().catch(() => false)) return
  saving.value = true; formError.value = ''
  try {
    syncWeek()
    if (editingId.value) await store.edit(editingId.value, { ...form })
    else { const id = await store.create({ ...form }); dataScope.value = 'all'; selectedId.value = id; detailVisible.value = true }
    formVisible.value = false; ElMessage.success('已保存，等待讨论确认')
  } catch (error) { formError.value = error instanceof Error ? error.message : '保存失败' }
  finally { saving.value = false }
}
async function confirmRow(row: DefectRecord) {
  try {
    await ElMessageBox.confirm(`确认 ${row.partNo} 的处理方案与顺序？确认后内容和顺序锁定，变更需填写原因并退回。`, '确认处理方案', { confirmButtonText: '确认并锁定', cancelButtonText: '继续讨论', type: 'info' })
    await perform(() => store.confirm(row.id), '处理方案已确认，内容和顺序已锁定')
  } catch { /* Cancellation keeps the record unchanged. */ }
}
const returnVisible = ref(false); const returnReason = ref(''); const actionError = ref('')
function openReturn() { returnReason.value = ''; actionError.value = ''; returnVisible.value = true }
async function submitReturn() { if (!selected.value) return; try { await store.sendBack(selected.value.id, returnReason.value); returnVisible.value = false; ElMessage.success('已退回待确认，原任务暂停') } catch (error) { actionError.value = error instanceof Error ? error.message : '退回失败' } }
const resultVisible = ref(false); const result = reactive({ good: 0, scrap: 0, other: 0, note: '' })
function openResult() { if (!selected.value) return; Object.assign(result, { good: ['scrap', 'other'].includes(selected.value.disposition) ? 0 : remainingQty(selected.value), scrap: selected.value.disposition === 'scrap' ? remainingQty(selected.value) : 0, other: selected.value.disposition === 'other' ? remainingQty(selected.value) : 0, note: '' }); actionError.value = ''; resultVisible.value = true }
async function submitExecution() { if (!selected.value) return; try { await store.submit(selected.value.id, { ...result }); resultVisible.value = false; ElMessage.success('已提交品质验收') } catch (error) { actionError.value = error instanceof Error ? error.message : '提交失败' } }
const inspectionVisible = ref(false); const inspectionPassed = ref(true); const inspectionNote = ref('')
const inspectionEvidence = reactive<InspectionEvidence>({ checks: [], quantityChecked: false, releaseChecked: false })
const willClose = computed(() => !!selected.value?.submission && submittedQty(selected.value.submission) === remainingQty(selected.value))
function openInspection() { if (!selected.value) return; Object.assign(inspectionEvidence, { checks: selected.value.inspectionItems.map(item => ({ id: item.id, actual: '', passed: null })), quantityChecked: false, releaseChecked: false }); inspectionPassed.value = true; inspectionNote.value = ''; actionError.value = ''; inspectionVisible.value = true }
async function submitInspection() { if (!selected.value) return; try { await store.inspect(selected.value.id, inspectionPassed.value, inspectionNote.value, JSON.parse(JSON.stringify(inspectionEvidence))); inspectionVisible.value = false; ElMessage.success('品质验收结果已保存') } catch (error) { actionError.value = error instanceof Error ? error.message : '验收失败' } }
const stepVisible = ref(false); const stepId = ref(''); const stepNote = ref('')
const currentStep = computed(() => selected.value?.planSteps.find(step => step.id === stepId.value))
function openStep(id: string) { stepId.value = id; stepNote.value = ''; actionError.value = ''; stepVisible.value = true }
async function submitStep() { if (!selected.value) return; try { await store.finishStep(selected.value.id, stepId.value, stepNote.value); stepVisible.value = false; ElMessage.success('本步完成情况已保存') } catch (error) { actionError.value = error instanceof Error ? error.message : '保存失败' } }
</script>
