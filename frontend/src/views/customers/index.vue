<template>
  <div class="customers-container">
    <div class="page-header">
      <h2>客户管理</h2>
      <el-button type="primary" @click="openCreate" v-if="userStore.userInfo?.role_level >= 4">
        <el-icon><Plus /></el-icon>新增客户
      </el-button>
    </div>

    <el-card class="filter-card">
      <el-form :inline="true" :model="filter">
        <el-form-item label="搜索">
          <el-input v-model="filter.search" placeholder="客户名称" clearable style="width:200px" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="fetchCustomers">搜索</el-button>
          <el-button @click="resetFilter">重置</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <el-table :data="customers" v-loading="loading" stripe>
      <el-table-column prop="name" label="客户名称" min-width="200" />
      <el-table-column prop="sheet_key" label="Sheet Key" width="150" />
      <el-table-column prop="created_at" label="创建时间" width="160">
        <template #default="{ row }">
          {{ row.created_at ? formatDate(row.created_at) : '-' }}
        </template>
      </el-table-column>
      <el-table-column label="操作" width="140" fixed="right" v-if="userStore.userInfo?.role_level >= 4">
        <template #default="{ row }">
          <el-button link type="primary" size="small" @click="openEdit(row)">编辑</el-button>
          <el-button link type="danger" size="small" @click="handleDelete(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <div class="pagination">
      <el-pagination
        v-model:current-page="page.current"
        v-model:page-size="page.size"
        :total="page.total"
        :page-sizes="[20, 50, 100]"
        layout="total, sizes, prev, pager, next"
        @size-change="fetchCustomers"
        @current-change="fetchCustomers"
      />
    </div>

    <!-- 新增/编辑对话框 -->
    <el-dialog v-model="dialogVisible" :title="editId ? '编辑客户' : '新增客户'" width="480px">
      <el-form :model="form" label-width="90px" :rules="rules" ref="formRef">
        <el-form-item label="客户名称" prop="name">
          <el-input v-model="form.name" placeholder="请输入客户名称" />
        </el-form-item>
        <el-form-item label="Sheet Key">
          <el-input v-model="form.sheet_key" placeholder="选填" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="doSave">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'
import { get, post } from '@/utils/request'
import { useUserStore } from '@/stores/user'
import apiClient from '@/utils/request'

const userStore = useUserStore()

const customers = ref([])
const loading = ref(false)
const saving = ref(false)
const dialogVisible = ref(false)
const editId = ref(null)
const formRef = ref(null)

const filter = reactive({ search: '' })
const page = reactive({ current: 1, size: 20, total: 0 })
const form = reactive({ name: '', sheet_key: '' })

const rules = {
  name: [{ required: true, message: '请输入客户名称', trigger: 'blur' }]
}

const formatDate = (date) => {
  if (!date) return '-'
  return new Date(date).toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit'
  })
}

const fetchCustomers = async () => {
  loading.value = true
  try {
    const params = {
      skip: (page.current - 1) * page.size,
      limit: page.size,
      ...(filter.search && { search: filter.search }),
    }
    const data = await get('/customers', params)
    customers.value = Array.isArray(data) ? data : (data.items || [])
    page.total = data.total || customers.value.length
  } catch (e) {
    ElMessage.error(e.message || '获取失败')
  } finally {
    loading.value = false
  }
}

const resetFilter = () => {
  filter.search = ''
  page.current = 1
  fetchCustomers()
}

const openCreate = () => {
  editId.value = null
  Object.assign(form, { name: '', sheet_key: '' })
  dialogVisible.value = true
}

const openEdit = (row) => {
  editId.value = row.id
  Object.assign(form, {
    name: row.name,
    sheet_key: row.sheet_key || '',
  })
  dialogVisible.value = true
}

const doSave = async () => {
  await formRef.value?.validate()
  saving.value = true
  try {
    if (editId.value) {
      await apiClient.patch(`/customers/${editId.value}`, form)
      ElMessage.success('已更新')
    } else {
      await post('/customers', form)
      ElMessage.success('已创建')
    }
    dialogVisible.value = false
    fetchCustomers()
  } catch (e) {
    ElMessage.error(e.message)
  } finally {
    saving.value = false
  }
}

const handleDelete = async (row) => {
  await ElMessageBox.confirm(`确认删除客户「${row.name}」？`, '确认', { type: 'warning' })
  try {
    await apiClient.delete(`/customers/${row.id}`)
    ElMessage.success('已删除')
    fetchCustomers()
  } catch (e) {
    ElMessage.error(e.message)
  }
}

onMounted(() => { fetchCustomers() })
</script>

<style scoped>
.customers-container { padding: 20px; }
.page-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }
.page-header h2 { margin: 0; }
.filter-card { margin-bottom: 16px; }
.pagination { display: flex; justify-content: flex-end; margin-top: 16px; }
</style>
