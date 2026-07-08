<template>
  <div class="customer-prices">
    <el-card>
      <template #header>
        <h2>Customer Price History</h2>
      </template>

      <el-tabs v-model="activeTab">
        <el-tab-pane label="Material Prices" name="materials">
          <el-form :inline="true" style="margin-bottom: 20px;">
            <el-form-item label="Customer ID">
              <el-input-number v-model="materialFilters.customer_id" :min="1" />
            </el-form-item>
            <el-form-item label="Material ID">
              <el-input-number v-model="materialFilters.material_id" :min="1" />
            </el-form-item>
            <el-form-item>
              <el-button type="primary" @click="loadMaterialPrices">Search</el-button>
              <el-button @click="showMaterialDialog = true">Add Price</el-button>
            </el-form-item>
          </el-form>

          <el-table :data="materialPrices" stripe>
            <el-table-column prop="customer_id" label="Customer ID" width="120" />
            <el-table-column prop="material_id" label="Material ID" width="120" />
            <el-table-column prop="unit_price" label="Unit Price" width="120" align="right">
              <template #default="{ row }">
                {{ Number(row.unit_price).toFixed(4) }}
              </template>
            </el-table-column>
            <el-table-column prop="scrap_price" label="Scrap Price" width="120" align="right">
              <template #default="{ row }">
                {{ row.scrap_price ? Number(row.scrap_price).toFixed(4) : '-' }}
              </template>
            </el-table-column>
            <el-table-column prop="effective_date" label="Effective Date" width="150" />
            <el-table-column prop="created_at" label="Created At" width="180">
              <template #default="{ row }">
                {{ new Date(row.created_at).toLocaleString() }}
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>

        <el-tab-pane label="Treatment Prices" name="treatments">
          <el-form :inline="true" style="margin-bottom: 20px;">
            <el-form-item label="Customer ID">
              <el-input-number v-model="treatmentFilters.customer_id" :min="1" />
            </el-form-item>
            <el-form-item label="Treatment Name">
              <el-input v-model="treatmentFilters.treatment_name" />
            </el-form-item>
            <el-form-item>
              <el-button type="primary" @click="loadTreatmentPrices">Search</el-button>
              <el-button @click="showTreatmentDialog = true">Add Price</el-button>
            </el-form-item>
          </el-form>

          <el-table :data="treatmentPrices" stripe>
            <el-table-column prop="customer_id" label="Customer ID" width="120" />
            <el-table-column prop="treatment_name" label="Treatment" min-width="150" />
            <el-table-column prop="rate" label="Rate" width="120" align="right">
              <template #default="{ row }">
                {{ Number(row.rate).toFixed(4) }}
              </template>
            </el-table-column>
            <el-table-column prop="calc_mode" label="Calc Mode" width="120" />
            <el-table-column prop="unit" label="Unit" width="120" />
            <el-table-column prop="effective_date" label="Effective Date" width="150" />
            <el-table-column prop="created_at" label="Created At" width="180">
              <template #default="{ row }">
                {{ new Date(row.created_at).toLocaleString() }}
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>
      </el-tabs>
    </el-card>

    <!-- Material Price Dialog -->
    <el-dialog title="Add Material Price" v-model="showMaterialDialog" width="500px">
      <el-form :model="materialForm" label-width="140px">
        <el-form-item label="Customer ID">
          <el-input-number v-model="materialForm.customer_id" :min="1" />
        </el-form-item>
        <el-form-item label="Material ID">
          <el-input-number v-model="materialForm.material_id" :min="1" />
        </el-form-item>
        <el-form-item label="Unit Price">
          <el-input-number v-model="materialForm.unit_price" :precision="4" :step="0.1" />
        </el-form-item>
        <el-form-item label="Scrap Price">
          <el-input-number v-model="materialForm.scrap_price" :precision="4" :step="0.1" />
        </el-form-item>
        <el-form-item label="Effective Date">
          <el-date-picker v-model="materialForm.effective_date" type="date" value-format="YYYY-MM-DD" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showMaterialDialog = false">Cancel</el-button>
        <el-button type="primary" @click="saveMaterialPrice">Save</el-button>
      </template>
    </el-dialog>

    <!-- Treatment Price Dialog -->
    <el-dialog title="Add Treatment Price" v-model="showTreatmentDialog" width="500px">
      <el-form :model="treatmentForm" label-width="140px">
        <el-form-item label="Customer ID">
          <el-input-number v-model="treatmentForm.customer_id" :min="1" />
        </el-form-item>
        <el-form-item label="Treatment Name">
          <el-input v-model="treatmentForm.treatment_name" />
        </el-form-item>
        <el-form-item label="Rate">
          <el-input-number v-model="treatmentForm.rate" :precision="4" :step="0.1" />
        </el-form-item>
        <el-form-item label="Calc Mode">
          <el-select v-model="treatmentForm.calc_mode">
            <el-option label="Manual" value="manual" />
            <el-option label="Net Weight" value="net_weight" />
          </el-select>
        </el-form-item>
        <el-form-item label="Unit">
          <el-input v-model="treatmentForm.unit" />
        </el-form-item>
        <el-form-item label="Effective Date">
          <el-date-picker v-model="treatmentForm.effective_date" type="date" value-format="YYYY-MM-DD" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showTreatmentDialog = false">Cancel</el-button>
        <el-button type="primary" @click="saveTreatmentPrice">Save</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive } from 'vue'
import { ElMessage } from 'element-plus'
import api from '@/api'

const activeTab = ref('materials')
const materialPrices = ref([])
const treatmentPrices = ref([])
const showMaterialDialog = ref(false)
const showTreatmentDialog = ref(false)

const materialFilters = reactive({
  customer_id: null,
  material_id: null,
})

const treatmentFilters = reactive({
  customer_id: null,
  treatment_name: '',
})

const materialForm = reactive({
  customer_id: 1,
  material_id: 1,
  unit_price: 0,
  scrap_price: null,
  effective_date: new Date().toISOString().split('T')[0],
})

const treatmentForm = reactive({
  customer_id: 1,
  treatment_name: '',
  rate: 0,
  calc_mode: 'manual',
  unit: 'yuan/piece',
  effective_date: new Date().toISOString().split('T')[0],
})

const loadMaterialPrices = async () => {
  try {
    const params: any = {}
    if (materialFilters.customer_id) params.customer_id = materialFilters.customer_id
    if (materialFilters.material_id) params.material_id = materialFilters.material_id

    const { data } = await api.get('/customer-prices/materials', { params })
    materialPrices.value = data
  } catch (error) {
    ElMessage.error('Failed to load material prices')
  }
}

const loadTreatmentPrices = async () => {
  try {
    const params: any = {}
    if (treatmentFilters.customer_id) params.customer_id = treatmentFilters.customer_id
    if (treatmentFilters.treatment_name) params.treatment_name = treatmentFilters.treatment_name

    const { data } = await api.get('/customer-prices/treatments', { params })
    treatmentPrices.value = data
  } catch (error) {
    ElMessage.error('Failed to load treatment prices')
  }
}

const saveMaterialPrice = async () => {
  try {
    await api.post('/customer-prices/materials', materialForm)
    ElMessage.success('Material price created')
    showMaterialDialog.value = false
    await loadMaterialPrices()
  } catch (error: any) {
    ElMessage.error(error.response?.data?.detail || 'Failed to save')
  }
}

const saveTreatmentPrice = async () => {
  try {
    await api.post('/customer-prices/treatments', treatmentForm)
    ElMessage.success('Treatment price created')
    showTreatmentDialog.value = false
    await loadTreatmentPrices()
  } catch (error: any) {
    ElMessage.error(error.response?.data?.detail || 'Failed to save')
  }
}
</script>

<style scoped>
.customer-prices {
  padding: 20px;
}
</style>
