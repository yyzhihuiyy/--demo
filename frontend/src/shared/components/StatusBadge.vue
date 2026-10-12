<script setup lang="ts">
withDefaults(defineProps<{ tone?: 'neutral' | 'success' | 'warning' | 'danger' }>(), { tone: 'neutral' })
</script>
<template><span :class="['badge', `badge--${tone}`]"><slot /></span></template>
