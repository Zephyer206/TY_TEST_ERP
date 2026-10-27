<template>
  <div v-for="(labels,index) in sheets" :key="index" class="qr-paper" :aria-label="'标签第 ' + (index + 1) + ' 页'">
    <article v-for="label in labels" :key="label.id" class="qr-label"><div v-if="label.box" class="label-business"><strong>{{ label.box.product_code }} · {{ label.box.product_name_snapshot }}</strong><span>{{ label.box.customer_part_no }}</span><span>{{ label.box.customer_name_snapshot }}</span><span>订单 #{{ label.box.order_id }}</span><span>下一工艺 {{ label.box.next_process_code || '未指定' }}</span></div><div v-else class="label-business"><strong>产品框标签</strong><span>待绑定订单</span></div><img :src="label.qr_image_base64" :alt="label.public_code + ' 二维码'" /><code>{{ label.public_code }}</code></article>
  </div>
</template>
<script setup lang="ts">
import { computed } from 'vue'
import type { QrPrintLabel } from '@/types/productBox'
const props=defineProps<{items:QrPrintLabel[]}>()
const sheets=computed(()=>{const result=[];for(let i=0;i<props.items.length;i+=21)result.push(props.items.slice(i,i+21));return result})
</script>
