<template>
  <div class="report-page">
    <van-nav-bar title="报工" left-text="返回" @click-left="router.back()" />

    <van-form @submit="handleSubmit">
      <van-cell-group title="基本信息">
        <van-field
          v-model="form.machineCode"
          label="机台编号"
          placeholder="请扫码或输入"
          readonly
          @click="scanMachine"
        />
        <van-field
          v-model="form.partCode"
          label="零件编号"
          placeholder="请扫码或输入"
          readonly
          @click="scanPart"
        />
        <van-field
          v-model="form.partName"
          label="零件名称"
          placeholder="自动填充"
          readonly
        />
      </van-cell-group>

      <van-cell-group title="报工数量">
        <van-field
          v-model.number="form.goodCount"
          type="number"
          label="良品数量"
          placeholder="请输入良品数量"
          :rules="[{ required: true, message: '请输入良品数量' }]"
        />
        <van-field
          v-model.number="form.scrapCount"
          type="number"
          label="报废数量"
          placeholder="请输入报废数量"
        />
        <van-field
          v-if="form.scrapCount > 0"
          v-model="form.scrapReason"
          label="报废原因"
          placeholder="请选择或输入报废原因"
        />
      </van-cell-group>

      <van-cell-group title="备注">
        <van-field
          v-model="form.remark"
          type="textarea"
          placeholder="可选备注信息"
          rows="2"
        />
      </van-cell-group>

      <div class="submit-area">
        <van-button type="primary" size="large" native-type="submit" :loading="submitting">
          提交报工
        </van-button>
      </div>
    </van-form>

    <van-action-sheet
      v-model:show="showScrapReasons"
      title="选择报废原因"
      :actions="scrapReasons"
      @select="onSelectScrapReason"
    />
  </div>
</template>

<script setup>
import { ref, reactive } from 'vue'
import { useRouter } from 'vue-router'
import { showToast, showDialog } from 'vant'

const router = useRouter()
const submitting = ref(false)
const showScrapReasons = ref(false)

const serverUrl = localStorage.getItem('server_url') || 'http://124.222.29.229:8000'

const form = reactive({
  machineCode: '',
  machineId: null,
  partCode: '',
  partId: null,
  partName: '',
  goodCount: null,
  scrapCount: 0,
  scrapReason: '',
  remark: '',
})

const scrapReasons = [
  { name: '材料缺陷' },
  { name: '模具问题' },
  { name: '设备故障' },
  { name: '操作失误' },
  { name: '其他' },
]

const scanMachine = () => {
  // TODO: 扫码获取机台
  showToast({ message: '请使用扫码功能选择机台', position: 'top' })
}

const scanPart = async () => {
  // TODO: 扫码获取零件并填充信息
  showToast({ message: '请使用扫码功能选择零件', position: 'top' })
}

const onSelectScrapReason = (action) => {
  form.scrapReason = action.name
  showScrapReasons.value = false
}

const handleSubmit = async () => {
  if (form.scrapCount > 0 && !form.scrapReason.trim()) {
    showToast({ message: '有报废数量必须填写原因', position: 'top' })
    return
  }

  submitting.value = true
  try {
    const formData = new FormData()
    formData.append('machine_id', form.machineId || 0)
    formData.append('part_id', form.partId || 0)
    formData.append('good_count', form.goodCount || 0)
    formData.append('scrap_count', form.scrapCount || 0)
    formData.append('scrap_reason', form.scrapReason || '')
    formData.append('remark', form.remark || '')

    const response = await fetch(`${serverUrl}/operator/report`, {
      method: 'POST',
      body: formData,
      credentials: 'include',
    })

    if (response.ok || response.redirected) {
      showToast({ message: '报工成功', position: 'top' })
      // 重置表单
      Object.assign(form, {
        machineCode: '',
        machineId: null,
        partCode: '',
        partId: null,
        partName: '',
        goodCount: null,
        scrapCount: 0,
        scrapReason: '',
        remark: '',
      })
    } else {
      const error = await response.text()
      showToast({ message: '报工失败: ' + error, position: 'top' })
    }
  } catch (error) {
    showToast({ message: '提交失败: ' + error.message, position: 'top' })
  } finally {
    submitting.value = false
  }
}
</script>

<style scoped>
.report-page {
  min-height: 100vh;
  background-color: #f5f5f5;
  padding-bottom: 80px;
}

.submit-area {
  margin: 16px;
}
</style>
