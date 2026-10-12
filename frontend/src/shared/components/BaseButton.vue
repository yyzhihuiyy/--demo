<script setup lang="ts">
withDefaults(defineProps<{ variant?: 'primary' | 'secondary' | 'danger'; loading?: boolean; disabled?: boolean; type?: 'button' | 'submit' | 'reset' }>(), {
  variant: 'primary', loading: false, disabled: false, type: 'button',
})
</script>
<template><button :type="type" :class="['button', `button--${variant}`]" :disabled="disabled || loading" :aria-busy="loading"><span v-if="loading" class="spinner" /><slot /></button></template>
