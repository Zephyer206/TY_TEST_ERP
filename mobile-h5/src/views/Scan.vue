<template>
  <div class="scan-page">
    <van-nav-bar title="扫码" left-text="返回" @click-left="router.back()" />

    <div class="scan-area">
      <van-empty v-if="!scanResult" description="点击下方按钮开始扫码" />
      <van-cell-group v-else>
        <van-cell title="扫码结果" :value="scanResult" />
        <van-cell title="类型" :value="entityInfo.entityType || scanType" />
        <van-cell v-if="entityInfo.found" title="实体ID" :value="entityInfo.entityId" />
        <van-cell v-if="entityInfo.error" title="错误" :value="entityInfo.error" />
      </van-cell-group>

      <!-- 实体详情 -->
      <van-cell-group v-if="entityInfo.found && entityInfo.entityData" title="详情" style="margin-top: 12px">
        <van-cell
          v-for="(value, key) in entityInfo.entityData"
          :key="key"
          :title="formatKey(key)"
          :value="value"
        />
      </van-cell-group>
    </div>

    <div class="action-buttons">
      <van-button type="primary" size="large" icon="scan" @click="handleScan">
        点击扫码
      </van-button>
      <van-button v-if="scanResult" type="success" size="large" @click="handleConfirm">
        确认执行
      </van-button>
    </div>

    <van-cell-group title="扫码历史" style="margin-top: 16px">
      <van-cell
        v-for="(item, index) in scanHistory"
        :key="index"
        :title="item.code"
        :label="item.time"
        :value="item.type"
        is-link
        @click="viewHistoryItem(item)"
      />
    </van-cell-group>

    <!-- 输入框弹窗（备用） -->
    <van-dialog v-model:show="showInput" title="手动输入" show-cancel-button @confirm="handleManualInput">
      <van-field v-model="manualCode" placeholder="请输入编码" />
    </van-dialog>

    <!-- 加载状态 -->
    <van-loading v-if="loading" type="spinner" class="loading-overlay" />
  </div>
</template>

<script setup>
import { ref, reactive } from 'vue'
import { useRouter } from 'vue-router'
import { showToast, showDialog, showLoadingToast, closeToast } from 'vant'

const router = useRouter()
const scanResult = ref('')
const scanType = ref('')
const showInput = ref(false)
const manualCode = ref('')
const scanHistory = ref([])
const loading = ref(false)

// 实体信息
const entityInfo = reactive({
  found: false,
  entityId: null,
  entityType: null,
  entityData: null,
  error: null
})

// API 基础路径
const API_BASE = '/api/v1'

// 扫码处理
const handleScan = () => {
  // H5 环境调用微信扫一扫
  if (navigator.userAgent.toLowerCase().includes('micromessenger')) {
    // 微信环境
    wx.scanQRCode({
      needResult: 1,
      scanType: ['QR_CODE', 'EAN_13'],
      success: (res) => {
        scanResult.value = res.resultStr
        parseResult(res.resultStr)
        lookupQRCode(res.resultStr)
      },
      fail: (err) => {
        showToast({ message: '扫码失败: ' + err, position: 'top' })
      }
    })
  } else {
    // 非微信环境，弹出输入框
    showInput.value = true
  }
}

// 手动输入处理
const handleManualInput = () => {
  if (manualCode.value.trim()) {
    scanResult.value = manualCode.value.trim()
    parseResult(manualCode.value.trim())
    lookupQRCode(manualCode.value.trim())
    manualCode.value = ''
  }
}

// 解析扫码结果前缀
const parseResult = (code) => {
  if (code.startsWith('MAT:')) {
    scanType.value = '原材料批次'
  } else if (code.startsWith('MCN:')) {
    scanType.value = '机台'
  } else if (code.startsWith('PFC:')) {
    scanType.value = '工艺流转卡'
  } else if (code.startsWith('PRT:')) {
    scanType.value = '零件'
  } else if (code.startsWith('TLG:')) {
    scanType.value = '模具工装'
  } else if (code.startsWith('PKG:')) {
    scanType.value = '包装'
  } else if (code.startsWith('COT:')) {
    scanType.value = '喷涂记录'
  } else {
    scanType.value = '未知'
  }

  addToHistory(code, scanType.value)
}

// 查询二维码对应的实体
const lookupQRCode = async (code) => {
  loading.value = true
  const token = localStorage.getItem('token')

  try {
    const response = await fetch(`${API_BASE}/qr/lookup?code=${encodeURIComponent(code)}`, {
      method: 'GET',
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json'
      }
    })

    if (!response.ok) {
      throw new Error('查询失败')
    }

    const data = await response.json()
    entityInfo.found = data.found
    entityInfo.entityId = data.entity_id
    entityInfo.entityType = data.entity_type
    entityInfo.entityData = data.entity_data
    entityInfo.error = data.error
  } catch (error) {
    console.error('QR lookup error:', error)
    entityInfo.found = false
    entityInfo.error = error.message || '查询失败'
    showToast({ message: '查询失败: ' + error.message, position: 'top' })
  } finally {
    loading.value = false
  }
}

// 添加到历史记录
const addToHistory = (code, type) => {
  scanHistory.value.unshift({
    code: code,
    type: type,
    time: new Date().toLocaleString()
  })

  // 最多保留20条
  if (scanHistory.value.length > 20) {
    scanHistory.value.pop()
  }
}

// 查看历史记录
const viewHistoryItem = (item) => {
  scanResult.value = item.code
  parseResult(item.code)
  lookupQRCode(item.code)
}

// 格式化键名
const formatKey = (key) => {
  const keyMap = {
    batch_id: '批次ID',
    batch_no: '批次号',
    machine_id: '机台ID',
    machine_no: '机台编号',
    machine_name: '机台名称',
    card_id: '流转卡ID',
    card_no: '流转卡号',
    part_id: '零件ID',
    part_number: '零件号',
    internal_name: '零件名称',
    tooling_id: '工装ID',
    tooling_no: '工装编号',
    tooling_name: '工装名称',
    status: '状态',
    quantity: '数量'
  }
  return keyMap[key] || key
}

// 确认执行
const handleConfirm = () => {
  if (!entityInfo.found) {
    showToast({ message: '请先扫描有效的二维码', position: 'top' })
    return
  }

  showDialog({
    title: '确认',
    message: `确认执行 ${entityInfo.entityType} (ID: ${entityInfo.entityId}) 操作？`,
    showCancelButton: true,
  }).then(() => {
    showToast({ message: '操作成功', position: 'top' })
    // 重置状态
    resetScan()
  }).catch(() => {
    // 取消
  })
}

// 重置扫码状态
const resetScan = () => {
  scanResult.value = ''
  scanType.value = ''
  entityInfo.found = false
  entityInfo.entityId = null
  entityInfo.entityType = null
  entityInfo.entityData = null
  entityInfo.error = null
}
</script>

<style scoped>
.scan-page {
  min-height: 100vh;
  background-color: #f5f5f5;
  padding-bottom: 80px;
  position: relative;
}

.scan-area {
  padding: 16px;
  min-height: 200px;
  background: white;
  margin: 16px;
  border-radius: 8px;
}

.action-buttons {
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.loading-overlay {
  position: fixed;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  z-index: 1000;
}
</style>
