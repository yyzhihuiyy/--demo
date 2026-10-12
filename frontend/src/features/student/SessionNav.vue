<script setup lang="ts">
defineProps<{ id: number }>()
</script>
<template><nav class="student-session-nav" aria-label="场次步骤"><RouterLink to="/student">← 我的实训</RouterLink><RouterLink :to="`/sessions/${id}/prepare`">01 经营准备</RouterLink><RouterLink :to="`/sessions/${id}/live`">02 协作直播</RouterLink><RouterLink :to="`/sessions/${id}/review`">03 履约与复盘</RouterLink></nav></template>
<style scoped>.student-session-nav{display:flex;gap:8px;flex-wrap:wrap;margin:0 0 26px;font-size:12px}.student-session-nav a{padding:9px 13px;color:#7a8980;border-radius:7px}.student-session-nav .router-link-exact-active{background:#e7f0e9;color:#216b51;font-weight:600}</style>
