<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import {
  agentStatusLabels, cloneConfig, configMatches, createAgent, createAssignment, createRun,
  fetchHealth, listAgents, listAssignments, listPublications, listRuns, listSubmissions,
  listVersions, loadSessionOptions, notReadyText, previewPublication, publishAssignment,
  publishSubmission, QUICK_QUESTIONS, reviewSubmission, saveAgent, sourceLabel, statusTone,
  submitWork, TEMPLATE_CONFIG, updateAssignment, useAgentFeedback,
  type AgentAssignment, type AgentConfig, type AgentDraft, type AgentPublication,
  type AgentRun, type AgentSubmission, type AgentVersion, type ClassroomData,
  type SessionOption, type Task,
} from '../../features/agents/workshop'
import { api } from '../../shared/api'
import type { Health } from '../../shared/contracts'
import { useAuth } from '../../shared/auth'
import { dateTime } from '../../shared/format'
import AlertMessage from '../../shared/components/AlertMessage.vue'
import BaseButton from '../../shared/components/BaseButton.vue'
import DataTable from '../../shared/components/DataTable.vue'
import EmptyState from '../../shared/components/EmptyState.vue'
import FormField from '../../shared/components/FormField.vue'
import StatusBadge from '../../shared/components/StatusBadge.vue'
import AgentConfigForm from '../../features/agents/AgentConfigForm.vue'
import RunCompare from '../../features/agents/RunCompare.vue'
import RunHistory from '../../features/agents/RunHistory.vue'
import '../../features/agents/agents.css'

const { user } = useAuth()
const isTeacher = computed(() => user.value?.role === 'teacher')

const tabs = computed(() => isTeacher.value
  ? [
      { key: 'assign', label: '01 作业布置' },
      { key: 'review', label: '02 作业评审' },
      { key: 'shelf', label: '03 班级上架' },
    ]
  : [
      { key: 'design', label: '01 设计与预演' },
      { key: 'submit', label: '02 提交作业' },
      { key: 'shelf', label: '03 班级上架' },
    ])
const activeTab = ref(tabs.value[0].key)
watch(isTeacher, () => { activeTab.value = tabs.value[0].key })

const health = ref<Health | null>(null)
const healthError = ref('')
const classroom = ref<ClassroomData | null>(null)
const classroomError = ref('')
const sessions = ref<SessionOption[]>([])
const sessionsError = ref('')
const displayName = (userId: number) => classroom.value?.students.find(item => item.id === userId)?.username ?? `同学 #${userId}`

// ---------- student: design & preview ----------
const drafts = ref<AgentDraft[]>([])
const draftsError = ref('')
const selectedDraftId = ref<number | null>(null)
const selectedDraft = computed(() => drafts.value.find(item => item.id === selectedDraftId.value) ?? null)
const form = ref<AgentConfig>(cloneConfig(TEMPLATE_CONFIG))
const versions = ref<AgentVersion[]>([])
const versionsError = ref('')
const question = ref('')
const sessionId = ref<number | null>(null)
const runs = ref<AgentRun[]>([])
const runsError = ref('')
const compareIds = ref<number[]>([])
const compareRuns = computed(() => runs.value.filter(run => compareIds.value.includes(run.id)))
const latestRun = ref<AgentRun | null>(null)
const designFeedback = useAgentFeedback()

function selectDraft(draft: AgentDraft) {
  selectedDraftId.value = draft.id
  form.value = cloneConfig(draft.config)
  versions.value = []
  void loadVersions()
}

async function loadDrafts() {
  draftsError.value = ''
  try {
    drafts.value = await listAgents()
    if (!selectedDraftId.value && drafts.value.length) selectDraft(drafts.value[0])
  } catch (error) { draftsError.value = notReadyText(error) }
}

async function loadVersions() {
  if (!selectedDraftId.value) return
  versionsError.value = ''
  try { versions.value = await listVersions(selectedDraftId.value) }
  catch (error) { versionsError.value = notReadyText(error) }
}

async function createFromTemplate() {
  const result = await designFeedback.run(() => createAgent(cloneConfig(TEMPLATE_CONFIG)), '已从客服模板创建草稿')
  if (result) { drafts.value = [result, ...drafts.value]; selectDraft(result) }
}

async function saveVersion() {
  if (!selectedDraftId.value) return
  const result = await designFeedback.run(() => saveAgent(selectedDraftId.value!, form.value))
  if (result) {
    drafts.value = drafts.value.map(item => item.id === result.agent.id ? result.agent : item)
    await loadVersions()
    designFeedback.notice.value = `已保存为不可变版本 v${result.version.version_no}（#${result.version.id}）`
  }
}

async function runPreview() {
  const result = await designFeedback.run(() => createRun({
    agent_id: selectedDraftId.value ?? undefined,
    config: form.value,
    question: question.value,
    session_id: sessionId.value ?? undefined,
  }))
  if (result) {
    latestRun.value = result
    runs.value = [result, ...runs.value]
  }
}

function toggleCompare(id: number) {
  if (compareIds.value.includes(id)) compareIds.value = compareIds.value.filter(item => item !== id)
  else compareIds.value = [...compareIds.value, id].slice(-2)
}

async function loadMyRuns() {
  runsError.value = ''
  try { runs.value = await listRuns({ limit: 50 }) }
  catch (error) { runsError.value = notReadyText(error) }
}

// ---------- student: submit ----------
const myAssignments = ref<AgentAssignment[]>([])
const myAssignmentsError = ref('')
const submitAssignmentId = ref<number | null>(null)
const submitDraftId = ref<number | null>(null)
const submitVersionId = ref<number | null>(null)
const submitVersions = ref<AgentVersion[]>([])
const pickedRunIds = ref<number[]>([])
const improvementNotes = ref('')
const mySubmissions = ref<AgentSubmission[]>([])
const mySubmissionsError = ref('')
const submitFeedback = useAgentFeedback()

const selectedVersion = computed(() => submitVersions.value.find(item => item.id === submitVersionId.value) ?? null)
const qualifyingRunIds = computed(() => {
  if (!selectedVersion.value) return [] as number[]
  return runs.value
    .filter(run => run.status === 'succeeded' && run.source === 'model'
      && configMatches(run.config_snapshot, selectedVersion.value!.config))
    .map(run => run.id)
})
const pickedRuns = computed(() => runs.value.filter(run => pickedRunIds.value.includes(run.id)))
const pickedCompareIds = ref<number[]>([])
const pickedCompareRuns = computed(() => pickedRuns.value.filter(run => pickedCompareIds.value.includes(run.id)))

async function loadMyAssignments() {
  myAssignmentsError.value = ''
  try {
    myAssignments.value = (await listAssignments()).filter(item => item.status === 'published')
    if (!submitAssignmentId.value && myAssignments.value.length) submitAssignmentId.value = myAssignments.value[0].id
  } catch (error) { myAssignmentsError.value = notReadyText(error) }
}

async function loadSubmitVersions() {
  submitVersions.value = []
  submitVersionId.value = null
  if (!submitDraftId.value) return
  try {
    const ownVersions = await listVersions(submitDraftId.value)
    submitVersions.value = ownVersions
    if (ownVersions.length) submitVersionId.value = ownVersions[0].id
  } catch { /* list stays empty; submissions only accept own versions anyway */ }
}

watch(submitDraftId, () => { void loadSubmitVersions() })

async function loadMySubmissions() {
  mySubmissionsError.value = ''
  try { mySubmissions.value = await listSubmissions() }
  catch (error) { mySubmissionsError.value = notReadyText(error) }
}

async function submit() {
  if (!submitAssignmentId.value || !submitVersionId.value || !pickedRunIds.value.length) return
  const result = await submitFeedback.run(() => submitWork({
    assignment_id: submitAssignmentId.value!,
    version_id: submitVersionId.value!,
    run_ids: pickedRunIds.value,
    improvement_notes: improvementNotes.value,
  }), '提交成功，等待教师评审')
  if (result) {
    mySubmissions.value = [result, ...mySubmissions.value]
    pickedRunIds.value = []
    improvementNotes.value = ''
  }
}

function togglePickedRun(id: number) {
  if (pickedRunIds.value.includes(id)) pickedRunIds.value = pickedRunIds.value.filter(item => item !== id)
  else pickedRunIds.value = [...pickedRunIds.value, id]
}

function togglePickedCompare(id: number) {
  if (pickedCompareIds.value.includes(id)) pickedCompareIds.value = pickedCompareIds.value.filter(item => item !== id)
  else pickedCompareIds.value = [...pickedCompareIds.value, id].slice(-2)
}

// ---------- teacher: assignments ----------
const teacherAssignments = ref<AgentAssignment[]>([])
const teacherAssignmentsError = ref('')
const tasks = ref<Task[]>([])
const tasksError = ref('')
const assignmentForm = ref({ title: '', scenario: '', instructions: '', rubricText: '', task_id: null as number | null })
const assignmentEditingId = ref<number | null>(null)
const assignmentFeedback = useAgentFeedback()

const rubricLines = () => assignmentForm.value.rubricText.split('\n').map(line => line.trim()).filter(Boolean).slice(0, 12)

function startEdit(assignment: AgentAssignment) {
  assignmentEditingId.value = assignment.id
  assignmentForm.value = {
    title: assignment.title, scenario: assignment.scenario, instructions: assignment.instructions,
    rubricText: (assignment.rubric ?? []).join('\n'), task_id: assignment.task_id,
  }
  activeTab.value = 'assign'
}

function resetAssignmentForm() {
  assignmentEditingId.value = null
  assignmentForm.value = { title: '', scenario: '', instructions: '', rubricText: '', task_id: null }
}

async function loadTeacherAssignments() {
  teacherAssignmentsError.value = ''
  try { teacherAssignments.value = await listAssignments() }
  catch (error) { teacherAssignmentsError.value = notReadyText(error) }
}

async function saveAssignmentForm() {
  const payload = {
    title: assignmentForm.value.title, instructions: assignmentForm.value.instructions,
    scenario: assignmentForm.value.scenario, rubric: rubricLines(), task_id: assignmentForm.value.task_id,
  }
  const result = assignmentEditingId.value
    ? await assignmentFeedback.run(() => updateAssignment(assignmentEditingId.value!, payload), '草稿已保存')
    : await assignmentFeedback.run(() => createAssignment(payload), '作业草稿已创建')
  if (result) {
    resetAssignmentForm()
    await loadTeacherAssignments()
  }
}

async function publish(id: number) {
  const result = await assignmentFeedback.run(() => publishAssignment(id), '作业已发布到本班')
  if (result) await loadTeacherAssignments()
}

// ---------- teacher: review ----------
const teacherSubmissions = ref<AgentSubmission[]>([])
const teacherSubmissionsError = ref('')
const reviewAssignmentId = ref<number | null>(null)
const selectedSubmissionId = ref<number | null>(null)
const reviewForm = ref({ grade: '', comment: '' })
const reviewFeedback = useAgentFeedback()

const publishedAssignments = computed(() => teacherAssignments.value.filter(item => item.status === 'published'))
const reviewableSubmissions = computed(() => reviewAssignmentId.value
  ? teacherSubmissions.value.filter(item => item.assignment_id === reviewAssignmentId.value)
  : teacherSubmissions.value)
const selectedSubmission = computed(() => reviewableSubmissions.value.find(item => item.id === selectedSubmissionId.value) ?? null)
const frozenConfig = computed(() => selectedSubmission.value?.content_snapshot?.config as AgentConfig | undefined)
const frozenRuns = computed(() => (selectedSubmission.value?.content_snapshot?.runs as AgentRun[] | undefined) ?? [])
const frozenAssignment = computed(() => selectedSubmission.value?.content_snapshot?.assignment as { title?: string; scenario?: string; rubric?: string[] } | undefined)
const frozenCompareIds = ref<number[]>([])
const frozenCompareRuns = computed(() => frozenRuns.value.filter(run => frozenCompareIds.value.includes(run.id)))

async function loadTeacherSubmissions() {
  teacherSubmissionsError.value = ''
  try { teacherSubmissions.value = await listSubmissions() }
  catch (error) { teacherSubmissionsError.value = notReadyText(error) }
}

watch(selectedSubmissionId, () => {
  reviewForm.value = { grade: selectedSubmission.value?.grade != null ? String(selectedSubmission.value.grade) : '', comment: '' }
  frozenCompareIds.value = []
})

async function review(decision: 'approve' | 'return') {
  if (!selectedSubmissionId.value) return
  const gradeInput = Number(reviewForm.value.grade)
  const result = await reviewFeedback.run(() => reviewSubmission(selectedSubmissionId.value!, {
    decision,
    grade: decision === 'approve' ? gradeInput : null,
    comment: reviewForm.value.comment,
  }), decision === 'approve' ? '已批准' : '已退回')
  if (result) {
    teacherSubmissions.value = teacherSubmissions.value.map(item => item.id === result.id ? result : item)
  }
}

async function publishToClass() {
  if (!selectedSubmissionId.value) return
  const result = await reviewFeedback.run(() => publishSubmission(selectedSubmissionId.value!), '已上架到班级列表')
  if (result) {
    publications.value = [result, ...publications.value.filter(item => item.id !== result.id)]
    await loadPublications()
  }
}

function toggleFrozenCompare(id: number) {
  if (frozenCompareIds.value.includes(id)) frozenCompareIds.value = frozenCompareIds.value.filter(item => item !== id)
  else frozenCompareIds.value = [...frozenCompareIds.value, id].slice(-2)
}

// ---------- shelf (all roles) ----------
const publications = ref<AgentPublication[]>([])
const publicationsError = ref('')
const tryPublicationId = ref<number | null>(null)
const tryQuestion = ref('')
const trySessionId = ref<number | null>(null)
const tryRun = ref<AgentRun | null>(null)
const tryFeedback = useAgentFeedback()

async function loadPublications() {
  publicationsError.value = ''
  try { publications.value = await listPublications() }
  catch (error) { publicationsError.value = notReadyText(error) }
}

async function runPublicationPreview() {
  if (!tryPublicationId.value) return
  const result = await tryFeedback.run(() => previewPublication(tryPublicationId.value!, {
    question: tryQuestion.value,
    session_id: trySessionId.value ?? undefined,
  }))
  if (result) tryRun.value = result
}

// ---------- lifecycle ----------
onMounted(async () => {
  try { health.value = await fetchHealth() } catch (error) { healthError.value = notReadyText(error) }
  try { classroom.value = await api<ClassroomData>('/classroom') } catch { classroomError.value = '班级成员信息暂不可用（等待核心模块）' }
  if (!isTeacher.value && user.value) {
    try { sessions.value = await loadSessionOptions(user.value.id) }
    catch { sessionsError.value = '场次列表暂不可用（等待核心模块），可先仅用知识卡预演' }
    await Promise.all([loadDrafts(), loadMyRuns()])
    await Promise.all([loadMyAssignments(), loadMySubmissions()])
  } else {
    await Promise.all([loadTeacherAssignments(), loadTeacherSubmissions()])
    try { tasks.value = await api<Task[]>('/tasks') } catch { tasksError.value = '经营任务列表暂不可用，可先不关联任务' }
  }
  await loadPublications()
})

watch(activeTab, (tab) => {
  if (!isTeacher.value && tab === 'submit' && !mySubmissions.value.length) void loadMySubmissions()
  if (isTeacher.value && tab === 'review') { void loadTeacherSubmissions() }
})

const submissionColumns = [
  { key: 'assignment', label: '作业' },
  { key: 'status', label: '状态' },
  { key: 'version', label: '版本' },
  { key: 'grade', label: '分数' },
  { key: 'comment', label: '评语' },
  { key: 'submitted_at', label: '提交时间' },
]
const mySubmissionRows = computed(() => mySubmissions.value.map(item => ({
  id: item.id,
  assignment: myAssignments.value.find(a => a.id === item.assignment_id)?.title ?? `作业 #${item.assignment_id}`,
  status: item.status,
  version: `#${item.version_id}`,
  grade: item.grade ?? '—',
  comment: item.comment ?? '—',
  submitted_at: dateTime(item.submitted_at),
})))

const teacherSubmissionRows = computed(() => reviewableSubmissions.value.map(item => ({
  id: item.id,
  student: displayName(item.owner_id),
  status: item.status,
  version: `#${item.version_id}`,
  grade: item.grade ?? '—',
  submitted_at: dateTime(item.submitted_at),
  notes: item.improvement_notes.slice(0, 40) + (item.improvement_notes.length > 40 ? '…' : ''),
})))
</script>

<template>
  <div class="page-heading">
    <div>
      <h1>客服智能体</h1>
      <p class="text-muted small">设计服务边界与知识依据，用真实模型预演，提交、评审并上架到班级。</p>
    </div>
    <StatusBadge v-if="health" :tone="health.model_configured ? 'success' : 'warning'">
      {{ health.model_configured ? '模型已配置' : '模型未配置：预演返回规则演示（source=rule）' }}
    </StatusBadge>
  </div>

  <AlertMessage v-if="health && !health.model_configured" tone="info">
    真实模型预演阻塞中：backend/.env 尚未配置 LLM_BASE_URL / LLM_API_KEY / LLM_MODEL。
    编辑、版本、作业与评审功能可用；预演将保存 failed 记录并返回明确标注的规则演示文本，不冒充真实模型结果。
  </AlertMessage>
  <AlertMessage v-if="healthError" tone="info">{{ healthError }}</AlertMessage>

  <nav class="agent-tabs" aria-label="智能体工作台">
    <button v-for="tab in tabs" :key="tab.key" type="button" :class="{ active: activeTab === tab.key }" @click="activeTab = tab.key">
      {{ tab.label }}
    </button>
  </nav>

  <!-- ================= 学生：设计与预演 ================= -->
  <section v-if="!isTeacher && activeTab === 'design'" class="agent-stack">
    <div class="agent-grid">
      <div class="panel">
        <div class="agent-section-title">
          <h3>我的草稿</h3>
          <BaseButton variant="secondary" type="button" @click="createFromTemplate">从客服模板新建</BaseButton>
        </div>
        <AlertMessage v-if="draftsError" tone="error">{{ draftsError }}</AlertMessage>
        <AlertMessage v-if="designFeedback.error.value" tone="error">{{ designFeedback.error.value }}</AlertMessage>
        <AlertMessage v-if="designFeedback.notice.value" tone="success">{{ designFeedback.notice.value }}</AlertMessage>
        <EmptyState v-if="!drafts.length && !draftsError" title="还没有草稿" description="从客服模板开始：预置了职责、边界、行为指令和两张示例知识卡。" />
        <div v-else class="agent-pick">
          <button v-for="draft in drafts" :key="draft.id" type="button" class="agent-pick-item"
            :class="{ active: draft.id === selectedDraftId }" @click="selectDraft(draft)">
            <span>{{ draft.config.name || '（未命名）' }}</span>
            <small class="text-muted">更新于 {{ dateTime(draft.updated_at) }}</small>
          </button>
        </div>
      </div>
      <div class="panel">
        <div class="agent-section-title">
          <h3>当前配置（预演使用这里的实时内容，不是上一次保存的版本）</h3>
        </div>
        <AlertMessage v-if="classroomError" tone="info">{{ classroomError }}</AlertMessage>
        <AgentConfigForm v-if="selectedDraft || !drafts.length" :config="form" />
        <p v-else class="text-muted">选择左侧草稿，或从模板新建后再编辑。</p>
      </div>
    </div>

    <div class="panel">
      <div class="agent-section-title">
        <h3>预演</h3>
        <small class="text-muted">咨询与售后两类快捷问题；可绑定本组场次获取授权商品上下文</small>
      </div>
      <AlertMessage v-if="sessionsError" tone="info">{{ sessionsError }}</AlertMessage>
      <div class="agent-grid">
        <FormField label="问题" for-id="agent-question" hint="也可以点击右侧快捷问题一键填入">
          <textarea id="agent-question" v-model="question" placeholder="输入要预演的观众问题" />
        </FormField>
        <FormField label="绑定场次（可选）" for-id="agent-session" hint="绑定后预演可读取本组授权商品与最近咨询">
          <select id="agent-session" v-model="sessionId">
            <option :value="null">不绑定：仅使用配置与知识卡</option>
            <option v-for="option in sessions" :key="option.id" :value="option.id">{{ option.label }}</option>
          </select>
        </FormField>
      </div>
      <div class="agent-actions">
        <BaseButton :loading="designFeedback.busy.value" :disabled="!question.trim()" @click="runPreview">预演当前配置</BaseButton>
        <BaseButton variant="secondary" :disabled="!selectedDraftId" :loading="designFeedback.busy.value" @click="saveVersion">保存为不可变版本</BaseButton>
        <button v-for="quick in QUICK_QUESTIONS" :key="quick.key" type="button" class="text-button" @click="question = quick.text">
          {{ quick.label }}
        </button>
      </div>
      <AlertMessage v-if="latestRun" :tone="latestRun.status === 'succeeded' ? 'success' : 'error'">
        <template v-if="latestRun.status === 'succeeded'">
          本次预演来源：{{ sourceLabel(latestRun) }}，耗时 {{ latestRun.duration_ms }}ms。
        </template>
        <template v-else>
          本次预演失败（{{ latestRun.error }}），已保存 failed 记录并返回明确标注的规则演示文本（source=rule），不冒充真实模型结果。
        </template>
      </AlertMessage>
    </div>

    <div class="panel">
      <div class="agent-section-title">
        <h3>运行记录</h3>
        <small class="text-muted">勾选最多两条记录进行配置对照</small>
      </div>
      <AlertMessage v-if="runsError" tone="error">{{ runsError }}</AlertMessage>
      <RunHistory :runs="runs" :compare-ids="compareIds" show-compare dense @toggle-compare="toggleCompare" />
    </div>

    <div class="panel" v-if="compareRuns.length">
      <div class="agent-section-title"><h3>配置对照</h3></div>
      <RunCompare :runs="compareRuns" />
    </div>

    <div class="panel" v-if="versions.length">
      <div class="agent-section-title"><h3>版本历史（不可变）</h3></div>
      <div class="agent-kv" v-for="version in versions" :key="version.id">
        <span>v{{ version.version_no }} · #{{ version.id }}</span>
        <div>{{ version.config.name }} · {{ (version.config.knowledge_cards ?? []).length }} 张知识卡 · {{ dateTime(version.created_at) }}</div>
      </div>
    </div>
  </section>

  <!-- ================= 学生：提交作业 ================= -->
  <section v-if="!isTeacher && activeTab === 'submit'" class="agent-stack">
    <div class="panel">
      <div class="agent-section-title">
        <h3>提交作业</h3>
        <small class="text-muted">最终版本至少需要一次配置完全一致的成功真实模型预演（source=model）</small>
      </div>
      <AlertMessage v-if="myAssignmentsError" tone="error">{{ myAssignmentsError }}</AlertMessage>
      <AlertMessage v-if="submitFeedback.error.value" tone="error">{{ submitFeedback.error.value }}</AlertMessage>
      <AlertMessage v-if="submitFeedback.notice.value" tone="success">{{ submitFeedback.notice.value }}</AlertMessage>
      <EmptyState v-if="!myAssignments.length && !myAssignmentsError" title="本班还没有已发布的智能体作业" description="教师发布作业后可在这里提交。" />
      <div v-else class="agent-grid">
        <FormField label="选择作业" for-id="submit-assignment">
          <select id="submit-assignment" v-model="submitAssignmentId">
            <option v-for="assignment in myAssignments" :key="assignment.id" :value="assignment.id">{{ assignment.title }}</option>
          </select>
        </FormField>
        <FormField label="选择草稿" for-id="submit-draft">
          <select id="submit-draft" v-model="submitDraftId">
            <option :value="null">— 请选择 —</option>
            <option v-for="draft in drafts" :key="draft.id" :value="draft.id">{{ draft.config.name || `草稿 #${draft.id}` }}</option>
          </select>
        </FormField>
        <FormField label="选择版本" for-id="submit-version" hint="提交后内容冻结，继续编辑草稿不影响已提交内容">
          <select id="submit-version" v-model="submitVersionId">
            <option v-for="version in submitVersions" :key="version.id" :value="version.id">
              v{{ version.version_no }} · #{{ version.id }} · {{ dateTime(version.created_at) }}
            </option>
          </select>
        </FormField>
        <FormField label="优化说明" for-id="submit-notes" hint="说明你相对上一版的改动与理由">
          <textarea id="submit-notes" v-model="improvementNotes" placeholder="例如：补充了售后边界，增加了发货时效知识卡……" />
        </FormField>
      </div>
      <div v-if="selectedVersion" class="agent-stack">
        <div class="agent-section-title"><h3>选定运行记录</h3></div>
        <p class="agent-caption">
          符合提交要求的运行（配置与版本完全一致 + source=model + 成功）会标注「可用」；规则演示不能替代真实模型预演。
        </p>
        <div class="agent-check-list">
          <label v-for="run in runs" :key="run.id">
            <input type="checkbox" :checked="pickedRunIds.includes(run.id)" @change="togglePickedRun(run.id)" />
            <span>运行 #{{ run.id }} · {{ agentStatusLabels[run.status] }} · {{ sourceLabel(run) }}
              <StatusBadge v-if="qualifyingRunIds.includes(run.id)" tone="success">可用</StatusBadge>
              <StatusBadge v-else tone="warning">配置不一致或非模型</StatusBadge>
            </span>
          </label>
        </div>
        <div class="agent-actions">
          <BaseButton :loading="submitFeedback.busy.value"
            :disabled="!submitAssignmentId || !submitVersionId || !pickedRunIds.length || !improvementNotes.trim()"
            @click="submit">提交作业</BaseButton>
        </div>
        <div v-if="pickedCompareRuns.length">
          <div class="agent-section-title"><h3>所选运行对照</h3></div>
          <RunCompare :runs="pickedCompareRuns" />
        </div>
        <div v-if="pickedRuns.length" class="agent-actions">
          <button type="button" class="text-button" @click="pickedCompareIds = pickedRuns.map(run => run.id).slice(0, 2)">
            对照所选的两条运行
          </button>
        </div>
      </div>
    </div>

    <div class="panel">
      <div class="agent-section-title"><h3>我的提交</h3></div>
      <AlertMessage v-if="mySubmissionsError" tone="error">{{ mySubmissionsError }}</AlertMessage>
      <DataTable :columns="submissionColumns" :rows="mySubmissionRows">
        <template #cell-status="{ value }">
          <StatusBadge :tone="statusTone(String(value))">{{ agentStatusLabels[String(value)] ?? value }}</StatusBadge>
        </template>
      </DataTable>
    </div>
  </section>

  <!-- ================= 教师：作业布置 ================= -->
  <section v-if="isTeacher && activeTab === 'assign'" class="agent-stack">
    <div class="panel">
      <div class="agent-section-title">
        <h3>{{ assignmentEditingId ? `编辑作业草稿 #${assignmentEditingId}` : '布置新作业' }}</h3>
        <button v-if="assignmentEditingId" type="button" class="text-button" @click="resetAssignmentForm">取消编辑</button>
      </div>
      <AlertMessage v-if="assignmentFeedback.error.value" tone="error">{{ assignmentFeedback.error.value }}</AlertMessage>
      <AlertMessage v-if="assignmentFeedback.notice.value" tone="success">{{ assignmentFeedback.notice.value }}</AlertMessage>
      <div class="agent-grid">
        <FormField label="标题" for-id="assign-title">
          <input id="assign-title" v-model="assignmentForm.title" maxlength="200" placeholder="设计一名客服智能体" />
        </FormField>
        <FormField label="服务场景" for-id="assign-scenario" hint="例如：助农直播间的咨询与售后争议处理">
          <input id="assign-scenario" v-model="assignmentForm.scenario" maxlength="500" />
        </FormField>
        <FormField label="作业说明" for-id="assign-instructions">
          <textarea id="assign-instructions" v-model="assignmentForm.instructions" placeholder="说明学生要完成什么、用什么依据评价" />
        </FormField>
        <FormField label="评价标准" for-id="assign-rubric" hint="每行一条，最多 12 条">
          <textarea id="assign-rubric" v-model="assignmentForm.rubricText" placeholder="边界遵守&#10;依据使用&#10;语气与服务意识" />
        </FormField>
        <FormField label="关联经营任务（可选）" for-id="assign-task">
          <select id="assign-task" v-model="assignmentForm.task_id">
            <option :value="null">不关联</option>
            <option v-for="task in tasks" :key="task.id" :value="task.id">{{ task.title }}</option>
          </select>
        </FormField>
      </div>
      <AlertMessage v-if="tasksError" tone="info">{{ tasksError }}</AlertMessage>
      <div class="agent-actions">
        <BaseButton :loading="assignmentFeedback.busy.value"
          :disabled="!assignmentForm.title.trim() || !assignmentForm.instructions.trim()" @click="saveAssignmentForm">
          {{ assignmentEditingId ? '保存草稿' : '创建草稿' }}
        </BaseButton>
      </div>
    </div>

    <div class="panel">
      <div class="agent-section-title"><h3>我的作业</h3></div>
      <AlertMessage v-if="teacherAssignmentsError" tone="error">{{ teacherAssignmentsError }}</AlertMessage>
      <DataTable :columns="[
        { key: 'title', label: '标题' },
        { key: 'status', label: '状态' },
        { key: 'scenario', label: '服务场景' },
        { key: 'published_at', label: '发布时间' },
        { key: 'actions', label: '操作' },
      ]" :rows="teacherAssignments.map(item => ({
        id: item.id, title: item.title, status: item.status, scenario: item.scenario || '—',
        published_at: item.published_at ? dateTime(item.published_at) : '—', actions: '',
      }))">
        <template #cell-status="{ value }">
          <StatusBadge :tone="statusTone(String(value))">{{ agentStatusLabels[String(value)] ?? value }}</StatusBadge>
        </template>
        <template #cell-actions="{ row }">
          <button v-if="row.status === 'draft'" type="button" class="text-button" @click="startEdit(teacherAssignments.find(a => a.id === Number(row.id))!)">编辑</button>
          <button v-if="row.status === 'draft'" type="button" class="text-button" @click="publish(Number(row.id))">发布到本班</button>
        </template>
      </DataTable>
    </div>
  </section>

  <!-- ================= 教师：作业评审 ================= -->
  <section v-if="isTeacher && activeTab === 'review'" class="agent-stack">
    <div class="panel">
      <div class="agent-section-title">
        <h3>提交列表</h3>
        <div class="agent-actions">
          <select v-model="reviewAssignmentId" aria-label="按作业筛选">
            <option :value="null">全部作业</option>
            <option v-for="assignment in teacherAssignments" :key="assignment.id" :value="assignment.id">{{ assignment.title }}</option>
          </select>
        </div>
      </div>
      <AlertMessage v-if="teacherSubmissionsError" tone="error">{{ teacherSubmissionsError }}</AlertMessage>
      <EmptyState v-if="!reviewableSubmissions.length && !teacherSubmissionsError" title="暂无提交" description="学生提交后会出现在这里。" />
      <DataTable v-else :columns="[
        { key: 'student', label: '学生' },
        { key: 'status', label: '状态' },
        { key: 'version', label: '版本' },
        { key: 'grade', label: '分数' },
        { key: 'submitted_at', label: '提交时间' },
        { key: 'notes', label: '优化说明' },
        { key: 'actions', label: '操作' },
      ]" :rows="teacherSubmissionRows">
        <template #cell-status="{ value }">
          <StatusBadge :tone="statusTone(String(value))">{{ agentStatusLabels[String(value)] ?? value }}</StatusBadge>
        </template>
        <template #cell-actions="{ row }">
          <button type="button" class="text-button" @click="selectedSubmissionId = Number(row.id)">查看 / 评审</button>
        </template>
      </DataTable>
    </div>

    <div class="panel" v-if="selectedSubmission">
      <div class="agent-section-title">
        <h3>提交 #{{ selectedSubmission.id }} · {{ displayName(selectedSubmission.owner_id) }}</h3>
        <StatusBadge :tone="statusTone(selectedSubmission.status)">{{ agentStatusLabels[selectedSubmission.status] }}</StatusBadge>
      </div>
      <AlertMessage v-if="reviewFeedback.error.value" tone="error">{{ reviewFeedback.error.value }}</AlertMessage>
      <AlertMessage v-if="reviewFeedback.notice.value" tone="success">{{ reviewFeedback.notice.value }}</AlertMessage>

      <div class="agent-kv"><span>作业</span><div>{{ frozenAssignment?.title ?? '—' }}</div></div>
      <div class="agent-kv"><span>服务场景</span><div>{{ frozenAssignment?.scenario || '—' }}</div></div>
      <div class="agent-kv"><span>评价标准</span><div>{{ (frozenAssignment?.rubric ?? []).join('；') || '—' }}</div></div>
      <div class="agent-kv"><span>优化说明</span><div>{{ selectedSubmission.improvement_notes }}</div></div>

      <div class="agent-section-title" style="margin-top: 16px"><h3>提交时冻结的配置</h3></div>
      <div class="agent-muted-box" v-if="frozenConfig">
        <p><strong>{{ frozenConfig.name }}</strong></p>
        <p>职责：{{ frozenConfig.duties }}</p>
        <p>服务边界：{{ frozenConfig.boundaries }}</p>
        <p>行为指令：{{ frozenConfig.instructions }}</p>
        <div v-for="(card, index) in frozenConfig.knowledge_cards ?? []" :key="index">
          <p>【知识卡｜{{ card.title }}】{{ card.content }}</p>
        </div>
      </div>

      <div class="agent-section-title" style="margin-top: 16px">
        <h3>冻结的运行记录</h3>
        <small class="text-muted">勾选最多两条对照两次配置与输出</small>
      </div>
      <RunHistory :runs="frozenRuns" :compare-ids="frozenCompareIds" show-compare dense @toggle-compare="toggleFrozenCompare" />
      <RunCompare v-if="frozenCompareRuns.length" :runs="frozenCompareRuns" style="margin-top: 16px" />

      <div v-if="selectedSubmission.status === 'submitted'" class="agent-grid" style="margin-top: 16px">
        <FormField label="分数（0～100）" for-id="review-grade">
          <input id="review-grade" v-model="reviewForm.grade" inputmode="decimal" placeholder="88" />
        </FormField>
        <FormField label="评语" for-id="review-comment">
          <textarea id="review-comment" v-model="reviewForm.comment" placeholder="准确性、边界遵守、依据使用的评价" />
        </FormField>
      </div>
      <div class="agent-actions">
        <template v-if="selectedSubmission.status === 'submitted'">
          <BaseButton :loading="reviewFeedback.busy.value" :disabled="!reviewForm.comment.trim()" @click="review('approve')">批准</BaseButton>
          <BaseButton variant="danger" :loading="reviewFeedback.busy.value" :disabled="!reviewForm.comment.trim()" @click="review('return')">退回</BaseButton>
        </template>
        <BaseButton v-if="selectedSubmission.status === 'approved'" variant="secondary" :loading="reviewFeedback.busy.value" @click="publishToClass">
          上架到班级（固定版本 #{{ selectedSubmission.version_id }}）
        </BaseButton>
      </div>
      <p v-if="selectedSubmission.status === 'approved'" class="agent-caption">
        上架后同班学生可试用该固定版本；作者继续编辑草稿不会改变已上架内容。
      </p>
    </div>
  </section>

  <!-- ================= 班级上架（所有角色） ================= -->
  <section v-if="activeTab === 'shelf'" class="agent-stack">
    <div class="panel">
      <div class="agent-section-title">
        <h3>班级上架列表</h3>
        <small class="text-muted">来自已通过评审的固定版本，作者后续编辑不影响这里的内容</small>
      </div>
      <AlertMessage v-if="publicationsError" tone="error">{{ publicationsError }}</AlertMessage>
      <EmptyState v-if="!publications.length && !publicationsError" title="班级还没有上架的智能体" description="教师批准提交并上架后，同班同学可以在这里试用。" />
      <div v-else class="agent-pick">
        <button v-for="item in publications" :key="item.id" type="button" class="agent-pick-item"
          :class="{ active: item.id === tryPublicationId }" @click="tryPublicationId = item.id; tryRun = null">
          <span>{{ item.name }} · 作者 {{ displayName(item.owner_id) }}</span>
          <small class="text-muted">版本 #{{ item.version_id }} · {{ dateTime(item.published_at) }}</small>
        </button>
      </div>
    </div>

    <div class="panel" v-if="tryPublicationId">
      <div class="agent-section-title">
        <h3>试用预演</h3>
        <small class="text-muted">预演只生成建议并记录运行，不会写入经营数据</small>
      </div>
      <div class="agent-grid">
        <FormField label="问题" for-id="shelf-question">
          <textarea id="shelf-question" v-model="tryQuestion" placeholder="输入要试用的问题" />
        </FormField>
        <FormField label="绑定场次（可选）" for-id="shelf-session">
          <select id="shelf-session" v-model="trySessionId">
            <option :value="null">不绑定：仅使用配置与知识卡</option>
            <option v-for="option in sessions" :key="option.id" :value="option.id">{{ option.label }}</option>
          </select>
        </FormField>
      </div>
      <div class="agent-actions">
        <BaseButton :loading="tryFeedback.busy.value" :disabled="!tryQuestion.trim()" @click="runPublicationPreview">预演该固定版本</BaseButton>
        <button v-for="quick in QUICK_QUESTIONS" :key="quick.key" type="button" class="text-button" @click="tryQuestion = quick.text">
          {{ quick.label }}
        </button>
      </div>
      <AlertMessage v-if="tryFeedback.error.value" tone="error">{{ tryFeedback.error.value }}</AlertMessage>
      <div v-if="tryRun" class="agent-stack" style="margin-top: 16px">
        <RunHistory :runs="[tryRun]" />
      </div>
    </div>

    <div class="panel" v-if="tryPublicationId">
      <div class="agent-section-title"><h3>该版本的固定配置</h3></div>
      <div class="agent-muted-box" v-if="publications.find(item => item.id === tryPublicationId)">
        <AgentConfigForm :config="publications.find(item => item.id === tryPublicationId)!.config" disabled />
      </div>
    </div>
  </section>
</template>
