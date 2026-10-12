<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { api } from '../shared/api'
import type { Health } from '../shared/contracts'
import StatusBadge from '../shared/components/StatusBadge.vue'
const health = ref<Health | null>(null)
const disconnected = ref(false)
const steps = [
  { no: '01', title: '调研与选品', text: '认识目标客群，配置货盘，制定有依据的价格。', link: '/student', tag: '经营决策' },
  { no: '02', title: '直播运营实训', text: '从脚本和开播准备，到互动成交与订单履约。', link: '/student', tag: '岗位协作' },
  { no: '03', title: '竞赛与复盘', text: '在相同条件下比较策略，用过程证据解释结果。', link: '/competitions', tag: '学习评价' },
  { no: '04', title: '客服智能体', text: '设计服务边界，预演真实问题，改进你的助手。', link: '/agents', tag: '人机协同' },
]
onMounted(async () => { try { health.value = await api<Health>('/health') } catch { disconnected.value = true } })
</script>
<template>
  <div class="page-heading"><div><div class="eyebrow">LEARNING BY DOING</div><h1>把一次直播，变成一次成长。</h1><p>从经营决策到现场协作，完成一场有准备、有记录、有反馈的实训。</p></div><StatusBadge :tone="health ? 'success' : disconnected ? 'warning' : 'neutral'">{{ health ? '服务已连接' : disconnected ? '服务未连接' : '正在连接' }}</StatusBadge></div>
  <section class="hero-panel"><div class="hero-copy"><span class="hero-kicker">本期实训主题</span><h2>让好农产<br />遇见好生意。</h2><p>助农直播综合实训<br />调研 · 货盘 · 开播 · 履约 · 复盘</p><RouterLink to="/student" class="button button--primary">进入我的实训 <span>↗</span></RouterLink></div><div class="hero-art" aria-hidden="true"><div class="orbit orbit-one"/><div class="orbit orbit-two"/><div class="produce-card"><span class="produce-emoji">🍊</span><div>产地好物</div><small>从了解产品开始</small></div><div class="floating-label">准备充分，自信开播</div></div></section>
  <div class="section-heading"><h2>四个场景，一条完整学习路径</h2><span class="text-muted">决策 → 执行 → 复盘 → 改进</span></div>
  <section class="scenario-grid"><RouterLink v-for="step in steps" :key="step.no" :to="step.link" class="scenario-card"><div class="scenario-top"><span class="step-number">{{ step.no }}</span><span class="scenario-tag">{{ step.tag }}</span></div><h3>{{ step.title }}</h3><p>{{ step.text }}</p><span class="card-arrow">进入学习场景 ↗</span></RouterLink></section>
  <div class="notice-line"><span>ⓘ</span><p>本平台中的市场资料、观众、订单、资金与物流均用于教学模拟。当前为开发预览，业务模块接入后开放完整训练。</p></div>
</template>
