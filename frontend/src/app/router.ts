import { createRouter, createWebHistory } from 'vue-router'
import { useAuth } from '../shared/auth'
import { ApiError } from '../shared/api'

export const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', name: 'home', component: () => import('./HomePage.vue') },
    { path: '/login', name: 'login', component: () => import('./LoginPage.vue') },
    { path: '/student', name: 'student', component: () => import('../pages/student/StudentHome.vue'), meta: { auth: true, role: 'student' } },
    { path: '/sessions/:id/prepare', name: 'prepare', component: () => import('../pages/student/PreparationPage.vue'), meta: { auth: true, role: 'student' } },
    { path: '/sessions/:id/live', name: 'live', component: () => import('../pages/student/LivePage.vue'), meta: { auth: true, role: 'student' } },
    { path: '/sessions/:id/review', name: 'review', component: () => import('../pages/student/ReviewPage.vue'), meta: { auth: true, role: 'student' } },
    { path: '/teacher', name: 'teacher', component: () => import('../pages/teacher/TeacherPage.vue'), meta: { auth: true, role: 'teacher' } },
    { path: '/teacher/tasks/:id', name: 'teacher-task', component: () => import('../pages/teacher/TeacherTaskPage.vue'), meta: { auth: true, role: 'teacher' } },
    { path: '/teacher/sessions/:id/evidence', name: 'teacher-evidence', component: () => import('../pages/teacher/TeacherSessionPage.vue'), meta: { auth: true, role: 'teacher' } },
    { path: '/competitions', name: 'competitions', component: () => import('../pages/competition/CompetitionPage.vue'), meta: { auth: true } },
    { path: '/agents', name: 'agents', component: () => import('../pages/agents/AgentWorkshop.vue'), meta: { auth: true } },
    { path: '/:pathMatch(.*)*', redirect: '/' },
  ],
})

router.beforeEach(async (to) => {
  if (!to.meta.auth) return true
  const auth = useAuth()
  try { await auth.restore() } catch (error) {
    if (!(error instanceof ApiError) || error.status !== 401) return { name: 'login', query: { redirect: to.fullPath, error: 'service' } }
  }
  if (!auth.user.value) return { name: 'login', query: { redirect: to.fullPath } }
  if (to.meta.role && to.meta.role !== auth.user.value.role) return { name: 'home' }
})
