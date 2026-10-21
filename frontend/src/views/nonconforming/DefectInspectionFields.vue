<template>
  <div class="quality-inspection-checks">
    <div v-for="(item, index) in record.inspectionItems" :key="item.id" class="quality-edit-card quality-inspection-check">
      <h4>{{ index + 1 }}. {{ item.name }}</h4><p class="quality-inspection-standard">验收标准：{{ item.standard }}</p>
      <el-form-item label="实测 / 核实结果" required><el-input v-model="evidence.checks[index].actual" type="textarea" :rows="2" maxlength="1000" placeholder="填写处理后的实测数据、检查范围或核实凭据" /></el-form-item>
      <el-form-item label="项目判定" required><el-radio-group v-model="evidence.checks[index].passed"><el-radio :value="true">通过</el-radio><el-radio :value="false">不通过</el-radio></el-radio-group></el-form-item>
    </div>
  </div>
  <div v-if="releaseRequired(record.release)" class="quality-release-review"><strong>本次放行及发货要求</strong><p v-if="record.release.mode === 'concession'">让步放行 · {{ record.release.approvedBy }}</p><p v-for="item in requirements" :key="item[0]"><b>{{ item[0] }}：</b>{{ item[1] }}</p></div>
  <div class="quality-inspection-confirmations"><el-checkbox v-model="evidence.quantityChecked">已核对本次提交的实物数量</el-checkbox><el-checkbox v-if="releaseRequired(record.release)" v-model="evidence.releaseChecked">已核对放行依据及标识、包装、去向要求</el-checkbox></div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { releaseRequired, type DefectRecord, type InspectionEvidence } from '@/domain/nonconforming'
const props = defineProps<{ record: DefectRecord; evidence: InspectionEvidence }>()
const requirements = computed(() => { const r = props.record.release; return [['放行依据', r.basis], ['对应零件号', r.outputPartNo], ['发货去向', r.destination], ['标识', r.labeling], ['包装', r.packing], ['批次 / 余料', r.batchRequirement]].filter(item => item[1]) })
</script>
