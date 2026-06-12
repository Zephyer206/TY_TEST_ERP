<template>
  <div class="scan-page">
    <van-nav-bar title="扫码" left-text="返回" @click-left="router.back()" />

    <div class="scan-area">
      <van-empty v-if="!scanResult" description="点击下方按钮开始扫码" />
      <van-cell-group v-else>
        <van-cell title="扫码结果" :value="scanResult" />
        <van-cell title="类型" :value="scanType" />
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
      />
    </van-cell-group>

    <!-- 输入框弹窗（备用） -->
    <van-dialog v-model:show="showInput" title="手动输入" show-cancel-button @confirm="handleManualInput">
      <van-field v-model="manualCode" placeholder="请输入编码" />
    </van-dialog>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { showToast, showDialog } from 'vant'

const router = useRouter()
const scanResult = ref('')
const scanType = ref('')
const showInput = ref(false)
const manualCode = ref('')
const scanHistory = ref([])

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

const handleManualInput = () => {
  if (manualCode.value.trim()) {
    scanResult.value = manualCode.value.trim()
    parseResult(manualCode.value.trim())
    manualCode.value = ''
  }
}

const parseResult = (code) => {
  // 解析扫码结果
  if (code.startsWith('MAT-')) {
    scanType.value = '原材料'
  } else if (code.startsWith('MCN-')) {
    scanType.value = '机台'
  } else if (code.startsWith('PFC-')) {
    scanType.value = '工艺流转卡'
  } else if (code.startsWith('PART-')) {
    scanType.value = '零件'
  } else {
    scanType.value = '未知'
  }

  // 添加到历史
  scanHistory.value.unshift({
    code: code,
    type: scanType.value,
    time: new Date().toLocaleTimeString(),
  })

  // 最多保留10条
  if (scanHistory.value.length > 10) {
    scanHistory.value.pop()
  }
}

const handleConfirm = () => {
  showDialog({
    title: '确认',
    message: `确认执行 ${scanType.value} 操作？`,
    showCancelButton: true,
  }).then(() => {
    showToast({ message: '操作成功', position: 'top' })
    scanResult.value = ''
    scanType.value = ''
  }).catch(() => {
    // 取消
  })
}
</script>

<style scoped>
.scan-page {
  min-height: 100vh;
  background-color: #f5f5f5;
  padding-bottom: 80px;
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
</style>
