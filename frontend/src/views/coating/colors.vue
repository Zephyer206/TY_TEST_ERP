<template>
  <div class="colors-container">
    <el-card class="header-card">
      <div class="header-content">
        <h2>标准颜色库</h2>
        <el-button type="primary" @click="showCreateDialog = true">
          <el-icon><Plus /></el-icon>
          新增颜色
        </el-button>
      </div>
    </el-card>

    <!-- 筛选条件 -->
    <el-card class="filter-card">
      <el-form :inline="true" :model="filters">
        <el-form-item label="颜色名称">
          <el-input v-model="filters.name" placeholder="颜色名称" clearable style="width: 150px" />
        </el-form-item>
        <el-form-item label="颜色系列">
          <el-select v-model="filters.series" placeholder="全部系列" clearable style="width: 120px">
            <el-option label="黑色系" value="black" />
            <el-option label="白色系" value="white" />
            <el-option label="灰色系" value="gray" />
            <el-option label="红色系" value="red" />
            <el-option label="蓝色系" value="blue" />
            <el-option label="绿色系" value="green" />
            <el-option label="黄色系" value="yellow" />
            <el-option label="其他" value="other" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="loadData">查询</el-button>
          <el-button @click="resetFilters">重置</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- 颜色卡片展示 -->
    <el-card>
      <el-row :gutter="20">
        <el-col
          v-for="color in colorList"
          :key="color.id"
          :xs="24"
          :sm="12"
          :md="8"
          :lg="6"
          :xl="4"
        >
          <el-card class="color-card" shadow="hover">
            <div class="color-display" :style="{ backgroundColor: color.colorCode }">
              <div class="color-code-overlay">{{ color.colorCode }}</div>
            </div>
            <div class="color-info">
              <div class="color-name">{{ color.colorName }}</div>
              <div class="color-standard">
                <el-tag size="small">{{ color.standardCode }}</el-tag>
              </div>
              <div class="color-series">
                <el-text type="info" size="small">{{ getSeriesText(color.series) }}</el-text>
              </div>
              <div class="color-usage">
                <el-text type="info" size="small">使用次数: {{ color.usageCount }}</el-text>
              </div>
              <div class="color-actions">
                <el-button type="primary" link @click="handleEdit(color)">编辑</el-button>
                <el-button type="success" link @click="viewRecipes(color)">关联配方</el-button>
                <el-button type="danger" link @click="handleDelete(color)">删除</el-button>
              </div>
            </div>
          </el-card>
        </el-col>
      </el-row>

      <!-- 分页 -->
      <div class="pagination-container">
        <el-pagination
          v-model:current-page="pagination.page"
          v-model:page-size="pagination.pageSize"
          :page-sizes="[12, 24, 48]"
          :total="pagination.total"
          layout="total, sizes, prev, pager, next, jumper"
          @size-change="loadData"
          @current-change="loadData"
        />
      </div>
    </el-card>

    <!-- 新增/编辑颜色对话框 -->
    <el-dialog
      v-model="showCreateDialog"
      :title="editMode ? '编辑颜色' : '新增颜色'"
      width="600px"
      :close-on-click-modal="false"
    >
      <el-form :model="colorForm" :rules="colorRules" ref="colorFormRef" label-width="120px">
        <el-form-item label="颜色名称" prop="colorName">
          <el-input v-model="colorForm.colorName" placeholder="如：亮黑色" />
        </el-form-item>
        <el-form-item label="颜色代码" prop="colorCode">
          <div style="display: flex; gap: 10px; align-items: center">
            <el-input v-model="colorForm.colorCode" placeholder="如：#000000" style="flex: 1" />
            <el-color-picker v-model="colorForm.colorCode" show-alpha />
            <div class="color-preview-large" :style="{ backgroundColor: colorForm.colorCode }"></div>
          </div>
        </el-form-item>
        <el-form-item label="标准代码" prop="standardCode">
          <el-input v-model="colorForm.standardCode" placeholder="如：RAL9005">
            <template #prepend>
              <el-select v-model="colorForm.standardType" style="width: 100px">
                <el-option label="RAL" value="RAL" />
                <el-option label="Pantone" value="Pantone" />
                <el-option label="CMYK" value="CMYK" />
                <el-option label="RGB" value="RGB" />
              </el-select>
            </template>
          </el-input>
        </el-form-item>
        <el-form-item label="颜色系列" prop="series">
          <el-select v-model="colorForm.series" style="width: 100%">
            <el-option label="黑色系" value="black" />
            <el-option label="白色系" value="white" />
            <el-option label="灰色系" value="gray" />
            <el-option label="红色系" value="red" />
            <el-option label="蓝色系" value="blue" />
            <el-option label="绿色系" value="green" />
            <el-option label="黄色系" value="yellow" />
            <el-option label="其他" value="other" />
          </el-select>
        </el-form-item>
        <el-form-item label="光泽度">
          <el-select v-model="colorForm.gloss" style="width: 100%">
            <el-option label="高光" value="high" />
            <el-option label="半光" value="semi" />
            <el-option label="哑光" value="matte" />
          </el-select>
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="colorForm.description" type="textarea" :rows="3" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showCreateDialog = false">取消</el-button>
        <el-button type="primary" @click="submitColor" :loading="submitting">
          {{ editMode ? '保存' : '创建' }}
        </el-button>
      </template>
    </el-dialog>

    <!-- 关联配方对话框 -->
    <el-dialog v-model="showRecipesDialog" title="关联配方" width="700px">
      <el-table :data="relatedRecipes" border stripe max-height="400">
        <el-table-column prop="recipeNo" label="配方编号" width="140" />
        <el-table-column prop="recipeName" label="配方名称" width="200" />
        <el-table-column prop="coatingType" label="涂层类型" width="120" align="center">
          <template #default="{ row }">
            {{ getCoatingTypeText(row.coatingType) }}
          </template>
        </el-table-column>
        <el-table-column prop="usageCount" label="使用次数" width="100" align="center" />
        <el-table-column label="操作" width="120">
          <template #default="{ row }">
            <el-button type="primary" link @click="goToRecipe(row)">查看</el-button>
          </template>
        </el-table-column>
      </el-table>
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
const showRecipesDialog = ref(false)
const editMode = ref(false)

const filters = reactive({
  name: '',
  series: ''
})

const pagination = reactive({
  page: 1,
  pageSize: 24,
  total: 0
})

const colorList = ref<any[]>([])
const relatedRecipes = ref<any[]>([])

const colorFormRef = ref<FormInstance>()
const colorForm = reactive({
  id: null as any,
  colorName: '',
  colorCode: '#000000',
  standardType: 'RAL',
  standardCode: '',
  series: 'black',
  gloss: 'semi',
  description: ''
})

const colorRules: FormRules = {
  colorName: [{ required: true, message: '请输入颜色名称', trigger: 'blur' }],
  colorCode: [{ required: true, message: '请选择颜色代码', trigger: 'blur' }],
  standardCode: [{ required: true, message: '请输入标准代码', trigger: 'blur' }],
  series: [{ required: true, message: '请选择颜色系列', trigger: 'change' }]
}

const loadData = async () => {
  loading.value = true
  try {
    // TODO: API
    colorList.value = [
      {
        id: 1,
        colorName: '亮黑色',
        colorCode: '#000000',
        standardType: 'RAL',
        standardCode: 'RAL9005',
        series: 'black',
        gloss: 'high',
        usageCount: 25,
        description: '经典黑色，高光泽'
      },
      {
        id: 2,
        colorName: '纯白色',
        colorCode: '#FFFFFF',
        standardType: 'RAL',
        standardCode: 'RAL9016',
        series: 'white',
        gloss: 'semi',
        usageCount: 18,
        description: '纯白色，半光泽'
      },
      {
        id: 3,
        colorName: '银灰色',
        colorCode: '#C0C0C0',
        standardType: 'RAL',
        standardCode: 'RAL9006',
        series: 'gray',
        gloss: 'matte',
        usageCount: 12,
        description: '银灰色，哑光效果'
      }
    ]
    pagination.total = 3
  } catch (error) {
    ElMessage.error('加载失败')
  } finally {
    loading.value = false
  }
}

const resetFilters = () => {
  filters.name = ''
  filters.series = ''
  loadData()
}

const getSeriesText = (series: string) => {
  const map: any = {
    black: '黑色系',
    white: '白色系',
    gray: '灰色系',
    red: '红色系',
    blue: '蓝色系',
    green: '绿色系',
    yellow: '黄色系',
    other: '其他'
  }
  return map[series] || series
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
  Object.assign(colorForm, row)
  showCreateDialog.value = true
}

const handleDelete = async (row: any) => {
  try {
    await ElMessageBox.confirm('确认删除此颜色吗？', '提示', {
      confirmButtonText: '确认',
      cancelButtonText: '取消',
      type: 'warning'
    })
    // TODO: API
    ElMessage.success('删除成功')
    loadData()
  } catch (error) {
    // 用户取消
  }
}

const viewRecipes = async (row: any) => {
  try {
    // TODO: API
    relatedRecipes.value = [
      {
        id: 1,
        recipeNo: 'RCP-2026-001',
        recipeName: '亮黑色粉末喷涂',
        coatingType: 'powder',
        usageCount: 25
      }
    ]
    showRecipesDialog.value = true
  } catch (error) {
    ElMessage.error('加载配方失败')
  }
}

const goToRecipe = (row: any) => {
  router.push('/coating/recipes')
}

const submitColor = async () => {
  if (!colorFormRef.value) return
  await colorFormRef.value.validate(async (valid) => {
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
.colors-container {
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

  .color-card {
    margin-bottom: 20px;
    transition: all 0.3s;

    &:hover {
      transform: translateY(-4px);
    }

    .color-display {
      width: 100%;
      height: 150px;
      border-radius: 4px;
      margin-bottom: 12px;
      display: flex;
      align-items: flex-end;
      justify-content: center;
      padding: 8px;
      position: relative;

      .color-code-overlay {
        background: rgba(255, 255, 255, 0.9);
        padding: 4px 8px;
        border-radius: 4px;
        font-weight: bold;
        font-size: 12px;
      }
    }

    .color-info {
      .color-name {
        font-size: 16px;
        font-weight: 500;
        margin-bottom: 8px;
      }

      .color-standard {
        margin-bottom: 8px;
      }

      .color-series,
      .color-usage {
        margin-bottom: 8px;
      }

      .color-actions {
        margin-top: 12px;
        display: flex;
        gap: 8px;
        justify-content: space-between;
      }
    }
  }

  .color-preview-large {
    width: 60px;
    height: 60px;
    border-radius: 4px;
    border: 2px solid #dcdfe6;
  }

  .pagination-container {
    margin-top: 20px;
    display: flex;
    justify-content: flex-end;
  }
}
</style>
