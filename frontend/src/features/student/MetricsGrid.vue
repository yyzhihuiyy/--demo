<script setup lang="ts">
import { computed } from 'vue'
import type { Metrics } from '../../shared/contracts'
import { money, percent } from '../../shared/format'
const props = defineProps<{ metrics: Metrics; live?: boolean }>()
const entries = computed(() => props.live ? [
  ['当前在线', String(props.metrics.online_count ?? 0)], ['累计进房人次', String(props.metrics.cumulative_entries ?? 0)], ['商品点击', String(props.metrics.product_clicks ?? 0)], ['成交订单', String(props.metrics.order_count ?? 0)], ['成交 GMV', money(props.metrics.gmv_cents ?? 0)], ['净销售额', money(props.metrics.net_sales_cents ?? 0)],
] : [
  ['成交 GMV', money(props.metrics.gmv_cents ?? 0)], ['净销售额', money(props.metrics.net_sales_cents ?? 0)], ['经营利润', money(props.metrics.profit_cents ?? 0)], ['资金余额', money(props.metrics.cash_balance_cents ?? 0)], ['成交转化率', percent(props.metrics.conversion_rate)], ['咨询回复率', percent(props.metrics.reply_rate)],
])
</script>
<template><div class="student-metrics"><div v-for="entry in entries" :key="entry[0]" class="student-metric"><span>{{ entry[0] }}</span><strong>{{ entry[1] }}</strong></div></div></template>
<style scoped>.student-metrics{display:grid;grid-template-columns:repeat(6,minmax(0,1fr));gap:12px}.student-metric{background:var(--metric-bg,#fff);border:1px solid var(--metric-border,#e3e9e5);border-radius:10px;padding:17px 15px}.student-metric span{font-size:11px;color:var(--metric-muted,#829086);display:block;margin-bottom:10px}.student-metric strong{font-size:22px;font-weight:600;letter-spacing:-.5px;color:var(--metric-value,#284e3b)}@media(max-width:1200px){.student-metrics{grid-template-columns:repeat(3,1fr)}}@media(max-width:600px){.student-metrics{grid-template-columns:repeat(2,1fr)}.student-metric strong{font-size:19px}}</style>
