<template>
  <main class="notifications-workspace"><header><div><h1>{{adminMode?'通知投递管理':'规格异常通知'}}</h1><p>按订单核对卷料差异和负责人处理结果，通知投递状态单独显示。</p></div><div class="actions"><el-button v-if="canAdmin" :disabled="loading || !!retrying" @click="switchMode">{{adminMode?'我的通知':'投递管理'}}</el-button><el-button :loading="loading" :disabled="!!retrying" @click="load">重新读取</el-button></div></header>
    <section class="filters" aria-label="通知筛选"><label>投递状态</label><el-select v-model="status" aria-label="通知投递状态筛选" :disabled="loading || !!retrying"><el-option label="全部投递状态" value="all"/><el-option label="待投递" value="pending"/><el-option label="已投递" value="sent"/><el-option label="失败" value="failed"/></el-select><el-checkbox v-if="!adminMode" v-model="unread" :disabled="loading || !!retrying">仅未读站内通知</el-checkbox><span>{{total}} 条</span></section>
    <p v-if="error" class="error" role="alert">{{error}}</p>
    <p v-if="adminMode" class="note">失败记录保留每次尝试。新建重试批次不会修改异常处理结果。</p>
    <el-table :data="items" row-key="id" :aria-busy="loading" empty-text="当前筛选下没有通知" class="notification-table">
      <el-table-column label="订单 / 产品" min-width="220"><template #default="{row}"><strong>{{row.exception.plan_no}} · {{row.exception.product_name}}</strong><span class="subline">{{row.exception.process_code}} · {{row.exception.batch_no || '未维护批次'}}</span></template></el-table-column>
      <el-table-column label="负责人确认" min-width="130"><template #default="{row}">{{row.exception.status==='pending_confirmation'?'待确认':'已确认'}}<span class="subline">{{resolution(row.exception.resolution)}}{{row.exception.released_at?' · 暂停已解除':''}}</span></template></el-table-column>
      <el-table-column label="通知投递" min-width="155"><template #default="{row}"><b>{{delivery(row.delivery_status)}}</b><span class="subline">本批尝试 {{row.attempts}} / 5<span v-if="row.retry_batch"> · 重试批次 {{row.retry_batch}}</span></span><span v-if="row.last_error" class="subline error">{{safeError(row.last_error)}}</span></template></el-table-column>
      <el-table-column label="时间" min-width="175"><template #default="{row}">{{time(row.sent_at || row.created_at)}}<span v-if="row.delivery_status==='pending'" class="subline">下次尝试 {{time(row.next_retry_at)}}</span></template></el-table-column>
      <el-table-column label="操作" min-width="190"><template #default="{row}"><el-button v-if="row.exception.allowed_actions.includes('confirm')" link :disabled="loading || !!retrying" @click="selected=row.exception">处理异常</el-button><el-button v-if="row.exception.allowed_actions.includes('resume')" link :disabled="loading || !!retrying" @click="selected=row.exception">复核并恢复</el-button><el-button v-if="adminMode && row.delivery_status==='failed'" link :loading="retrying===row.id" :disabled="loading || !!retrying" @click="retry(row)">新建重试批次</el-button><details class="record-details"><summary>规格与记录</summary><CoilSpecComparison :expected="row.exception.expected_spec" :actual="row.exception.actual_spec"/><p v-if="row.exception.remark">处理备注：{{row.exception.remark}}</p><p v-if="row.exception.resume_reason">恢复依据：{{row.exception.resume_reason}}</p><p v-if="row.exception.confirmed_by">确认账号 {{row.exception.confirmed_by}} · {{time(row.exception.confirmed_at)}}</p><p v-if="adminMode">收件账号 {{row.recipient_user_id}}</p><ol v-if="row.attempt_history.length" class="attempts"><li v-for="attempt in row.attempt_history" :key="`${attempt.retry_batch}-${attempt.attempt_no}`">批次 {{attempt.retry_batch}} / 第 {{attempt.attempt_no}} 次 · {{delivery(attempt.result)}} · {{time(attempt.created_at)}}</li></ol></details></template></el-table-column>
    </el-table>
    <el-pagination v-if="total>pageSize" v-model:current-page="page" :page-size="pageSize" :total="total" layout="prev,pager,next" :disabled="loading || !!retrying" @current-change="load"/>
    <ExceptionDecisionDialog v-if="selected" :item="selected" @cancel="selected=null" @reload="reloadDecision" @completed="reloadDecision"/>
  </main>
</template>
<script setup lang="ts">
import {onMounted,ref,watch} from 'vue'
import {ElMessage} from 'element-plus'
import {coilExceptionsApi as api} from '@/api/coilExceptions'
import type {CoilException,CoilResolution,DeliveryStatus,NotificationDelivery} from '@/types/coilException'
import type {QrId} from '@/types/productBox'
import {qrError} from './messages'
import ExceptionDecisionDialog from '@/components/product-box-qr/ExceptionDecisionDialog.vue'
import CoilSpecComparison from '@/components/product-box-qr/CoilSpecComparison.vue'
const loading=ref(false),error=ref(''),items=ref<NotificationDelivery[]>([]),total=ref(0),page=ref(1),pageSize=25
const status=ref<DeliveryStatus|'all'>('all'),unread=ref(false),adminMode=ref(false),canAdmin=ref(false),selected=ref<CoilException|null>(null),retrying=ref<QrId|null>(null)
const retryKeys=new Map<string,string>();let sequence=0
const time=(value:string|null)=>value?new Date(value).toLocaleString('zh-CN',{hour12:false}):'—'
const delivery=(value:string)=>({pending:'待投递',sent:'已投递',failed:'失败'} as Record<string,string>)[value]||value
const resolution=(value:CoilResolution|null)=>value?({accept_continue:'接受继续生产',pause:'暂停生产',reconfirm_coil:'重新确认卷料'} as const)[value]:'等待处理'
const safeError=(value:string)=>value==='RECIPIENT_NO_LONGER_AUTHORIZED'?'收件权限已变化，请核对配置':'站内投递未完成，保留重试记录'
async function load(){const request=++sequence;loading.value=true;error.value='';items.value=[];total.value=0;try{const params={page:page.value,page_size:pageSize,delivery_status:status.value==='all'?undefined:status.value,...(!adminMode.value?{unread_only:unread.value}:{})};const result=await(adminMode.value?api.deliveries(params):api.notifications(params));if(request!==sequence)return;items.value=result.items;total.value=result.total;canAdmin.value=result.can_manage_deliveries}catch(e){if(request===sequence)error.value=qrError(e)}finally{if(request===sequence)loading.value=false}}
function switchMode(){adminMode.value=!adminMode.value;page.value=1;selected.value=null;load()}
async function reloadDecision(){selected.value=null;await load()}
async function retry(row:NotificationDelivery){if(retrying.value)return;retrying.value=row.id;error.value='';const slot=`${row.id}:${row.version}`;if(!retryKeys.has(slot))retryKeys.set(slot,crypto.randomUUID());try{await api.retry(row.id,{expected_version:row.version,idempotency_key:retryKeys.get(slot)!});ElMessage.success('重试批次已创建，工作器将更新投递状态');await load()}catch(e){error.value=qrError(e)}finally{retrying.value=null}}
watch([status,unread],()=>{page.value=1;load()});onMounted(load)
</script>
<style scoped>
.notifications-workspace{padding:24px;color:var(--zephyr-ink)}header{display:flex;justify-content:space-between;gap:20px;margin-bottom:20px}h1{font-size:22px;margin:0 0 8px}p{font-size:12px;line-height:1.7;color:var(--zephyr-muted);margin:6px 0}.actions{display:flex;gap:8px;white-space:nowrap}.filters{display:flex;align-items:center;gap:12px;padding:14px 16px;border:1px solid var(--zephyr-border);border-radius:6px;background:var(--zephyr-surface);margin-bottom:16px;font-size:12px}.filters .el-select{width:180px}.filters>span{margin-left:auto;color:var(--zephyr-muted);font-variant-numeric:tabular-nums}.notification-table{font-variant-numeric:tabular-nums}.subline{display:block;font-size:11px;color:var(--zephyr-muted);margin-top:5px}.error{color:var(--zephyr-danger)}.record-details{font-size:12px;margin:8px 0}summary{cursor:pointer;width:fit-content;color:var(--zephyr-muted)}summary:focus-visible{outline:2px solid var(--zephyr-primary);outline-offset:3px}.attempts{padding-left:20px;color:var(--zephyr-muted);font-size:11px;line-height:1.8}.el-pagination{margin-top:16px}@media(max-width:700px){.notifications-workspace{padding:12px}header,.filters{flex-wrap:wrap}}
</style>
