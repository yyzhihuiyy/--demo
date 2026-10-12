<script setup lang="ts">
import StatusBadge from '../../shared/components/StatusBadge.vue'
import { dateTime } from '../../shared/format'
import type { AgentRun } from '../../shared/contracts'
import { agentStatusLabels, sourceLabel } from './workshop'

defineProps<{ runs: AgentRun[]; compareIds?: number[]; showCompare?: boolean; dense?: boolean }>()
const emit = defineEmits<{ (e: 'toggleCompare', id: number): void }>()
</script>

<template>
  <div class="agent-stack">
    <p v-if="!runs.length" class="text-muted">暂无预演记录。</p>
    <article v-for="run in runs" :key="run.id" class="agent-run">
      <header class="agent-run-header">
        <label v-if="showCompare" class="agent-compare-check">
          <input type="checkbox" :checked="compareIds?.includes(run.id)" @change="emit('toggleCompare', run.id)" /> 对照
        </label>
        <strong>运行 #{{ run.id }}</strong>
        <StatusBadge :tone="run.status === 'succeeded' ? 'success' : 'danger'">{{ agentStatusLabels[run.status] ?? run.status }}</StatusBadge>
        <StatusBadge :tone="run.source === 'model' ? 'success' : 'warning'">{{ sourceLabel(run) }}</StatusBadge>
        <small class="text-muted">{{ dateTime(run.created_at) }} · 耗时 {{ run.duration_ms }}ms</small>
      </header>
      <p class="agent-run-question">问题：{{ run.question }}</p>
      <p v-if="run.output" class="agent-run-output" :class="{ 'agent-compact-output': dense }">{{ run.output }}</p>
      <p v-if="run.error" class="text-danger small">失败原因：{{ run.error }}</p>
      <small class="text-muted">上下文来源：{{ (run.context_sources ?? []).join('、') || '—' }}</small>
    </article>
  </div>
</template>
