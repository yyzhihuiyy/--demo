<script setup lang="ts">
import StatusBadge from '../../shared/components/StatusBadge.vue'
import { dateTime } from '../../shared/format'
import type { AgentRun } from '../../shared/contracts'
import { agentStatusLabels, sourceLabel } from './workshop'

defineProps<{ runs: AgentRun[] }>()
</script>

<template>
  <div class="agent-compare">
    <article v-for="run in runs" :key="run.id" class="agent-compare-item">
      <header>
        <strong>运行 #{{ run.id }}</strong>
        <StatusBadge :tone="run.status === 'succeeded' ? 'success' : 'danger'">{{ agentStatusLabels[run.status] ?? run.status }}</StatusBadge>
        <StatusBadge :tone="run.source === 'model' ? 'success' : 'warning'">{{ sourceLabel(run) }}</StatusBadge>
        <small class="text-muted">{{ dateTime(run.created_at) }} · 耗时 {{ run.duration_ms }}ms</small>
      </header>
      <dl class="agent-compare-config">
        <div><dt>名称</dt><dd>{{ run.config_snapshot.name || '未填写' }}</dd></div>
        <div><dt>服务边界</dt><dd>{{ run.config_snapshot.boundaries || '未填写' }}</dd></div>
        <div><dt>行为指令</dt><dd>{{ run.config_snapshot.instructions || '未填写' }}</dd></div>
        <div><dt>知识卡</dt><dd>{{ (run.config_snapshot.knowledge_cards ?? []).map(card => card.title || '（无标题）').join('、') || '未配置' }}</dd></div>
      </dl>
      <p class="agent-compare-question">问题：{{ run.question }}</p>
      <p class="agent-compare-output">{{ run.output ?? '（无输出）' }}</p>
      <p v-if="run.error" class="text-danger small">失败原因：{{ run.error }}</p>
    </article>
    <p v-if="!runs.length" class="text-muted">还没有可对照的运行。</p>
  </div>
</template>
