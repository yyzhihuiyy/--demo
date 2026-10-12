import { ref } from 'vue'
import { api, mutation, requestKey, ApiError, errorMessage } from '../../shared/api'
import type { Task, Team, TrainingEvent, TrainingSession, User } from '../../shared/contracts'

export interface ClassroomData { classroom: { id: number; name: string; teacher_id: number }; teams: Team[]; students: User[] }
export interface TaskDetail { task: Task; sessions: TrainingSession[] }

export const statusLabels: Record<string, string> = {
  preparing: '准备中', live: '直播中', paused: '已暂停', ended: '已下播',
  submitted: '待教师评分', graded: '已评分', draft: '草稿', published: '已发布',
  closed: '已结束', pending_shipment: '待发货', shipped: '待签收', signed: '已签收',
  refunded: '已退款', pending: '待处理', approved: '已同意', rejected: '已驳回',
  finished: '已完赛', provisional: '临时榜', final: '最终榜', overtime: '超时未提交',
}
export const positions: Record<string, string> = { host: '主播', control: '场控', service: '客服', operations: '运营' }
export const productRoles: Record<string, string> = { traffic: '引流款', profit: '利润款', image: '形象款' }
export const scoreLabels = { process: '过程表现', business: '经营结果', service: '客户服务', compliance: '合规表现', review: '复盘完成度' }
export const sortRuleText = '同分依次按净销售额、较少违规、组 ID 稳定排序（CONTRACTS.md 6.2）'

export const eventLabels: Record<string, string> = {
  speech: '主播口播', reply: '客服回复', execute_script: '执行脚本', select_product: '切换商品',
  issue_coupon: '发放优惠券', announcement: '更新公告', audience_question: '观众咨询',
  violation: '合规提示', compliance: '合规提示', control: '直播控制', order: '仿真成交',
  order_created: '仿真成交', simulation_tick: '仿真推进', tick: '仿真推进', system_recovery: '系统恢复',
}

export function eventText(event: TrainingEvent) {
  const payload = event.payload
  for (const key of ['text', 'question', 'message', 'content']) if (typeof payload[key] === 'string') return payload[key] as string
  if (event.type === 'select_product') return `切换至场次商品 #${payload.session_product_id ?? '—'}`
  if (event.type === 'execute_script') return `已执行脚本 ${payload.script_id ?? ''}`
  if (typeof payload.action === 'string') return ({ start: '开始直播', pause: '暂停直播', resume: '恢复直播', end: '结束直播' } as Record<string, string>)[payload.action] ?? payload.action
  return JSON.stringify(payload)
}

export const yuanToCents = (value: string | number) => {
  const cents = Math.round(Number(value) * 100)
  return Number.isFinite(cents) ? cents : NaN
}
export const centsToYuanText = (cents: number | null | undefined) => cents == null ? '' : String(cents / 100)
export const percent = (value: number | null | undefined) => value == null ? '暂无样本' : `${(value * 100).toFixed(1)}%`

export function notReadyText(error: unknown) {
  if (error instanceof ApiError && (error.status === 503 || error.status === 502)) return `接口尚未就绪：${error.message}`
  return errorMessage(error)
}

export function useFeedback() {
  const busy = ref(false), error = ref(''), notice = ref('')
  async function run<T>(action: () => Promise<T>, success = ''): Promise<T | undefined> {
    if (busy.value) return
    busy.value = true; error.value = ''; notice.value = ''
    try { const result = await action(); notice.value = success; return result }
    catch (e) { error.value = errorMessage(e); return undefined }
    finally { busy.value = false }
  }
  async function write<T>(path: string, body?: unknown, method = 'POST') {
    return mutation<T>(path, body, method, requestKey())
  }
  return { busy, error, notice, run, write }
}

export function useAsync<T>() {
  const data = ref<T | null>(null), loading = ref(false), error = ref(''), notReady = ref(false)
  async function load(action: () => Promise<T>) {
    loading.value = true; error.value = ''
    try { data.value = await action(); notReady.value = false }
    catch (e) { error.value = notReadyText(e); notReady.value = e instanceof ApiError && (e.status === 503 || e.status === 502); data.value = null }
    finally { loading.value = false }
  }
  return { data, loading, error, notReady, load }
}

export function localDateTimeInput(date: Date) {
  const pad = (value: number) => String(value).padStart(2, '0')
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`
}
export function toIsoFromLocalInput(value: string) { return new Date(value).toISOString() }

export { api }
