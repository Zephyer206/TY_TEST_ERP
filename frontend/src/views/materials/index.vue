<template>
  <div class="materials-container">
    <el-card class="header-card">
      <div class="header-content">
        <h2>原材料管理</h2>
        <el-button type="primary" @click="showCreateDialog = true">
          <el-icon><Plus /></el-icon>
          新增原材料
        </el-button>
      </div>
    </el-card>

    <!-- 筛选条件 -->
    <el-card class="filter-card">
      <el-form :inline="true" :model="filters">
        <el-form-item label="材质">
          <el-select v-model="filters.material" placeholder="全部材质" clearable style="width: 150px">
            <el-option label="SPCC" value="SPCC" />
            <el-option label="SECC" value="SECC" />
            <el-option label="不锈钢" value="stainless" />
            <el-option label="铝合金" value="aluminum" />
          </el-select>
        </el-form-item>
        <el-form-item label="规格">
          <el-input v-model="filters.spec" placeholder="如：1.0×1000" clearable style="width: 150px" />
        </el-form-item>
        <el-form-item label="供应商">
          <el-input v-model="filters.supplier" placeholder="供应商名称" clearable style="width: 150px" />
        </el-form-item>
        <el-form-item label="库存预警">
          <el-select v-model="filters.stockAlert" placeholder="全部" clearable style="width: 120px">
            <el-option label="库存充足" value="normal" />
            <el-option label="库存预警" value="warning" />
            <el-option label="库存不足" value="shortage" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="loadData">查询</el-button>
          <el-button @click="resetFilters">重置</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- 原材料列表 -->
    <el-card>
      <el-table :data="materialList" v-loading="loading" border stripe>
        <el-table-column prop="materialCode" label="物料编码" width="130" fixed="left" />
        <el-table-column prop="materialName" label="材质" width="120" />
        <el-table-column prop="specification" label="规格" width="150">
          <template #default="{ row }">
            {{ row.thickness }}×{{ row.width }}mm
          </template>
        </el-table-column>
        <el-table-column prop="supplierName" label="供应商" width="150" />
        <el-table-column prop="stockQuantity" label="库存数量" width="120" align="right">
          <template #default="{ row }">
            <el-text :type="getStockColor(row.stockQuantity, row.safetyStock)">
              {{ row.stockQuantity.toFixed(2) }} {{ row.unit }}
            </el-text>
          </template>
        </el-table-column>
        <el-table-column prop="safetyStock" label="安全库存" width="120" align="right">
          <template #default="{ row }">
            {{ row.safetyStock }} {{ row.unit }}
          </template>
        </el-table-column>
        <el-table-column prop="unit" label="单位" width="80" align="center" />
        <el-table-column prop="unitPrice" label="单价" width="100" align="right">
          <template #default="{ row }">
            ¥{{ row.unitPrice.toFixed(2) }}
          </template>
        </el-table-column>
        <el-table-column label="库存状态" width="100" align="center">
          <template #default="{ row }">
            <el-tag :type="getStockAlertType(row.stockQuantity, row.safetyStock)">
              {{ getStockAlertText(row.stockQuantity, row.safetyStock) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="lastPurchaseDate" label="最近采购" width="110" />
        <el-table-column label="操作" width="220" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" link @click="viewBatches(row.id)">批次管理</el-button>
            <el-button type="success" link @click="handlePurchase(row)">采购</el-button>
            <el-button type="warning" link @click="handleEdit(row)">编辑</el-button>
          </template>
        </el-table-column>
      </el-table>

      <!-- 分页 -->
      <div class="pagination-container">
        <el-pagination
          v-model:current-page="pagination.page"
          v-model:page-size="pagination.pageSize"
          :page-sizes="[10, 20, 50, 100]"
          :total="pagination.total"
          layout="total, sizes, prev, pager, next, jumper"
          @size-change="loadData"
          @current-change="loadData"
        />
      </div>
    </el-card>

    <!-- 新增/编辑原材料对话框 -->
    <el-dialog
      v-model="showCreateDialog"
      :title="editMode ? '编辑原材料' : '新增原材料'"
      width="700px"
      :close-on-click-modal="false"
    >
      <el-form :model="materialForm" :rules="materialRules" ref="materialFormRef" label-width="120px">
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="物料编码" prop="materialCode">
              <el-input v-model="materialForm.materialCode" placeholder="如：MAT-2026-001" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="材质" prop="materialName">
              <el-select v-model="materialForm.materialName" placeholder="选择材质" style="width: 100%">
                <el-option label="SPCC" value="SPCC" />
                <el-option label="SECC" value="SECC" />
                <el-option label="不锈钢" value="不锈钢" />
                <el-option label="铝合金" value="铝合金" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="8">
            <el-form-item label="厚度(mm)" prop="thickness">
              <el-input-number v-model="materialForm.thickness" :min="0.1" :max="10" :precision="2" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="宽度(mm)" prop="width">
              <el-input-number v-model="materialForm.width" :min="10" :max="2000" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="单位" prop="unit">
              <el-select v-model="materialForm.unit" style="width: 100%">
                <el-option label="吨" value="吨" />
                <el-option label="公斤" value="公斤" />
                <el-option label="米" value="米" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="供应商" prop="supplierId">
              <el-select v-model="materialForm.supplierId" placeholder="选择供应商" style="width: 100%">
                <el-option
                  v-for="supplier in suppliersList"
                  :key="supplier.id"
                  :label="supplier.name"
                  :value="supplier.id"
                />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="单价(元)" prop="unitPrice">
              <el-input-number v-model="materialForm.unitPrice" :min="0" :precision="2" style="width: 100%" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="当前库存">
              <el-input-number v-model="materialForm.stockQuantity" :min="0" :precision="2" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="安全库存" prop="safetyStock">
              <el-input-number v-model="materialForm.safetyStock" :min="0" :precision="2" style="width: 100%" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="备注">
          <el-input v-model="materialForm.notes" type="textarea" :rows="2" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showCreateDialog = false">取消</el-button>
        <el-button type="primary" @click="submitMaterial" :loading="submitting">
          {{ editMode ? '保存' : '创建' }}
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'
import { useRouter } from 'vue-router'
import type { FormInstance, FormRules } from 'element-plus'

const router = useRouter()

const loading = ref(false)
const showCreateDialog = ref(false)
const submitting = ref(false)
const editMode = ref(false)

const filters = reactive({
  material: '',
  spec: '',
  supplier: '',
  stockAlert: ''
})

const pagination = reactive({
  page: 1,
  pageSize: 20,
  total: 0
})

const materialList = ref<any[]>([])
const suppliersList = ref<any[]>([])

const materialFormRef = ref<FormInstance>()
const materialForm = reactive({
  id: null as any,
  materialCode: '',
  materialName: '',
  thickness: 1.0,
  width: 1000,
  unit: '公斤',
  supplierId: null as any,
  unitPrice: 0,
  stockQuantity: 0,
  safetyStock: 500,
  notes: ''
})

const materialRules: FormRules = {
  materialCode: [{ required: true, message: '请输入物料编码', trigger: 'blur' }],
  materialName: [{ required: true, message: '请选择材质', trigger: 'change' }],
  thickness: [{ required: true, message: '请输入厚度', trigger: 'blur' }],
  width: [{ required: true, message: '请输入宽度', trigger: 'blur' }],
  unit: [{ required: true, message: '请选择单位', trigger: 'change' }],
  supplierId: [{ required: true, message: '请选择供应商', trigger: 'change' }],
  unitPrice: [{ required: true, message: '请输入单价', trigger: 'blur' }],
  safetyStock: [{ required: true, message: '请输入安全库存', trigger: 'blur' }]
}

const loadData = async () => {
  loading.value = true
  try {
    // TODO: API
    materialList.value = [
      {
        id: 1,
        materialCode: 'MAT-2026-001',
        materialName: 'SPCC',
        thickness: 1.0,
        width: 1000,
        unit: '公斤',
        supplierName: '供应商A',
        stockQuantity: 1500,
        safetyStock: 500,
        unitPrice: 8.5,
        lastPurchaseDate: '2026-06-15'
      }
    ]
    pagination.total = 1
  } catch (error) {
    ElMessage.error('加载失败')
  } finally {
    loading.value = false
  }
}

const loadSuppliers = async () => {
  try {
    suppliersList.value = [
      { id: 1, name: '供应商A' },
      { id: 2, name: '供应商B' }
    ]
  } catch (error) {
    ElMessage.error('加载供应商失败')
  }
}

const resetFilters = () => {
  filters.material = ''
  filters.spec = ''
  filters.supplier = ''
  filters.stockAlert = ''
  loadData()
}

const getStockColor = (current: number, safety: number) => {
  if (current < safety * 0.5) return 'danger'
  if (current < safety) return 'warning'
  return 'success'
}

const getStockAlertType = (current: number, safety: number) => {
  if (current < safety * 0.5) return 'danger'
  if (current < safety) return 'warning'
  return 'success'
}

const getStockAlertText = (current: number, safety: number) => {
  if (current < safety * 0.5) return '库存不足'
  if (current < safety) return '库存预警'
  return '库存充足'
}

const viewBatches = (id: number) => {
  router.push(`/materials/batches/${id}`)
}

const handlePurchase = (row: any) => {
  ElMessage.info('采购功能')
}

const handleEdit = (row: any) => {
  editMode.value = true
  Object.assign(materialForm, row)
  showCreateDialog.value = true
}

const submitMaterial = async () => {
  if (!materialFormRef.value) return
  await materialFormRef.value.validate(async (valid) => {
    if (valid) {
      submitting.value = true
      try {
        // TODO: API
        ElMessage.success(editMode.value ? '保存成功' : '创建成功')
        showCreateDialog.value = false
        loadData()
      } catch (error) {
        ElMessage.error(editMode.value ? '保存失败' : '创建失败')
      } finally {
        submitting.value = false
      }
    }
  })
}

onMounted(() => {
  loadData()
  loadSuppliers()
})
</script>

<style scoped lang="scss">
.materials-container {
  padding: 20px;

  .header-card {
    margin-bottom: 20px;
  }

  .header-content {
    display: flex;
    justify-content: space-between;
    align-items: center;

    h2 {
      margin: 0;
      font-size: 20px;
      font-weight: 500;
    }
  }

  .filter-card {
    margin-bottom: 20px;
  }

  .pagination-container {
    margin-top: 20px;
    display: flex;
    justify-content: flex-end;
  }
}
</style>
