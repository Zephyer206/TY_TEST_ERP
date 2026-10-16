<template>
  <MobileShell title="扫码">
    <div class="scan-page">
      <div class="scan-area">
        <van-empty v-if="!scanResult" description="点击下方按钮开始扫码" />
        <van-cell-group v-else>
          <van-cell title="扫码结果" :value="scanResult" />
          <van-cell title="类型" :value="entityInfo.entityType || scanType" />
          <van-cell v-if="entityInfo.found" title="实体编号" :value="String(entityInfo.entityId || '-')" />
          <van-cell v-if="entityInfo.error" title="错误" :value="entityInfo.error" />
        </van-cell-group>
        <van-cell-group v-if="entityInfo.found && entityInfo.entityData" title="详情" inset>
          <van-cell v-for="(value, key) in entityInfo.entityData" :key="key" :title="formatKey(key)" :value="String(value ?? '-')" />
        </van-cell-group>
      </div>
      <div class="action-buttons">
        <van-button type="primary" size="large" icon="scan" @click="handleScan">点击扫码</van-button>
        <van-button v-if="scanResult" type="success" size="large" @click="handleConfirm">确认执行</van-button>
      </div>
      <van-cell-group v-if="scanHistory.length" title="扫码历史" inset>
        <van-cell v-for="(item, index) in scanHistory" :key="index" :title="item.code" :label="item.time" :value="item.type" is-link @click="viewHistoryItem(item)" />
      </van-cell-group>
      <van-dialog v-model:show="showInput" title="手动输入" show-cancel-button @confirm="handleManualInput">
        <van-field v-model="manualCode" placeholder="请输入编码" />
      </van-dialog>
      <van-loading v-if="loading" type="spinner" class="loading-overlay" />
    </div>
  </MobileShell>
</template>

<script setup>
import { reactive, ref } from 'vue'
import { showDialog, showToast } from 'vant'
import MobileShell from '@/components/MobileShell.vue'
import { lookupQrCode } from '@/api/qr'

const scanResult = ref('')
const scanType = ref('')
const showInput = ref(false)
const manualCode = ref('')
const scanHistory = ref([])
const loading = ref(false)
const entityInfo = reactive({ found: false, entityId: null, entityType: null, entityData: null, error: null })

const handleScan = () => {
  if (navigator.mediaDevices && window.BarcodeDetector) {
    showToast({ message: '摄像头扫码将在二维码阶段启用，请先使用手动输入', position: 'top' })
  }
  showInput.value = true
}
const handleManualInput = () => {
  const code = manualCode.value.trim()
  if (!code) return
  scanResult.value = code
  parseResult(code)
  lookupQRCode(code)
  manualCode.value = ''
}
const parseResult = (code) => {
  const prefix = code.split(':')[0]
  scanType.value = ({ MAT: '原材料批次', MCN: '机台', PFC: '工艺流转卡', PRT: '零件', TLG: '模具工装', PKG: '包装' }[prefix] || '未知')
  scanHistory.value.unshift({ code, type: scanType.value, time: new Date().toLocaleString('zh-CN') })
  if (scanHistory.value.length > 20) scanHistory.value.pop()
}
const lookupQRCode = async (code) => {
  loading.value = true
  try {
    const data = await lookupQrCode(code)
    Object.assign(entityInfo, { found: data.found, entityId: data.entity_id, entityType: data.entity_type, entityData: data.entity_data, error: data.error })
  } catch (error) {
    Object.assign(entityInfo, { found: false, entityId: null, entityType: null, entityData: null, error: error.message || '查询失败' })
    showToast({ message: error.message || '查询失败', position: 'top' })
  } finally { loading.value = false }
}
const viewHistoryItem = (item) => { scanResult.value = item.code; parseResult(item.code); lookupQRCode(item.code) }
const formatKey = (key) => ({ batch_id: '批次编号', batch_no: '批次号', machine_id: '机台编号', machine_no: '机台号', card_id: '流转卡编号', card_no: '流转卡号', part_id: '零件编号', customer_part_no: '客户件号', part_name: '零件名称', tooling_id: '模具编号', tooling_number: '模具号', status: '状态', quantity: '数量', current_weight: '当前重量' }[key] || key)
const handleConfirm = () => {
  if (!entityInfo.found) { showToast({ message: '请先扫描有效二维码', position: 'top' }); return }
  showDialog({ title: '确认', message: '确认执行当前扫码操作？', showCancelButton: true }).then(() => { showToast({ message: '二维码已确认', position: 'top' }); resetScan() }).catch(() => {})
}
const resetScan = () => { scanResult.value = ''; scanType.value = ''; Object.assign(entityInfo, { found: false, entityId: null, entityType: null, entityData: null, error: null }) }
</script>

<style scoped>
.scan-page { min-height: calc(100dvh - 48px); padding: 12px 0 20px; }
.scan-area { min-height: 180px; padding: 12px 0; }
.action-buttons { display: grid; gap: 10px; padding: 12px 16px 18px; }
.loading-overlay { position: fixed; top: 50%; left: 50%; z-index: 1000; transform: translate(-50%, -50%); }
</style>
