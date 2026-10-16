<template>
  <div class="materials-container">
    <div class="list-view-toolbar">
      <div class="list-title-block">
        <el-button type="primary" @click="openCreate"><el-icon><Plus /></el-icon>新增</el-button>
        <h1>材料</h1>
      </div>

      <div class="search-control">
        <el-icon><Search /></el-icon>
        <el-input v-model="filter.search" placeholder="搜索材料名" clearable @keyup.enter="fetchMaterials" />
      </div>

      <div class="filter-controls">
        <el-select v-model="filter.category" placeholder="分类" clearable @change="fetchMaterials">
          <el-option v-for="category in categories" :key="category" :label="category" :value="category" />
        </el-select>
        <el-select v-model="filter.active" placeholder="状态" clearable @change="fetchMaterials">
          <el-option label="已启用" value="true" />
          <el-option label="已停用" value="false" />
        </el-select>
        <el-button @click="fetchMaterials">筛选</el-button>
        <el-button text @click="resetFilter">重置</el-button>
        <el-button class="view-toggle" text circle aria-label="列表视图" title="列表视图"><el-icon><Menu /></el-icon></el-button>
      </div>
    </div>

    <div class="table-meta"><span>{{ filteredMaterials.length }} 条记录</span><span>材料主数据列表</span></div>

    <el-table :data="pagedMaterials" v-loading="loading" stripe>
      <el-table-column prop="name" label="材料名" min-width="180" />
      <el-table-column prop="category" label="分类" width="130">
        <template #default="{ row }">{{ row.category || '-' }}</template>
      </el-table-column>
      <el-table-column label="密度" width="100" align="right">
        <template #default="{ row }">{{ formatDecimal(row.density) }}</template>
      </el-table-column>
      <el-table-column label="原料价 (元/kg)" width="140" align="right">
        <template #default="{ row }">{{ formatCurrency(row.default_price) }}</template>
      </el-table-column>
      <el-table-column label="废料价 (元/kg)" width="140" align="right">
        <template #default="{ row }">{{ formatCurrency(row.scrap_price) }}</template>
      </el-table-column>
      <el-table-column label="状态" width="100" align="center">
        <template #default="{ row }"><el-tag :type="row.is_active ? 'success' : 'info'">{{ row.is_active ? '已启用' : '已停用' }}</el-tag></template>
      </el-table-column>
      <el-table-column label="操作" width="145" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" size="small" :icon="Edit" @click="openEdit(row)">编辑</el-button>
          <el-button link type="danger" size="small" :icon="Delete" @click="removeMaterial(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <div class="pagination">
      <el-pagination
        v-model:current-page="page.current"
        v-model:page-size="page.size"
        :total="filteredMaterials.length"
        :page-sizes="[20, 50, 100]"
        layout="total, sizes, prev, pager, next"
        @size-change="page.current = 1"
      />
    </div>

    <el-dialog v-model="dialogVisible" :title="editId ? '编辑材料' : '新增材料'" width="min(620px, 92vw)" destroy-on-close>
      <el-form ref="formRef" :model="form" :rules="rules" label-width="92px">
        <el-form-item label="材料名" prop="name"><el-input v-model="form.name" placeholder="例如 SUS301/304" /></el-form-item>
        <el-form-item label="分类"><el-select v-model="form.category" filterable allow-create default-first-option placeholder="选择或输入分类" style="width: 100%"><el-option v-for="category in categories" :key="category" :label="category" :value="category" /></el-select></el-form-item>
        <div class="material-metrics">
          <el-form-item label="密度"><el-input-number v-model="form.density" :min="0" :precision="4" :formatter="formatInputNumber" controls-position="right" style="width: 100%" /></el-form-item>
          <el-form-item label="原料价"><el-input-number v-model="form.default_price" :min="0" :precision="4" :formatter="formatInputNumber" controls-position="right" style="width: 100%" /></el-form-item>
          <el-form-item label="废料价"><el-input-number v-model="form.scrap_price" :min="0" :precision="4" :formatter="formatInputNumber" controls-position="right" style="width: 100%" /></el-form-item>
        </div>
        <el-form-item label="状态"><el-switch v-model="form.is_active" active-text="启用" inactive-text="停用" /></el-form-item>
      </el-form>
      <template #footer><el-button @click="dialogVisible = false">取消</el-button><el-button type="primary" :loading="saving" @click="saveMaterial">保存</el-button></template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Delete, Edit, Menu, Plus, Search } from '@element-plus/icons-vue'
import { materialsApi } from '@/api/dictionary'

type Material = {
  id: number
  code: string
  name: string
  name_cn?: string | null
  density?: number | null
  thickness_range?: string | null
  category?: string | null
  standard?: string | null
  default_price?: number | null
  scrap_price?: number | null
  is_active: boolean
}

const loading = ref(false)
const saving = ref(false)
const dialogVisible = ref(false)
const editId = ref<number | null>(null)
const formRef = ref()
const materials = ref<Material[]>([])
const filter = reactive({ search: '', category: '', active: '' })
const page = reactive({ current: 1, size: 20 })
const form = reactive({
  code: '', name: '', name_cn: '', density: undefined as number | undefined,
  thickness_range: '', category: '', standard: '', default_price: undefined as number | undefined,
  scrap_price: undefined as number | undefined, is_active: true,
})

const rules = {
  name: [{ required: true, message: '请输入材料名', trigger: 'blur' }],
}

const categories = computed(() => [...new Set(materials.value.map(item => item.category).filter((item): item is string => Boolean(item)))].sort())
const filteredMaterials = computed(() => materials.value)
const pagedMaterials = computed(() => {
  const start = (page.current - 1) * page.size
  return filteredMaterials.value.slice(start, start + page.size)
})

const normalizeNullable = (value: string | number | undefined) => value === '' || value === undefined ? null : value
const formatDecimal = (value: number | null | undefined) => {
  if (value == null || !Number.isFinite(Number(value))) return '-'
  return Number(value).toFixed(4).replace(/\.?0+$/, '')
}
const formatCurrency = (value: number | null | undefined) => {
  if (value == null || !Number.isFinite(Number(value))) return ''
  return `¥${Number(value).toFixed(4).replace(/\.?0+$/, '')}`
}
const formatInputNumber = (value: string | number | undefined) => {
  if (value == null || value === '') return ''
  return String(value).replace(/\.?0+$/, '')
}

const materialCodeForName = (name: string) => {
  const normalized = name
    .trim()
    .toUpperCase()
    .replace(/[^A-Z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')

  return (normalized || 'MAT').slice(0, 38) + '-' + Date.now()
}

const fetchMaterials = async () => {
  loading.value = true
  try {
    const data = await materialsApi.list<Material[]>({
      search: filter.search || undefined,
      category: filter.category || undefined,
      is_active: filter.active || undefined,
      skip: 0,
      limit: 500,
    })
    materials.value = Array.isArray(data) ? data : []
    page.current = 1
  } catch (error: any) {
    materials.value = []
    ElMessage.error(error?.message || '获取材料列表失败')
  } finally {
    loading.value = false
  }
}

const resetFilter = () => {
  Object.assign(filter, { search: '', category: '', active: '' })
  fetchMaterials()
}

const resetForm = () => Object.assign(form, {
  code: '', name: '', name_cn: '', density: undefined, thickness_range: '', category: '',
  standard: '', default_price: undefined, scrap_price: undefined, is_active: true,
})

const openCreate = () => {
  editId.value = null
  resetForm()
  dialogVisible.value = true
}

const openEdit = (row: Material) => {
  editId.value = row.id
  Object.assign(form, {
    code: row.code, name: row.name, name_cn: row.name_cn || '', density: row.density ?? undefined,
    thickness_range: row.thickness_range || '', category: row.category || '', standard: row.standard || '',
    default_price: row.default_price ?? undefined, scrap_price: row.scrap_price ?? undefined, is_active: row.is_active,
  })
  dialogVisible.value = true
}

const saveMaterial = async () => {
  await formRef.value?.validate()
  saving.value = true
  const payload = {
    name: form.name.trim(),
    density: form.density ?? null,
    category: normalizeNullable(form.category.trim()),
    default_price: form.default_price ?? null, scrap_price: form.scrap_price ?? null, is_active: form.is_active,
  }
  try {
    if (editId.value) {
      await materialsApi.update(editId.value, payload)
      ElMessage.success('材料已更新')
    } else {
      const { is_active, ...createPayload } = payload
      await materialsApi.create({ code: materialCodeForName(form.name), ...createPayload })
      ElMessage.success('材料已创建')
    }
    dialogVisible.value = false
    await fetchMaterials()
  } catch (error: any) {
    ElMessage.error(error?.message || '保存材料失败')
  } finally {
    saving.value = false
  }
}

const removeMaterial = async (row: Material) => {
  try {
    await ElMessageBox.confirm(
      '删除材料“' + row.name + '”后，它将不再出现在材料库和报价候选中。',
      '确认删除材料',
      { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' },
    )
    await materialsApi.remove(row.id)
    ElMessage.success('材料已删除')
    await fetchMaterials()
  } catch (error: any) {
    if (error === 'cancel' || error === 'close') return
    ElMessage.error(error?.message || '删除材料失败')
  }
}

onMounted(fetchMaterials)
</script>

<style scoped>
.materials-container { min-width: 0; padding: 20px; }
.material-metrics { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 14px; margin-bottom: 18px; }
.material-metrics :deep(.el-form-item) { display: block; margin-bottom: 0; }
.material-metrics :deep(.el-form-item__label) { display: block; height: auto; padding: 0; margin-bottom: 6px; color: var(--zephyr-muted); line-height: 18px; text-align: left; }
.material-metrics :deep(.el-form-item__content) { margin-left: 0 !important; }
.material-metrics :deep(.el-input-number) { width: 100% !important; }
.list-view-toolbar { display: grid; grid-template-columns: auto minmax(240px, 1fr) auto; align-items: center; gap: 14px; min-height: 58px; margin-bottom: 10px; padding: 8px 0; }
.list-title-block { display: flex; align-items: center; gap: 10px; min-width: 150px; }
.list-title-block h1 { margin: 0; color: #4a4850; font-size: 20px; font-weight: 600; }
.search-control { display: flex; align-items: center; gap: 8px; width: min(480px, 100%); padding: 4px 10px; border: 1px solid #cbc9d1; border-radius: 3px; background: #fff; color: #7a7782; }
.search-control :deep(.el-input__wrapper) { padding: 0; box-shadow: none; }
.filter-controls { display: flex; align-items: center; justify-content: flex-end; gap: 6px; }
.filter-controls :deep(.el-select) { width: 110px; }
.view-toggle { color: #625780; }
.table-meta { display: flex; justify-content: space-between; margin: 0 0 8px; color: var(--zephyr-muted); font-size: 12px; }
.table-meta span:last-child { color: #96939e; }
.pagination { display: flex; justify-content: flex-end; margin-top: 16px; }
@media (max-width: 1040px) { .list-view-toolbar { grid-template-columns: 1fr; }.filter-controls { justify-content: flex-start; flex-wrap: wrap; } }
@media (max-width: 520px) { .material-metrics { grid-template-columns: 1fr; gap: 10px; } }
</style>
