<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { api, notReadyText, positions, sessionPath, statusLabels, type ClassroomData, type TaskDetail } from '../../features/student/workspace'
import type { Task, TrainingSession } from '../../shared/contracts'
import { useAuth } from '../../shared/auth'
import { money, dateTime } from '../../shared/format'
import AlertMessage from '../../shared/components/AlertMessage.vue'
import BaseButton from '../../shared/components/BaseButton.vue'
import EmptyState from '../../shared/components/EmptyState.vue'
import StatusBadge from '../../shared/components/StatusBadge.vue'

const { user } = useAuth()
const loading = ref(true)
const loadError = ref('')
const notReady = ref(false)
const tasks = ref<Task[]>([])
const details = ref<Record<number, TaskDetail>>({})
const classroom = ref<ClassroomData | null>(null)

const myTeam = computed(() => classroom.value?.teams.find(team => team.members?.some(member => member.user_id === user.value?.id)) ?? null)
const myPosition = computed(() => myTeam.value?.members?.find(member => member.user_id === user.value?.id)?.position)
const joinedTasks = computed(() => tasks.value.filter(task => task.status !== 'draft'))
const cards = computed(() => joinedTasks.value.map(task => {
  const detail = details.value[task.id]
  const session = detail?.sessions.find(item => item.team_id === myTeam.value?.id) ?? null
  return { task, session }
}))

async function load() {
  loading.value = true; loadError.value = ''; notReady.value = false
  try {
    const [taskList, classroomData] = await Promise.all([api<Task[]>('/tasks'), api<ClassroomData>('/classroom')])
    tasks.value = taskList
    classroom.value = classroomData
    const results = await Promise.allSettled(joinedTasks.value.map(task => api<TaskDetail>(`/tasks/${task.id}`)))
    results.forEach((result, index) => {
      if (result.status === 'fulfilled') details.value[joinedTasks.value[index].id] = result.value
    })
  } catch (error) {
    loadError.value = notReadyText(error)
    notReady.value = true
  } finally { loading.value = false }
}
onMounted(load)

function entryLabel(session: TrainingSession) {
  return { preparing: '进入准备工作台', live: '进入直播工作台', paused: '回到直播工作台', ended: '进入履约与复盘', submitted: '查看复盘与成绩', graded: '查看复盘与成绩' }[session.status] ?? '查看场次'
}
const sessionTone = (session: TrainingSession) => session.status === 'live' ? 'success' : ['paused', 'preparing'].includes(session.status) ? 'warning' : 'neutral'
const taskTone = (task: Task) => task.status === 'published' ? 'success' : task.status === 'closed' ? 'neutral' : 'warning'
</script>

<template>
  <div class="page-heading">
    <div>
      <p class="eyebrow">STUDENT WORKSPACE</p>
      <h1>我的实训</h1>
      <p>查看教师发布的实训任务，进入本小组场次完成选品、开播与复盘。</p>
    </div>
  </div>

  <div v-if="loading" class="panel"><p class="text-muted">正在加载任务…</p></div>
  <AlertMessage v-else-if="loadError" tone="error">
    {{ loadError }}
    <template v-if="notReady">后端经营接口正在接入中，稍后可点击重试。</template>
    <div style="margin-top:10px"><BaseButton variant="secondary" @click="load">重新加载</BaseButton></div>
  </AlertMessage>
  <template v-else>
    <div class="student-stack">
      <section class="panel" aria-label="我的小组">
        <div class="student-section-title"><h2>我的小组</h2></div>
        <template v-if="myTeam">
          <div class="student-actions" style="margin-bottom:14px">
            <span class="student-member">{{ myTeam.name }}</span>
            <span v-if="myPosition" class="student-member">我的岗位：{{ positions[myPosition] ?? myPosition }}</span>
          </div>
          <p class="student-caption" v-if="myTeam.members?.length">
            组员：
            <template v-for="(member, index) in myTeam.members" :key="member.user_id">
              {{ classroom?.students.find(student => student.id === member.user_id)?.username ?? `学员#${member.user_id}` }}（{{ positions[member.position] ?? member.position }}）<template v-if="index < myTeam.members.length - 1">、</template>
            </template>
          </p>
          <p class="student-caption">同组账号共享同一场次：组员保存的调研、货盘与脚本会实时进入同一场数据。</p>
        </template>
        <p v-else class="student-caption">教师尚未把你加入任何小组；加入小组并发布任务后，这里会显示你的岗位与场次入口。</p>
      </section>

      <section aria-label="实训任务列表">
        <div class="student-section-title"><h2>实训任务</h2><span class="text-muted small">{{ cards.length }} 个任务</span></div>
        <EmptyState v-if="!cards.length" title="教师尚未发布实训任务" description="任务发布后，你会在这里看到任务目标、预算和小组场次入口。" />
        <div class="student-stack">
          <article v-for="card in cards" :key="card.task.id" class="panel student-task-card">
            <div class="student-section-title" style="margin-bottom:12px">
              <h3>{{ card.task.title }}</h3>
              <StatusBadge :tone="taskTone(card.task)">{{ statusLabels[card.task.status] ?? card.task.status }}</StatusBadge>
            </div>
            <p class="student-caption" style="margin-bottom:16px">{{ card.task.description || '暂无任务说明' }}</p>
            <div class="student-stats">
              <div><span>目标人群</span><strong style="font-size:13px">{{ card.task.target_audience || '—' }}</strong></div>
              <div><span>初始预算</span><strong>{{ money(card.task.initial_budget_cents ?? 0) }}</strong></div>
              <div><span>GMV 目标</span><strong>{{ money(card.task.target_gmv_cents ?? 0) }}</strong></div>
              <div><span>市场热度／难度</span><strong>{{ card.task.market_heat ?? 1 }} / {{ card.task.difficulty ?? 1 }}</strong></div>
              <div><span>任务时间</span><strong style="font-size:12px">{{ dateTime(card.task.starts_at) }} ～ {{ dateTime(card.task.ends_at) }}</strong></div>
            </div>
            <div class="student-footer" style="margin-top:18px">
              <template v-if="card.session">
                <div class="student-actions">
                  <StatusBadge :tone="sessionTone(card.session)">本场次：{{ statusLabels[card.session.status] ?? card.session.status }}</StatusBadge>
                  <span class="small text-muted">教学仿真场次 #{{ card.session.id }}</span>
                </div>
                <RouterLink :to="sessionPath(card.session)"><BaseButton>{{ entryLabel(card.session) }}</BaseButton></RouterLink>
              </template>
              <p v-else class="small text-muted">本组未参加该任务，暂无场次入口。</p>
            </div>
          </article>
        </div>
      </section>
    </div>
  </template>
</template>

<style scoped>
.student-task-card{border-left:3px solid #8db79a}
</style>
