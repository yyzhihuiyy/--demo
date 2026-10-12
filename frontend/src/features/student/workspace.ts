import { computed, onUnmounted, ref } from 'vue'
import { api, errorMessage, mutation, requestKey, ApiError } from '../../shared/api'
import type { Preparation, Team, User, Task, TrainingSession, TrainingEvent, SessionDetail } from '../../shared/contracts'

export interface ClassroomData { classroom: { id: number; name: string; teacher_id: number }; teams: Team[]; students: User[] }
export interface TaskDetail { task: Task; sessions: TrainingSession[] }
export const statusLabels: Record<string, string> = { preparing: '准备中', live: '直播中', paused: '已暂停', ended: '已下播', submitted: '待教师评分', graded: '已评分', draft: '草稿', published: '已发布', closed: '已结束', pending_shipment: '待发货', shipped: '待签收', signed: '已签收', refunded: '已退款', pending: '待处理', approved: '已同意', rejected: '已驳回' }
export const positions: Record<string, string> = { host: '主播', control: '场控', service: '客服', operations: '运营' }
export const productRoles = { traffic: '引流款', profit: '利润款', image: '形象款' }
export const scriptKinds = { opening: '开场', product: '商品讲解', interaction: '互动', closing: '收尾' }
export const scoreLabels = { process: '过程表现', business: '经营结果', service: '客户服务', compliance: '合规表现', review: '复盘完成度' }
export const sessionPath = (session: TrainingSession) => `/sessions/${session.id}/${session.status === 'preparing' ? 'prepare' : ['live', 'paused'].includes(session.status) ? 'live' : 'review'}`
export function allowed(detail: SessionDetail | null, key: string, statuses: string[]) { return !!detail && statuses.includes(detail.session.status) && detail.capabilities[key] !== false }
export function completePreparation(value: Preparation = {}) {
  return {
    research: { audience: '', competitor_notes: '', price_notes: '', selection_reason: '', ...value.research },
    plan: { theme: '', target_audience: '', ...value.plan },
    script: (value.script?.length ? value.script : Object.keys(scriptKinds).map(kind => ({ id: kind, kind, product_id: null, text: '' }))).map(segment => ({ ...segment, text: segment.text ?? '', product_id: segment.product_id ?? null })) as Required<NonNullable<Preparation['script']>[number]>[],
    promotion: { channel: 'simulated_feed' as const, budget_cents: 0, audience: '', ...value.promotion },
    room: { theme: 'agriculture', title: '', announcement: '', ...value.room },
    coupon: { discount_cents: 0, ...value.coupon },
  }
}
export const eventLabels: Record<string, string> = { speech: '主播口播', reply: '客服回复', execute_script: '执行脚本', select_product: '切换商品', issue_coupon: '发放优惠券', announcement: '更新公告', audience_question: '观众咨询', question: '观众咨询', violation: '合规提示', compliance: '合规提示', control: '直播控制', simulation_tick: '仿真推进', tick: '仿真推进', order: '仿真成交', order_created: '仿真成交', system_recovery: '系统恢复' }
export function eventText(event: TrainingEvent) {
  const p = event.payload
  for (const key of ['text', 'question', 'message', 'content']) if (typeof p[key] === 'string') return p[key] as string
  if (event.type === 'select_product') return `切换至场次商品 #${p.session_product_id ?? '—'}`
  if (event.type === 'execute_script') return `已执行脚本 ${p.script_id ?? ''}`
  if (p.action) return ({ start: '开始直播', pause: '暂停直播', resume: '恢复直播', end: '结束直播' } as Record<string, string>)[String(p.action)] ?? String(p.action)
  return JSON.stringify(p)
}

export const yuanToCents = (value: string | number) => {
  const cents = Math.round(Number(value) * 100)
  return Number.isFinite(cents) ? cents : NaN
}
export const centsToYuanText = (cents: number | null | undefined) => cents == null ? '' : String(cents / 100)
export const positiveCents = (value: string | number) => { const cents = yuanToCents(value); return Number.isInteger(cents) && cents > 0 ? cents : null }

export function notReadyText(error: unknown) {
  if (error instanceof ApiError && (error.status === 503 || error.status === 502)) return `接口尚未就绪：${error.message}`
  return errorMessage(error)
}

export function useFeedback() {
  const busy = ref(false), error = ref(''), notice = ref(''), conflict = ref(false)
  const keys = new Map<string, string>()
  async function run<T>(action: () => Promise<T>, success = ''): Promise<T | undefined> {
    if (busy.value) return
    busy.value = true; error.value = ''; notice.value = ''; conflict.value = false
    try { const result = await action(); notice.value = success; return result }
    catch (e) { error.value = errorMessage(e); conflict.value = e instanceof ApiError && e.status === 409; return undefined }
    finally { busy.value = false }
  }
  async function write<T>(path: string, body?: unknown, method = 'POST') {
    const fingerprint = `${method}:${path}:${JSON.stringify(body)}`
    if (!keys.has(fingerprint)) keys.set(fingerprint, requestKey())
    const value = await mutation<T>(path, body, method, keys.get(fingerprint))
    keys.delete(fingerprint)
    return value
  }
  return { busy, error, notice, conflict, run, write }
}

export function usePolling(refresh: () => Promise<void>, delay = 2000) {
  let timer: ReturnType<typeof setTimeout> | undefined, stopped = false
  async function tick() {
    try { await refresh() } finally { if (!stopped) timer = setTimeout(tick, delay) }
  }
  function start() { stopped = false; void tick() }
  function stop() { stopped = true; if (timer) clearTimeout(timer) }
  onUnmounted(stop)
  return { start, stop }
}

export interface MarketSample { source: string; notice?: string; categories: { name: string; heat: number; price_band: string }[]; audience: { name: string; share: number }[] }

export function useSession(idGetter: () => number) {
  const detail = ref<SessionDetail | null>(null)
  const classroom = ref<ClassroomData | null>(null)
  const task = ref<Task | null>(null)
  const loading = ref(true), loadError = ref(''), notReady = ref(false)
  async function load() {
    const id = idGetter()
    if (!Number.isInteger(id)) { loadError.value = '场次地址不正确'; loading.value = false; return }
    loading.value = true; loadError.value = ''
    try {
      detail.value = await api<SessionDetail>(`/sessions/${id}`)
      notReady.value = false
      const [taskResult, classroomResult] = await Promise.allSettled([
        api<TaskDetail>(`/tasks/${detail.value.session.task_id}`),
        api<ClassroomData>('/classroom'),
      ])
      task.value = taskResult.status === 'fulfilled' ? taskResult.value.task : null
      classroom.value = classroomResult.status === 'fulfilled' ? classroomResult.value : null
    } catch (error) {
      loadError.value = notReadyText(error)
      notReady.value = error instanceof ApiError && (error.status === 503 || error.status === 502)
      detail.value = null
    } finally { loading.value = false }
  }
  const team = computed(() => {
    const teamId = detail.value?.session.team_id
    return classroom.value?.teams.find(item => item.id === teamId) ?? null
  })
  const members = computed(() => team.value?.members ?? [])
  return { detail, classroom, task, team, members, loading, loadError, notReady, load }
}
export { api }
