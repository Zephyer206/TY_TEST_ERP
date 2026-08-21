<template>
  <div class="price-adjustments">
    <el-card>
      <template #header>
        <div class="header">
          <h2>Price Adjustment Requests</h2>
          <el-button type="primary" @click="showCreateDialog = true">New Request</el-button>
        </div>
      </template>

      <el-form :inline="true" style="margin-bottom: 20px;">
        <el-form-item label="Customer ID">
          <el-input-number v-model="filters.customer_id" :min="1" />
        </el-form-item>
        <el-form-item label="Status">
          <el-select v-model="filters.status" clearable>
            <el-option label="Pending" value="pending" />
            <el-option label="Approved" value="approved" />
            <el-option label="Rejected" value="rejected" />
            <el-option label="Cancelled" value="cancelled" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="loadAdjustments">Search</el-button>
        </el-form-item>
      </el-form>

      <el-table :data="adjustments" stripe>
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column prop="customer_id" label="Customer" width="100" />
        <el-table-column prop="adjustment_type" label="Type" width="100" />
        <el-table-column prop="old_price" label="Old Price" width="110" align="right">
          <template #default="{ row }">
            {{ row.old_price ? Number(row.old_price).toFixed(4) : '-' }}
          </template>
        </el-table-column>
        <el-table-column prop="new_price" label="New Price" width="110" align="right">
          <template #default="{ row }">
            {{ Number(row.new_price).toFixed(4) }}
          </template>
        </el-table-column>
        <el-table-column prop="reason" label="Reason" min-width="150" show-overflow-tooltip />
        <el-table-column prop="status" label="Status" width="100">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row.status)">{{ row.status }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="requested_at" label="Requested" width="180">
          <template #default="{ row }">
            {{ new Date(row.requested_at).toLocaleString() }}
          </template>
        </el-table-column>
        <el-table-column label="Actions" width="200" fixed="right">
          <template #default="{ row }">
            <el-button size="small" @click="viewDetail(row)">Detail</el-button>
            <el-button
              v-if="row.status === 'pending'"
              size="small"
              type="success"
              @click="approve(row)"
            >
              Approve
            </el-button>
            <el-button
              v-if="row.status === 'pending'"
              size="small"
              type="danger"
              @click="reject(row)"
            >
              Reject
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- Create Dialog -->
    <el-dialog title="New Price Adjustment Request" v-model="showCreateDialog" width="600px">
      <el-form :model="form" label-width="140px">
        <el-form-item label="Customer ID">
          <el-input-number v-model="form.customer_id" :min="1" />
        </el-form-item>
        <el-form-item label="Adjustment Type">
          <el-select v-model="form.adjustment_type">
            <el-option label="Material" value="material" />
            <el-option label="Treatment" value="treatment" />
            <el-option label="Part" value="part" />
          </el-select>
        </el-form-item>
        <el-form-item v-if="form.adjustment_type === 'material'" label="Material ID">
          <el-input-number v-model="form.material_id" :min="1" />
        </el-form-item>
        <el-form-item v-if="form.adjustment_type === 'treatment'" label="Treatment Name">
          <el-input v-model="form.treatment_name" />
        </el-form-item>
        <el-form-item v-if="form.adjustment_type === 'part'" label="Part ID">
          <el-input-number v-model="form.part_id" :min="1" />
        </el-form-item>
        <el-form-item label="Old Price">
          <el-input-number v-model="form.old_price" :precision="4" :step="0.1" />
        </el-form-item>
        <el-form-item label="New Price">
          <el-input-number v-model="form.new_price" :precision="4" :step="0.1" />
        </el-form-item>
        <el-form-item label="Reason">
          <el-input v-model="form.reason" type="textarea" :rows="3" />
        </el-form-item>
        <el-form-item label="Effective Date">
          <el-date-picker v-model="form.effective_date" type="date" value-format="YYYY-MM-DD" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showCreateDialog = false">Cancel</el-button>
        <el-button type="primary" @click="createAdjustment">Submit</el-button>
      </template>
    </el-dialog>

    <!-- Detail/Approval Dialog -->
    <el-dialog title="Price Adjustment Detail" v-model="showDetailDialog" width="600px">
      <el-descriptions v-if="currentAdjustment" :column="2" border>
        <el-descriptions-item label="ID">{{ currentAdjustment.id }}</el-descriptions-item>
        <el-descriptions-item label="Customer ID">{{ currentAdjustment.customer_id }}</el-descriptions-item>
        <el-descriptions-item label="Type">{{ currentAdjustment.adjustment_type }}</el-descriptions-item>
        <el-descriptions-item label="Status">
          <el-tag :type="getStatusType(currentAdjustment.status)">{{ currentAdjustment.status }}</el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="Old Price">{{ currentAdjustment.old_price || '-' }}</el-descriptions-item>
        <el-descriptions-item label="New Price">{{ currentAdjustment.new_price }}</el-descriptions-item>
        <el-descriptions-item label="Reason" :span="2">{{ currentAdjustment.reason }}</el-descriptions-item>
        <el-descriptions-item label="Requested At" :span="2">
          {{ new Date(currentAdjustment.requested_at).toLocaleString() }}
        </el-descriptions-item>
        <el-descriptions-item v-if="currentAdjustment.reviewed_at" label="Reviewed At" :span="2">
          {{ new Date(currentAdjustment.reviewed_at).toLocaleString() }}
        </el-descriptions-item>
        <el-descriptions-item v-if="currentAdjustment.review_notes" label="Review Notes" :span="2">
          {{ currentAdjustment.review_notes }}
        </el-descriptions-item>
      </el-descriptions>

      <el-form v-if="showApprovalForm" :model="approvalForm" label-width="100px" style="margin-top: 20px;">
        <el-form-item label="Notes">
          <el-input v-model="approvalForm.notes" type="textarea" :rows="3" />
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="showDetailDialog = false">Close</el-button>
        <el-button
          v-if="showApprovalForm && currentAdjustment?.status === 'pending'"
          type="danger"
          @click="submitApproval(false)"
        >
          Reject
        </el-button>
        <el-button
          v-if="showApprovalForm && currentAdjustment?.status === 'pending'"
          type="success"
          @click="submitApproval(true)"
        >
          Approve
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive } from 'vue'
import { ElMessage } from 'element-plus'
import api from '@/api'

const adjustments = ref([])
const showCreateDialog = ref(false)
const showDetailDialog = ref(false)
const showApprovalForm = ref(false)
const currentAdjustment = ref<any>(null)

const filters = reactive({
  customer_id: null,
  status: '',
})

const form = reactive({
  customer_id: 1,
  adjustment_type: 'material',
  material_id: null,
  treatment_name: '',
  part_id: null,
  old_price: null,
  new_price: 0,
  reason: '',
  effective_date: new Date().toISOString().split('T')[0],
})

const approvalForm = reactive({
  notes: '',
})

const getStatusType = (status: string) => {
  const types: any = {
    pending: 'warning',
    approved: 'success',
    rejected: 'danger',
    cancelled: 'info',
  }
  return types[status] || ''
}

const loadAdjustments = async () => {
  try {
    const params: any = {}
    if (filters.customer_id) params.customer_id = filters.customer_id
    if (filters.status) params.status = filters.status

    const { data } = await api.get('/price-adjustments', { params })
    adjustments.value = data
  } catch (error) {
    ElMessage.error('Failed to load adjustments')
  }
}

const createAdjustment = async () => {
  try {
    await api.post('/price-adjustments', form)
    ElMessage.success('Adjustment request created')
    showCreateDialog.value = false
    await loadAdjustments()
  } catch (error: any) {
    ElMessage.error(error.response?.data?.detail || 'Failed to create')
  }
}

const viewDetail = (adjustment: any) => {
  currentAdjustment.value = adjustment
  showApprovalForm.value = false
  showDetailDialog.value = true
}

const approve = (adjustment: any) => {
  currentAdjustment.value = adjustment
  showApprovalForm.value = true
  approvalForm.notes = ''
  showDetailDialog.value = true
}

const reject = (adjustment: any) => {
  currentAdjustment.value = adjustment
  showApprovalForm.value = true
  approvalForm.notes = ''
  showDetailDialog.value = true
}

const submitApproval = async (approved: boolean) => {
  try {
    await api.post(`/price-adjustments/${currentAdjustment.value.id}/approve`, {
      approved,
      notes: approvalForm.notes,
    })
    ElMessage.success(approved ? 'Approved successfully' : 'Rejected successfully')
    showDetailDialog.value = false
    await loadAdjustments()
  } catch (error: any) {
    ElMessage.error(error.response?.data?.detail || 'Failed to submit approval')
  }
}

loadAdjustments()
</script>

<style scoped>
.price-adjustments {
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
