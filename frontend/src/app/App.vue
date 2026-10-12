<script setup lang="ts">
import { useRouter } from 'vue-router'
import { useAuth } from '../shared/auth'
const { user, logout } = useAuth()
const router = useRouter()
function exit() { logout(); router.push('/login') }
</script>
<template>
  <div class="app-layout">
    <aside class="sidebar">
      <RouterLink to="/" class="brand"><span class="brand-icon">▶</span><span>直播运营<span class="brand-sub">虚拟仿真实训平台</span></span></RouterLink>
      <div class="nav-label">教学工作台</div>
      <nav aria-label="主要导航">
        <RouterLink to="/" class="nav-item"><span>▦</span>实训概览</RouterLink>
        <RouterLink v-if="user?.role !== 'teacher'" to="/student" class="nav-item"><span>◈</span>我的实训</RouterLink>
        <RouterLink v-if="user?.role !== 'student'" to="/teacher" class="nav-item"><span>▤</span>教学管理</RouterLink>
        <RouterLink to="/competitions" class="nav-item"><span>◎</span>竞赛与对比</RouterLink>
        <RouterLink to="/agents" class="nav-item"><span>◇</span>客服智能体</RouterLink>
      </nav>
      <div class="sidebar-note"><span class="live-dot" />教学仿真环境<p>在练习中积累经验<br />从每一次复盘开始进步</p></div>
    </aside>
    <div class="app-main">
      <header class="topbar"><span>直播电商全流程实训</span><div class="topbar-right"><span class="environment-label">教学模拟 · 无真实交易</span><template v-if="user"><span>{{ user.username }}</span><button class="text-button" @click="exit">退出</button></template><RouterLink v-else to="/login" class="text-button">登录账号 →</RouterLink></div></header>
      <main class="page-content"><RouterView /></main>
    </div>
  </div>
</template>
