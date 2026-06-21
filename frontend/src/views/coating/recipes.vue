<template>
  <div class="recipes-container">
    <el-card class="header-card">
      <div class="header-content">
        <h2>喷涂配方管理</h2>
        <el-button type="primary" @click="showCreateDialog = true">
          <el-icon><Plus /></el-icon>
          新增配方
        </el-button>
      </div>
    </el-card>

    <!-- 筛选条件 -->
    <el-card class="filter-card">
      <el-form :inline="true" :model="filters">
        <el-form-item label="配方名称">
          <el-input v-model="filters.name" placeholder="配方名称" clearable style="width: 180px" />
        </el-form-item>
        <el-form-item label="颜色">
          <el-input v-model="filters.color" placeholder="颜色名称" clearable style="width: 150px" />
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="filters.status" placeholder="全部状态" clearable style="width: 120px">
            <el-option label="启用" value="active" />
            <el-option label="停用" value="inactive" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="loadData">查询</el-button>
          <el-button @click="resetFilters">重置</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- 配方列表 -->
    <el-card>
      <el-table :data="recipeList" v-loading="loading" border stripe>
        <el-table-column type="expand">
          <template #default="{ row }">
            <div class="expand-content">
              <h4>配方详情</h4>
              <el-descriptions :column="2" border>
                <el-descriptions-item label="基材处理">{{ row.substrate || '-' }}</el-descriptions-item>
                <el-descriptions-item label="底漆">{{ row.primer || '-' }}</el-descriptions-item>
                <el-descriptions-item label="面漆">{{ row.topcoat || '-' }}</el-descriptions-item>
                <el-descriptions-item label="固化剂">{{ row.hardener || '-' }}</el-descriptions-item>
                <el-descriptions-item label="稀释剂">{{ row.thinner || '-' }}</el-descriptions-item>
                <el-descriptions-item label="混合比例">{{ row.mixRatio || '-' }}</el-descriptions-item>
                <el-descriptions-item label="喷涂温度">{{ row.temperature }}℃</el-descriptions-item>
                <el-descriptions-item label="喷涂湿度">{{ row.humidity }}%</el-descriptions-item>
                <el-descriptions-item label="干燥时间">{{ row.dryingTime }}分钟</el-descriptions-item>
                <el-descriptions-item label="固化时间">{{ row.curingTime }}分钟</el-descriptions-item>
                <el-descriptions-item label="备注" :span="2">{{ row.notes || '-' }}</el-descriptions-item>
              </el-descriptions>
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="recipeNo" label="配方编号" width="140" fixed="left" />
        <el-table-column prop="recipeName" label="配方名称" width="180" />
        <el-table-column prop="colorName" label="颜色名称" width="150">
          <template #default="{ row }">
            <div style="display: flex; align-items: center; gap: 8px">
              <div
                class="color-preview"
                :style="{ backgroundColor: row.colorCode }"
              ></div>
              <span>{{ row.colorName }}</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="colorCode" label="颜色代码" width="120" />
        <el-table-column prop="coatingType" label="涂层类型" width="120" align="center">
          <template #default="{ row }">
            {{ getCoatingTypeText(row.coatingType) }}
          </template>
        </el-table-column>
        <el-table-column prop="usageCount" label="使用次数" width="100" align="center" />
        <el-table-column prop="status" label="状态" width="100" align="center">
          <template #default="{ row }">
            <el-tag :type="row.status === 'active' ? 'success' : 'info'">
              {{ row.status === 'active' ? '启用' : '停用' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="createdBy" label="创建人" width="100" />
        <el-table-column prop="createdAt" label="创建时间" width="160" />
        <el-table-column label="操作" width="220" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" link @click="handleEdit(row)">编辑</el-button>
            <el-button type="success" link @click="goToRecords(row)">喷涂记录</el-button>
            <el-button
              :type="row.status === 'active' ? 'warning' : 'success'"
              link
              @click="toggleStatus(row)"
            >
              {{ row.status === 'active' ? '停用' : '启用' }}
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <!-- 分页 -->
      <div class="pagination-container">
        <el-pagination
          v-model:current-page="pagination.page"
          v-model:page-size="pagination.pageSize"
          :page-sizes="[10, 20, 50]"
          :total="pagination.total"
          layout="total, sizes, prev, pager, next, jumper"
          @size-change="loadData"
          @current-change="loadData"
        />
      </div>
    </el-card>

    <!-- 新增/编辑配方对话框 -->
    <el-dialog
      v-model="showCreateDialog"
      :title="editMode ? '编辑配方' : '新增配方'"
      width="800px"
      :close-on-click-modal="false"
    >
      <el-form :model="recipeForm" :rules="recipeRules" ref="recipeFormRef" label-width="120px">
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="配方编号" prop="recipeNo">
              <el-input v-model="recipeForm.recipeNo" placeholder="如：RCP-2026-001" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="配方名称" prop="recipeName">
              <el-input v-model="recipeForm.recipeName" placeholder="配方名称" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="颜色名称" prop="colorName">
              <el-input v-model="recipeForm.colorName" placeholder="如：亮黑色" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="颜色代码" prop="colorCode">
              <el-input v-model="recipeForm.colorCode" placeholder="如：RAL9005">
                <template #append>
                  <el-color-picker v-model="recipeForm.colorCode" />
                </template>
              </el-input>
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="涂层类型" prop="coatingType">
          <el-select v-model="recipeForm.coatingType" style="width: 100%">
            <el-option label="粉末喷涂" value="powder" />
            <el-option label="液态喷涂" value="liquid" />
            <el-option label="电泳涂装" value="electrocoat" />
          </el-select>
        </el-form-item>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="基材处理">
              <el-input v-model="recipeForm.substrate" placeholder="如：除油、除锈" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="底漆">
              <el-input v-model="recipeForm.primer" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="面漆">
              <el-input v-model="recipeForm.topcoat" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="混合比例">
              <el-input v-model="recipeForm.mixRatio" placeholder="如：4:1:1" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="喷涂温度(℃)">
              <el-input-number v-model="recipeForm.temperature" :min="15" :max="35" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="喷涂湿度(%)">
              <el-input-number v-model="recipeForm.humidity" :min="40" :max="80" style="width: 100%" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="干燥时间(分)">
              <el-input-number v-model="recipeForm.dryingTime" :min="0" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="固化时间(分)">
              <el-input-number v-model="recipeForm.curingTime" :min="0" style="width: 100%" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="备注">
          <el-input v-model="recipeForm.notes" type="textarea" :rows="3" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showCreateDialog = false">取消</el-button>
        <el-button type="primary" @click="submitRecipe" :loading="submitting">
          {{ editMode ? '保存' : '创建' }}
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'
import { useRouter } from 'vue-router'
import type { FormInstance, FormRules } from 'element-plus'

const router = useRouter()

const loading = ref(false)
const submitting = ref(false)
const showCreateDialog = ref(false)
const editMode = ref(false)

const filters = reactive({
  name: '',
  color: '',
  status: ''
})

const pagination = reactive({
  page: 1,
  pageSize: 20,
  total: 0
})

const recipeList = ref<any[]>([])

const recipeFormRef = ref<FormInstance>()
const recipeForm = reactive({
  id: null as any,
  recipeNo: '',
  recipeName: '',
  colorName: '',
  colorCode: '#000000',
  coatingType: 'powder',
  substrate: '',
  primer: '',
  topcoat: '',
  mixRatio: '',
  temperature: 25,
  humidity: 60,
  dryingTime: 30,
  curingTime: 120,
  notes: ''
})

const recipeRules: FormRules = {
  recipeNo: [{ required: true, message: '请输入配方编号', trigger: 'blur' }],
  recipeName: [{ required: true, message: '请输入配方名称', trigger: 'blur' }],
  colorName: [{ required: true, message: '请输入颜色名称', trigger: 'blur' }],
  colorCode: [{ required: true, message: '请输入颜色代码', trigger: 'blur' }],
  coatingType: [{ required: true, message: '请选择涂层类型', trigger: 'change' }]
}

const loadData = async () => {
  loading.value = true
  try {
    // TODO: API
    recipeList.value = [
      {
        id: 1,
        recipeNo: 'RCP-2026-001',
        recipeName: '亮黑色粉末喷涂',
        colorName: '亮黑色',
        colorCode: '#000000',
        coatingType: 'powder',
        substrate: '除油、除锈、磷化',
        primer: '环氧底漆',
        topcoat: '聚酯粉末',
        mixRatio: '-',
        temperature: 25,
        humidity: 60,
        dryingTime: 30,
        curingTime: 180,
        usageCount: 25,
        status: 'active',
        createdBy: '张三',
        createdAt: '2026-01-15 10:00',
        notes: '常用配方'
      }
    ]
    pagination.total = 1
  } catch (error) {
    ElMessage.error('加载失败')
  } finally {
    loading.value = false
  }
}

const resetFilters = () => {
  filters.name = ''
  filters.color = ''
  filters.status = ''
  loadData()
}

const getCoatingTypeText = (type: string) => {
  const map: any = {
    powder: '粉末喷涂',
    liquid: '液态喷涂',
    electrocoat: '电泳涂装'
  }
  return map[type] || type
}

const handleEdit = (row: any) => {
  editMode.value = true
  Object.assign(recipeForm, row)
  showCreateDialog.value = true
}

const toggleStatus = async (row: any) => {
  try {
    const action = row.status === 'active' ? '停用' : '启用'
    await ElMessageBox.confirm(`确认${action}此配方吗？`, '提示', {
      confirmButtonText: '确认',
      cancelButtonText: '取消',
      type: 'warning'
    })
    // TODO: API
    ElMessage.success(`已${action}`)
    loadData()
  } catch (error) {
    // 用户取消
  }
}

const goToRecords = (row: any) => {
  router.push(`/coating/records?recipeId=${row.id}`)
}

const submitRecipe = async () => {
  if (!recipeFormRef.value) return
  await recipeFormRef.value.validate(async (valid) => {
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
})
</script>

<style scoped lang="scss">
.recipes-container {
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

  .color-preview {
    width: 24px;
    height: 24px;
    border-radius: 4px;
    border: 1px solid #dcdfe6;
  }

  .expand-content {
    padding: 16px;

    h4 {
      margin-top: 0;
      margin-bottom: 12px;
    }
  }

  .pagination-container {
    margin-top: 20px;
    display: flex;
    justify-content: flex-end;
  }
}
</style>
