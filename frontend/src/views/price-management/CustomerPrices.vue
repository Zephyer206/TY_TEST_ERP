<template>
  <div class="customer-prices">
    <el-container>
      <!-- 左侧：客户列表 -->
      <el-aside width="300px">
        <el-card class="customer-list-card">
          <template #header>
            <div class="card-header">
              <h3>客户列表</h3>
              <el-input
                v-model="customerSearch"
                placeholder="搜索客户"
                clearable
                size="small"
                style="margin-top: 10px"
              >
                <template #prefix>
                  <el-icon><Search /></el-icon>
                </template>
              </el-input>
            </div>
          </template>
          <el-scrollbar height="calc(100vh - 220px)">
            <div
              v-for="customer in filteredCustomers"
              :key="customer.id"
              :class="['customer-item', { active: selectedCustomer?.id === customer.id }]"
              @click="selectCustomer(customer)"
            >
              <div class="customer-name">{{ customer.name }}</div>
              <div class="customer-code">{{ customer.customer_code || customer.code }}</div>
            </div>
            <el-empty v-if="filteredCustomers.length === 0" description="无客户数据" :image-size="100" />
          </el-scrollbar>
        </el-card>
      </el-aside>

      <!-- 右侧：选中客户的零件价格 -->
      <el-main>
        <el-card v-if="selectedCustomer">
          <template #header>
            <div class="main-header">
              <div>
                <h2>{{ selectedCustomer.name }}</h2>
                <span class="customer-code-label">客户编号: {{ selectedCustomer.customer_code || selectedCustomer.code }}</span>
              </div>
            </div>
          </template>

          <el-table :data="customerParts" stripe v-loading="loading">
            <el-table-column prop="part_no" label="零件编号" min-width="130" />
            <el-table-column prop="part_name" label="零件名称" min-width="150" />
            <el-table-column label="材料" min-width="120">
              <template #default="{ row }">
                {{ row.material_name || '-' }}
              </template>
            </el-table-column>
            <el-table-column label="材料价格" min-width="180">
              <template #default="{ row }">
                <div v-if="row.material_unit_price">
                  <div class="price-value">¥{{ Number(row.material_unit_price).toFixed(2) }}/kg</div>
                  <div class="price-date" v-if="row.material_effective_date">{{ row.material_effective_date }}</div>
                </div>
                <el-button
                  v-else
                  size="small"
                  type="primary"
                  link
                  @click="editMaterialPrice(row)"
                >
                  设置价格
                </el-button>
              </template>
            </el-table-column>
            <el-table-column label="工序价格" min-width="220">
              <template #default="{ row }">
                <div v-if="row.treatment_prices && row.treatment_prices.length > 0">
                  <div v-for="tp in row.treatment_prices.slice(0, 3)" :key="tp.id" class="treatment-item">
                    <span>{{ tp.treatment_name }}</span>
                    <span class="price-value">¥{{ Number(tp.rate).toFixed(2) }}</span>
                  </div>
                  <div v-if="row.treatment_prices.length > 3" class="more-text">
                    +{{ row.treatment_prices.length - 3 }} 更多...
                  </div>
                </div>
                <el-button
                  v-else
                  size="small"
                  type="primary"
                  link
                  @click="editTreatmentPrices(row)"
                >
                  设置工序
                </el-button>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="200" fixed="right">
              <template #default="{ row }">
                <el-button size="small" @click="editMaterialPrice(row)">材料</el-button>
                <el-button size="small" @click="editTreatmentPrices(row)">工序</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-card>

        <el-empty
          v-else
          description="请从左侧选择一个客户"
          :image-size="200"
        />
      </el-main>
    </el-container>

    <!-- 材料价格对话框 -->
    <el-dialog v-model="showMaterialPriceDialog" title="设置材料价格" width="500px">
      <el-form :model="materialPriceForm" label-width="120px">
        <el-form-item label="零件">
          <el-input :value="currentEditingPart?.part_name" disabled />
        </el-form-item>
        <el-form-item label="材料">
          <el-select v-model="materialPriceForm.material_id" filterable placeholder="选择材料">
            <el-option
              v-for="mat in materials"
              :key="mat.id"
              :label="mat.name"
              :value="mat.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="单价(元/kg)">
          <el-input-number
            v-model="materialPriceForm.unit_price"
            :min="0"
            :precision="2"
            :step="0.1"
          />
        </el-form-item>
        <el-form-item label="废料价格">
          <el-input-number
            v-model="materialPriceForm.scrap_price"
            :min="0"
            :precision="2"
            :step="0.1"
          />
        </el-form-item>
        <el-form-item label="生效日期">
          <el-date-picker
            v-model="materialPriceForm.effective_date"
            type="date"
            placeholder="选择日期"
            value-format="YYYY-MM-DD"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showMaterialPriceDialog = false">取消</el-button>
        <el-button type="primary" @click="saveMaterialPrice" :loading="saving">
          保存
        </el-button>
      </template>
    </el-dialog>

    <!-- 工序价格对话框 -->
    <el-dialog v-model="showTreatmentPriceDialog" title="设置工序价格" width="600px">
      <div style="margin-bottom: 15px">
        <strong>零件：</strong>{{ currentEditingPart?.part_name }}
      </div>
      <div class="treatment-price-form">
        <div v-for="(item, index) in treatmentPriceForm.items" :key="index" class="treatment-row">
          <el-select v-model="item.treatment_name" placeholder="选择工序" style="width: 220px">
            <el-option
              v-for="t in treatments"
              :key="t.name"
              :label="t.name"
              :value="t.name"
            />
          </el-select>
          <el-input-number
            v-model="item.rate"
            placeholder="单价"
            :min="0"
            :precision="2"
            style="width: 150px; margin: 0 10px"
          />
          <el-button
            type="danger"
            icon="Delete"
            circle
            size="small"
            @click="treatmentPriceForm.items.splice(index, 1)"
          />
        </div>
        <el-button
          type="primary"
          icon="Plus"
          @click="addTreatmentRow"
          style="margin-top: 10px"
          size="small"
        >
          添加工序
        </el-button>
      </div>
      <template #footer>
        <el-button @click="showTreatmentPriceDialog = false">取消</el-button>
        <el-button type="primary" @click="saveTreatmentPrices" :loading="saving">
          保存
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import api from '@/api'

interface Customer {
  id: number
  name: string
  code?: string
  customer_code?: string
}

interface CustomerPart {
  part_id: number
  part_no: string
  part_name: string
  material_name?: string
  material_unit_price?: number
  material_effective_date?: string
  treatment_prices?: any[]
}

const customerSearch = ref('')
const customers = ref<Customer[]>([])
const selectedCustomer = ref<Customer | null>(null)
const customerParts = ref<CustomerPart[]>([])
const materials = ref<any[]>([])
const treatments = ref<any[]>([])
const loading = ref(false)
const saving = ref(false)

const showMaterialPriceDialog = ref(false)
const showTreatmentPriceDialog = ref(false)

const materialPriceForm = ref({
  material_id: null as number | null,
  unit_price: 0,
  scrap_price: 0,
  effective_date: new Date().toISOString().split('T')[0]
})

const treatmentPriceForm = ref({
  items: [] as Array<{ treatment_name: string, rate: number }>
})

const currentEditingPart = ref<CustomerPart | null>(null)

const filteredCustomers = computed(() => {
  if (!customerSearch.value) return customers.value
  const search = customerSearch.value.toLowerCase()
  return customers.value.filter(c =>
    c.name.toLowerCase().includes(search) ||
    (c.code && c.code.toLowerCase().includes(search)) ||
    (c.customer_code && c.customer_code.toLowerCase().includes(search))
  )
})

const loadCustomers = async () => {
  try {
    const { data } = await api.get('/customers')
    customers.value = data
  } catch (error) {
    ElMessage.error('加载客户列表失败')
    console.error(error)
  }
}

const loadMaterials = async () => {
  try {
    const { data } = await api.get('/materials')
    materials.value = data
  } catch (error) {
    console.error('加载材料失败', error)
  }
}

const loadTreatments = async () => {
  try {
    const { data } = await api.get('/treatments')
    treatments.value = data
  } catch (error) {
    console.error('加载工序失败', error)
  }
}

const selectCustomer = async (customer: Customer) => {
  selectedCustomer.value = customer
  await loadCustomerParts()
}

const loadCustomerParts = async () => {
  if (!selectedCustomer.value) return

  loading.value = true
  try {
    // 获取该客户的所有零件
    const { data: parts } = await api.get(`/customers/${selectedCustomer.value.id}/parts`)

    customerParts.value = parts.map((part: any) => ({
      part_id: part.id,
      part_no: part.part_no,
      part_name: part.name,
      material_name: part.material_name,
      material_unit_price: part.material_unit_price,
      material_effective_date: part.material_effective_date,
      treatment_prices: part.treatment_prices || []
    }))
  } catch (error) {
    ElMessage.error('加载客户零件失败')
    console.error(error)
    customerParts.value = []
  } finally {
    loading.value = false
  }
}

const editMaterialPrice = (part: CustomerPart) => {
  currentEditingPart.value = part
  materialPriceForm.value = {
    material_id: null,
    unit_price: Number(part.material_unit_price) || 0,
    scrap_price: 0,
    effective_date: new Date().toISOString().split('T')[0]
  }
  showMaterialPriceDialog.value = true
}

const saveMaterialPrice = async () => {
  if (!selectedCustomer.value || !currentEditingPart.value) return

  if (!materialPriceForm.value.material_id) {
    ElMessage.warning('请选择材料')
    return
  }

  saving.value = true
  try {
    await api.post('/customer-prices/materials', {
      customer_id: selectedCustomer.value.id,
      material_id: materialPriceForm.value.material_id,
      unit_price: materialPriceForm.value.unit_price,
      scrap_price: materialPriceForm.value.scrap_price || 0,
      effective_date: materialPriceForm.value.effective_date
    })

    ElMessage.success('材料价格保存成功')
    showMaterialPriceDialog.value = false
    await loadCustomerParts()
  } catch (error: any) {
    ElMessage.error(error.response?.data?.detail || '保存失败')
  } finally {
    saving.value = false
  }
}

const editTreatmentPrices = (part: CustomerPart) => {
  currentEditingPart.value = part
  treatmentPriceForm.value = {
    items: part.treatment_prices && part.treatment_prices.length > 0
      ? part.treatment_prices.map(tp => ({
          treatment_name: tp.treatment_name,
          rate: Number(tp.rate)
        }))
      : [{ treatment_name: '', rate: 0 }]
  }
  showTreatmentPriceDialog.value = true
}

const addTreatmentRow = () => {
  treatmentPriceForm.value.items.push({ treatment_name: '', rate: 0 })
}

const saveTreatmentPrices = async () => {
  if (!selectedCustomer.value || !currentEditingPart.value) return

  const validItems = treatmentPriceForm.value.items.filter(
    item => item.treatment_name && item.rate > 0
  )

  if (validItems.length === 0) {
    ElMessage.warning('请至少添加一条有效的工序价格')
    return
  }

  saving.value = true
  try {
    await Promise.all(
      validItems.map(item =>
        api.post('/customer-prices/treatments', {
          customer_id: selectedCustomer.value!.id,
          treatment_name: item.treatment_name,
          rate: item.rate,
          calc_mode: 'manual',
          unit: 'yuan/piece',
          effective_date: new Date().toISOString().split('T')[0]
        })
      )
    )

    ElMessage.success('工序价格保存成功')
    showTreatmentPriceDialog.value = false
    await loadCustomerParts()
  } catch (error: any) {
    ElMessage.error(error.response?.data?.detail || '保存失败')
  } finally {
    saving.value = false
  }
}

onMounted(() => {
  loadCustomers()
  loadMaterials()
  loadTreatments()
})
</script>

<style scoped>
.customer-prices {
  height: calc(100vh - 100px);
}

.customer-list-card {
  height: 100%;
}

.card-header h3 {
  margin: 0 0 10px 0;
}

.customer-item {
  padding: 14px;
  border-bottom: 1px solid #ebeef5;
  cursor: pointer;
  transition: all 0.2s;
}

.customer-item:hover {
  background: #f5f7fa;
}

.customer-item.active {
  background: #ecf5ff;
  border-left: 3px solid #409eff;
  padding-left: 11px;
}

.customer-name {
  font-weight: 500;
  font-size: 14px;
  margin-bottom: 6px;
  color: #303133;
}

.customer-code {
  font-size: 12px;
  color: #909399;
}

.main-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.main-header h2 {
  margin: 0 0 6px 0;
  font-size: 20px;
}

.customer-code-label {
  font-size: 13px;
  color: #909399;
}

.price-value {
  color: #f56c6c;
  font-weight: 600;
  font-size: 14px;
}

.price-date {
  font-size: 12px;
  color: #909399;
  margin-top: 4px;
}

.treatment-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 4px 0;
  font-size: 13px;
}

.more-text {
  font-size: 12px;
  color: #909399;
  margin-top: 4px;
}

.treatment-price-form {
  max-height: 400px;
  overflow-y: auto;
  padding: 4px;
}

.treatment-row {
  display: flex;
  align-items: center;
  margin-bottom: 12px;
}
</style>
