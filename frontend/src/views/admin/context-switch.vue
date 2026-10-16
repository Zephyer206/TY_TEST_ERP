<template>
  <div class="context-switch">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>超级管理员视角切换</span>
          <el-tag v-if="isSwitched" type="warning" size="large">
            已切换至: LV{{ contextStatus?.current_role_level }} {{ contextStatus?.current_dept }}
          </el-tag>
        </div>
      </template>

      <!-- Current Status -->
      <div v-if="isSwitched" class="current-status">
        <el-alert
          title="视角切换中"
          type="info"
          :description="`已切换至 LV${contextStatus?.current_role_level} ${contextStatus?.current_dept}，到期时间 ${formatTime(contextStatus?.expires_at || undefined)}`"
          show-icon
          :closable="false"
        />
        <div class="status-info">
          <p>原始角色: LV{{ contextStatus?.original_role_level }} / {{ contextStatus?.original_dept }}</p>
          <p>切换时间: {{ formatTime(contextStatus?.switched_at || undefined) }}</p>
          <p>到期时间: {{ formatTime(contextStatus?.expires_at || undefined) }}</p>
        </div>
        <el-button type="primary" @click="handleSwitchBack" :loading="switching">
          恢复超级管理员视角
        </el-button>
      </div>

      <!-- Switch Form -->
      <div v-else class="switch-form">
        <p class="description">
          切换视角后，将临时获得该角色的权限，可正常操作系统。老板专属按钮将被隐藏，防止越权自审。
        </p>
        <el-form :model="form" label-width="120px">
          <el-form-item label="目标视角">
            <el-select v-model="form.target_role" placeholder="请选择部门视角">
              <el-option v-for="item in permissionStore.availableDepartments" :key="item.department" :label="item.role_name + ' · ' + item.department" :value="item.department" />
            </el-select>
          </el-form-item>
          <el-form-item label="切换时长">
            <el-select v-model="form.duration_minutes" placeholder="请选择时长">
              <el-option label="30 分钟" :value="30" />
              <el-option label="1 小时" :value="60" />
              <el-option label="2 小时" :value="120" />
              <el-option label="4 小时" :value="240" />
              <el-option label="8 小时" :value="480" />
            </el-select>
          </el-form-item>
          <el-form-item label="切换原因">
            <el-input
              v-model="form.reason"
              type="textarea"
              :rows="3"
              placeholder="请输入切换原因（必填）"
            />
          </el-form-item>
        </el-form>
        <el-button type="primary" @click="handleSwitch" :loading="switching">
          执行切换
        </el-button>
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, computed } from 'vue'
import { ElMessage } from 'element-plus'
import { usePermissionStore } from '@/stores/permission'

const permissionStore = usePermissionStore()

const form = reactive({
  target_role: 'design',
  duration_minutes: 60,
  reason: '',
})

const switching = ref(false)

const isSwitched = computed(() => permissionStore.isSwitched)
const contextStatus = computed(() => permissionStore.contextSwitch)

onMounted(async () => {
  await Promise.all([permissionStore.fetchContextInfo(), permissionStore.fetchDepartments()])
})

const handleSwitch = async () => {
  if (!form.reason.trim()) {
    ElMessage.warning('请输入切换原因')
    return
  }

  switching.value = true
  try {
    await permissionStore.switchContext(form.target_role)
    ElMessage.success('已完成视角切换')
    window.location.reload()
  } catch (err) {
    ElMessage.error('网络错误，请重试')
  } finally {
    switching.value = false
  }
}

const handleSwitchBack = async () => {
  switching.value = true
  try {
    await permissionStore.switchBack()
    ElMessage.success('已恢复超级管理员视角')
    window.location.reload()
  } catch (err) {
    ElMessage.error('网络错误，请重试')
  } finally {
    switching.value = false
  }
}

const formatTime = (isoString?: string) => {
  if (!isoString) return '-'
  return new Date(isoString).toLocaleString('zh-CN')
}
</script>

<style scoped>
.context-switch {
  padding: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.current-status {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.status-info {
  background: #f5f7fa;
  padding: 15px;
  border-radius: 4px;
}

.status-info p {
  margin: 5px 0;
  color: #606266;
}

.switch-form {
  max-width: 500px;
}

.description {
  color: #909399;
  margin-bottom: 20px;
}
</style>
