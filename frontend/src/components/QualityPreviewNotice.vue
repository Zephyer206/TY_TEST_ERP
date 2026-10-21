<template>
  <div class="quality-preview-notice" role="status">
    <el-icon><InfoFilled /></el-icon>
    <span><strong>服务器数据库台账</strong> · {{ store.loading ? '正在读取服务器数据…' : store.loadError ? '读取失败，请重试；当前不会使用本地预览数据。' : '记录与处理结果由服务器保存，可在不同设备读取。' }}</span>
  </div>
</template>
<script setup lang="ts">
import { InfoFilled } from '@element-plus/icons-vue'
import { useNonconformingPreview } from '@/stores/nonconformingPreview'
const store = useNonconformingPreview()
</script>
<style scoped>
.quality-preview-notice{display:flex;align-items:center;gap:8px;padding:9px 12px;margin-bottom:16px;border:1px solid var(--zephyr-primary-border);border-radius:6px;background:var(--zephyr-surface-muted);color:var(--zephyr-primary);font-size:12px;line-height:1.6}.quality-preview-notice .el-icon{flex-shrink:0;font-size:15px}.quality-preview-notice strong{font-weight:600}
</style>
