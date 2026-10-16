<template>
  <div class="price-management">
    <el-card>
      <template #header>
        <div class="header">
          <h2>Treatment Dictionary</h2>
          <el-button type="primary" @click="showCreateDialog = true">Add Treatment</el-button>
        </div>
      </template>

      <el-table :data="treatments" stripe>
        <el-table-column prop="name" label="Name" min-width="150" />
        <el-table-column prop="calc_mode" label="Calc Mode" width="120" />
        <el-table-column prop="default_rate" label="Default Rate" width="120" align="right">
          <template #default="{ row }">
            {{ Number(row.default_rate).toFixed(2) }}
          </template>
        </el-table-column>
        <el-table-column prop="unit" label="Unit" width="120" />
        <el-table-column prop="is_active" label="Active" width="100">
          <template #default="{ row }">
            <el-tag :type="row.is_active ? 'success' : 'danger'">
              {{ row.is_active ? 'Yes' : 'No' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="Actions" width="150" fixed="right">
          <template #default="{ row }">
            <el-button size="small" @click="editTreatment(row as Treatment)">Edit</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- Create/Edit Dialog -->
    <el-dialog
      :title="editingTreatment ? 'Edit Treatment' : 'Create Treatment'"
      v-model="showCreateDialog"
      width="500px"
    >
      <el-form :model="form" label-width="120px">
        <el-form-item label="Name">
          <el-input v-model="form.name" />
        </el-form-item>
        <el-form-item label="Calc Mode">
          <el-select v-model="form.calc_mode">
            <el-option label="Manual" value="manual" />
            <el-option label="Net Weight" value="net_weight" />
          </el-select>
        </el-form-item>
        <el-form-item label="Default Rate">
          <el-input-number v-model="form.default_rate" :precision="2" :step="0.1" />
        </el-form-item>
        <el-form-item label="Unit">
          <el-input v-model="form.unit" />
        </el-form-item>
        <el-form-item label="Active">
          <el-switch v-model="form.is_active" />
        </el-form-item>
        <el-form-item label="Sort Order">
          <el-input-number v-model="form.sort_order" :min="0" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showCreateDialog = false">Cancel</el-button>
        <el-button type="primary" @click="saveTreatment" :loading="saving">Save</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { treatmentsApi } from '@/api/pricing'

interface Treatment {
  id?: number
  name: string
  calc_mode: string
  default_rate: number
  unit: string
  is_active: boolean
  sort_order: number
}

const treatments = ref<Treatment[]>([])
const showCreateDialog = ref(false)
const editingTreatment = ref<Treatment | null>(null)
const saving = ref(false)

const form = ref<Treatment>({
  name: '',
  calc_mode: 'manual',
  default_rate: 0,
  unit: 'yuan/piece',
  is_active: true,
  sort_order: 0,
})

const loadTreatments = async () => {
  try {
    treatments.value = await treatmentsApi.list()
  } catch (error) {
    ElMessage.error('Failed to load treatments')
    console.error(error)
  }
}

const editTreatment = (treatment: Treatment) => {
  editingTreatment.value = treatment
  form.value = { ...treatment }
  showCreateDialog.value = true
}

const saveTreatment = async () => {
  saving.value = true
  try {
    if (editingTreatment.value?.id) {
      await treatmentsApi.update(editingTreatment.value.id, form.value)
      ElMessage.success('Treatment updated')
    } else {
      await treatmentsApi.create(form.value)
      ElMessage.success('Treatment created')
    }
    showCreateDialog.value = false
    editingTreatment.value = null
    form.value = {
      name: '',
      calc_mode: 'manual',
      default_rate: 0,
      unit: 'yuan/piece',
      is_active: true,
      sort_order: 0,
    }
    await loadTreatments()
  } catch (error: any) {
    ElMessage.error(error.response?.data?.detail || 'Failed to save treatment')
  } finally {
    saving.value = false
  }
}

onMounted(() => {
  loadTreatments()
})
</script>

<style scoped>
.price-management {
  padding: 20px;
}

.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.header h2 {
  margin: 0;
}
</style>
