<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import {
  api, eventLabels, eventText, notReadyText, positions, scoreLabels, statusLabels, useFeedback,
  type ClassroomData, type TaskDetail,
} from './teacherWorkspace'
import type { Grade, Order, ReviewDetail, SessionDetail, TrainingEvent } from '../../shared/contracts'
import { money, dateTime } from '../../shared/format'
import AlertMessage from '../../shared/components/AlertMessage.vue'
import BaseButton from '../../shared/components/BaseButton.vue'
import DataTable from '../../shared/components/DataTable.vue'
import EmptyState from '../../shared/components/EmptyState.vue'
import FormField from '../../shared/components/FormField.vue'
import StatusBadge from '../../shared/components/StatusBadge.vue'

const route = useRoute()
const sessionId = computed(() => Number(route.params.id))

const loading = ref(true)
const loadError = ref('')
const loadNotReady = ref(false)
const detail = ref<SessionDetail | null>(null)
const taskDetail = ref<TaskDetail | null>(null)
const classroom = ref<ClassroomData | null>(null)

const events = ref<TrainingEvent[]>([])
const eventsError = ref('')
const orders = ref<Order[]>([])
const ordersError = ref('')
const reviewDetail = ref<ReviewDetail | null>(null)
const reviewError = ref('')

const tabs = [
  { key: 'events', label: '01 过程证据' },
  { key: 'orders', label: '02 订单记录' },
  { key: 'review', label: '03 复盘与成绩' },
] as const
const activeTab = ref<string>('events')

const task = computed(() => taskDetail.value?.task ?? null)
const team = computed(() => classroom.value?.teams.find(item => item.id === detail.value?.session.team_id) ?? null)
const memberName = (id: number | null) => id == null ? '系统' : classroom.value?.students.find(student => student.id === id)?.username ?? `学员#${id}`
const memberLine = computed(() => (team.value?.members ?? [])
  .map(member => `${memberName(member.user_id)}（${positions[member.position] ?? member.position}）`).join('、') || '—')
const sessionTone = (status: string) => status === 'live' ? 'success' : ['paused', 'preparing'].includes(status) ? 'warning' : ['submitted', 'graded'].includes(status) ? 'success' : 'neutral'

const eventColumns = [
  { key: 'time', label: '时间' },
  { key: 'type', label: '类型' },
  { key: 'text', label: '内容' },
  { key: 'actor', label: '操作人' },
  { key: 'source', label: '来源' },
]
const eventRows = computed(() => events.value.map(event => ({
  id: event.id,
  time: dateTime(event.created_at),
  type: eventLabels[event.type] ?? event.type,
  rawType: event.type,
  text: eventText(event),
  actor: memberName(event.actor_id ?? null),
  source: event.source === 'manual' ? '人工操作' : '规则仿真',
})))
const speechCount = computed(() => events.value.filter(event => event.type === 'speech').length)
const replyCount = computed(() => events.value.filter(event => event.type === 'reply').length)
const scriptCount = computed(() => events.value.filter(event => event.type === 'execute_script').length)
const questionCount = computed(() => events.value.filter(event => event.type === 'audience_question').length)
const violationCount = computed(() => events.value.filter(event => ['violation', 'compliance'].includes(event.type)).length)

const orderColumns = [
  { key: 'id', label: '订单号' },
  { key: 'product', label: '商品' },
  { key: 'qty', label: '数量' },
  { key: 'amount', label: '成交金额' },
  { key: 'status', label: '状态' },
  { key: 'time', label: '时间' },
]
const orderRows = computed(() => orders.value.map(order => ({
  id: order.id,
  product: detail.value?.products.find(product => product.id === order.session_product_id)?.title ?? `场次商品 #${order.session_product_id}`,
  qty: String(order.qty),
  amount: money(order.amount_cents),
  status: order.status,
  time: dateTime(order.created_at),
})))
const orderTone = (status: string) => status === 'signed' ? 'success' : status === 'refunded' ? 'neutral' : status === 'shipped' ? 'warning' : 'danger'

const weightRows = computed(() => {
  const breakdown = reviewDetail.value?.breakdown
  const weights = task.value?.score_weights
  return (Object.keys(scoreLabels) as (keyof typeof scoreLabels)[]).map(key => ({
    key, label: scoreLabels[key], weight: weights?.[key] ?? '—', score: breakdown ? String(breakdown[key]) : '—',
  }))
})
const grade = computed<Grade | null>(() => reviewDetail.value?.grade ?? null)
const canGrade = computed(() => detail.value?.session.status === 'submitted' && !grade.value)

const gradeFeedback = useFeedback()
const gradeForm = ref({ subjective_score: 80, comment: '' })
async function submitGrade() {
  const form = gradeForm.value
  if (form.subjective_score < 0 || form.subjective_score > 100) {
    gradeFeedback.error.value = '主观分需在 0～100 之间。'
    return
  }
  await gradeFeedback.run(async () => {
    await gradeFeedback.write(`/sessions/${sessionId.value}/grade`, {
      subjective_score: Number(form.subjective_score), comment: form.comment,
    })
    await load()
    await loadReview()
  }, '评分已保存。')
}

async function loadEvents() {
  eventsError.value = ''
  try { events.value = await api<TrainingEvent[]>(`/sessions/${sessionId.value}/events?after_id=0&limit=200`) }
  catch (error) { eventsError.value = notReadyText(error); events.value = [] }
}
async function loadOrders() {
  ordersError.value = ''
  try { orders.value = await api<Order[]>(`/sessions/${sessionId.value}/orders`) }
  catch (error) { ordersError.value = notReadyText(error); orders.value = [] }
}
async function loadReview() {
  reviewError.value = ''
  try { reviewDetail.value = await api<ReviewDetail>(`/sessions/${sessionId.value}/review`) }
  catch (error) { reviewError.value = notReadyText(error); reviewDetail.value = null }
}

async function load() {
  if (!Number.isInteger(sessionId.value) || sessionId.value <= 0) { loadError.value = '场次地址不正确'; loading.value = false; return }
  loading.value = true; loadError.value = ''; loadNotReady.value = false
  try {
    const sessionDetail = await api<SessionDetail>(`/sessions/${sessionId.value}`)
    detail.value = sessionDetail
    const [taskResult, classroomResult] = await Promise.allSettled([
      api<TaskDetail>(`/tasks/${sessionDetail.session.task_id}`), api<ClassroomData>('/classroom'),
    ])
    taskDetail.value = taskResult.status === 'fulfilled' ? taskResult.value : null
    classroom.value = classroomResult.status === 'fulfilled' ? classroomResult.value : null
    await loadEvents()
  } catch (error) {
    loadError.value = notReadyText(error)
    loadNotReady.value = true
    detail.value = null
  } finally { loading.value = false }
}
onMounted(load)
watch(sessionId, load)
watch(activeTab, tab => {
  if (tab === 'orders') void loadOrders()
  if (tab === 'review') { void loadReview(); void loadOrders() }
})
</script>

<template>
  <div class="page-heading">
    <div>
      <p class="eyebrow">TEACHER CENTER</p>
      <h1>场次证据与评分</h1>
      <p v-if="detail">
        {{ task?.title ?? `任务#${detail.session.task_id}` }} · {{ team?.name ?? `小组#${detail.session.team_id}` }} · 场次 #{{ detail.session.id }}
      </p>
    </div>
    <div class="heading-actions">
      <RouterLink v-if="task" :to="`/teacher/tasks/${task.id}`"><BaseButton variant="secondary">返回任务详情</BaseButton></RouterLink>
      <BaseButton variant="secondary" @click="load">刷新</BaseButton>
    </div>
  </div>

  <div v-if="loading" class="panel"><p class="text-muted">正在加载场次数据…</p></div>
  <AlertMessage v-else-if="loadError" tone="error">
    {{ loadError }}
    <template v-if="loadNotReady">后端接口正在接入中，稍后可点击重试。</template>
    <div style="margin-top:10px"><BaseButton variant="secondary" @click="load">重新加载</BaseButton></div>
  </AlertMessage>
  <template v-else-if="detail">
    <section class="panel" aria-label="场次信息">
      <div class="section-heading" style="margin:0 0 12px">
        <h2>场次信息</h2>
        <StatusBadge :tone="sessionTone(detail.session.status)">{{ statusLabels[detail.session.status] ?? detail.session.status }}</StatusBadge>
      </div>
      <div class="info-grid">
        <div><span>成员</span><strong style="font-size:12px">{{ memberLine }}</strong></div>
        <div><span>开始／结束时间</span><strong style="font-size:12px">{{ dateTime(detail.session.started_at) }} / {{ dateTime(detail.session.ended_at) }}</strong></div>
        <div><span>有效直播时长</span><strong>{{ Math.round((detail.session.live_elapsed_seconds ?? 0) / 60) }} 分钟</strong></div>
        <div><span>规则版本</span><strong style="font-size:12px">{{ task?.rules_version ?? '—' }}</strong></div>
      </div>
      <p class="small text-muted" style="margin-bottom:0">教师对场次只读：不提供代写口播、代操作经营或修改证据的入口。</p>
    </section>

    <div class="tab-row" role="tablist">
      <button v-for="tab in tabs" :key="tab.key" :class="['tab', { active: activeTab === tab.key }]" type="button" @click="activeTab = tab.key">{{ tab.label }}</button>
    </div>

    <section v-if="activeTab === 'events'" aria-label="过程证据" class="panel">
      <div class="section-heading" style="margin:0 0 12px">
        <h2>过程证据</h2>
        <div class="heading-actions">
          <span class="small text-muted">口播 {{ speechCount }} · 回复 {{ replyCount }} · 脚本 {{ scriptCount }} · 咨询 {{ questionCount }} · 合规提示 {{ violationCount }}</span>
          <BaseButton variant="secondary" @click="loadEvents">重新读取</BaseButton>
        </div>
      </div>
      <AlertMessage v-if="eventsError" tone="error">{{ eventsError }}</AlertMessage>
      <DataTable v-else :columns="eventColumns" :rows="eventRows">
        <template #cell-type="{ row }">
          <StatusBadge :tone="row.rawType === 'violation' || row.rawType === 'compliance' ? 'danger' : 'neutral'">{{ row.type }}</StatusBadge>
        </template>
      </DataTable>
      <p class="small text-muted" style="margin-bottom:0">事件为追加式只读记录；“来源”区分学生人工操作与规则仿真；合规提示为教学规则标记。</p>
    </section>

    <section v-else-if="activeTab === 'orders'" aria-label="订单记录" class="panel">
      <div class="section-heading" style="margin:0 0 12px">
        <h2>订单记录</h2>
        <div class="heading-actions"><span class="small text-muted">{{ orders.length }} 笔订单</span>
          <BaseButton variant="secondary" @click="loadOrders">重新读取</BaseButton></div>
      </div>
      <AlertMessage v-if="ordersError" tone="error">{{ ordersError }}</AlertMessage>
      <DataTable v-else :columns="orderColumns" :rows="orderRows">
        <template #cell-status="{ row }">
          <StatusBadge :tone="orderTone(String(row.status))">{{ statusLabels[String(row.status)] ?? row.status }}</StatusBadge>
        </template>
      </DataTable>
      <p class="small text-muted" style="margin-bottom:0">订单含价格与优惠快照；履约与售后操作由本组学生在学生端完成，教师在此只读。</p>
    </section>

    <section v-else aria-label="复盘与成绩" class="panel">
      <div class="section-heading" style="margin:0 0 12px">
        <h2>复盘与成绩</h2>
        <div class="heading-actions"><span v-if="reviewDetail" class="small text-muted">报告来源：规则引擎（source=rule）</span>
          <BaseButton variant="secondary" @click="loadReview">重新读取</BaseButton></div>
      </div>
      <AlertMessage v-if="reviewError" tone="error">{{ reviewError }}</AlertMessage>
      <EmptyState v-else-if="!reviewDetail" title="暂无复盘记录" description="该组结束直播并提交复盘后，这里会显示规则报告、维度分与成绩。" />
      <template v-else>
        <div class="review-grid">
          <div><span>复盘状态</span><strong>{{ statusLabels[reviewDetail.review?.status ?? 'draft'] ?? reviewDetail.review?.status }}</strong></div>
          <div><span>提交时间</span><strong style="font-size:12px">{{ dateTime(reviewDetail.review?.submitted_at) }}</strong></div>
          <div><span>GMV／净销售额</span><strong>{{ money(reviewDetail.metrics.gmv_cents ?? 0) }} / {{ money(reviewDetail.metrics.net_sales_cents ?? 0) }}</strong></div>
          <div><span>利润／资金余额</span><strong>{{ money(reviewDetail.metrics.profit_cents ?? 0) }} / {{ money(reviewDetail.metrics.cash_balance_cents ?? 0) }}</strong></div>
        </div>
        <div class="review-text">
          <h3>学生复盘分析</h3>
          <p>{{ reviewDetail.review?.analysis || '未填写' }}</p>
          <h3>改进措施</h3>
          <p>{{ reviewDetail.review?.improvements || '未填写' }}</p>
        </div>
        <div class="table-wrap">
          <table>
            <thead><tr><th>评分维度</th><th>任务权重</th><th>系统分</th></tr></thead>
            <tbody>
              <tr v-for="row in weightRows" :key="row.key"><td>{{ row.label }}</td><td>{{ row.weight }}</td><td>{{ row.score }}</td></tr>
              <tr><td><strong>系统分合计</strong></td><td>—</td><td><strong>{{ reviewDetail.breakdown?.objective_score ?? '—' }}</strong></td></tr>
            </tbody>
          </table>
        </div>

        <template v-if="grade">
          <div class="grade-box">
            <h3>已评分</h3>
            <p>系统分 {{ grade.objective_score }} × 0.7 + 主观分 {{ grade.subjective_score }} × 0.3 = <strong>综合分 {{ grade.total_score }}</strong></p>
            <p class="small text-muted">评语：{{ grade.comment || '—' }} · 规则版本 {{ grade.rules_version }} · 评分时间 {{ dateTime(grade.graded_at) }}</p>
          </div>
        </template>
        <div v-else-if="canGrade" class="grade-box">
          <h3>录入评分</h3>
          <p class="small text-muted" style="margin-bottom:14px">仅已提交复盘可评分；综合分 = 系统分 × 0.7 + 主观分 × 0.3，系统分与维度依据取自提交时快照。</p>
          <div class="grade-form-grid">
            <FormField label="主观分（0～100）" for-id="subjective-score">
              <input id="subjective-score" v-model.number="gradeForm.subjective_score" type="number" min="0" max="100" step="0.5" />
            </FormField>
            <FormField label="评语" for-id="grade-comment">
              <input id="grade-comment" v-model="gradeForm.comment" maxlength="500" placeholder="对复盘质量与团队表现的评价" />
            </FormField>
          </div>
          <AlertMessage v-if="gradeFeedback.error.value" tone="error">{{ gradeFeedback.error.value }}</AlertMessage>
          <AlertMessage v-else-if="gradeFeedback.notice.value" tone="success">{{ gradeFeedback.notice.value }}</AlertMessage>
          <div class="heading-actions"><BaseButton :loading="gradeFeedback.busy.value" @click="submitGrade">保存评分</BaseButton></div>
        </div>
        <AlertMessage v-else tone="info">该场次尚未提交复盘；学生完成履约并提交后才能评分。</AlertMessage>
      </template>
    </section>
  </template>
</template>

<style scoped>
.heading-actions{display:flex;gap:10px;align-items:center;flex-wrap:wrap}
.info-grid,.review-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:10px 18px;font-size:12px}
.info-grid span,.review-grid span{display:block;color:var(--muted);margin-bottom:4px}
.tab-row{display:flex;gap:8px;margin:4px 0 16px;flex-wrap:wrap}
.tab{border:1px solid var(--line);background:#fff;border-radius:20px;padding:8px 16px;font-size:13px;color:#5d6a63}
.tab.active{background:#e9f3ed;color:#17654d;font-weight:600;border-color:#bcd9c8}
.review-text h3{font-size:14px;margin:14px 0 6px}
.review-text p{font-size:13px;white-space:pre-wrap;background:#f7faf8;border-radius:8px;padding:10px 12px;margin:0 0 8px}
.grade-box{border-top:1px solid var(--line);margin-top:16px;padding-top:14px}
.grade-box h3{font-size:14px;margin:0 0 8px}
.grade-form-grid{display:grid;grid-template-columns:220px 1fr;gap:0 16px;max-width:760px}
.table-wrap{overflow:auto;border:1px solid var(--line);border-radius:10px;margin-top:14px}
.table-wrap table{width:100%;border-collapse:collapse;font-size:13px}
.table-wrap th,.table-wrap td{padding:10px 12px;text-align:left;border-bottom:1px solid var(--line)}
.table-wrap th{background:#f7faf8;font-size:12px;color:var(--muted)}
.table-wrap tr:last-child td{border-bottom:0}
</style>
