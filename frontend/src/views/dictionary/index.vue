<template>
  <div class="dictionary-management">
    <el-card>
      <template #header>
        <div class="card-header">
          <span class="title">字典管理</span>
        </div>
      </template>

      <el-tabs v-model="activeTab" type="card">
        <!-- 零件名称字典 -->
        <el-tab-pane label="零件名称" name="partName">
          <div class="table-operations">
            <el-input
              v-model="partNameSearch"
              placeholder="搜索零件名称"
              style="width: 300px"
              clearable
              @clear="loadPartNames"
            >
              <template #append>
                <el-button :icon="Search" @click="loadPartNames" />
              </template>
            </el-input>
            <el-button type="primary" @click="openPartNameDialog()">新增零件名称</el-button>
          </div>

          <el-table :data="partNames" border stripe style="margin-top: 20px">
            <el-table-column prop="id" label="ID" width="80" />
            <el-table-column prop="primary_category" label="一级分类" width="120" />
            <el-table-column prop="secondary_category" label="二级分类" width="120" />
            <el-table-column prop="customer_part_name" label="客户零件名称" min-width="180" />
            <el-table-column prop="remark" label="备注" min-width="150" show-overflow-tooltip />
            <el-table-column prop="usage_count" label="使用次数" width="100" />
            <el-table-column prop="is_active" label="状态" width="80">
              <template #default="{ row }">
                <el-tag :type="row.is_active ? 'success' : 'info'">
                  {{ row.is_active ? '启用' : '停用' }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="150" fixed="right">
              <template #default="{ row }">
                <el-button link type="primary" size="small" @click="openPartNameDialog(row)">编辑</el-button>
                <el-button link type="danger" size="small" @click="deletePartName(row)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>

        <!-- 材质字典 -->
        <el-tab-pane label="材质" name="material">
          <div class="table-operations">
            <el-input
              v-model="materialSearch"
              placeholder="搜索材质代码或名称"
              style="width: 300px"
              clearable
              @clear="loadMaterials"
            >
              <template #append>
                <el-button :icon="Search" @click="loadMaterials" />
              </template>
            </el-input>
            <el-button type="primary" @click="openMaterialDialog()">新增材质</el-button>
          </div>

          <el-table :data="materials" border stripe style="margin-top: 20px">
            <el-table-column prop="id" label="ID" width="80" />
            <el-table-column prop="code" label="材质代码" width="150" />
            <el-table-column prop="name" label="材质名称" width="180" />
            <el-table-column prop="name_cn" label="中文俗称" width="150" />
            <el-table-column prop="category" label="分类" width="120" />
            <el-table-column prop="density" label="密度(g/cm³)" width="120" />
            <el-table-column prop="is_active" label="状态" width="80">
              <template #default="{ row }">
                <el-tag :type="row.is_active ? 'success' : 'info'">
                  {{ row.is_active ? '启用' : '停用' }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="150" fixed="right">
              <template #default="{ row }">
                <el-button link type="primary" size="small" @click="openMaterialDialog(row)">编辑</el-button>
                <el-button link type="danger" size="small" @click="deleteMaterial(row)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>

        <!-- 机台吨位字典 -->
        <el-tab-pane label="机台吨位" name="machineTonnage">
          <div class="table-operations">
            <el-button type="primary" @click="openMachineTonnageDialog()">新增机台吨位</el-button>
          </div>

          <el-table :data="machineTonnages" border stripe style="margin-top: 20px">
            <el-table-column prop="id" label="ID" width="80" />
            <el-table-column prop="tonnage" label="吨位" width="100" />
            <el-table-column prop="machine_type" label="机台类型" width="150" />
            <el-table-column prop="display_name" label="显示名称" width="180" />
            <el-table-column prop="size_category" label="规模分类" width="120" />
            <el-table-column prop="type_category" label="类型分类" width="120" />
            <el-table-column prop="is_active" label="状态" width="80">
              <template #default="{ row }">
                <el-tag :type="row.is_active ? 'success' : 'info'">
                  {{ row.is_active ? '启用' : '停用' }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="150" fixed="right">
              <template #default="{ row }">
                <el-button link type="primary" size="small" @click="openMachineTonnageDialog(row)">编辑</el-button>
                <el-button link type="danger" size="small" @click="deleteMachineTonnage(row)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>

        <!-- 模具类型字典 -->
        <el-tab-pane label="模具类型" name="moldType">
          <div class="table-operations">
            <el-button type="primary" @click="openMoldTypeDialog()">新增模具类型</el-button>
          </div>

          <el-table :data="moldTypes" border stripe style="margin-top: 20px">
            <el-table-column prop="id" label="ID" width="80" />
            <el-table-column prop="code" label="类型代码" width="150" />
            <el-table-column prop="name" label="类型名称" width="150" />
            <el-table-column prop="name_en" label="英文名称" width="180" />
            <el-table-column prop="complexity_level" label="复杂度" width="100" />
            <el-table-column prop="typical_lifecycle" label="典型寿命(万次)" width="140" />
            <el-table-column prop="is_active" label="状态" width="80">
              <template #default="{ row }">
                <el-tag :type="row.is_active ? 'success' : 'info'">
                  {{ row.is_active ? '启用' : '停用' }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="150" fixed="right">
              <template #default="{ row }">
                <el-button link type="primary" size="small" @click="openMoldTypeDialog(row)">编辑</el-button>
                <el-button link type="danger" size="small" @click="deleteMoldType(row)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>
      </el-tabs>
    </el-card>

    <!-- 零件名称对话框 -->
    <el-dialog
      v-model="partNameDialogVisible"
      :title="partNameForm.id ? '编辑零件名称' : '新增零件名称'"
      width="600px"
    >
      <el-form :model="partNameForm" label-width="120px">
        <el-form-item label="一级分类" required>
          <el-input v-model="partNameForm.primary_category" placeholder="必填。如：弹簧片、报警器" />
        </el-form-item>
        <el-form-item label="二级分类">
          <el-input v-model="partNameForm.secondary_category" placeholder="选填。如：标准型、加强型" />
        </el-form-item>
        <el-form-item label="客户零件名称">
          <el-input v-model="partNameForm.customer_part_name" placeholder="选填。客户定制的零件名称" />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="partNameForm.remark" type="textarea" :rows="3" placeholder="选填" />
        </el-form-item>
        <el-form-item label="状态">
          <el-switch v-model="partNameForm.is_active" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="partNameDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="savePartName">保存</el-button>
      </template>
    </el-dialog>

    <!-- 材质对话框 -->
    <el-dialog
      v-model="materialDialogVisible"
      :title="materialForm.id ? '编辑材质' : '新增材质'"
      width="600px"
    >
      <el-form :model="materialForm" label-width="120px">
        <el-form-item label="材质代码" required>
          <el-input v-model="materialForm.code" placeholder="如：SPCC、08AL" />
        </el-form-item>
        <el-form-item label="材质名称" required>
          <el-input v-model="materialForm.name" placeholder="请输入材质名称" />
        </el-form-item>
        <el-form-item label="中文俗称">
          <el-input v-model="materialForm.name_cn" placeholder="如：冷轧钢板" />
        </el-form-item>
        <el-form-item label="分类">
          <el-input v-model="materialForm.category" placeholder="如：冷轧板、不锈钢" />
        </el-form-item>
        <el-form-item label="密度(g/cm³)">
          <el-input-number v-model="materialForm.density" :precision="4" :step="0.01" />
        </el-form-item>
        <el-form-item label="执行标准">
          <el-input v-model="materialForm.standard" placeholder="如：GB/T、JIS" />
        </el-form-item>
        <el-form-item label="状态">
          <el-switch v-model="materialForm.is_active" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="materialDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="saveMaterial">保存</el-button>
      </template>
    </el-dialog>

    <!-- 机台吨位对话框 -->
    <el-dialog
      v-model="machineTonnageDialogVisible"
      :title="machineTonnageForm.id ? '编辑机台吨位' : '新增机台吨位'"
      width="600px"
    >
      <el-form :model="machineTonnageForm" label-width="120px">
        <el-form-item label="吨位" required>
          <el-input-number v-model="machineTonnageForm.tonnage" :min="1" />
        </el-form-item>
        <el-form-item label="机台类型" required>
          <el-select v-model="machineTonnageForm.machine_type" placeholder="请选择机台类型">
            <el-option label="冲床" value="punch_press" />
            <el-option label="液压机" value="hydraulic_press" />
            <el-option label="伺服压力机" value="servo_press" />
          </el-select>
        </el-form-item>
        <el-form-item label="显示名称" required>
          <el-input v-model="machineTonnageForm.display_name" placeholder="如：25吨冲床" />
        </el-form-item>
        <el-form-item label="规模分类">
          <el-select v-model="machineTonnageForm.size_category" placeholder="请选择规模">
            <el-option label="小型" value="小型" />
            <el-option label="中型" value="中型" />
            <el-option label="大型" value="大型" />
            <el-option label="特大型" value="特大型" />
          </el-select>
        </el-form-item>
        <el-form-item label="类型分类">
          <el-input v-model="machineTonnageForm.type_category" placeholder="如：冲床、液压机" />
        </el-form-item>
        <el-form-item label="状态">
          <el-switch v-model="machineTonnageForm.is_active" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="machineTonnageDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="saveMachineTonnage">保存</el-button>
      </template>
    </el-dialog>

    <!-- 模具类型对话框 -->
    <el-dialog
      v-model="moldTypeDialogVisible"
      :title="moldTypeForm.id ? '编辑模具类型' : '新增模具类型'"
      width="600px"
    >
      <el-form :model="moldTypeForm" label-width="140px">
        <el-form-item label="类型代码" required>
          <el-input v-model="moldTypeForm.code" placeholder="如：progressive" />
        </el-form-item>
        <el-form-item label="类型名称" required>
          <el-input v-model="moldTypeForm.name" placeholder="如：连续模" />
        </el-form-item>
        <el-form-item label="英文名称">
          <el-input v-model="moldTypeForm.name_en" placeholder="如：Progressive Die" />
        </el-form-item>
        <el-form-item label="复杂度">
          <el-select v-model="moldTypeForm.complexity_level" placeholder="请选择复杂度">
            <el-option label="简单" value="简单" />
            <el-option label="中等" value="中等" />
            <el-option label="复杂" value="复杂" />
          </el-select>
        </el-form-item>
        <el-form-item label="典型寿命(万次)">
          <el-input-number v-model="moldTypeForm.typical_lifecycle" :min="0" :step="100000" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="moldTypeForm.description" type="textarea" :rows="3" />
        </el-form-item>
        <el-form-item label="状态">
          <el-switch v-model="moldTypeForm.is_active" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="moldTypeDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="saveMoldType">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Search } from '@element-plus/icons-vue'
import request from '@/utils/request'

const activeTab = ref('partName')

// 零件名称
const partNames = ref([])
const partNameSearch = ref('')
const partNameDialogVisible = ref(false)
const partNameForm = ref({
  id: null,
  primary_category: '',
  secondary_category: '',
  customer_part_name: '',
  remark: '',
  is_active: true
})

// 材质
const materials = ref([])
const materialSearch = ref('')
const materialDialogVisible = ref(false)
const materialForm = ref({
  id: null,
  code: '',
  name: '',
  name_cn: '',
  category: '',
  density: null,
  standard: '',
  is_active: true
})

// 机台吨位
const machineTonnages = ref([])
const machineTonnageDialogVisible = ref(false)
const machineTonnageForm = ref({
  id: null,
  tonnage: null,
  machine_type: '',
  display_name: '',
  size_category: '',
  type_category: '',
  is_active: true
})

// 模具类型
const moldTypes = ref([])
const moldTypeDialogVisible = ref(false)
const moldTypeForm = ref({
  id: null,
  code: '',
  name: '',
  name_en: '',
  complexity_level: '',
  typical_lifecycle: null,
  description: '',
  is_active: true
})

// 加载数据
const loadPartNames = async () => {
  try {
    const params: any = { limit: 500 }
    if (partNameSearch.value) params.search = partNameSearch.value
    const res = await request.get('/api/v1/part-names', { params })
    partNames.value = res.data
  } catch (error: any) {
    ElMessage.error(error.response?.data?.detail || '加载失败')
  }
}

const loadMaterials = async () => {
  try {
    const params: any = { limit: 500 }
    if (materialSearch.value) params.search = materialSearch.value
    const res = await request.get('/api/v1/materials', { params })
    materials.value = res.data
  } catch (error: any) {
    ElMessage.error(error.response?.data?.detail || '加载失败')
  }
}

const loadMachineTonnages = async () => {
  try {
    const res = await request.get('/api/v1/machine-tonnages', { params: { limit: 500 } })
    machineTonnages.value = res.data
  } catch (error: any) {
    ElMessage.error(error.response?.data?.detail || '加载失败')
  }
}

const loadMoldTypes = async () => {
  try {
    const res = await request.get('/api/v1/mold-types', { params: { limit: 500 } })
    moldTypes.value = res.data
  } catch (error: any) {
    ElMessage.error(error.response?.data?.detail || '加载失败')
  }
}

// 打开对话框
const openPartNameDialog = (row?: any) => {
  if (row) {
    partNameForm.value = { ...row }
  } else {
    partNameForm.value = {
      id: null,
      primary_category: '',
      secondary_category: '',
      customer_part_name: '',
      remark: '',
      is_active: true
    }
  }
  partNameDialogVisible.value = true
}

const openMaterialDialog = (row?: any) => {
  if (row) {
    materialForm.value = { ...row }
  } else {
    materialForm.value = { id: null, code: '', name: '', name_cn: '', category: '', density: null, standard: '', is_active: true }
  }
  materialDialogVisible.value = true
}

const openMachineTonnageDialog = (row?: any) => {
  if (row) {
    machineTonnageForm.value = { ...row }
  } else {
    machineTonnageForm.value = { id: null, tonnage: null, machine_type: '', display_name: '', size_category: '', type_category: '', is_active: true }
  }
  machineTonnageDialogVisible.value = true
}

const openMoldTypeDialog = (row?: any) => {
  if (row) {
    moldTypeForm.value = { ...row }
  } else {
    moldTypeForm.value = { id: null, code: '', name: '', name_en: '', complexity_level: '', typical_lifecycle: null, description: '', is_active: true }
  }
  moldTypeDialogVisible.value = true
}

// 保存
const savePartName = async () => {
  try {
    if (!partNameForm.value.primary_category) {
      ElMessage.warning('请输入一级分类')
      return
    }
    if (partNameForm.value.id) {
      await request.patch(`/api/v1/part-names/${partNameForm.value.id}`, partNameForm.value)
      ElMessage.success('更新成功')
    } else {
      await request.post('/api/v1/part-names', partNameForm.value)
      ElMessage.success('创建成功')
    }
    partNameDialogVisible.value = false
    loadPartNames()
  } catch (error: any) {
    ElMessage.error(error.response?.data?.detail || '保存失败')
  }
}

const saveMaterial = async () => {
  try {
    if (!materialForm.value.code || !materialForm.value.name) {
      ElMessage.warning('请输入材质代码和名称')
      return
    }
    if (materialForm.value.id) {
      await request.patch(`/api/v1/materials/${materialForm.value.id}`, materialForm.value)
      ElMessage.success('更新成功')
    } else {
      await request.post('/api/v1/materials', materialForm.value)
      ElMessage.success('创建成功')
    }
    materialDialogVisible.value = false
    loadMaterials()
  } catch (error: any) {
    ElMessage.error(error.response?.data?.detail || '保存失败')
  }
}

const saveMachineTonnage = async () => {
  try {
    if (!machineTonnageForm.value.tonnage || !machineTonnageForm.value.machine_type || !machineTonnageForm.value.display_name) {
      ElMessage.warning('请填写必填项')
      return
    }
    if (machineTonnageForm.value.id) {
      await request.patch(`/api/v1/machine-tonnages/${machineTonnageForm.value.id}`, machineTonnageForm.value)
      ElMessage.success('更新成功')
    } else {
      await request.post('/api/v1/machine-tonnages', machineTonnageForm.value)
      ElMessage.success('创建成功')
    }
    machineTonnageDialogVisible.value = false
    loadMachineTonnages()
  } catch (error: any) {
    ElMessage.error(error.response?.data?.detail || '保存失败')
  }
}

const saveMoldType = async () => {
  try {
    if (!moldTypeForm.value.code || !moldTypeForm.value.name) {
      ElMessage.warning('请输入类型代码和名称')
      return
    }
    if (moldTypeForm.value.id) {
      await request.patch(`/api/v1/mold-types/${moldTypeForm.value.id}`, moldTypeForm.value)
      ElMessage.success('更新成功')
    } else {
      await request.post('/api/v1/mold-types', moldTypeForm.value)
      ElMessage.success('创建成功')
    }
    moldTypeDialogVisible.value = false
    loadMoldTypes()
  } catch (error: any) {
    ElMessage.error(error.response?.data?.detail || '保存失败')
  }
}

// 删除
const deletePartName = async (row: any) => {
  try {
    const displayName = [
      row.primary_category,
      row.secondary_category,
      row.customer_part_name
    ].filter(Boolean).join(' - ') || `ID: ${row.id}`

    await ElMessageBox.confirm(`确定删除零件名称 "${displayName}" 吗？`, '提示', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    })
    await request.delete(`/api/v1/part-names/${row.id}`)
    ElMessage.success('删除成功')
    loadPartNames()
  } catch (error: any) {
    if (error !== 'cancel') {
      ElMessage.error(error.response?.data?.detail || '删除失败')
    }
  }
}

const deleteMaterial = async (row: any) => {
  try {
    await ElMessageBox.confirm(`确定删除材质 "${row.name}" 吗？`, '提示', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    })
    await request.delete(`/api/v1/materials/${row.id}`)
    ElMessage.success('删除成功')
    loadMaterials()
  } catch (error: any) {
    if (error !== 'cancel') {
      ElMessage.error(error.response?.data?.detail || '删除失败')
    }
  }
}

const deleteMachineTonnage = async (row: any) => {
  try {
    await ElMessageBox.confirm(`确定删除机台吨位 "${row.display_name}" 吗？`, '提示', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    })
    await request.delete(`/api/v1/machine-tonnages/${row.id}`)
    ElMessage.success('删除成功')
    loadMachineTonnages()
  } catch (error: any) {
    if (error !== 'cancel') {
      ElMessage.error(error.response?.data?.detail || '删除失败')
    }
  }
}

const deleteMoldType = async (row: any) => {
  try {
    await ElMessageBox.confirm(`确定删除模具类型 "${row.name}" 吗？`, '提示', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    })
    await request.delete(`/api/v1/mold-types/${row.id}`)
    ElMessage.success('删除成功')
    loadMoldTypes()
  } catch (error: any) {
    if (error !== 'cancel') {
      ElMessage.error(error.response?.data?.detail || '删除失败')
    }
  }
}

onMounted(() => {
  loadPartNames()
  loadMaterials()
  loadMachineTonnages()
  loadMoldTypes()
})
</script>

<style scoped lang="scss">
.dictionary-management {
  .card-header {
    display: flex;
    justify-content: space-between;
    align-items: center;

    .title {
      font-size: 18px;
      font-weight: bold;
    }
  }

  .table-operations {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 20px;
  }
}
</style>
