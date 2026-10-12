import { ref } from 'vue'
import { ApiError, api, errorMessage, mutation } from '../../shared/api'
import type { AgentConfig, AgentRun, Health, KnowledgeCard, Task, TrainingSession, User } from '../../shared/contracts'

export interface AgentAssignment {
  id: number
  class_id: number
  teacher_id: number
  task_id: number | null
  title: string
  instructions: string
  scenario: string
  rubric: string[]
  status: 'draft' | 'published'
  created_at: string
  published_at: string | null
}

export interface AgentAssignmentWrite {
  title: string
  instructions: string
  scenario?: string
  rubric?: string[]
  task_id?: number | null
}

export interface AgentDraft {
  id: number
  owner_id: number
  class_id: number
  current_version_id: number | null
  created_at: string
  updated_at: string
  config: AgentConfig
}

export interface AgentVersion {
  id: number
  agent_id: number
  owner_id: number
  version_no: number
  config: AgentConfig
  created_at: string
}

export interface AgentSaveResult {
  agent: AgentDraft
  version: AgentVersion
}

export interface AgentSubmission {
  id: number
  assignment_id: number
  owner_id: number
  version_id: number
  run_ids: number[]
  improvement_notes: string
  status: 'submitted' | 'approved' | 'returned'
  grade: number | null
  comment: string | null
  reviewer_id: number | null
  content_snapshot: Record<string, unknown>
  submitted_at: string
  reviewed_at: string | null
}

export interface AgentPublication {
  id: number
  class_id: number
  submission_id: number
  version_id: number
  owner_id: number
  name: string
  config: AgentConfig
  published_at: string
}

export interface ClassroomData {
  classroom: { id: number; name: string; teacher_id: number }
  teams: { id: number; name: string; members?: { user_id: number; position: string }[] }[]
  students: User[]
}

export interface SessionOption { id: number; label: string }

export const agentStatusLabels: Record<string, string> = {
  draft: '草稿', published: '已发布', submitted: '待评审', approved: '已通过',
  returned: '已退回', succeeded: '成功', failed: '失败', running: '运行中',
}

export const statusTone = (status: string): 'success' | 'warning' | 'danger' | 'neutral' =>
  ({ succeeded: 'success', approved: 'success', published: 'success', submitted: 'warning', returned: 'danger', failed: 'danger' } as Record<string, 'success' | 'warning' | 'danger' | 'neutral'>)[status] ?? 'neutral'

export const sourceLabel = (run: AgentRun) => run.source === 'model' ? `真实模型${run.model ? `：${run.model}` : ''}` : '规则演示（非真实模型）'

export const TEMPLATE_CONFIG: AgentConfig = {
  name: '助农客服小助手',
  duties: '解答农产品咨询（品种、产地、口感、储存），说明价格与优惠，引导下单并登记售后诉求。',
  boundaries: '只讨论本场商品；不做医疗或功效承诺；不承诺无条件退款，退款按平台售后政策登记后人工处理；无法确认的信息如实说明并转人工。',
  instructions: '语气亲切、口语化；先确认问题再回答；引用知识卡信息时说明依据；遇到投诉先安抚再给处理路径。',
  knowledge_cards: [
    { title: '商品知识卡（示例，请替换为你的场次商品）', content: '赣南脐橙 5 斤装：产地直采、当季鲜果，参考价 29.9 元；高山红茶 100g：山地茶园、独立小袋，参考价 59 元；山野农产礼盒：组合农产、礼赠包装，参考价 129 元。' },
    { title: '售后政策卡（示例）', content: '未发货订单可申请整单退款；已发货问题件先登记再由人工核实处理；处理时效以平台公示为准。' },
  ],
}

export const QUICK_QUESTIONS = [
  { key: 'consult', label: '高频咨询', text: '想问下这个脐橙是当季的吗？5 斤装大概几个，甜不甜？现在下单什么时候发货？' },
  { key: 'dispute', label: '售后争议', text: '我收到的大米有漏袋，你们必须马上全额退款，不然我就去投诉你们直播间！' },
]

export const cloneConfig = (config: AgentConfig): AgentConfig => ({
  name: config.name ?? '',
  duties: config.duties ?? '',
  boundaries: config.boundaries ?? '',
  instructions: config.instructions ?? '',
  knowledge_cards: (config.knowledge_cards ?? []).map(card => ({ title: card.title ?? '', content: card.content ?? '' })),
})

export const configKey = (config: AgentConfig) => JSON.stringify({
  name: config.name, duties: config.duties, boundaries: config.boundaries,
  instructions: config.instructions,
  knowledge_cards: (config.knowledge_cards ?? []).map(card => [card.title, card.content]),
})

export const configMatches = (a: AgentConfig, b: AgentConfig) => configKey(a) === configKey(b)

export function notReadyText(error: unknown) {
  if (error instanceof ApiError && (error.status === 503 || error.status === 502)) return `接口尚未就绪：${error.message}`
  return errorMessage(error)
}

export function useAgentFeedback() {
  const busy = ref(false), error = ref(''), notice = ref('')
  async function run<T>(action: () => Promise<T>, success = ''): Promise<T | undefined> {
    if (busy.value) return
    busy.value = true; error.value = ''; notice.value = ''
    try { const result = await action(); notice.value = success; return result }
    catch (e) { error.value = errorMessage(e); return undefined }
    finally { busy.value = false }
  }
  return { busy, error, notice, run }
}

export async function loadSessionOptions(userId: number): Promise<SessionOption[]> {
  const [classroomResult, tasksResult] = await Promise.all([
    api<ClassroomData>('/classroom'),
    api<Task[]>('/tasks'),
  ])
  const myTeamIds = new Set(classroomResult.teams
    .filter(team => (team.members ?? []).some(member => member.user_id === userId))
    .map(team => team.id))
  const details = await Promise.all(tasksResult
    .filter(task => task.status !== 'draft')
    .map(task => api<{ task: Task; sessions: TrainingSession[] }>(`/tasks/${task.id}`)))
  const options: SessionOption[] = []
  for (const detail of details) {
    for (const session of detail.sessions) {
      if (myTeamIds.has(session.team_id)) {
        options.push({ id: session.id, label: `${detail.task.title} · 场次 #${session.id}（${agentStatusLabels[session.status] ?? session.status}）` })
      }
    }
  }
  return options
}

export const listAssignments = () => api<AgentAssignment[]>('/agent-assignments')
export const createAssignment = (payload: AgentAssignmentWrite) => mutation<AgentAssignment>('/agent-assignments', payload)
export const updateAssignment = (id: number, payload: AgentAssignmentWrite) => mutation<AgentAssignment>(`/agent-assignments/${id}`, payload, 'PUT')
export const publishAssignment = (id: number) => mutation<AgentAssignment>(`/agent-assignments/${id}/publish`)

export const listAgents = () => api<AgentDraft[]>('/agents')
export const createAgent = (config: AgentConfig) => mutation<AgentDraft>('/agents', config)
export const saveAgent = (id: number, config: AgentConfig) => mutation<AgentSaveResult>(`/agents/${id}`, config, 'PUT')
export const listVersions = (id: number) => api<AgentVersion[]>(`/agents/${id}/versions`)

export const createRun = (payload: { agent_id?: number | null; config: AgentConfig; question: string; session_id?: number | null }) =>
  mutation<AgentRun>('/agent-runs', payload)
export const listRuns = (params?: { agent_id?: number; submission_id?: number; limit?: number }) => {
  const query = Object.entries(params ?? {}).filter(([, value]) => value != null).map(([key, value]) => `${key}=${value}`).join('&')
  return api<AgentRun[]>(`/agent-runs${query ? `?${query}` : ''}`)
}

export const submitWork = (payload: { assignment_id: number; version_id: number; run_ids: number[]; improvement_notes: string }) =>
  mutation<AgentSubmission>('/agent-submissions', payload)
export const listSubmissions = (assignmentId?: number) =>
  api<AgentSubmission[]>(`/agent-submissions${assignmentId ? `?assignment_id=${assignmentId}` : ''}`)
export const reviewSubmission = (id: number, payload: { decision: 'approve' | 'return'; grade?: number | null; comment: string }) =>
  mutation<AgentSubmission>(`/agent-submissions/${id}/review`, payload)
export const publishSubmission = (id: number) => mutation<AgentPublication>(`/agent-submissions/${id}/publish`)

export const listPublications = () => api<AgentPublication[]>('/agent-publications')
export const previewPublication = (id: number, payload: { question: string; session_id?: number | null }) =>
  mutation<AgentRun>(`/agent-publications/${id}/preview`, payload)

export const fetchHealth = () => api<Health>('/health')

export type { AgentConfig, AgentRun, KnowledgeCard, Task, TrainingSession, User }
