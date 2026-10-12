<script setup lang="ts">
defineProps<{ columns: { key: string; label: string }[]; rows: Record<string, unknown>[]; rowKey?: string; loading?: boolean }>()
</script>
<template><div class="table-wrap" :aria-busy="loading"><table><thead><tr><th v-for="column in columns" :key="column.key" scope="col">{{ column.label }}</th></tr></thead><tbody><tr v-if="loading"><td :colspan="columns.length">正在加载…</td></tr><tr v-else-if="!rows.length"><td :colspan="columns.length" class="text-muted">暂无记录</td></tr><template v-else><tr v-for="(row, index) in rows" :key="String(row[rowKey ?? 'id'] ?? index)"><td v-for="column in columns" :key="column.key"><slot :name="`cell-${column.key}`" :row="row" :value="row[column.key]">{{ row[column.key] ?? '—' }}</slot></td></tr></template></tbody></table></div></template>
