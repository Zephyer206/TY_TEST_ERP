<template>
  <div class="after-sales-page">
    <nav class="company-navigation" aria-label="公司与盖博档案类型">
      <el-select v-model="companyStore.selectedCompany" aria-label="所属公司" @change="handleCompanyChange">
        <el-option label="天越" value="tianyue" />
        <el-option label="盖博" value="gaibo" />
      </el-select>
      <el-segmented v-model="filters.recordType" :options="recordTypeOptions" aria-label="盖博档案类型" @change="selectRecordType" />
      <span class="company-scope-note">盖博档案按单件和安装包管理</span>
    </nav>

    <header class="archive-toolbar">
      <div class="archive-heading">
        <h1>{{ archiveTitle }}</h1>
        <span>{{ archiveSubtitle }}</span>
      </div>
      <label class="archive-search">
        <el-icon aria-hidden="true"><Search /></el-icon>
        <el-input v-model="filters.q" clearable aria-label="搜索售后档案" placeholder="搜索客户件号、安装包号、D code、天悦 PN、IBI 或天越内部组成" @keyup.enter="applyFilters" />
      </label>
      <div class="archive-filters" aria-label="售后档案筛选">
        <el-select v-model="filters.status" clearable placeholder="全部状态" aria-label="资料状态" @change="applyFilters">
          <el-option label="进行中" value="in_progress" />
          <el-option label="OK" value="ok" />
          <el-option label="NOT OK" value="not_ok" />
        </el-select>
        <el-tooltip content="刷新档案" placement="bottom"><el-button class="icon-button" :loading="loading" :icon="Refresh" aria-label="刷新售后档案" @click="loadWorkspace" /></el-tooltip>
        <el-tooltip content="视图设置" placement="bottom"><el-button class="icon-button" :icon="Setting" aria-label="打开视图设置" @click="openViewSettings" /></el-tooltip>
      </div>
    </header>

    <div class="archive-summary" aria-live="polite">
      <span>当前 <strong>{{ total }}</strong> 条</span>
      <span>已确认价格 <strong>{{ summary.priced_records }}</strong> 条</span>
      <span :class="{ warning: summary.missing_price_records }">待确认价格 <strong>{{ summary.missing_price_records }}</strong> 条</span>
      <span class="ok">图纸通过 <strong>{{ summary.drawing_ok_records }}</strong> 款</span>
      <span class="ok">样件通过 <strong>{{ summary.sample_ok_records }}</strong> 款</span>
      <span class="ok">PPAP 通过 <strong>{{ summary.ppap_ok_records }}</strong> 款</span>
      <el-button v-if="hasActiveFilters" link type="primary" size="small" @click="resetFilters">清除筛选</el-button>
    </div>

    <div v-if="errorMessage" class="error-state" role="alert" aria-live="assertive">
      <span>{{ errorMessage }}</span>
      <el-button link @click="loadWorkspace">重新加载</el-button>
    </div>

    <section class="record-panel" v-loading="loading" :aria-busy="loading">
      <ExcelGrid ref="excelGridRef" v-if="records.length" :data="records" :columns="excelColumns" height="100%" :loading="loading" row-key="record_id" aria-label="售后档案列表" @row-click="openRecord" @sort-change="handleExcelSortChange" @filter-change="handleExcelFilterChange" @column-resize="handleExcelColumnResize" @column-order-change="handleExcelColumnOrderChange">
        <template #cell="{ row, column }">
            <template v-if="isInlineEditing(row, column.key)"><el-input ref="inlineInput" v-model="inlineDraft" size="small" :type="columnDefinitions[column.key]?.dataType === 'number' || column.key === 'price' || column.key === 'priority' ? 'number' : 'text'" autofocus @click.stop @keyup.enter.stop="commitInlineEdit" @keyup.esc.stop="cancelInlineEdit" @blur="commitInlineEdit" /></template>
            <template v-else>
              <span v-if="column.key === 'type'" class="type-mark" :class="row.record_type">{{ row.record_type === 'single_part' ? '单件' : '安装包' }}</span>
              <span v-else-if="column.key === 'workspace'">{{ workspaceDisplayName(row.workspace_name) }}</span>
              <button v-else-if="column.key === 'primaryNumber'" class="record-link mono" type="button" @click.stop="handlePrimaryClick(row)" @dblclick.stop="handlePrimaryDoubleClick(row)">{{ row.customer_part_number || '未填写' }}</button>
              <span v-else-if="column.key === 'priority'" class="priority-text" @dblclick.stop="startInlineEdit(row, column.key)">{{ row.priority ? `P${row.priority}` : '—' }}</span>
              <span v-else-if="column.key === 'dCode'" class="mono" @dblclick.stop="startInlineEdit(row, column.key)">{{ row.d_code || '—' }}</span>
              <span v-else-if="column.key === 'tianyuePn'" class="mono" @dblclick.stop="startInlineEdit(row, column.key)">{{ row.tianyue_pn || '—' }}</span>
              <span v-else-if="column.key === 'internalComposition'" class="component-inline mono" @dblclick.stop="startInlineEdit(row, column.key)"><template v-if="row.component_items?.length"><template v-for="(item, index) in row.component_items" :key="`internal-${item.sequence}`"><span v-if="index" class="component-separator"> + </span><span :class="['component-token', `component-token-${item.status || 'unset'}`]">{{ componentLabel(item.tianyue_internal_composition, item.quantity) }}</span></template></template><template v-else>{{ row.tianyue_internal_composition || '—' }}</template></span>
              <span v-else-if="column.key === 'ibi'" class="component-inline mono" @dblclick.stop="startInlineEdit(row, column.key)"><template v-if="row.component_items?.length"><template v-for="(item, index) in row.component_items" :key="`ibi-${item.sequence}`"><span v-if="index" class="component-separator"> + </span><span :class="['component-token', `component-token-${item.status || 'unset'}`]">{{ componentIbiLabel(item.ibi, item.quantity) }}</span></template></template><template v-else>{{ row.ibi || '—' }}</template></span>
              <span v-else-if="column.key === 'status'" class="package-status" :title="statusTooltip(row)"><span><i :class="`status-dot-${normalizedStatus(row.drawing_status)}`" />图纸</span><span><i :class="`status-dot-${normalizedStatus(row.sample_status)}`" />样件</span><span><i :class="`status-dot-${normalizedStatus(row.ppap_status)}`" />PPAP</span></span>
              <span v-else-if="column.key === 'price'" class="price-cell" @dblclick.stop="startInlineEdit(row, column.key)"><span :class="['numeric', { 'price-mismatch': row.price_mismatch }]">{{ formatPrice(row.price) }}</span><span v-if="row.price_mismatch" class="price-mismatch-mark" title="FMG Price 与 FCA 价格不一致">差</span></span>
              <span v-else-if="column.key === 'remark'" @dblclick.stop="startInlineEdit(row, column.key)">{{ row.remark || '—' }}</span>
              <span v-else-if="column.key === 'updatedAt'">{{ formatDate(row.updated_at) }}</span>
              <span v-else-if="columnDefinitions[column.key]?.custom" :class="{ numeric: columnDefinitions[column.key]?.dataType === 'number' }" @dblclick.stop="startInlineEdit(row, column.key)">{{ formatCustomValue(row.extra_data?.[column.key], columnDefinitions[column.key]) }}</span>
            </template>
        </template>
      </ExcelGrid>
      <el-empty v-else description="暂无匹配的售后档案" />
      <div class="mobile-record-list" v-if="records.length">
        <button v-for="row in records" :key="recordRowKey(row)" type="button" class="mobile-record-row" @click="openRecord(row)">
          <span class="mobile-record-main"><strong class="mono">{{ row.customer_part_number }}</strong><small>{{ workspaceDisplayName(row.workspace_name) }} · {{ row.record_type === 'single_part' ? '单件' : '安装包' }}</small><span class="mono">{{ row.tianyue_internal_composition || '—' }}</span></span>
          <span class="mobile-record-meta"><span :class="['numeric', { 'price-mismatch': row.price_mismatch }]">{{ formatPrice(row.price) }}</span><span>{{ overallStatusLabel(row) }}</span></span>
        </button>
      </div>
      <footer class="record-pagination">
        <span>第 {{ currentPage }} / {{ Math.max(1, Math.ceil(total / pageSize)) }} 页</span>
        <el-pagination v-model:current-page="currentPage" v-model:page-size="pageSize" :page-sizes="[20, 50, 100]" :total="total" layout="sizes, prev, pager, next" size="small" @size-change="handlePageSizeChange" @current-change="changePage" />
      </footer>
    </section>

    <el-drawer v-model="settingsOpen" :before-close="closeViewSettings" :title="filters.workspaceId ? `${selectedWorkspaceName} · 表格配置` : '视图设置'" size="520px" class="view-settings-drawer">
      <div class="view-settings-body">
        <section v-if="filters.workspaceId" class="workspace-template-intro"><div class="settings-section-heading"><div><h3>客户字段模板</h3><span>配置对该客户的所有售后档案生效</span></div><el-button :icon="Plus" size="small" @click="addCustomColumn">新增选项</el-button></div><p>隐藏列不会删除数据；删除自定义列会停用字段，历史值仍保留并可恢复。</p></section>
        <section v-if="filters.workspaceId"><div class="settings-section-heading"><h3>详情标题</h3><span>对该客户的所有售后档案生效</span></div><el-input v-model="detailSectionLabelDraft" maxlength="50" placeholder="核心字段" aria-label="核心字段标题" /></section>
        <section><h3>显示密度</h3><el-segmented v-model="viewConfig.density" :options="densityOptions" block /></section>
        <section><h3>默认排序</h3><div class="sort-setting"><el-select v-model="viewConfig.sortKey"><el-option v-for="option in sortOptions" :key="option.value" :label="option.label" :value="option.value" /></el-select><el-select v-model="viewConfig.sortOrder"><el-option label="升序" value="asc" /><el-option label="降序" value="desc" /></el-select></div></section>
        <section><div class="settings-section-heading"><h3>列表字段</h3><span>可见性 · 名称 · 列宽 · 顺序</span></div><div class="column-setting-list"><article v-for="(key, index) in viewConfig.order" :key="key" :class="['column-setting-item', { custom: isCustomColumnKey(key) }]"><div class="column-setting-row"><el-checkbox :model-value="viewConfig.visible.includes(key)" :disabled="key === 'primaryNumber'" :aria-label="`显示${columnDefinitions[key]?.label || key}`" @change="toggleColumn(key, Boolean($event))" /><el-input :model-value="columnDraftLabel(key)" size="small" maxlength="50" :aria-label="`${columnDefinitions[key]?.label || key}显示名称`" @input="updateColumnDraftLabel(key, String($event))" /><el-input-number v-model="viewConfig.widths[key]" :min="56" :max="420" :step="8" :controls="false" :aria-label="`${columnDefinitions[key]?.label || key}列宽`" /><div class="column-move-actions"><el-button text :icon="ArrowUp" :disabled="index === 0" :aria-label="`上移${columnDefinitions[key]?.label || key}`" @click="moveColumn(index, -1)" /><el-button text :icon="ArrowDown" :disabled="index === viewConfig.order.length - 1" :aria-label="`下移${columnDefinitions[key]?.label || key}`" @click="moveColumn(index, 1)" /></div><el-button v-if="isCustomColumnKey(key)" text type="danger" :icon="Delete" :aria-label="`停用${columnDefinitions[key]?.label || key}`" title="停用并从列表移除" @click="archiveCustomColumn(key)" /></div><div v-if="isCustomColumnKey(key)" class="custom-column-options"><el-select :model-value="customFieldByKey(key)?.data_type" size="small" :disabled="isPersistedCustomField(key)" aria-label="字段类型" @change="updateCustomField(key, 'data_type', $event)"><el-option label="文本" value="text" /><el-option label="数字" value="number" /><el-option label="日期" value="date" /><el-option label="是 / 否" value="boolean" /><el-option label="单选" value="select" /></el-select><el-select :model-value="customFieldByKey(key)?.scope" size="small" :disabled="isPersistedCustomField(key)" aria-label="适用档案" @change="updateCustomField(key, 'scope', $event)"><el-option label="单件与安装包" value="both" /><el-option label="仅单件" value="single_part" /><el-option label="仅安装包" value="installation_package" /></el-select><el-input v-if="customFieldByKey(key)?.data_type === 'select'" :model-value="customFieldByKey(key)?.options.join('、')" size="small" placeholder="选项，用、分隔" aria-label="单选字段选项" @input="updateCustomFieldOptions(key, String($event))" /></div></article></div><div v-if="archivedCustomFields.length" class="archived-fields"><h4>已停用字段</h4><div v-for="field in archivedCustomFields" :key="field.key"><span>{{ field.label }}</span><el-button link type="primary" size="small" @click="restoreCustomColumn(field.key)">恢复</el-button></div></div></section>
      </div>
      <template #footer><div class="settings-footer"><el-button link @click="resetViewConfig">恢复默认</el-button><span class="settings-footer-actions"><el-button @click="closeViewSettings">取消</el-button><el-button type="primary" :loading="viewSaving" @click="saveViewSettings">{{ filters.workspaceId ? '保存客户表格' : '保存为我的视图' }}</el-button></span></div></template>
    </el-drawer>

    <el-drawer v-model="drawerOpen" :before-close="requestDrawerClose" :with-header="false" size="min(960px, 94vw)" destroy-on-close class="gaibo-drawer">
      <div v-if="detailLoading" class="drawer-loading"><el-skeleton :rows="12" animated /></div>
      <template v-else-if="detail">
        <header class="dossier-header">
          <div><p class="eyebrow">{{ detailTypeLabel }} / {{ companyLabel(detail.workspace_id) }} · {{ detail.workspace_name || selectedWorkspaceName }}</p><h2>{{ detailTitle }}</h2></div>
          <div class="dossier-actions">
            <el-button v-if="!editing" @click="router.push({ path: '/ppap', query: { company: 'gaibo', [detail.type === 'installation_package' ? 'package_id' : 'requirement_id']: detail.id } })">查看PPAP</el-button>
            <el-button v-if="!editing" :icon="Edit" @click="startEditing">编辑档案</el-button>
            <template v-else><el-button :loading="saving" type="primary" :icon="Check" @click="saveDetail">保存核心资料</el-button><el-button :disabled="saving" :icon="Close" @click="cancelEditing">取消</el-button></template>
            <el-button text :icon="Close" aria-label="关闭详情" title="关闭详情" @click="requestDrawerClose(() => { drawerOpen = false })" />
          </div>
        </header>
        <p v-if="saveError" class="detail-save-error" role="alert">{{ saveError }}</p>

        <div class="dossier-body">
          <section class="dossier-section"><h3>{{ detailSectionTitle }}</h3>
            <div class="field-grid">
              <div class="field-grid-item primary-number-field"><span>客户件号 / 安装包号</span><el-input v-if="editing" v-model="draft.primaryNumber" class="primary-number-input" clearable autocomplete="off" aria-label="客户件号或安装包号" placeholder="请输入客户件号或安装包号" @click.stop /><strong v-else class="mono">{{ detail.primaryNumber || '—' }}</strong><small v-if="editing" class="field-hint">可直接修改，保存后会同步到列表</small></div>
              <label v-if="detail.type === 'installation_package'"><span>优先级</span><el-select v-if="editing" v-model="draft.priority" clearable><el-option label="P1" value="1" /><el-option label="P2" value="2" /><el-option label="P3" value="3" /></el-select><strong v-else>{{ detail.priority ? `P${detail.priority}` : '—' }}</strong></label>
              <label v-if="detail.type === 'installation_package'"><span>D code</span><el-input v-if="editing" v-model="draft.dCode" /><strong v-else class="mono">{{ detail.dCode || '—' }}</strong></label>
              <label v-if="detail.type === 'installation_package'"><span>天悦 PN</span><el-input v-if="editing" v-model="draft.tianyuePn" /><strong v-else class="mono">{{ detail.tianyuePn || '—' }}</strong></label>
              <label v-if="detail.type === 'single_part'"><span>IBI</span><el-input v-if="editing" v-model="draft.ibi" /><strong v-else class="mono">{{ detail.ibi || '—' }}</strong></label>
              <label v-if="detail.type === 'single_part'"><span>天越内部组成</span><el-input v-if="editing" v-model="draft.internalComposition" /><strong v-else class="mono">{{ detail.internalComposition || '—' }}</strong></label>
              <label><span>价格（FCA USD）</span><el-input v-if="editing" v-model="draft.price" type="number" min="0" step="0.0001" /><template v-else><strong :class="['numeric', { 'price-mismatch': detail.price_mismatch }]" :title="detail.price_mismatch ? 'FMG Price 与 FCA TIANYUE Plant Price+TTOP 不一致，详见备注' : undefined">{{ detail.price == null ? '待确认' : detail.price }}</strong><small v-if="detail.price_mismatch" class="price-mismatch-note">FMG Price 不一致，详见备注</small></template></label>
              <label><span>显示名称</span><el-input v-if="editing" v-model="draft.name" /><strong v-else>{{ detail.name || '—' }}</strong></label>
              <label v-for="field in activeDetailCustomFields" :key="field.key"><span>{{ field.label }}</span><template v-if="editing"><el-select v-if="field.data_type === 'select'" v-model="draft.extraData[field.key]" clearable><el-option v-for="option in field.options" :key="option" :label="option" :value="option" /></el-select><el-date-picker v-else-if="field.data_type === 'date'" v-model="draft.extraData[field.key]" type="date" value-format="YYYY-MM-DD" style="width: 100%" /><el-switch v-else-if="field.data_type === 'boolean'" :model-value="Boolean(draft.extraData[field.key])" inline-prompt active-text="是" inactive-text="否" @change="draft.extraData[field.key] = Boolean($event)" /><el-input v-else v-model="draft.extraData[field.key]" :type="field.data_type === 'number' ? 'number' : 'text'" /></template><strong v-else :class="{ numeric: field.data_type === 'number' }">{{ formatCustomValue(detail.extraData?.[field.key], customColumnDefinition(field)) }}</strong></label>
              <label class="wide"><span>备注</span><el-input v-if="editing" v-model="draft.remark" type="textarea" :rows="2" /><strong v-else>{{ detail.remark || '—' }}</strong></label>
            </div>
          </section>

          <section v-if="detail.type === 'installation_package'" class="dossier-section"><div class="section-heading"><h3>安装包组成 <small>{{ detail.items.length }} 项</small></h3><el-button v-if="editing" link type="primary" @click="addPackageItem">新增组成项</el-button></div>
            <el-table :data="detail.items" :row-key="itemRowKey" size="small" class="items-table">
              <el-table-column label="#" width="56"><template #default="{ row }"><el-input-number v-if="editing" v-model="row.sequence" :min="1" :controls="false" size="small" /><span v-else class="numeric">{{ row.sequence }}</span></template></el-table-column>
              <el-table-column label="单件 / 客户件号" min-width="172"><template #default="{ row }"><div v-if="editing" class="package-link-editor"><el-select v-model="row.requirement_id" size="small" clearable filterable placeholder="选择已有单件" @change="applyRequirementSelection(row)"><el-option v-for="option in requirementOptions" :key="option.record_id" :label="requirementOptionLabel(option)" :value="option.record_id" /></el-select><el-input v-if="!row.requirement_id" v-model="row.unlinked_customer_part_number" size="small" placeholder="填写暂存客户件号" /></div><div v-else class="package-link-readout"><el-button v-if="row.requirement_id" link type="primary" size="small" @click.stop="openLinkedRequirement(row.requirement_id)">{{ requirementDisplayLabel(row.requirement_id) }}</el-button><span v-else class="muted">暂存件</span><small v-if="!row.requirement_id" class="mono">{{ row.unlinked_customer_part_number || '—' }}</small></div></template></el-table-column>
              <el-table-column label="IBI" min-width="132"><template #default="{ row }"><el-input v-if="editing" v-model="row.ibi" size="small" placeholder="待补 IBI" /><span v-else-if="row.ibi" class="mono">{{ row.ibi }}</span><span v-else class="missing-ibi">待补 IBI</span></template></el-table-column>
              <el-table-column label="天越内部组成" min-width="154"><template #default="{ row }"><el-input v-if="editing" v-model="row.tianyue_internal_composition" size="small" /><span v-else class="mono">{{ row.tianyue_internal_composition }}</span></template></el-table-column>
              <el-table-column label="数量" width="72" align="right"><template #default="{ row }"><el-input v-if="editing" v-model="row.quantity" size="small" /><span v-else class="numeric">{{ row.quantity }}</span></template></el-table-column>
              <el-table-column label="零件标注" width="108"><template #default="{ row }"><el-select v-if="editing" v-model="row.status" size="small" clearable placeholder="未标注"><el-option label="外购" value="external_purchase" /><el-option label="暂无模具" value="no_tooling" /><el-option label="开发中" value="in_development" /></el-select><span v-else class="status-value" :class="row.status">{{ packageItemStatus(row.status) }}</span></template></el-table-column>
              <el-table-column label="备注" min-width="112"><template #default="{ row }"><el-input v-if="editing" v-model="row.remark" size="small" /><span v-else>{{ row.remark || '—' }}</span></template></el-table-column>
              <el-table-column v-if="editing" label="操作" width="64"><template #default="{ row }"><el-button link type="primary" size="small" @click="saveItem(row)">保存</el-button></template></el-table-column>
            </el-table>
          </section>

          <section v-if="detail.type === 'installation_package'" class="dossier-section">
            <div class="section-heading">
              <h3>图纸位置</h3>
              <span class="drawing-section-note">按组成单件关联 · PDF 预留</span>
            </div>
            <div class="drawing-reservation-grid">
              <article class="drawing-slot-card">
                <div class="drawing-slot-heading">
                  <div><h5>客户图纸</h5><small>归属：安装包组成单件的客户需求</small></div>
                  <span class="drawing-slot-status">位置预留</span>
                </div>
                <div class="drawing-thumbnail"><div class="drawing-thumbnail-placeholder"><strong>PDF</strong><span>缩略图预留</span></div></div>
              </article>
              <article class="drawing-slot-card">
                <div class="drawing-slot-heading">
                  <div><h5>天越图纸</h5><small>归属：安装包组成单件的主档案</small></div>
                  <span class="drawing-slot-status">位置预留</span>
                </div>
                <div class="drawing-thumbnail"><div class="drawing-thumbnail-placeholder"><strong>PDF</strong><span>缩略图预留</span></div></div>
              </article>
            </div>
          </section>

          <section v-if="detail.type === 'single_part'" class="dossier-section">
            <div class="section-heading">
              <h3>图纸与工艺</h3>
              <div v-if="editing" class="section-heading-actions">
                <el-button link type="primary" :icon="Plus" @click="addRoute">新增工艺路线</el-button>
              </div>
            </div>
            <div class="detail-columns">
              <div class="record-column">
                <h4>客户图纸</h4>
                <article v-for="drawing in detail.drawings" :key="drawing.id || drawing._draftKey" class="editable-record">
                  <div class="drawing-thumbnail" :class="{ 'has-preview': drawingPreviewUrl(drawing) }">
                    <el-image v-if="drawingPreviewUrl(drawing)" :src="drawingPreviewUrl(drawing)" fit="contain" class="drawing-thumbnail-image" alt="客户图纸 PDF 缩略图" />
                    <div v-else class="drawing-thumbnail-placeholder"><strong>PDF</strong><span>缩略图预留</span></div>
                  </div>
                  <template v-if="editing">
                    <div class="drawing-editor-grid">
                      <label class="compact-field"><span>版本</span><el-input v-model="drawing.version" size="small" aria-label="图纸版本" /></label>
                      <label class="compact-field"><span>状态</span><el-input v-model="drawing.status" size="small" aria-label="图纸状态" /></label>
                      <label class="compact-field wide"><span>文件路径</span><el-input v-model="drawing.file_key" size="small" aria-label="图纸文件路径" /></label>
                      <label class="compact-field"><span>生效日期</span><el-date-picker v-model="drawing.effective_from" type="date" value-format="YYYY-MM-DD" placeholder="选择日期" size="small" aria-label="图纸生效日期" /></label>
                      <label class="compact-field"><span>提交日期</span><el-date-picker v-model="drawing.submitted_at" type="date" value-format="YYYY-MM-DD" placeholder="选择日期" size="small" aria-label="图纸提交日期" /></label>
                      <label class="compact-field"><span>批准日期</span><el-date-picker v-model="drawing.approved_at" type="date" value-format="YYYY-MM-DD" placeholder="选择日期" size="small" aria-label="图纸批准日期" /></label>
                      <label class="compact-field wide"><span>备注</span><el-input v-model="drawing.remark" size="small" aria-label="图纸备注" /></label>
                      <div class="record-editor-action"><el-button link type="primary" size="small" @click="saveDrawing(drawing)">{{ drawing.id ? '保存图纸' : '创建图纸' }}</el-button></div>
                    </div>
                  </template>
                  <template v-else>
                    <p class="record-summary"><span class="mono">{{ drawing.version }}</span><span>{{ drawing.status }}</span><small>{{ drawing.file_key }}</small></p>
                    <dl class="record-meta"><div><dt>生效</dt><dd>{{ formatDateOnly(drawing.effective_from) }}</dd></div><div><dt>提交</dt><dd>{{ formatDateOnly(drawing.submitted_at) }}</dd></div><div><dt>批准</dt><dd>{{ formatDateOnly(drawing.approved_at) }}</dd></div><div class="wide"><dt>备注</dt><dd>{{ drawing.remark || '—' }}</dd></div></dl>
                  </template>
                </article>
                <p v-if="!detail.drawings.length" class="muted">暂无客户图纸版本</p>
                <article class="drawing-slot-card">
                  <div class="drawing-slot-heading">
                    <div>
                      <h5>天越图纸</h5>
                      <small>归属：单件主档案</small>
                    </div>
                    <span class="drawing-slot-status">PDF位置预留</span>
                  </div>
                  <div class="drawing-thumbnail" :class="{ 'has-preview': detail.singlePartDrawingPreviewUrl }">
                    <el-image v-if="detail.singlePartDrawingPreviewUrl" :src="detail.singlePartDrawingPreviewUrl" fit="contain" class="drawing-thumbnail-image" alt="天越图纸 PDF 缩略图" />
                    <div v-else class="drawing-thumbnail-placeholder"><strong>PDF</strong><span>缩略图预留</span></div>
                  </div>
                  <p v-if="detail.singlePartDrawingReference" class="drawing-slot-reference mono">{{ detail.singlePartDrawingReference }}</p>
                  <p v-else class="muted">暂未登记图纸引用</p>
                  <small class="drawing-slot-note">当前仅保留位置和版本接口，暂不上传文件。</small>
                </article>
              </div>

              <div class="record-column">
                <h4>工艺路线</h4>
                <article v-for="route in detail.process_routes" :key="route.id || route._draftKey" class="editable-record route-record">
                  <template v-if="editing">
                    <div class="route-editor-header">
                      <label class="compact-field"><span>版本</span><el-input v-model="route.version" size="small" aria-label="工艺路线版本" /></label>
                      <label class="compact-field"><span>状态</span><el-input v-model="route.status" size="small" aria-label="工艺路线状态" /></label>
                      <label class="compact-field"><span>生效日期</span><el-date-picker v-model="route.effective_from" type="date" value-format="YYYY-MM-DD" placeholder="选择日期" size="small" aria-label="工艺路线生效日期" /></label>
                      <label class="compact-field"><span>当前版本</span><el-switch v-model="route.is_current" active-text="当前" aria-label="当前工艺路线版本" /></label>
                      <label class="compact-field wide"><span>备注</span><el-input v-model="route.remark" size="small" aria-label="工艺路线备注" /></label>
                    </div>
                  </template>
                  <template v-else>
                    <p class="record-summary"><span class="mono">{{ route.version }}</span><span>{{ route.status }}</span><span>生效：{{ formatDateOnly(route.effective_from) }}</span><span v-if="route.is_current" class="current-mark">当前</span></p>
                    <p v-if="route.remark" class="route-remark">{{ route.remark }}</p>
                  </template>

                  <div class="route-step-heading"><strong>工艺步骤</strong><el-button v-if="editing" link type="primary" size="small" :icon="Plus" @click="addRouteStep(route)">新增步骤</el-button></div>
                  <div class="route-step-wrap" role="region" tabindex="0" :aria-label="`工艺路线 ${route.version || ''} 的步骤表`">
                    <el-table :data="route.steps" :row-key="routeStepRowKey" size="small" class="route-step-table" aria-label="工艺路线步骤">
                      <el-table-column label="#" width="58" align="right"><template #default="{ row }"><el-input-number v-if="editing" v-model="row.sequence" :min="1" :controls="false" size="small" :aria-label="`步骤顺序 ${row.sequence || ''}`" /><span v-else class="numeric">{{ row.sequence }}</span></template></el-table-column>
                      <el-table-column label="工序名称" min-width="142"><template #default="{ row }"><el-input v-if="editing" v-model="row.operation_name" size="small" aria-label="工序名称" /><span v-else>{{ row.operation_name }}</span></template></el-table-column>
                      <el-table-column label="机台 ID" min-width="92" align="right"><template #default="{ row }"><el-input-number v-if="editing" v-model="row.machine_id" :min="1" :controls="false" size="small" aria-label="机台 ID" /><span v-else class="mono">{{ row.machine_id || '—' }}</span></template></el-table-column>
                      <el-table-column label="模具 ID" min-width="92" align="right"><template #default="{ row }"><el-input-number v-if="editing" v-model="row.tooling_id" :min="1" :controls="false" size="small" aria-label="模具 ID" /><span v-else class="mono">{{ row.tooling_id || '—' }}</span></template></el-table-column>
                      <el-table-column label="关键参数 JSON" min-width="176"><template #default="{ row }"><el-input v-if="editing" v-model="row._keyParametersText" type="textarea" :autosize="{ minRows: 2, maxRows: 5 }" resize="vertical" aria-label="关键参数 JSON" /><pre v-else class="json-readout">{{ formatJson(row.key_parameters) }}</pre></template></el-table-column>
                      <el-table-column label="质量检查点 JSON" min-width="176"><template #default="{ row }"><el-input v-if="editing" v-model="row._qualityCheckpointsText" type="textarea" :autosize="{ minRows: 2, maxRows: 5 }" resize="vertical" aria-label="质量检查点 JSON" /><pre v-else class="json-readout">{{ formatJson(row.quality_checkpoints) }}</pre></template></el-table-column>
                      <el-table-column label="备注" min-width="156"><template #default="{ row }"><el-input v-if="editing" v-model="row.remark" type="textarea" :autosize="{ minRows: 2, maxRows: 4 }" resize="vertical" aria-label="工艺步骤备注" /><span v-else>{{ row.remark || '—' }}</span></template></el-table-column>
                      <el-table-column v-if="editing" label="操作" width="64" fixed="right"><template #default="{ $index }"><el-button text type="danger" size="small" :icon="Delete" :aria-label="`删除第 ${$index + 1} 步`" :title="`删除第 ${$index + 1} 步`" @click="removeRouteStep(route, $index)" /></template></el-table-column>
                    </el-table>
                  </div>
                  <p v-if="!route.steps.length" class="muted route-empty">暂无工艺步骤</p>
                  <div v-if="editing" class="record-editor-action"><el-button link type="primary" size="small" @click="saveRoute(route)">{{ route.id ? '保存路线' : '创建路线' }}</el-button></div>
                </article>
                <p v-if="!detail.process_routes.length" class="muted">暂无工艺路线</p>
              </div>
            </div>
          </section>

          <section class="dossier-section"><div class="section-heading"><h3>{{ detail.type === 'installation_package' ? '安装包状态' : '资料状态' }}</h3><el-button v-if="editing" link type="primary" @click="addDocument">新增资料状态</el-button></div><div class="status-line"><div v-for="document in detail.documents" :key="document.id || document._draftKey" class="document-status-row" :class="[document.status, { editing }]" ><template v-if="editing"><el-input v-model="document.document_type" size="small" placeholder="资料类型" aria-label="资料类型" /><el-select v-model="document.status" size="small" aria-label="资料状态"><el-option label="未开始" value="not_started" /><el-option label="进行中" value="in_progress" /><el-option label="OK" value="ok" /><el-option label="NOT OK" value="not_ok" /><el-option label="不适用" value="not_applicable" /></el-select><el-date-picker v-model="document.submitted_at" type="date" value-format="YYYY-MM-DD" size="small" placeholder="提交日期" aria-label="提交日期" /><el-date-picker v-model="document.concluded_at" type="date" value-format="YYYY-MM-DD" size="small" placeholder="结论日期" aria-label="结论日期" /><el-input v-model="document.remark" size="small" placeholder="备注" aria-label="资料备注" /><el-button link type="primary" size="small" @click="saveDocument(document)">{{ document.id ? '保存' : '创建' }}</el-button></template><template v-else><div class="document-status-heading"><span class="document-type">{{ documentTypeLabel(document.document_type) }}</span><span class="document-status"><i class="status-dot" aria-hidden="true" />状态：{{ documentStatusLabel(document.status) }}</span></div><div v-if="document.events?.length" class="document-event-list"><div v-for="(event, eventIndex) in document.events" :key="`${event.event_type}-${eventIndex}-${event.raw_text}`" class="document-event"><span class="document-event-date">{{ event.date_text || '记录' }}</span><strong>{{ event.label }}</strong><span v-if="event.raw_text" class="document-event-raw">Excel 原文：{{ event.raw_text }}</span></div></div><p v-else class="document-event-empty">暂无过程记录</p></template></div><span v-if="!detail.documents.length" class="muted">暂无资料状态</span></div></section>
          <section class="dossier-section"><h3>修改历史</h3><div v-if="detail.change_history.length" class="history-list"><div v-for="entry in detail.change_history" :key="entry.id" class="history-row"><span class="history-dot" /><div><strong>{{ entry.summary }}</strong><p>{{ formatDate(entry.created_at) }} · 操作人 {{ entry.actor_user_id || '系统' }}</p><pre>{{ JSON.stringify(entry.change_data, null, 2) }}</pre></div></div></div><p v-else class="muted">暂无修改历史</p></section>
        </div>
      </template>
    </el-drawer>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { ArrowDown, ArrowUp, Check, Close, Delete, Edit, Plus, Refresh, Search, Setting } from '@element-plus/icons-vue'
import { afterSalesApi } from '@/api/afterSales'
import { ExcelGrid } from '@/components/excel-grid'
import type { ExcelFilterOption, ExcelGridColumn, ExcelGridFilterValues } from '@/components/excel-grid'
import { useRouter } from 'vue-router'
import { useCompanyStore, type CompanyKey } from '@/stores/company'

type RecordType = 'single_part' | 'installation_package'
type CustomFieldType = 'text' | 'number' | 'date' | 'boolean' | 'select'
type CustomFieldScope = RecordType | 'both'
interface CustomFieldDefinition { key: string; label: string; data_type: CustomFieldType; scope: CustomFieldScope; default_visible: boolean; width: number; sequence: number; is_active: boolean; options: string[] }
interface Workspace { id: number; after_sales_customer_id: number; after_sales_customer_name: string; display_name: string; slug: string; company_id?: number | string | null; company_name?: string | null; field_labels: Record<string, string>; extra_field_definitions: { schema_version?: number; columns?: CustomFieldDefinition[] }; default_view_config: Partial<ViewConfig>; column_config_version: number }
interface WorkspaceColumnConfig { workspace_id: number; version: number; field_labels: Record<string, string>; detail_section_labels: Record<string, string>; custom_fields: CustomFieldDefinition[]; default_view_config: ViewConfig }
interface SearchComponent { sequence: number; ibi: string; tianyue_internal_composition: string; quantity: number | string; status?: string | null }
interface DocumentEvent { event_type: string; label: string; date_text?: string | null; raw_text?: string | null }
interface DocumentStatus { id?: number; _draftKey?: string; document_type: string; status: string; submitted_at?: string | null; concluded_at?: string | null; remark?: string | null; events?: DocumentEvent[]; latest_event?: DocumentEvent | null }
interface SearchItem { record_type: RecordType; record_id: number; workspace_id: number; workspace_name: string; customer_part_number?: string | null; priority?: number | null; d_code?: string | null; tianyue_pn?: string | null; ibi?: string | null; tianyue_internal_composition?: string | null; price?: number | string | null; price_mismatch?: boolean; display_name?: string | null; remark?: string | null; extra_data?: Record<string, unknown>; drawing_status?: string | null; sample_status?: string | null; ppap_status?: string | null; drawing_latest_event?: DocumentEvent | null; sample_latest_event?: DocumentEvent | null; ppap_latest_event?: DocumentEvent | null; component_items?: SearchComponent[]; updated_at: string }
interface Detail { type: RecordType; id: number; workspace_id: number; workspace_name?: string; updatedAt?: string; single_part_id?: number; singlePartDrawingReference?: string | null; singlePartDrawingPreviewUrl?: string | null; primaryNumber: string; priority?: number | null; dCode?: string | null; tianyuePn?: string | null; ibi?: string | null; internalComposition?: string | null; price?: number | string | null; price_mismatch?: boolean; name?: string | null; remark?: string | null; extraData: Record<string, unknown>; items: any[]; drawings: any[]; process_routes: any[]; documents: DocumentStatus[]; change_history: any[] }
type ColumnKey = string
interface ColumnDefinition { key: ColumnKey; label: string; core: boolean; sortable?: boolean; minWidth: number; align?: 'left' | 'center' | 'right'; custom?: boolean; dataType?: CustomFieldType; scope?: CustomFieldScope; options?: string[] }
interface ViewConfig { visible: ColumnKey[]; order: ColumnKey[]; widths: Record<ColumnKey, number>; density: 'compact' | 'standard'; sortKey: ColumnKey; sortOrder: 'asc' | 'desc' }
interface SearchSummary { total_records: number; priced_records: number; missing_price_records: number; drawing_ok_records: number; sample_ok_records: number; ppap_ok_records: number }

const router = useRouter()
const companyStore = useCompanyStore()

const baseColumnDefinitions: Record<ColumnKey, ColumnDefinition> = {
  type: { key: 'type', label: '类型', core: true, minWidth: 66, align: 'center' },
  workspace: { key: 'workspace', label: '客户', core: true, minWidth: 100 },
  primaryNumber: { key: 'primaryNumber', label: '客户件号 / 安装包号', core: true, sortable: true, minWidth: 132 },
  priority: { key: 'priority', label: '优先级', core: false, sortable: true, minWidth: 62, align: 'center' },
  dCode: { key: 'dCode', label: 'D code', core: false, sortable: true, minWidth: 78 },
  tianyuePn: { key: 'tianyuePn', label: '天悦 PN', core: false, sortable: true, minWidth: 90 },
  internalComposition: { key: 'internalComposition', label: '天越内部组成', core: true, minWidth: 168 },
  ibi: { key: 'ibi', label: 'IBI', core: true, minWidth: 152 },
  status: { key: 'status', label: '安装包状态', core: true, minWidth: 156, align: 'center' },
  price: { key: 'price', label: '价格（FCA USD）', core: true, sortable: true, minWidth: 104, align: 'center' },
  remark: { key: 'remark', label: '备注', core: false, minWidth: 120 },
  updatedAt: { key: 'updatedAt', label: '更新时间', core: false, sortable: true, minWidth: 140 },
}
const baseColumnKeys = Object.keys(baseColumnDefinitions)
const baseViewConfig = (): ViewConfig => ({
  visible: ['type', 'workspace', 'primaryNumber', 'priority', 'dCode', 'tianyuePn', 'internalComposition', 'ibi', 'status', 'price', 'remark'],
  order: ['type', 'workspace', 'primaryNumber', 'priority', 'dCode', 'tianyuePn', 'internalComposition', 'ibi', 'status', 'price', 'remark', 'updatedAt'],
  widths: Object.fromEntries(baseColumnKeys.map(key => [key, baseColumnDefinitions[key].minWidth])) as Record<ColumnKey, number>,
  density: 'compact',
  sortKey: 'updatedAt',
  sortOrder: 'desc',
})

const loading = ref(false); const detailLoading = ref(false); const saving = ref(false); const viewSaving = ref(false); const settingsOpen = ref(false); const errorMessage = ref(''); const saveError = ref(''); const workspaces = ref<Workspace[]>([]); const records = ref<SearchItem[]>([]); const requirementOptions = ref<SearchItem[]>([]); const total = ref(0); const currentPage = ref(1); const pageSize = ref(50); const drawerOpen = ref(false); const editing = ref(false); const detail = ref<Detail | null>(null); const originalDetail = ref<Detail | null>(null); const summary = reactive<SearchSummary>({ total_records: 0, priced_records: 0, missing_price_records: 0, drawing_ok_records: 0, sample_ok_records: 0, ppap_ok_records: 0 })
const viewportWidth = ref(typeof window === 'undefined' ? 1280 : window.innerWidth)
const filters = reactive<{ q: string; workspaceId?: number; recordType: SearchItem['record_type']; status?: string }>({ q: '', recordType: 'installation_package' })
const draft = reactive<{ primaryNumber: string; priority: string; dCode: string; tianyuePn: string; ibi: string; internalComposition: string; price: string; name: string; remark: string; extraData: Record<string, unknown> }>({ primaryNumber: '', priority: '', dCode: '', tianyuePn: '', ibi: '', internalComposition: '', price: '', name: '', remark: '', extraData: {} })
const viewConfig = reactive<ViewConfig>(baseViewConfig())
const workspaceColumnConfig = ref<WorkspaceColumnConfig | null>(null)
const detailSectionLabelDraft = ref('核心字段')
const customFieldDrafts = ref<CustomFieldDefinition[]>([])
const fieldLabelDrafts = ref<Record<string, string>>({})
const personalFieldLabelsKey = 'zephyr-after-sales-field-labels'
const personalFieldLabels = ref<Record<string, string>>(typeof localStorage === 'undefined' ? {} : JSON.parse(localStorage.getItem(personalFieldLabelsKey) || '{}'))
const viewConfigBeforeEdit = ref<ViewConfig | null>(null)
const columnFilters = reactive<ExcelGridFilterValues>({})
const filterOptionsByColumn = reactive<Record<ColumnKey, ExcelFilterOption[]>>({})
const excelGridRef = ref<{ clearFilters?: () => void } | null>(null)
const editingCell = ref<{ rowKey: string; key: ColumnKey } | null>(null)
const inlineDraft = ref('')
let primaryClickTimer: ReturnType<typeof setTimeout> | null = null
const densityOptions = [{ label: '紧凑', value: 'compact' }, { label: '标准', value: 'standard' }]
const recordTypeOptions = [{ label: '单件', value: 'single_part' }, { label: '安装包', value: 'installation_package' }]
const companyLabel = (_workspaceId?: number) => '盖博'
const workspaceDisplayName = (name?: string | null) => {
  const value = String(name || '').trim()
  return value.replace(/^盖博[\s_-]+/, '') || value
}
const handleCompanyChange = async (company: CompanyKey) => {
  companyStore.setCompany(company)
  if (company === 'tianyue') await router.replace('/parts')
}
const columnDefinitions = computed<Record<ColumnKey, ColumnDefinition>>(() => {
  const labels = workspaceColumnConfig.value?.field_labels || personalFieldLabels.value
  const custom = Object.fromEntries(customFieldDrafts.value.filter(field => field.is_active).map(field => [field.key, { key: field.key, label: field.label, core: false, minWidth: field.width, custom: true, dataType: field.data_type, scope: field.scope, options: field.options }]))
  const core = Object.fromEntries(Object.entries(baseColumnDefinitions).map(([key, value]) => [key, { ...value, label: labels[key] || value.label }]))
  return { ...core, ...custom }
})
const columnKeys = computed(() => Object.keys(columnDefinitions.value))
const sortOptions = computed(() => Object.values(columnDefinitions.value).filter(column => column.sortable || column.custom).map(column => ({ label: column.label, value: column.key })))
const selectedWorkspaceName = computed(() => filters.workspaceId ? workspaces.value.find(item => item.id === filters.workspaceId)?.display_name || '盖博客户' : '盖博')
const tableWidthScale = computed(() => {
  const baseWidth = visibleColumns.value.reduce((total, column) => total + (viewConfig.widths[column.key] || column.minWidth || 120), 0)
  const availableWidth = Math.max(0, viewportWidth.value - 280)
  const targetScale = viewportWidth.value >= 2200 ? 1.45 : viewportWidth.value >= 1440 ? 1.28 : 1
  return baseWidth > 0 ? Math.max(1, Math.min(targetScale, availableWidth / baseWidth)) : 1
})
const archiveTitle = computed(() => filters.recordType === 'single_part' ? '盖博单件' : '盖博安装包')
const archiveSubtitle = computed(() => filters.recordType === 'single_part' ? '盖博单件档案' : '盖博安装包档案')
const detailTypeLabel = computed(() => detail.value?.type === 'single_part' ? '单件档案' : '安装包档案')
const detailTitle = computed(() => detail.value?.primaryNumber || '档案详情')
const detailSectionTitle = computed(() => detailSectionLabelDraft.value.trim() || workspaceColumnConfig.value?.detail_section_labels?.core_fields || '核心字段')
const hasActiveFilters = computed(() => Boolean(filters.q || filters.workspaceId || filters.recordType || filters.status || Object.values(columnFilters).some(values => values.length)))
const visibleColumns = computed(() => viewConfig.order.filter(key => viewConfig.visible.includes(key)).map(key => columnDefinitions.value[key]).filter(Boolean))
const excelColumns = computed<ExcelGridColumn[]>(() => visibleColumns.value.map(column => ({
  key: column.key,
  label: column.label,
  width: columnWidth(column.key),
  minWidth: column.minWidth,
  align: column.align,
  sortable: Boolean(column.sortable || column.custom),
  custom: column.custom,
  dataType: column.dataType,
  filters: filterOptionsByColumn[column.key] || [],
  filterMultiple: true,
})))
const activeDetailCustomFields = computed(() => customFieldDrafts.value.filter(field => field.is_active && (field.scope === 'both' || field.scope === detail.value?.type)))
const archivedCustomFields = computed(() => customFieldDrafts.value.filter(field => !field.is_active))

const formatDate = (value?: string) => value ? new Date(value).toLocaleString('zh-CN', { hour12: false }) : '—'
const formatDateOnly = (value?: string | null) => value ? String(value).slice(0, 10) : '—'
const formatPrice = (value?: number | string | null) => value == null || value === '' ? '待确认' : Number(value).toFixed(4).replace(/0+$/, '').replace(/\.$/, '')
const customColumnDefinition = (field: CustomFieldDefinition): ColumnDefinition => ({ key: field.key, label: field.label, core: false, minWidth: field.width, custom: true, dataType: field.data_type, scope: field.scope, options: field.options })
const formatCustomValue = (value: unknown, column: ColumnDefinition) => {
  if (value === null || value === undefined || value === '') return '—'
  if (column.dataType === 'boolean') return value ? '是' : '否'
  if (column.dataType === 'number') return Number(value).toLocaleString('zh-CN', { maximumFractionDigits: 6 })
  return String(value)
}
const componentLabel = (value?: string | null, quantity?: number | string | null) => {
  const text = String(value || '').trim()
  if (!text) return '—'
  if (!quantity || Number(quantity) === 1 || /(?:pcs?|[×x*]\s*\d)/i.test(text)) return text
  const normalizedQuantity = Number(quantity).toFixed(3).replace(/\.?0+$/, '')
  return `${text} ×${normalizedQuantity}`
}
const componentIbiLabel = (value?: string | null, quantity?: number | string | null) => {
  const text = componentLabel(value, quantity)
  return text === '—' ? '待补 IBI' : text
}
const normalizedStatus = (value?: string | null) => value === 'ok' ? 'ok' : value === 'not_ok' ? 'not_ok' : value === 'not_started' || value === 'not_applicable' ? 'not_started' : 'in_progress'
const statusTooltip = (row: SearchItem) => `图纸：${documentStatusLabel(row.drawing_status)}\n样件：${documentStatusLabel(row.sample_status)}\nPPAP：${documentStatusLabel(row.ppap_status)}`
const overallStatusLabel = (row: SearchItem) => {
  const statuses = [row.drawing_status, row.sample_status, row.ppap_status].filter(Boolean)
  if (statuses.includes('not_ok')) return 'NOT OK'
  if (statuses.length && statuses.every(status => status === 'ok')) return 'OK'
  return '进行中'
}
const recordRowKey = (row: SearchItem) => `${row.record_type}-${row.record_id}`
const itemRowKey = (row: Record<string, unknown>) => String(row.id || row._draftKey || '')
const routeStepRowKey = (row: Record<string, unknown>) => String(row.id || row._draftKey || row.sequence || '')
const cloneDetail = (value: Detail) => JSON.parse(JSON.stringify(value)) as Detail
const formatJson = (value: unknown) => {
  if (typeof value === 'string') {
    try { return JSON.stringify(JSON.parse(value), null, 2) } catch { return value }
  }
  return JSON.stringify(value || {}, null, 2)
}
const hydrateRoutes = (routes: any[]) => routes.map(route => ({
  ...route,
  steps: (route.steps || []).map((step: any) => ({
    ...step,
    _keyParametersText: formatJson(step.key_parameters),
    _qualityCheckpointsText: formatJson(step.quality_checkpoints),
  })),
}))
const documentTypeLabel = (value?: string | null) => ({ drawing: '图纸', sample: '样件', ppap: 'PPAP' } as Record<string, string>)[value || ''] || value || '资料'
const drawingPreviewUrl = (drawing: any) => drawing?.preview_url || drawing?.thumbnail_url || ''
const documentStatusLabel = (value?: string | null) => ({ not_started: '未开始', in_progress: '进行中', ok: 'OK', not_ok: 'NOT OK', not_applicable: '不适用' } as Record<string, string>)[value || ''] || value || '未开始'
const packageItemStatus = (value?: string | null) => ({ external_purchase: '外购', no_tooling: '暂无模具', in_development: '开发中' } as Record<string, string>)[value || ''] || '未标注'
const requirementOptionLabel = (option: SearchItem) => [option.customer_part_number, option.ibi, option.tianyue_internal_composition].filter(Boolean).join(' · ')
const requirementDisplayLabel = (requirementId?: number | null) => {
  const option = requirementOptions.value.find(item => item.record_id === requirementId)
  return option?.customer_part_number || '已关联单件'
}
const columnWidth = (key: ColumnKey) => Math.round((viewConfig.widths[key] || columnDefinitions.value[key]?.minWidth || 120) * tableWidthScale.value)
const cloneViewConfig = (value: ViewConfig) => JSON.parse(JSON.stringify(value)) as ViewConfig
const normalizeViewConfig = (value?: Partial<ViewConfig> | null): ViewConfig => {
  const defaults = baseViewConfig()
  const allowedKeys = columnKeys.value
  const customDefaults = customFieldDrafts.value.filter(field => field.is_active).map(field => field.key)
  defaults.order.push(...customDefaults)
  defaults.visible.push(...customFieldDrafts.value.filter(field => field.is_active && field.default_visible).map(field => field.key))
  Object.assign(defaults.widths, Object.fromEntries(customFieldDrafts.value.filter(field => field.is_active).map(field => [field.key, field.width])))
  const order = Array.from(new Set([...(value?.order || []), ...defaults.order])).filter(key => allowedKeys.includes(key)) as ColumnKey[]
  const visible = Array.from(new Set([...(value?.visible || []), ...defaults.visible.filter(key => baseColumnDefinitions[key]?.core || customDefaults.includes(key))])).filter(key => order.includes(key)) as ColumnKey[]
  if (!visible.includes('primaryNumber')) visible.unshift('primaryNumber')
  const widths = { ...defaults.widths, ...(value?.widths || {}) }
  for (const key of allowedKeys) widths[key] = Math.min(420, Math.max(56, Number(widths[key]) || defaults.widths[key] || 120))
  return { visible, order, widths, density: value?.density === 'standard' ? 'standard' : 'compact', sortKey: sortOptions.value.some(option => option.value === value?.sortKey) ? value!.sortKey! : defaults.sortKey, sortOrder: value?.sortOrder === 'asc' ? 'asc' : 'desc' }
}
function applyViewConfig(value?: Partial<ViewConfig> | null) { Object.assign(viewConfig, normalizeViewConfig(value)) }
function openViewSettings() { viewConfigBeforeEdit.value = cloneViewConfig(viewConfig); fieldLabelDrafts.value = { ...(workspaceColumnConfig.value?.field_labels || personalFieldLabels.value) }; detailSectionLabelDraft.value = workspaceColumnConfig.value?.detail_section_labels?.core_fields || '核心字段'; customFieldDrafts.value = customFieldDrafts.value.map(field => ({ ...field, options: [...field.options] })); settingsOpen.value = true }
function closeViewSettings(done?: unknown) { if (viewConfigBeforeEdit.value) applyViewConfig(viewConfigBeforeEdit.value); if (filters.workspaceId) detailSectionLabelDraft.value = workspaceColumnConfig.value?.detail_section_labels?.core_fields || '核心字段'; viewConfigBeforeEdit.value = null; settingsOpen.value = false; if (typeof done === 'function') done() }
function resetViewConfig() { applyViewConfig(baseViewConfig()); if (filters.workspaceId) { customFieldDrafts.value = workspaceColumnConfig.value?.custom_fields.map(field => ({ ...field, options: [...field.options] })) || []; fieldLabelDrafts.value = { ...(workspaceColumnConfig.value?.field_labels || {}) }; detailSectionLabelDraft.value = '核心字段' } }
function toggleColumn(key: ColumnKey, visible: boolean) { if (key === 'primaryNumber') return; viewConfig.visible = visible ? Array.from(new Set([...viewConfig.visible, key])) : viewConfig.visible.filter(item => item !== key) }
function moveColumn(index: number, offset: number) { const nextIndex = index + offset; if (nextIndex < 0 || nextIndex >= viewConfig.order.length) return; const order = [...viewConfig.order]; [order[index], order[nextIndex]] = [order[nextIndex], order[index]]; viewConfig.order = order }
const isCustomColumnKey = (key: ColumnKey) => customFieldDrafts.value.some(field => field.key === key)
const customFieldByKey = (key: ColumnKey) => customFieldDrafts.value.find(field => field.key === key)
const isPersistedCustomField = (key: ColumnKey) => Boolean(workspaceColumnConfig.value?.custom_fields.some(field => field.key === key))
const columnDraftLabel = (key: ColumnKey) => fieldLabelDrafts.value[key] || columnDefinitions.value[key]?.label || key
const updateColumnDraftLabel = (key: ColumnKey, label: string) => { if (isCustomColumnKey(key)) { const field = customFieldByKey(key); if (field) field.label = label } else fieldLabelDrafts.value[key] = label }
const updateCustomField = (key: ColumnKey, fieldName: 'data_type' | 'scope', value: CustomFieldType | CustomFieldScope) => { const field = customFieldByKey(key); if (field) { (field as any)[fieldName] = value; if (field.data_type !== 'select') field.options = [] } }
const updateCustomFieldOptions = (key: ColumnKey, value: string) => { const field = customFieldByKey(key); if (field) field.options = value.split('、').map(item => item.trim()).filter(Boolean).slice(0, 20) }
const archiveCustomColumn = (key: ColumnKey) => { const field = customFieldByKey(key); if (!field) return; field.is_active = false; viewConfig.visible = viewConfig.visible.filter(item => item !== key); viewConfig.order = viewConfig.order.filter(item => item !== key) }
const restoreCustomColumn = (key: ColumnKey) => { const field = customFieldByKey(key); if (!field) return; field.is_active = true; viewConfig.order.push(key); if (field.default_visible) viewConfig.visible.push(key) }
const addCustomColumn = () => { const key = `custom_${Math.random().toString(36).slice(2, 10)}`; const field: CustomFieldDefinition = { key, label: '新字段', data_type: 'text', scope: 'both', default_visible: true, width: 120, sequence: customFieldDrafts.value.length, is_active: true, options: [] }; customFieldDrafts.value.push(field); viewConfig.order.push(key); viewConfig.visible.push(key); viewConfig.widths[key] = field.width }
const hasUnsavedChanges = () => {
  if (!editing.value || !detail.value || !originalDetail.value) return false
  const coreChanged = draft.primaryNumber !== originalDetail.value.primaryNumber
    || draft.priority !== (originalDetail.value.priority == null ? '' : String(originalDetail.value.priority))
    || draft.dCode !== (originalDetail.value.dCode || '')
    || draft.tianyuePn !== (originalDetail.value.tianyuePn || '')
    || draft.ibi !== (originalDetail.value.ibi || '')
    || draft.internalComposition !== (originalDetail.value.internalComposition || '')
    || draft.price !== (originalDetail.value.price == null ? '' : String(originalDetail.value.price))
    || draft.name !== (originalDetail.value.name || '')
    || draft.remark !== (originalDetail.value.remark || '')
    || JSON.stringify(draft.extraData) !== JSON.stringify(originalDetail.value.extraData || {})
  return coreChanged || JSON.stringify(detail.value) !== JSON.stringify(originalDetail.value)
}
function clearWorkspaceColumns() { workspaceColumnConfig.value = null; customFieldDrafts.value = []; fieldLabelDrafts.value = {}; detailSectionLabelDraft.value = '核心字段'; applyViewConfig(baseViewConfig()) }
function selectRecordType(value: string | number) {
  filters.workspaceId = undefined
  filters.recordType = value as RecordType
  clearWorkspaceColumns()
  void loadViewPreference()
  applyFilters()
}
const applyFilters = () => { currentPage.value = 1; void loadRecords(); void loadVisibleFilterOptions() }
const resetFilters = () => {
  filters.q = ''; filters.workspaceId = undefined; filters.recordType = 'installation_package'; filters.status = undefined
  Object.keys(columnFilters).forEach(key => delete columnFilters[key])
  excelGridRef.value?.clearFilters?.()
  applyFilters()
}
const changePage = (page: number) => { currentPage.value = page; void loadRecords() }
const handlePageSizeChange = () => { currentPage.value = 1; void loadRecords() }
function handleExcelSortChange({ field, order }: { field: string; order: 'asc' | 'desc' | null }) {
  if (!field || !order || !columnKeys.value.includes(field)) return
  viewConfig.sortKey = field
  viewConfig.sortOrder = order
  void loadRecords()
}
function handleExcelFilterChange(nextFilters: ExcelGridFilterValues) {
  Object.keys(columnFilters).forEach(key => delete columnFilters[key])
  Object.entries(nextFilters).forEach(([key, values]) => { if (values.length) columnFilters[key] = values })
  currentPage.value = 1
  void loadRecords()
  void loadVisibleFilterOptions()
}
function handleExcelColumnResize({ field, width }: { field: string; width: number }) {
  if (field && columnKeys.value.includes(field) && width) viewConfig.widths[field] = Math.min(420, Math.max(56, Math.round(width / tableWidthScale.value)))
}
function handleExcelColumnOrderChange({ oldField, newField }: { oldField?: string; newField?: string }) {
  if (!oldField || !newField || oldField === newField) return
  const sourceIndex = viewConfig.order.indexOf(oldField)
  const targetIndex = viewConfig.order.indexOf(newField)
  if (sourceIndex < 0 || targetIndex < 0) return
  const order = [...viewConfig.order]
  order.splice(sourceIndex, 1)
  order.splice(order.indexOf(newField), 0, oldField)
  viewConfig.order = order
}
function isInlineEditable(row: SearchItem, key: ColumnKey) {
  if (key === 'primaryNumber' || key === 'price' || key === 'remark' || key.startsWith('custom_')) return true
  if (row.record_type === 'installation_package' && (key === 'priority' || key === 'dCode' || key === 'tianyuePn')) return true
  return row.record_type === 'single_part' && (key === 'ibi' || key === 'internalComposition')
}
function isInlineEditing(row: SearchItem, key: ColumnKey) { return editingCell.value?.rowKey === recordRowKey(row) && editingCell.value.key === key }
function inlineValue(row: SearchItem, key: ColumnKey) {
  if (key === 'primaryNumber') return row.customer_part_number || ''
  if (key === 'price') return row.price == null ? '' : String(row.price)
  if (key === 'priority') return row.priority == null ? '' : String(row.priority)
  if (key === 'remark') return row.remark || ''
  if (key === 'dCode') return row.d_code || ''
  if (key === 'tianyuePn') return row.tianyue_pn || ''
  if (key === 'ibi') return row.ibi || ''
  if (key === 'internalComposition') return row.tianyue_internal_composition || ''
  return row.extra_data?.[key] == null ? '' : String(row.extra_data[key])
}
function startInlineEdit(row: SearchItem, key: ColumnKey) {
  if (!isInlineEditable(row, key)) return
  editingCell.value = { rowKey: recordRowKey(row), key }
  inlineDraft.value = inlineValue(row, key)
}
function handlePrimaryClick(row: SearchItem) {
  if (primaryClickTimer) clearTimeout(primaryClickTimer)
  primaryClickTimer = setTimeout(() => { primaryClickTimer = null; void openRecord(row) }, 220)
}
function handlePrimaryDoubleClick(row: SearchItem) {
  if (primaryClickTimer) { clearTimeout(primaryClickTimer); primaryClickTimer = null }
  startInlineEdit(row, 'primaryNumber')
}
function cancelInlineEdit() { editingCell.value = null; inlineDraft.value = '' }
async function commitInlineEdit() {
  const target = editingCell.value
  if (!target) return
  const row = records.value.find(item => recordRowKey(item) === target.rowKey)
  if (!row) { cancelInlineEdit(); return }
  const key = target.key
  const value = inlineDraft.value.trim()
  if (value === inlineValue(row, key)) { cancelInlineEdit(); return }
  if (row.record_type === 'single_part' && (key === 'primaryNumber' || key === 'ibi' || key === 'internalComposition') && !value) { ElMessage.warning('客户件号、IBI 和天越内部组成不能为空'); return }
  if (row.record_type === 'single_part' && key === 'price' && !value) { ElMessage.warning('单件价格不能为空；如需调整请在详情中确认'); return }
  let payload: Record<string, unknown> = {}
  if (key === 'primaryNumber') payload = row.record_type === 'single_part' ? { customer_part_number: value } : { package_number: value }
  else if (key === 'price') payload = { price: value === '' ? null : Number(value) }
  else if (key === 'priority') payload = { priority: value === '' ? null : Number(value) }
  else if (key === 'remark') payload = { remark: value || null }
  else if (key === 'dCode') payload = { d_code: value || null }
  else if (key === 'tianyuePn') payload = { tianyue_pn: value || null }
  else if (key === 'ibi') payload = { ibi: value }
  else if (key === 'internalComposition') payload = { tianyue_internal_composition: value }
  else payload = { extra_data: { ...(row.extra_data || {}), [key]: value || null } }
  if (key === 'price' && (payload.price !== null && (!Number.isFinite(payload.price as number) || (payload.price as number) < 0))) { ElMessage.warning('价格必须是非负数字'); return }
  if (key === 'priority' && (payload.priority !== null && ![1, 2, 3].includes(payload.priority as number))) { ElMessage.warning('优先级只能填写 1、2 或 3'); return }
  try {
    if (row.record_type === 'single_part') await afterSalesApi.updateRequirement(row.record_id, payload)
    else await afterSalesApi.updatePackage(row.record_id, payload)
    ElMessage.success('已保存，修改历史已记录')
    cancelInlineEdit()
    await loadRecords()
  } catch (error: any) { ElMessage.error(error?.message || '保存失败') }
}
async function loadWorkspace() {
  loading.value = true; errorMessage.value = ''
  try { workspaces.value = await afterSalesApi.listWorkspaces<Workspace[]>(); if (filters.workspaceId) await loadWorkspaceColumns(filters.workspaceId); await Promise.all([loadRecords(), loadVisibleFilterOptions()]) } catch (error: any) { errorMessage.value = error?.message || '售后档案加载失败' } finally { loading.value = false }
}
async function loadWorkspaceColumns(workspaceId: number) {
  try {
    const response = await afterSalesApi.getWorkspaceColumns<WorkspaceColumnConfig>(workspaceId)
    workspaceColumnConfig.value = response
    customFieldDrafts.value = response.custom_fields.map(field => ({ ...field, options: [...field.options] }))
    fieldLabelDrafts.value = { ...response.field_labels }
    detailSectionLabelDraft.value = response.detail_section_labels?.core_fields || '核心字段'
    applyViewConfig(response.default_view_config)
  } catch (error: any) { workspaceColumnConfig.value = null; customFieldDrafts.value = []; fieldLabelDrafts.value = {}; detailSectionLabelDraft.value = '核心字段'; applyViewConfig(baseViewConfig()); if (error?.status !== 404) ElMessage.error(error?.message || '客户表格配置加载失败') }
}
async function loadRecords() {
  try {
    const activeColumnFilters = Object.fromEntries(Object.entries(columnFilters).filter(([, values]) => values.length))
    const response = await afterSalesApi.search<{ items: SearchItem[]; total: number; summary: SearchSummary }>({ q: filters.q || undefined, workspace_id: filters.workspaceId, record_type: filters.recordType, status: filters.status, column_filters: Object.keys(activeColumnFilters).length ? JSON.stringify(activeColumnFilters) : undefined, sort_by: viewConfig.sortKey, sort_order: viewConfig.sortOrder, page: currentPage.value, page_size: pageSize.value })
    records.value = response.items; total.value = response.total; Object.assign(summary, response.summary || { total_records: response.total, priced_records: 0, missing_price_records: 0, drawing_ok_records: 0, sample_ok_records: 0, ppap_ok_records: 0 })
    if (!records.value.length && total.value && currentPage.value > 1) { currentPage.value = Math.ceil(total.value / pageSize.value); await loadRecords() }
  } catch (error: any) { errorMessage.value = error?.message || '查询失败' }
}
async function loadFilterOptions(columnKey: ColumnKey) {
  if (!columnKeys.value.includes(columnKey)) return
  try {
    const response = await afterSalesApi.filterOptions<{ options: ExcelFilterOption[] }>({
      column_key: columnKey,
      q: filters.q || undefined,
      workspace_id: filters.workspaceId,
      record_type: filters.recordType,
      status: filters.status,
    })
    const selected = new Set(columnFilters[columnKey] || [])
    filterOptionsByColumn[columnKey] = response.options.map(option => ({ ...option, checked: selected.has(String(option.value)) }))
  } catch (error: any) {
    ElMessage.error(error?.message || `加载${columnDefinitions.value[columnKey]?.label || '字段'}筛选项失败`)
  }
}
async function loadVisibleFilterOptions() { await Promise.all(visibleColumns.value.map(column => loadFilterOptions(column.key))) }
async function loadViewPreference() {
    try { const response = await afterSalesApi.getViewPreference<{ config: Partial<ViewConfig> }>(); applyViewConfig(response.config) } catch { applyViewConfig(baseViewConfig()) }
}
async function saveViewSettings() {
  viewSaving.value = true
  try {
    if (filters.workspaceId && workspaceColumnConfig.value) {
      const customFields = customFieldDrafts.value.map((field, index) => ({ ...field, sequence: index, width: viewConfig.widths[field.key] || field.width }))
      const detailTitle = detailSectionLabelDraft.value.trim()
      if (!detailTitle) { ElMessage.warning('请填写详情标题'); return }
       const saved = await afterSalesApi.updateWorkspaceColumns<WorkspaceColumnConfig>(filters.workspaceId, { expected_version: workspaceColumnConfig.value.version, field_labels: fieldLabelDrafts.value, detail_section_labels: { core_fields: detailTitle }, custom_fields: customFields, default_view_config: cloneViewConfig(viewConfig) })
      workspaceColumnConfig.value = saved; customFieldDrafts.value = saved.custom_fields.map(field => ({ ...field, options: [...field.options] })); fieldLabelDrafts.value = { ...saved.field_labels }; applyViewConfig(saved.default_view_config); ElMessage.success('客户表格配置已保存')
    } else {
      personalFieldLabels.value = Object.fromEntries(Object.entries(fieldLabelDrafts.value).filter(([, label]) => label.trim()))
      localStorage.setItem(personalFieldLabelsKey, JSON.stringify(personalFieldLabels.value))
      await afterSalesApi.updateViewPreference({ config: cloneViewConfig(viewConfig) }); ElMessage.success('视图已保存为我的视图')
    }
    viewConfigBeforeEdit.value = null; settingsOpen.value = false; await loadRecords()
  } catch (error: any) { ElMessage.error(error?.message || '视图设置保存失败') } finally { viewSaving.value = false }
}
async function loadRequirementOptions(workspaceId: number) {
  try {
    const response = await afterSalesApi.search<{ items: SearchItem[] }>({ workspace_id: workspaceId, record_type: 'single_part', page: 1, page_size: 100 })
    requirementOptions.value = response.items
  } catch { requirementOptions.value = [] }
}
async function openRecord(row: SearchItem) {
  drawerOpen.value = true; detailLoading.value = true; editing.value = false
  try {
    if (row.record_type === 'installation_package') {
       const item = await afterSalesApi.getPackage<any>(row.record_id); detail.value = { type: row.record_type, id: item.id, workspace_id: item.workspace_id, workspace_name: row.workspace_name, primaryNumber: item.package_number, priority: item.priority, dCode: item.d_code, tianyuePn: item.tianyue_pn, name: item.name, price: item.price, price_mismatch: item.price_mismatch, remark: item.remark, extraData: item.extra_data || {}, items: item.items || [], drawings: [], process_routes: [], documents: item.documents || [], change_history: item.change_history || [] }; void loadRequirementOptions(item.workspace_id)
    } else {
       requirementOptions.value = []; const item = await afterSalesApi.getRequirement<any>(row.record_id); detail.value = { type: row.record_type, id: item.id, workspace_id: item.workspace_id, workspace_name: row.workspace_name, single_part_id: item.single_part?.id, singlePartDrawingReference: item.single_part?.drawing_reference || null, singlePartDrawingPreviewUrl: item.single_part?.drawing_preview_url || null, primaryNumber: item.customer_part_number, ibi: item.ibi, internalComposition: item.tianyue_internal_composition, price: item.price, price_mismatch: false, name: item.single_part?.name, remark: item.remark, extraData: item.extra_data || {}, items: [], drawings: item.drawings || [], process_routes: hydrateRoutes(item.process_routes || []), documents: item.documents || [], change_history: item.change_history || [] }
    }
    if (detail.value) detail.value.updatedAt = row.updated_at
  } catch (error: any) { ElMessage.error(error?.message || '详情加载失败'); drawerOpen.value = false } finally { detailLoading.value = false }
}
function applyRequirementSelection(item: any) {
  if (!item.requirement_id) return
  const option = requirementOptions.value.find(candidate => candidate.record_id === item.requirement_id)
  if (!option) return
  item.unlinked_customer_part_number = null
  item.ibi = option.ibi || item.ibi
  item.tianyue_internal_composition = option.tianyue_internal_composition || item.tianyue_internal_composition
}
async function openLinkedRequirement(requirementId: number) {
  if (!detail.value) return
  if (hasUnsavedChanges()) {
    try {
      await ElMessageBox.confirm('当前编辑尚未保存，打开关联单件将丢弃本次修改。', '放弃未保存修改？', { confirmButtonText: '放弃修改', cancelButtonText: '继续编辑', type: 'warning' })
      cancelEditing()
    } catch { return }
  }
  await openRecord({ record_type: 'single_part', record_id: requirementId, workspace_id: detail.value.workspace_id, workspace_name: detail.value.workspace_name || '', updated_at: '' })
}
function startEditing() { if (!detail.value) return; originalDetail.value = cloneDetail(detail.value); draft.primaryNumber = detail.value.primaryNumber; draft.priority = detail.value.priority == null ? '' : String(detail.value.priority); draft.dCode = detail.value.dCode || ''; draft.tianyuePn = detail.value.tianyuePn || ''; draft.ibi = detail.value.ibi || ''; draft.internalComposition = detail.value.internalComposition || ''; draft.price = detail.value.price == null ? '' : String(detail.value.price); draft.name = detail.value.name || ''; draft.remark = detail.value.remark || ''; draft.extraData = { ...detail.value.extraData }; editing.value = true }
function cancelEditing() { if (originalDetail.value) detail.value = cloneDetail(originalDetail.value); originalDetail.value = null; editing.value = false }
async function requestDrawerClose(done: () => void) {
  if (!hasUnsavedChanges()) { done(); return }
  try { await ElMessageBox.confirm('当前编辑尚未保存，关闭后将丢弃本次修改。', '放弃未保存修改？', { confirmButtonText: '放弃修改', cancelButtonText: '继续编辑', type: 'warning' }); cancelEditing(); done() } catch { /* Continue editing. */ }
}
async function refreshCurrentDetail() {
  if (!detail.value) return
  await openRecord({ record_type: detail.value.type, record_id: detail.value.id, workspace_id: detail.value.workspace_id, workspace_name: detail.value.workspace_name || '', updated_at: '' })
}
async function saveDetail() {
  if (!detail.value) return
  const primaryNumber = draft.primaryNumber.trim()
  const priceText = draft.price.trim()
  const price = priceText === '' ? null : Number(priceText)
  if (!primaryNumber) { ElMessage.warning(detail.value.type === 'installation_package' ? '请填写安装包号' : '请填写客户件号'); return }
  if (price !== null && (!Number.isFinite(price) || price < 0)) { ElMessage.warning('请填写有效的非负价格'); return }
  if (detail.value.type === 'single_part' && (!draft.ibi.trim() || !draft.internalComposition.trim() || price === null)) { ElMessage.warning('客户件号、IBI、天越内部组成和价格均为必填项'); return }
  saving.value = true
  try {
     if (detail.value.type === 'installation_package') await afterSalesApi.updatePackage(detail.value.id, { expected_updated_at: detail.value.updatedAt, package_number: primaryNumber, priority: draft.priority ? Number(draft.priority) : null, d_code: draft.dCode || null, tianyue_pn: draft.tianyuePn || null, name: draft.name || null, price, extra_data: draft.extraData, remark: draft.remark || null })
     else await afterSalesApi.updateRequirement(detail.value.id, { expected_updated_at: detail.value.updatedAt, customer_part_number: primaryNumber, ibi: draft.ibi.trim(), tianyue_internal_composition: draft.internalComposition.trim(), price, extra_data: draft.extraData, remark: draft.remark || null, single_part_name: draft.name || null })
    ElMessage.success('档案已保存，修改历史已记录'); originalDetail.value = null; editing.value = false; await loadRecords(); await refreshCurrentDetail()
  } catch (error: any) { ElMessage.error(error?.status === 409 ? '档案已被其他用户更新，请刷新后再保存' : error?.message || '保存失败') } finally { saving.value = false }
}
async function saveItem(item: any) {
  if (!detail.value) return
  const payload = { expected_updated_at: item.updated_at, requirement_id: item.requirement_id || null, unlinked_customer_part_number: item.unlinked_customer_part_number || null, ibi: item.ibi, tianyue_internal_composition: item.tianyue_internal_composition, quantity: Number(item.quantity), sequence: Number(item.sequence), status: item.status || null, remark: item.remark || null }
  try { if (item.id) await afterSalesApi.updatePackageItem(detail.value.id, item.id, payload); else await afterSalesApi.createPackageItem(detail.value.id, payload); ElMessage.success('组成项已保存，修改历史已记录'); await refreshCurrentDetail() } catch (error: any) { ElMessage.error(error?.message || '组成项保存失败') }
}
function addPackageItem() { if (!detail.value) return; detail.value.items.push({ id: 0, _draftKey: `item-${Date.now()}`, requirement_id: null, unlinked_customer_part_number: '', ibi: '', tianyue_internal_composition: '', quantity: 1, sequence: detail.value.items.length + 1, status: null, remark: '' }) }
async function saveDrawing(drawing: any) {
  const payload = { expected_updated_at: drawing.updated_at, version: drawing.version, status: drawing.status, file_key: drawing.file_key, effective_from: drawing.effective_from || null, effective_to: drawing.effective_to || null, submitted_at: drawing.submitted_at || null, approved_at: drawing.approved_at || null, remark: drawing.remark || null }
  try { if (drawing.id) await afterSalesApi.updateDrawing(drawing.id, payload); else if (detail.value) await afterSalesApi.createRequirementDrawing(detail.value.id, payload); ElMessage.success('图纸版本已保存，修改历史已记录'); await refreshCurrentDetail() } catch (error: any) { ElMessage.error(error?.message || '图纸保存失败') }
}
function addRoute() { if (!detail.value) return; detail.value.process_routes.push({ id: 0, _draftKey: `route-${Date.now()}`, version: 'v1', status: 'draft', is_current: false, effective_from: null, remark: '', steps: [] }) }
function addRouteStep(route: any) {
  route.steps.push({ id: 0, _draftKey: `step-${Date.now()}-${route.steps.length}`, sequence: route.steps.length + 1, operation_name: '', machine_id: null, tooling_id: null, key_parameters: {}, quality_checkpoints: {}, _keyParametersText: '{}', _qualityCheckpointsText: '{}', remark: '' })
}
function removeRouteStep(route: any, index: number) {
  route.steps.splice(index, 1)
  route.steps.forEach((step: any, stepIndex: number) => { step.sequence = stepIndex + 1 })
}
function parseJsonObject(value: unknown, label: string) {
  try {
    const parsed = JSON.parse(typeof value === 'string' && value.trim() ? value : '{}')
    if (parsed === null || Array.isArray(parsed) || typeof parsed !== 'object') throw new Error('not an object')
    return parsed as Record<string, unknown>
  } catch { throw new Error(`${label}必须填写 JSON 对象`) }
}
function parseOptionalId(value: unknown, label: string) {
  if (value === null || value === undefined || value === '') return null
  const id = Number(value)
  if (!Number.isInteger(id) || id <= 0) throw new Error(`${label}必须是正整数`)
  return id
}
function serializeRouteSteps(route: any) {
  const sequences = new Set<number>()
  return (route.steps || []).map((step: any, index: number) => {
    const sequence = Number(step.sequence)
    const operationName = String(step.operation_name || '').trim()
    if (!Number.isInteger(sequence) || sequence < 1) throw new Error(`第 ${index + 1} 步的顺序必须是正整数`)
    if (sequences.has(sequence)) throw new Error('工艺步骤顺序不能重复')
    if (!operationName) throw new Error(`请填写第 ${index + 1} 步的工序名称`)
    sequences.add(sequence)
    return { sequence, operation_name: operationName, machine_id: parseOptionalId(step.machine_id, '机台 ID'), tooling_id: parseOptionalId(step.tooling_id, '模具 ID'), key_parameters: parseJsonObject(step._keyParametersText, `第 ${index + 1} 步关键参数`), quality_checkpoints: parseJsonObject(step._qualityCheckpointsText, `第 ${index + 1} 步质量检查点`), remark: step.remark || null }
  })
}
async function saveRoute(route: any) {
  let steps: any[]
  try { steps = serializeRouteSteps(route) } catch (error: any) { ElMessage.warning(error?.message || '请检查工艺步骤'); return }
  const payload = { expected_updated_at: route.updated_at, version: route.version, status: route.status, is_current: !!route.is_current, effective_from: route.effective_from || null, effective_to: route.effective_to || null, remark: route.remark || null, steps }
  try { if (route.id) await afterSalesApi.updateRoute(route.id, payload); else if (detail.value) await afterSalesApi.createRequirementRoute(detail.value.id, payload); ElMessage.success('工艺路线已保存，修改历史已记录'); await refreshCurrentDetail() } catch (error: any) { ElMessage.error(error?.message || '工艺路线保存失败') }
}
function addDocument() { if (!detail.value) return; detail.value.documents.push({ id: 0, _draftKey: `document-${Date.now()}`, document_type: 'ppap', status: 'not_started', submitted_at: null, concluded_at: null, remark: '', events: [] }) }
async function saveDocument(document: any) {
  const payload = { expected_updated_at: document.updated_at, document_type: document.document_type, status: document.status, remark: document.remark || null, submitted_at: document.submitted_at || null, concluded_at: document.concluded_at || null }
  try { if (document.id) await afterSalesApi.updateDocument(document.id, payload); else if (detail.value) { if (detail.value.type === 'single_part') await afterSalesApi.createRequirementDocument(detail.value.id, payload); else await afterSalesApi.createPackageDocument(detail.value.id, payload) } ElMessage.success('资料状态已保存，修改历史已记录'); await refreshCurrentDetail() } catch (error: any) { ElMessage.error(error?.message || '资料状态保存失败') }
}
function handleViewportResize() { viewportWidth.value = window.innerWidth }
onMounted(async () => { companyStore.setCompany('gaibo'); window.addEventListener('resize', handleViewportResize, { passive: true }); await loadViewPreference(); await loadWorkspace() })
onBeforeUnmount(() => { window.removeEventListener('resize', handleViewportResize); if (primaryClickTimer) clearTimeout(primaryClickTimer) })
</script>

<style scoped>
.after-sales-page { --archive-body-size: 13px; --archive-header-size: 11px; --archive-cell-x: 7px; --archive-compact-row: 40px; --archive-standard-row: 48px; display: flex; flex: 1 1 auto; flex-direction: column; min-width: 0; min-height: 0; padding: 10px 0 20px; color: var(--zephyr-ink, var(--zephyr-ink)); font-size: var(--archive-body-size); letter-spacing: 0; }
h1, h2, h3, h4, p { margin-top: 0; } h1 { margin: 0; font-size: 20px; line-height: 1.35; } h2 { margin-bottom: 0; font-size: 20px; } h3 { margin-bottom: 12px; font-size: 14px; } h3 small { color: var(--zephyr-muted, var(--zephyr-muted)); font-weight: 500; }
.muted { color: var(--zephyr-muted, var(--zephyr-muted)); font-size: 12px; }
.company-navigation { display: flex; align-items: center; gap: 12px; min-height: 42px; padding: 4px 0 7px; border-bottom: 1px solid var(--zephyr-border-soft); }
.company-navigation :deep(.el-segmented) { flex: 0 0 auto; --el-segmented-item-selected-color: var(--zephyr-primary); --el-segmented-item-selected-bg-color: var(--zephyr-primary-soft); }
.customer-navigation { display: flex; align-items: center; gap: 3px; min-width: 0; overflow-x: auto; scrollbar-width: thin; }
.customer-navigation button { flex: 0 0 auto; height: 32px; padding: 0 10px; border: 0; border-bottom: 2px solid transparent; background: transparent; color: #66756f; font: inherit; font-size: 12px; cursor: pointer; }
.customer-navigation button:hover { color: var(--zephyr-primary-hover); }
.customer-navigation button:focus-visible { outline: 2px solid rgba(86, 101, 168, .45); outline-offset: -2px; }
.customer-navigation button.active { border-bottom-color: var(--zephyr-primary, var(--zephyr-primary)); color: var(--zephyr-primary, var(--zephyr-primary)); font-weight: 650; }
.company-scope-note { flex: 0 0 auto; color: #9a6a18; font-size: 11px; white-space: nowrap; }
.archive-tabs button { flex: 0 0 auto; height: 32px; padding: 0 10px; border: 0; border-bottom: 2px solid transparent; background: transparent; color: #66756f; font: inherit; font-size: 12px; cursor: pointer; }
.archive-tabs button:hover { color: var(--zephyr-primary-hover); }
.archive-tabs button:focus-visible { outline: 2px solid rgba(86, 101, 168, .45); outline-offset: -2px; }
.archive-tabs button.active { border-bottom-color: var(--zephyr-primary, var(--zephyr-primary)); color: var(--zephyr-primary, var(--zephyr-primary)); font-weight: 650; }
.add-workspace-button { display: inline-flex; align-items: center; gap: 4px; color: var(--zephyr-primary, var(--zephyr-primary)) !important; }
.archive-toolbar { display: grid; grid-template-columns: minmax(156px, .55fr) minmax(320px, 1.5fr) auto; align-items: center; gap: 12px; min-height: 58px; padding: 6px 0; }
.archive-heading { min-width: 0; }
.archive-heading h1 { font-weight: 650; letter-spacing: 0; }
.archive-heading span { color: #7a8883; font-size: 11px; }
.archive-search { display: flex; align-items: center; min-width: 0; height: 32px; padding: 0 10px; border: 1px solid var(--zephyr-border, var(--zephyr-border)); border-radius: 4px; background: #fff; color: #7b8984; }
.archive-search:focus-within { border-color: var(--zephyr-primary, var(--zephyr-primary)); box-shadow: 0 0 0 3px rgba(86, 101, 168, .1); }
.archive-search :deep(.el-input__wrapper) { padding: 0 0 0 7px; box-shadow: none; }
.archive-filters { display: flex; align-items: center; gap: 7px; }
.archive-filters .el-select { width: 108px; }
.archive-filters :deep(.el-select__wrapper) { min-height: 32px; border-radius: 4px; }
.icon-button { width: 32px; height: 32px; padding: 0; border-radius: 4px; color: #53655f; }
.archive-summary { display: flex; align-items: center; gap: 18px; min-height: 30px; color: var(--zephyr-muted); font-size: 11px; font-variant-numeric: tabular-nums; white-space: nowrap; overflow-x: auto; }
.archive-summary strong { color: #43524d; font-weight: 650; }
.archive-summary .ok, .archive-summary .ok strong { color: #2f8065; }
.archive-summary .warning, .archive-summary .warning strong { color: #a56b12; }
.error-state { display: flex; justify-content: space-between; align-items: center; padding: 8px 12px; margin-bottom: 12px; color: #9f3131; background: #fff4f2; border: 1px solid #f0c8c2; border-radius: 4px; }
.record-panel { display: flex; flex: 1 1 auto; flex-direction: column; min-width: 0; min-height: 0; border-top: 1px solid #dce5e1; border-bottom: 1px solid #dce5e1; background: #fff; }
.record-panel :deep(.excel-grid) { flex: 1 1 auto; min-height: 0; }
.record-table { width: 100%; }
.table-header-content { display: inline-flex; align-items: center; gap: 3px; max-width: 100%; cursor: grab; user-select: none; }
.table-header-content:active { cursor: grabbing; }
.column-filter-button { width: 20px; height: 20px; padding: 0; color: #87938e; }
.column-filter-button:hover, .column-filter-button.active { color: var(--zephyr-primary, var(--zephyr-primary)); background: #e4f0ec; }
.column-filter-popover { display: grid; gap: 8px; }
.column-filter-actions { display: flex; justify-content: space-between; align-items: center; }
.record-table :deep(.el-table__body .cell) { min-width: 0; }
.record-table :deep(.el-table__header th.el-table__cell) { height: 34px; padding: 0 var(--archive-cell-x); color: #586761; background: #f5f8f7; font-size: var(--archive-header-size); font-weight: 650; }
.record-table :deep(.el-table__body td.el-table__cell) { padding: 0 var(--archive-cell-x); }
.record-table.density-compact :deep(.el-table__body td.el-table__cell) { height: var(--archive-compact-row); }
.record-table.density-standard :deep(.el-table__body td.el-table__cell) { height: var(--archive-standard-row); }
.record-table :deep(.cell) { padding: 0; line-height: 1.35; }
.record-table :deep(.el-table__row) { cursor: pointer; }
.record-table :deep(.el-table__row:hover > td) { background: var(--zephyr-primary-soft); }
.record-link { padding: 5px 0; border: 0; background: transparent; color: var(--zephyr-primary, var(--zephyr-primary)); font: inherit; font-weight: 650; cursor: pointer; }
.record-link:focus-visible { outline: 2px solid rgba(86, 101, 168, .45); outline-offset: 2px; }
.priority-text { color: #50605a; font-weight: 700; font-variant-numeric: tabular-nums; }
.component-inline { display: block; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.component-separator { color: #909b97; }
.component-token-external_purchase { color: #1769aa; }
.component-token-no_tooling { color: #df2019; }
.component-token-in_development { color: #b97800; }
.component-token-missing_ibi, .missing-ibi { color: #a86d00; font-weight: 650; }
.package-status { display: inline-flex; align-items: center; justify-content: center; gap: 9px; white-space: nowrap; font-size: 11px; }
.package-status span { display: inline-flex; align-items: center; gap: 4px; }
.package-status i { width: 7px; height: 7px; border-radius: 50%; background: #d4a017; }
.package-status .status-dot-ok { background: #32906b; }
.package-status .status-dot-not_ok { background: #e5231d; }
.price-heading { display: inline-grid; justify-items: center; line-height: 1.15; white-space: nowrap; }
.price-heading small { color: #72807c; font-size: 10px; font-weight: 500; }
.price-cell { display: inline-flex; align-items: center; justify-content: center; gap: 4px; min-width: 70px; }
.price-mismatch { color: #d8231d; }
.price-mismatch-mark { display: inline-grid; width: 15px; height: 15px; place-items: center; border: 1px solid currentColor; border-radius: 2px; color: #d8231d; font-size: 10px; font-weight: 700; line-height: 1; }
.price-mismatch-note { color: #d8231d; font-size: 11px; font-weight: 500; }
.type-mark { display: inline-flex; padding: 2px 6px; border-radius: 3px; font-size: 10px; font-weight: 700; }
.type-mark.single_part { color: #23624e; background: #e4f2eb; }
.type-mark.installation_package { color: #765218; background: #fbf1d9; }
.mono { font-family: 'IBM Plex Mono', 'Cascadia Mono', monospace; font-variant-numeric: tabular-nums slashed-zero; }
.numeric { font-variant-numeric: tabular-nums; }
.record-pagination { display: flex; align-items: center; justify-content: space-between; min-height: 42px; color: var(--zephyr-muted); font-size: 11px; font-variant-numeric: tabular-nums; }
.mobile-record-list { display: none; }
:global(.view-settings-drawer .el-drawer__body) { padding: 0 18px 18px; }
.view-settings-body { display: grid; gap: 22px; }
.view-settings-body section { min-width: 0; }
.view-settings-body h3 { margin: 0 0 10px; font-size: 13px; }
.sort-setting { display: grid; grid-template-columns: minmax(0, 1fr) 92px; gap: 8px; }
.settings-section-heading { display: flex; align-items: baseline; justify-content: space-between; gap: 10px; }
.settings-section-heading span { color: #83908b; font-size: 10px; }
.workspace-template-intro { padding: 12px; border: 1px solid #dfe9e4; border-radius: 5px; background: #f7faf8; }
.workspace-template-intro p { margin: 6px 0 0; color: var(--zephyr-muted); font-size: 11px; line-height: 1.45; }
.column-setting-list { border-top: 1px solid var(--zephyr-border-soft); }
.column-setting-item { border-bottom: 1px solid #e6ece9; }
.column-setting-row { display: grid; grid-template-columns: 24px minmax(0, 1fr) 68px auto 28px; align-items: center; gap: 6px; min-height: 42px; }
.column-setting-row :deep(.el-input-number) { width: 68px; }
.column-move-actions { display: flex; justify-content: flex-end; }
.column-move-actions .el-button { width: 28px; height: 28px; padding: 0; margin: 0; }
.column-label-readout { overflow: hidden; color: #3e4d47; text-overflow: ellipsis; white-space: nowrap; }
.custom-column-options { display: grid; grid-template-columns: 1fr 1fr; gap: 6px; padding: 0 0 8px 30px; }
.custom-column-options :deep(.el-input), .custom-column-options :deep(.el-select) { min-width: 0; }
.archived-fields { padding-top: 10px; color: #6f7d78; font-size: 12px; }
.archived-fields h4 { margin: 0 0 6px; color: #3f4f49; font-size: 12px; }
.archived-fields > div { display: flex; align-items: center; justify-content: space-between; min-height: 30px; border-bottom: 1px solid #eef2f0; }
.settings-footer { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
.settings-footer-actions { display: flex; gap: 8px; }
.dossier-header { display: flex; justify-content: space-between; gap: 24px; align-items: flex-start; padding: 24px 28px 20px; border-bottom: 1px solid #dfe8e4; } .dossier-actions { display: flex; gap: 8px; align-items: center; } .dossier-body { padding: 0 28px 30px; } .dossier-section { padding: 20px 0; border-bottom: 1px solid #e7edea; } .field-grid { display: grid; grid-template-columns: repeat(2, minmax(0,1fr)); gap: 12px 24px; } .field-grid label { display: grid; gap: 4px; color: #73807c; font-size: 12px; } .field-grid label strong { min-height: 28px; color: #26342f; font-size: 14px; font-weight: 600; } .field-grid .wide { grid-column: 1 / -1; } .items-table { border: 1px solid #e4ebe8; } .detail-columns { display: grid; grid-template-columns: 1fr 1fr; gap: 24px; } .detail-columns h4 { margin-bottom: 8px; font-size: 13px; } .detail-columns p { padding-bottom: 8px; margin-bottom: 8px; border-bottom: 1px solid #eef2f0; font-size: 13px; } .status-line { display: grid; gap: 6px; } .document-status-row { display: grid; gap: 8px; min-height: 32px; padding: 9px 10px; border: 1px solid #e4ebe8; border-left-width: 3px; border-radius: 4px; color: #4e5a56; background: #fbfcfb; font-size: 12px; } .document-status-row.editing { display: flex; align-items: center; flex-wrap: wrap; } .document-status-heading { display: flex; align-items: center; flex-wrap: wrap; gap: 12px; } .document-type { min-width: 48px; color: #33423d; font-weight: 650; } .document-status { display: inline-flex; align-items: center; gap: 5px; min-width: 72px; } .status-dot { width: 7px; height: 7px; border-radius: 50%; background: #85918d; } .document-event-list { display: grid; gap: 5px; padding-left: 4px; } .document-event { display: grid; grid-template-columns: 48px 72px minmax(0, 1fr); align-items: baseline; gap: 8px; padding: 5px 8px; border-left: 2px solid #d8e3de; background: #f3f6f4; border-radius: 3px; } .document-event-date { color: #53645d; font-family: 'IBM Plex Mono', 'Cascadia Mono', monospace; font-size: 11px; font-variant-numeric: tabular-nums; } .document-event strong { color: #33423d; font-size: 11px; } .document-event-raw { min-width: 0; overflow-wrap: anywhere; color: var(--zephyr-muted); font-family: 'IBM Plex Mono', 'Cascadia Mono', monospace; font-size: 11px; } .document-event-empty { padding: 3px 0 0 4px; margin: 0; color: #87938e; font-size: 11px; } .document-source { flex: 1 1 260px; color: var(--zephyr-muted); line-height: 1.35; } .document-status-row.ok { border-left-color: #218653; } .document-status-row.ok .status-dot { background: #218653; } .document-status-row.not_ok { border-left-color: #d92820; } .document-status-row.not_ok .status-dot { background: #d92820; } .document-status-row.in_progress { border-left-color: #b77900; } .document-status-row.in_progress .status-dot { background: #b77900; } .document-status-row.not_applicable { border-left-color: var(--zephyr-muted); }
.package-link-editor, .package-link-readout { display: grid; min-width: 0; gap: 4px; justify-items: stretch; } .package-link-readout { justify-items: start; line-height: 1.25; } .package-link-readout small { overflow-wrap: anywhere; color: #52615c; }
.section-heading { display: flex; align-items: center; justify-content: space-between; gap: 12px; } .section-heading h3 { margin-bottom: 16px; } .current-mark { display: inline-flex; padding: 2px 5px; margin-left: 6px; color: var(--zephyr-primary); background: #e1f1e9; border-radius: 3px; font-size: 10px; font-weight: 700; }
.editable-record { padding-bottom: 8px; margin-bottom: 8px; border-bottom: 1px solid #eef2f0; } .editable-record :deep(.el-input) { margin: 3px 0; } .document-status-row :deep(.el-input) { width: 160px; } .document-status-row :deep(.el-select), .document-status-row :deep(.el-date-editor) { width: 124px; }
.dossier-body, .dossier-section, .record-column { min-width: 0; } .section-heading-actions { display: flex; flex-wrap: wrap; align-items: center; gap: 4px; margin-bottom: 12px; } .detail-columns .record-column > h4 { margin-bottom: 8px; }
.drawing-editor-grid, .route-editor-header { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 8px 12px; } .route-editor-header { grid-template-columns: repeat(2, minmax(0, 1fr)); padding: 8px; margin-bottom: 8px; border: 1px solid #e4ebe8; border-radius: 4px; background: #fbfcfb; } .compact-field { display: grid; min-width: 0; gap: 4px; color: #73807c; font-size: 11px; } .compact-field.wide { grid-column: 1 / -1; } .compact-field :deep(.el-input), .compact-field :deep(.el-date-editor) { width: 100%; margin: 0; } .compact-field :deep(.el-date-editor) { min-width: 0; } .compact-field :deep(.el-switch) { min-height: 28px; }
.record-summary { display: flex; flex-wrap: wrap; align-items: baseline; gap: 6px 10px; color: #33423d; } .record-summary small { flex: 1 1 100%; overflow-wrap: anywhere; color: var(--zephyr-muted); font-size: 11px; } .record-meta { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 6px 12px; margin: 0; } .record-meta div { min-width: 0; } .record-meta .wide { grid-column: 1 / -1; } .record-meta dt { margin: 0 0 2px; color: #80908a; font-size: 10px; } .record-meta dd { margin: 0; overflow-wrap: anywhere; color: #4e5a56; font-size: 12px; } .route-remark { padding: 0 !important; color: var(--zephyr-muted); }
.route-step-heading { display: flex; align-items: center; justify-content: space-between; gap: 8px; min-height: 32px; color: #4e5a56; font-size: 12px; } .route-step-wrap { max-width: 100%; overflow-x: auto; overscroll-behavior: contain; scrollbar-gutter: stable; border: 1px solid #e4ebe8; border-radius: 4px; } .route-step-wrap:focus-visible { outline: 2px solid var(--zephyr-primary, var(--zephyr-primary)); outline-offset: 2px; } .route-step-table { min-width: 1000px; } .route-step-table :deep(.el-table__cell) { padding: 4px 0; vertical-align: top; } .route-step-table :deep(.el-table__cell .cell) { overflow: visible; line-height: 1.35; } .route-step-table :deep(.el-input-number) { width: 100%; } .route-step-table :deep(.el-textarea__inner) { min-width: 138px; font-family: 'IBM Plex Mono', 'Cascadia Mono', monospace; font-size: 11px; line-height: 1.35; } .json-readout { max-width: 220px; padding: 0; margin: 0; overflow-wrap: anywhere; color: #52615c; font-family: 'IBM Plex Mono', 'Cascadia Mono', monospace; font-size: 10px; line-height: 1.35; white-space: pre-wrap; } .route-empty { padding: 6px 0; margin: 0; border-bottom: 0 !important; } .record-editor-action { display: flex; justify-content: flex-end; padding-top: 4px; }
.status-value { display: inline-flex; min-width: 72px; justify-content: center; padding: 3px 6px; border-radius: 3px; background: #eef3f1; color: #5c6b65; font-size: 11px; font-weight: 650; }
.status-value.external_purchase { color: #1769aa; background: #e5f0fb; } .status-value.no_tooling { color: #d92820; background: #fde8e7; } .status-value.in_development { color: #a86d00; background: #fff1c7; }
.drawing-slot-card { padding: 10px 12px; margin-top: 14px; border: 1px dashed #c9d8d2; border-radius: 4px; background: #f8fbf9; }
.drawing-reservation-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; }
.drawing-reservation-grid .drawing-slot-card { margin-top: 0; }
.drawing-section-note { color: #81908a; font-size: 10px; }
.drawing-slot-heading { display: flex; align-items: flex-start; justify-content: space-between; gap: 12px; }
.drawing-slot-heading h5 { margin: 0; color: #3e4d47; font-size: 12px; font-weight: 650; }
.drawing-slot-heading small, .drawing-slot-note { color: #81908a; font-size: 10px; }
.drawing-slot-status { flex: 0 0 auto; padding: 2px 5px; border: 1px solid #d4e2dc; border-radius: 3px; color: #6d7c76; font-size: 10px; }
.drawing-thumbnail { display: flex; width: 176px; aspect-ratio: 4 / 3; min-height: 96px; align-items: center; justify-content: center; margin: 8px 0; overflow: hidden; border: 1px dashed #c9d8d2; border-radius: 4px; background: #f3f7f5; }
.drawing-thumbnail.has-preview { border-style: solid; background: #fff; }
.drawing-thumbnail-image { display: block; width: 100%; height: 100%; }
.drawing-thumbnail-placeholder { display: grid; justify-items: center; gap: 4px; color: #81908a; font-size: 10px; }
.drawing-thumbnail-placeholder strong { padding: 3px 5px; border: 1px solid #b9ccc4; border-radius: 3px; color: #587066; font-size: 11px; font-weight: 700; letter-spacing: .04em; }
.drawing-slot-reference { padding: 6px 0 0; margin: 0; overflow-wrap: anywhere; color: #52615c; font-size: 11px; }
.drawing-slot-card > .muted { padding: 6px 0 0; margin: 0; border: 0; font-size: 11px; }
.drawing-slot-note { display: block; padding-top: 6px; margin: 0; line-height: 1.35; }
.history-row { display: flex; gap: 12px; padding: 10px 0; } .history-dot { flex: 0 0 8px; width: 8px; height: 8px; margin-top: 5px; border-radius: 50%; background: #2c8068; } .history-row strong { font-size: 13px; } .history-row p { margin: 4px 0; color: #83908b; font-size: 11px; } .history-row pre { max-width: 100%; padding: 8px; margin: 0; overflow: auto; color: #5f6c67; background: #f7f9f8; font-size: 11px; }
@media (min-width: 1440px) {
  .after-sales-page { --archive-body-size: 14px; --archive-header-size: 12px; --archive-cell-x: 10px; --archive-compact-row: 44px; --archive-standard-row: 52px; }
  .archive-tabs { gap: 8px; min-height: 38px; }
  .archive-tabs button { height: 38px; padding: 0 14px; font-size: 13px; }
  .archive-toolbar { gap: 16px; min-height: 64px; padding: 8px 0; }
  .archive-search { height: 36px; padding-inline: 12px; }
  .archive-filters { gap: 8px; }
  .archive-filters :deep(.el-select__wrapper), .icon-button { min-height: 36px; height: 36px; }
  .icon-button { width: 36px; }
  .archive-summary { gap: 24px; min-height: 34px; font-size: 12px; }
  .record-table :deep(.el-table__header th.el-table__cell) { height: 40px; }
  .package-status { font-size: 12px; }
  .record-pagination { min-height: 48px; font-size: 12px; }
}
@media (min-width: 2200px) {
  .after-sales-page { --archive-cell-x: 12px; --archive-compact-row: 48px; --archive-standard-row: 56px; }
  .archive-toolbar { gap: 20px; min-height: 70px; }
  .archive-summary { gap: 30px; min-height: 38px; }
  .record-table :deep(.el-table__header th.el-table__cell) { height: 44px; }
  .type-mark { padding: 3px 8px; font-size: 11px; }
  .package-status { gap: 12px; }
}
@media (max-width: 820px) { .after-sales-page { padding: 8px 0 16px; } .archive-toolbar { grid-template-columns: 1fr; gap: 7px; padding: 8px 0; } .archive-heading span { display: none; } .archive-search { width: 100%; } .archive-filters { flex-wrap: wrap; justify-content: flex-start; } .archive-filters .el-select { flex: 1 1 120px; width: auto; } .archive-summary { gap: 12px; } .archive-summary span:nth-of-type(2), .archive-summary span:nth-of-type(4) { display: none; } .record-table { display: none; } .mobile-record-list { display: grid; border-top: 1px solid #dce5e1; } .mobile-record-row { display: grid; grid-template-columns: minmax(0, 1fr) auto; align-items: center; gap: 10px; min-height: 68px; padding: 8px 4px; border: 0; border-bottom: 1px solid #e0e7e4; background: #fff; color: #354640; font: inherit; text-align: left; } .mobile-record-row:focus-visible { outline: 2px solid rgba(86, 101, 168, .5); outline-offset: -2px; } .mobile-record-main, .mobile-record-meta { display: grid; min-width: 0; gap: 3px; } .mobile-record-main strong { color: var(--zephyr-primary); } .mobile-record-main small, .mobile-record-main > span { overflow: hidden; color: #74827d; font-size: 11px; text-overflow: ellipsis; white-space: nowrap; } .mobile-record-meta { justify-items: end; color: #596863; font-size: 11px; } .record-pagination { align-items: flex-start; flex-direction: column; padding: 7px 0; } .record-pagination :deep(.el-pagination__sizes) { display: none; } :global(.view-settings-drawer) { width: 100% !important; } .field-grid, .detail-columns { grid-template-columns: 1fr; } .dossier-header { padding: 18px 16px; } .dossier-actions { flex-wrap: wrap; justify-content: flex-end; } .dossier-body { padding: 0 16px 24px; } .document-status-row { align-items: flex-start; } .document-source { flex-basis: 100%; } .drawing-editor-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); } .route-editor-header { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
@media (max-width: 560px) { .dossier-header { gap: 12px; } .dossier-actions { gap: 4px; } .section-heading { align-items: flex-start; flex-wrap: wrap; } .section-heading-actions { width: 100%; margin-top: -8px; } .drawing-editor-grid, .route-editor-header, .record-meta { grid-template-columns: 1fr; } .compact-field.wide, .record-meta .wide { grid-column: auto; } .route-step-wrap { margin-inline: 0; } }
@media (max-width: 820px) { .drawing-reservation-grid { grid-template-columns: 1fr; } }
@media (prefers-reduced-motion: reduce) { .archive-tabs button { scroll-behavior: auto; } }
@media (max-width: 820px) { .company-navigation { align-items: flex-start; flex-wrap: wrap; gap: 5px 8px; } .customer-navigation { flex-basis: 100%; order: 2; } .company-scope-note { order: 3; max-width: 100%; overflow: hidden; text-overflow: ellipsis; } }
.field-grid-item { display: grid; gap: 4px; color: #73807c; font-size: 12px; }
.field-grid-item > strong { min-height: 28px; color: #26342f; font-size: 14px; font-weight: 600; }
.primary-number-field .field-hint { display: block; }
.package-status .status-dot-not_started { background: #aab4b0; }
.package-status span:has(.status-dot-not_started) { color: #7b8783; }
</style>
