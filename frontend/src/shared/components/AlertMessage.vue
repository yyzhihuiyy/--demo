<script setup lang="ts">
withDefaults(defineProps<{ tone?: 'error' | 'success' | 'info' }>(), { tone: 'info' })
</script>
<template><div :class="['alert', `alert--${tone}`]" :role="tone === 'error' ? 'alert' : 'status'"><slot /></div></template>
