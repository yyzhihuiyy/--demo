<script setup lang="ts">
defineProps<{ title: string; description?: string }>()
</script>
<template><div class="empty-state"><div class="empty-symbol" aria-hidden="true">＋</div><h2>{{ title }}</h2><p v-if="description">{{ description }}</p><slot /></div></template>
