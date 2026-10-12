<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import {
  api, localDateTimeInput, notReadyText, positions, scoreLabels, statusLabels, toIsoFromLocalInput, useFeedback, yuanToCents,
  type ClassroomData,
} from './teacherWorkspace'
import type { Task } from '../../shared/contracts'
import { money, dateTime } from '../../shared/format'
import AlertMessage from '../../shared/components/AlertMessage.vue'
import BaseButton from '../../shared/components/BaseButton.vue'
import DataTable from '../../shared/components/DataTable.vue'
import EmptyState from '../../shared/components/EmptyState.vue'
import FormField from '../../shared/components/FormField.vue'
import StatusBadge from '../../shared/components/StatusBadge.vue'

const router = useRouter()
const loading = ref(true)
const loadError = ref('')
const tasks = ref<Task[]>([])
const classroom = ref<ClassroomData | null>(null)

const teamsLocked = computed(() => tasks.value.some(task => task.status !== 'draft'))
const studentName = (id: number) => classroom.value?.students.find(student => student.id === id)?.username ?? `学员#${id}`
const studentTeamName = (id: number) => classroom.value?.teams.find(team => team.members?.some(member => member.user_id === id))?.name

const teamColumns = [
  { key: 'name', label: '小组' },
  { key: 'members', label: '成员与岗位' },
  { key: 'actions', label: '操作' },
]
const teamRows = computed(() => (classroom.value?.teams ?? []).map(team => ({
  id: team.id, name: team.name,
  members: (team.members ?? []).map(member => `${studentName(member.user_id)}（${positions[member.position] ?? member.position}）`).join('、') || '—',
  locked: teamsLocked.value,
})))

const teamFeedback = useFeedback()
const teamFormOpen = ref(false)
const teamForm = ref<{ id: number | null; name: string; members: { user_id: number; position: string }[] }>({ id: null, name: '', members: [] })

function openTeamCreate() {
  teamForm.value = { id: null, name: '', members: [{ user_id: 0, position: 'host' }] }
  teamFormOpen.value = true
}
function openTeamEdit(teamId: number) {
  const team = classroom.value?.teams.find(item => item.id === teamId)
  if (!team) return
  teamForm.value = { id: team.id, name: team.name, members: (team.members ?? []).map(member => ({ ...member })) }
  teamFormOpen.value = true
}
function addMemberRow() { teamForm.value.members.push({ user_id: 0, position: 'service' }) }
function removeMemberRow(index: number) { teamForm.value.members.splice(index, 1) }
function takenByOther(row: { user_id: number; position: string }, userId: number) {
  return userId !== 0 && teamForm.value.members.some(other => other !== row && other.user_id === userId)
}

async function submitTeam() {
  const form = teamForm.value
  if (!form.name.trim() || form.members.length === 0 || form.members.some(member => !member.user_id)) {
    teamFeedback.error.value = '请填写小组名称，并选择至少一名成员。'
    return
  }
  const payload = { name: form.name.trim(), members: form.members.map(member => ({ user_id: member.user_id, position: member.position })) }
  const result = await teamFeedback.run(async () => {
    const team = form.id === null
      ? await teamFeedback.write<TeamLike>('/teams', payload)
      : await teamFeedback.write<TeamLike>(`/teams/${form.id}`, payload, 'PUT')
    await load()
    return team
  }, form.id === null ? '小组已创建。' : '小组已更新。')
  if (result) teamFormOpen.value = false
}
interface TeamLike { id: number; name: string }

const taskColumns = [
  { key: 'title', label: '任务' },
  { key: 'status', label: '状态' },
  { key: 'time', label: '任务时间' },
  { key: 'budget', label: '初始预算' },
  { key: 'teamCount', label: '参赛组' },
  { key: 'actions', label: '操作' },
]
const taskRows = computed(() => tasks.value.map(task => ({
  id: task.id,
  title: task.title,
  status: task.status,
  time: `${dateTime(task.starts_at)} ～ ${dateTime(task.ends_at)}`,
  budget: money(task.initial_budget_cents ?? 0),
  teamCount: String(task.team_ids?.length ?? 0),
})))
const taskTone = (status: string) => status === 'published' ? 'success' : status === 'closed' ? 'neutral' : 'warning'

const publishFeedback = useFeedback()
async function publishTask(taskId: number) {
  const task = tasks.value.find(item => item.id === taskId)
  if (!task || task.status !== 'draft') return
  if (!window.confirm(`发布任务「${task.title}」后将冻结规则与小组，并为每个参赛组创建场次。确认发布？`)) return
  await publishFeedback.run(async () => {
    await publishFeedback.write(`/tasks/${task.id}/publish`)
    await load()
  }, '任务已发布，规则与小组成员已冻结。')
}

const weightFields = (Object.keys(scoreLabels) as (keyof typeof scoreLabels)[]).map(key => ({ key, label: scoreLabels[key] }))
type WeightKey = (typeof weightFields)[number]['key']
const taskFeedback = useFeedback()
const formOpen = ref(false)
const defaults = () => ({
  title: '',
  description: '',
  target_audience: '',
  initialBudgetYuan: '1000',
  targetGmvYuan: '500',
  marketHeat: '1',
  difficulty: '1',
  startsAt: localDateTimeInput(new Date()),
  endsAt: localDateTimeInput(new Date(Date.now() + 14 * 24 * 3600 * 1000)),
  weights: { process: 25, business: 25, service: 20, compliance: 15, review: 15 } as Record<WeightKey, number>,
  teamIds: [] as number[],
  withCompetition: false,
  competitionTitle: '',
})
const taskForm = ref(defaults())
const weightSum = computed(() => Object.values(taskForm.value.weights).reduce((sum, value) => sum + Number(value || 0), 0))
function resetForm() { taskForm.value = defaults(); formOpen.value = true }

async function submitTask() {
  const form = taskForm.value
  if (!form.title.trim()) { taskFeedback.error.value = '请填写任务标题。'; return }
  if (form.teamIds.length < 1) { taskFeedback.error.value = '请选择至少一个参赛小组。'; return }
  if (form.withCompetition && !form.competitionTitle.trim()) { taskFeedback.error.value = '请填写竞赛标题。'; return }
  const payload = {
    title: form.title.trim(),
    description: form.description,
    target_audience: form.target_audience,
    initial_budget_cents: yuanToCents(form.initialBudgetYuan),
    target_gmv_cents: yuanToCents(form.targetGmvYuan),
    market_heat: Number(form.marketHeat),
    difficulty: Number(form.difficulty),
    starts_at: toIsoFromLocalInput(form.startsAt),
    ends_at: toIsoFromLocalInput(form.endsAt),
    score_weights: { ...form.weights },
    team_ids: form.teamIds,
  }
  if (!Number.isInteger(payload.initial_budget_cents) || payload.initial_budget_cents < 0) { taskFeedback.error.value = '初始预算金额不正确。'; return }
  if (!Number.isInteger(payload.target_gmv_cents) || payload.target_gmv_cents <= 0) { taskFeedback.error.value = 'GMV 目标金额不正确。'; return }
  const result = await taskFeedback.run(async () => {
    const task = await taskFeedback.write<Task>('/tasks', payload)
    if (form.withCompetition) {
      await taskFeedback.write('/competitions', { task_id: task.id, title: form.competitionTitle.trim() })
    }
    await load()
    return task
  }, form.withCompetition ? '任务草稿与关联竞赛已创建。' : '任务草稿已创建。')
  if (result) { formOpen.value = false; void router.push(`/teacher/tasks/${result.id}`) }
}

async function load() {
  loading.value = true; loadError.value = ''
  try {
    const [taskList, classroomData] = await Promise.all([api<Task[]>('/tasks'), api<ClassroomData>('/classroom')])
    tasks.value = taskList
    classroom.value = classroomData
  } catch (error) {
    loadError.value = notReadyText(error)
  } finally { loading.value = false }
}
onMounted(load)
</script>

<template>
  <div class="page-heading">
    <div>
      <p class="eyebrow">TEACHER CENTER</p>
      <h1>教学管理</h1>
      <p>组织小组、创建并发布实训任务，查看各组的经营方案与实训成果。</p>
    </div>
    <div class="heading-actions">
      <BaseButton variant="secondary" @click="load">刷新</BaseButton>
      <BaseButton @click="resetForm">创建实训任务</BaseButton>
    </div>
  </div>

  <div v-if="loading" class="panel"><p class="text-muted">正在加载班级与任务…</p></div>
  <AlertMessage v-else-if="loadError" tone="error">
    {{ loadError }}
    <template v-if="!classroom">后端接口正在接入中，稍后可点击重试。</template>
    <div style="margin-top:10px"><BaseButton variant="secondary" @click="load">重新加载</BaseButton></div>
  </AlertMessage>
  <template v-else>
    <section class="panel" aria-label="小组与成员">
      <div class="section-heading" style="margin:0 0 14px">
        <h2>小组与成员</h2>
        <div class="heading-actions">
          <span v-if="teamsLocked" class="small text-muted">已有发布任务，小组成员已冻结</span>
          <BaseButton v-else variant="secondary" @click="openTeamCreate">新建小组</BaseButton>
        </div>
      </div>
      <DataTable :columns="teamColumns" :rows="teamRows">
        <template #cell-actions="{ row }">
          <button class="text-button" :disabled="!!row.locked" @click="openTeamEdit(Number(row.id))">调整成员岗位</button>
        </template>
      </DataTable>
      <p class="small text-muted" style="margin-bottom:0">成员从本班已有学生中选择；岗位用于分工记录，同一学生在一个任务中只加入一个组。</p>

      <div v-if="teamFormOpen" class="form-block">
        <h3>{{ teamForm.id === null ? '新建小组' : `调整小组：${teamForm.name}` }}</h3>
        <FormField label="小组名称" for-id="team-name">
          <input id="team-name" v-model="teamForm.name" maxlength="100" placeholder="例如：青禾助农组" />
        </FormField>
        <FormField label="成员与岗位" hint="每行选择一名学生并指定岗位；同一学生不能在本组重复。">
          <div class="member-rows">
            <div v-for="(member, index) in teamForm.members" :key="index" class="member-row">
              <select v-model="member.user_id" :aria-label="`成员${index + 1}`">
                <option :value="0" disabled>选择学生</option>
                <option v-for="student in classroom?.students ?? []" :key="student.id" :value="student.id"
                  :disabled="takenByOther(member, student.id)">
                  {{ student.username }}{{ studentTeamName(student.id) ? `（已入组：${studentTeamName(student.id)}）` : '' }}
                </option>
              </select>
              <select v-model="member.position" :aria-label="`岗位${index + 1}`">
                <option v-for="(label, key) in positions" :key="key" :value="key">{{ label }}</option>
              </select>
              <BaseButton variant="secondary" :disabled="teamForm.members.length <= 1" @click="removeMemberRow(index)">移除</BaseButton>
            </div>
          </div>
          <BaseButton variant="secondary" @click="addMemberRow">添加成员</BaseButton>
        </FormField>
        <AlertMessage v-if="teamFeedback.error.value" tone="error">{{ teamFeedback.error.value }}</AlertMessage>
        <AlertMessage v-else-if="teamFeedback.notice.value" tone="success">{{ teamFeedback.notice.value }}</AlertMessage>
        <div class="heading-actions">
          <BaseButton variant="secondary" @click="teamFormOpen = false">取消</BaseButton>
          <BaseButton :loading="teamFeedback.busy.value" @click="submitTeam">保存小组</BaseButton>
        </div>
      </div>
    </section>

    <section aria-label="实训任务">
      <div class="section-heading">
        <h2>实训任务</h2>
        <span class="small text-muted">{{ tasks.length }} 个任务</span>
      </div>
      <EmptyState v-if="!tasks.length" title="还没有实训任务" description="点击右上角“创建实训任务”，填写目标、预算与参赛小组后发布。" />
      <DataTable v-else :columns="taskColumns" :rows="taskRows">
        <template #cell-status="{ row }">
          <StatusBadge :tone="taskTone(String(row.status))">{{ statusLabels[String(row.status)] ?? row.status }}</StatusBadge>
        </template>
        <template #cell-actions="{ row }">
          <RouterLink :to="`/teacher/tasks/${row.id}`" class="text-button">查看与评分</RouterLink>
          <button v-if="row.status === 'draft'" class="text-button" :disabled="publishFeedback.busy.value" @click="publishTask(Number(row.id))">发布</button>
        </template>
      </DataTable>
      <AlertMessage v-if="publishFeedback.error.value" tone="error">{{ publishFeedback.error.value }}</AlertMessage>
      <AlertMessage v-else-if="publishFeedback.notice.value" tone="success">{{ publishFeedback.notice.value }}</AlertMessage>
    </section>

    <section v-if="formOpen" class="panel" aria-label="创建实训任务">
      <div class="section-heading" style="margin:0 0 14px">
        <h2>创建实训任务</h2>
        <BaseButton variant="secondary" @click="formOpen = false">收起</BaseButton>
      </div>
      <form class="task-form" @submit.prevent="submitTask">
        <FormField label="任务标题" for-id="task-title"><input id="task-title" v-model="taskForm.title" maxlength="200" placeholder="例如：助农产品直播选品与运营" /></FormField>
        <FormField label="任务背景与要求" for-id="task-desc" hint="展示给学生，说明本次实训要完成什么。">
          <textarea id="task-desc" v-model="taskForm.description" rows="3" />
        </FormField>
        <FormField label="目标人群" for-id="task-audience"><input id="task-audience" v-model="taskForm.target_audience" maxlength="200" placeholder="例如：关注品质与价格的家庭消费者" /></FormField>
        <div class="form-grid">
          <FormField label="初始预算（元）" for-id="task-budget"><input id="task-budget" v-model="taskForm.initialBudgetYuan" inputmode="decimal" /></FormField>
          <FormField label="GMV 目标（元）" for-id="task-gmv"><input id="task-gmv" v-model="taskForm.targetGmvYuan" inputmode="decimal" /></FormField>
          <FormField label="市场热度（0.1～3）" for-id="task-heat"><input id="task-heat" v-model="taskForm.marketHeat" inputmode="decimal" /></FormField>
          <FormField label="竞争难度（0.1～3）" for-id="task-difficulty"><input id="task-difficulty" v-model="taskForm.difficulty" inputmode="decimal" /></FormField>
          <FormField label="开始时间" for-id="task-start"><input id="task-start" v-model="taskForm.startsAt" type="datetime-local" /></FormField>
          <FormField label="截止时间" for-id="task-end"><input id="task-end" v-model="taskForm.endsAt" type="datetime-local" /></FormField>
        </div>
        <FormField label="评分权重（之和必须为 100）" :hint="`当前合计：${weightSum}`">
          <div class="form-grid">
            <FormField v-for="field in weightFields" :key="field.key" :label="field.label" :for-id="`weight-${field.key}`">
              <input :id="`weight-${field.key}`" v-model.number="taskForm.weights[field.key]" type="number" min="0" max="100" step="1" />
            </FormField>
          </div>
        </FormField>
        <FormField label="参赛小组" hint="发布前确定参赛组；发布后成员与规则冻结。">
          <div class="team-checks">
            <label v-for="team in classroom?.teams ?? []" :key="team.id" class="team-check">
              <input v-model="taskForm.teamIds" type="checkbox" :value="team.id" />
              {{ team.name }}<span class="small text-muted">（{{ (team.members ?? []).length }} 人）</span>
            </label>
            <span v-if="!(classroom?.teams ?? []).length" class="small text-muted">请先在上方创建小组。</span>
          </div>
        </FormField>
        <FormField label="关联竞赛" hint="勾选后会在任务草稿上创建同截止时间、同评分规则的竞赛，随任务发布一同冻结。">
          <label class="team-check"><input v-model="taskForm.withCompetition" type="checkbox" />为本任务创建竞赛</label>
          <template v-if="taskForm.withCompetition">
            <input v-model="taskForm.competitionTitle" maxlength="200" placeholder="例如：助农直播同场竞赛" style="margin-top:8px" />
          </template>
        </FormField>
        <AlertMessage v-if="taskFeedback.error.value" tone="error">{{ taskFeedback.error.value }}</AlertMessage>
        <AlertMessage v-else-if="taskFeedback.notice.value" tone="success">{{ taskFeedback.notice.value }}</AlertMessage>
        <div class="heading-actions">
          <BaseButton type="submit" :loading="taskFeedback.busy.value">保存草稿</BaseButton>
          <span class="small text-muted">保存后可继续编辑，发布前不会出现在学生端。</span>
        </div>
      </form>
    </section>
  </template>
</template>

<style scoped>
.heading-actions{display:flex;gap:10px;align-items:center;flex-wrap:wrap}
.form-block{border-top:1px solid var(--line);margin-top:18px;padding-top:18px}
.member-rows{display:flex;flex-direction:column;gap:8px;margin-bottom:10px}
.member-row{display:grid;grid-template-columns:2fr 1fr auto;gap:8px;align-items:center}
.form-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:0 16px}
.team-checks{display:flex;flex-direction:column;gap:8px}
.team-check{display:flex;gap:8px;align-items:center;font-size:13px}
.task-form{max-width:860px}
</style>
