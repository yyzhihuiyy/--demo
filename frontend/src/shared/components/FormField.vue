<script setup lang="ts">
defineProps<{ label: string; forId?: string; hint?: string; error?: string }>()
</script>
<template><div class="form-field"><label :for="forId">{{ label }}</label><slot /><small v-if="error" class="text-danger" role="alert">{{ error }}</small><small v-else-if="hint" class="text-muted">{{ hint }}</small></div></template>
