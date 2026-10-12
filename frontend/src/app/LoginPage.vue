<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuth } from '../shared/auth'
import { errorMessage } from '../shared/api'
import BaseButton from '../shared/components/BaseButton.vue'
import FormField from '../shared/components/FormField.vue'
import AlertMessage from '../shared/components/AlertMessage.vue'
const auth = useAuth(); const route = useRoute(); const router = useRouter()
const username = ref(''); const password = ref(''); const loading = ref(false)
const error = ref(route.query.error ? '暂时无法恢复登录，请确认服务状态后重试' : '')
const target = computed(() => typeof route.query.redirect === 'string' && route.query.redirect.startsWith('/') && !route.query.redirect.startsWith('//') ? route.query.redirect : auth.user.value?.role === 'teacher' ? '/teacher' : '/student')
async function submit() {
  if (loading.value) return
  loading.value = true; error.value = ''
  try { await auth.login(username.value, password.value); await router.push(target.value) }
  catch (e) { error.value = errorMessage(e) }
  finally { loading.value = false }
}
</script>
<template><section class="login-card panel"><div class="eyebrow">WELCOME BACK</div><h1>开始你的实训</h1><p class="text-muted">使用分配给你的教师或学生账号登录。</p><AlertMessage v-if="error" tone="error">{{ error }}</AlertMessage><form @submit.prevent="submit"><FormField label="账号" for-id="username"><input id="username" v-model="username" autocomplete="username" required placeholder="输入账号" /></FormField><FormField label="密码" for-id="password"><input id="password" v-model="password" type="password" autocomplete="current-password" required placeholder="输入密码" /></FormField><BaseButton type="submit" :loading="loading">登录工作台 →</BaseButton></form><p class="text-muted small">开发预览阶段，账号服务接入后可使用分配的演示账号。</p></section></template>
