<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import {
  api, eventLabels, notReadyText, positions, scoreLabels, statusLabels, useFeedback, useSession,
} from '../../features/student/workspace'
import type { Grade, Order, Refund, ReviewDetail } from '../../shared/contracts'
import AlertMessage from '../../shared/components/AlertMessage.vue'
import BaseButton from '../../shared/components/BaseButton.vue'
import EmptyState from '../../shared/components/EmptyState.vue'
import FormField from '../../shared/components/FormField.vue'
import StatusBadge from '../../shared/components/StatusBadge.vue'
import SessionNav from '../../features/student/SessionNav.vue'
import MetricsGrid from '../../features/student/MetricsGrid.vue'
import { useAuth } from '../../shared/auth'
import { dateTime, money } from '../../shared/format'

const route = useRoute()
const sessionId = computed(() => Number(route.params.id))
const { user } = useAuth()
const { detail, classroom, task, team, members, loading, loadError, notReady, load } = useSession(() => sessionId.value)

const tabs = [
  { key: 'orders', label: '01 订单履约' },
  { key: 'refunds', label: '02 售后工单' },
  { key: 'review', label: '03 复盘与成绩' },
] as const
const activeTab = ref<string>('orders')

const orders = ref<Order[]>([])
const ordersError = ref('')
const ordersLoading = ref(false)
const refunds = ref<Refund[]>([])
const refundsError = ref('')
const refundsLoading = ref(false)
const reviewDetail = ref<ReviewDetail | null>(null)
const reviewError = ref('')
const reviewLoading = ref(false)
const events = ref<import('../../shared/contracts').TrainingEvent[]>([])
const refundReasons = ref<Record<number, string>>({})
const resolveNotes = ref<Record<number, string>>({})
const analysis = ref('')
const improvements = ref('')
const evidenceOpen = ref(false)

const orderFeedback = useFeedback()
const refundFeedback = useFeedback()
const reviewFeedback = useFeedback()

const sessionStatus = computed(() => detail.value?.session.status ?? 'preparing')
const canFulfill = computed(() => sessionStatus.value === 'ended')
const reviewStatus = computed(() => reviewDetail.value?.review?.status ?? 'draft')
const editableReview = computed(() => canFulfill.value && reviewStatus.value === 'draft')
const productTitle = (sessionProductId: number) => detail.value?.products.find(product => product.id === sessionProductId)?.title ?? `场次商品 #${sessionProductId}`
const memberName = (userId: number) => classroom.value?.students.find(student => student.id === userId)?.username ?? `学员#${userId}`
const orderTone = (status: string) => status === 'signed' ? 'success' : status === 'refunded' ? 'neutral' : status === 'shipped' ? 'warning' : 'danger'
const refundTone = (status: string) => status === 'approved' ? 'success' : status === 'rejected' ? 'neutral' : 'warning'

const unfulfilledOrders = computed(() => orders.value.filter(order => !['signed', 'refunded'].includes(order.status)))
const pendingRefunds = computed(() => refunds.value.filter(refund => refund.status === 'pending'))
const fulfillmentDone = computed(() => !ordersError.value && !refundsError.value && unfulfilledOrders.value.length === 0 && pendingRefunds.value.length === 0)
const breakdownRows = computed(() => {
  const breakdown = reviewDetail.value?.breakdown
  if (!breakdown) return []
  const weights = task.value?.score_weights
  return (Object.keys(scoreLabels) as (keyof typeof scoreLabels)[]).map(key => ({
    key, label: scoreLabels[key], weight: weights?.[key] ?? '—', score: breakdown[key] ?? 0,
  }))
})
const grade = computed<Grade | null>(() => reviewDetail.value?.grade ?? null)
const violations = computed(() => events.value.filter(event => ['violation', 'compliance'].includes(event.type)))

async function loadOrders() {
  ordersLoading.value = true; ordersError.value = ''
  try { orders.value = await api<Order[]>(`/sessions/${sessionId.value}/orders`) }
  catch (error) { ordersError.value = notReadyText(error); orders.value = [] }
  finally { ordersLoading.value = false }
}
async function loadRefunds() {
  refundsLoading.value = true; refundsError.value = ''
  try { refunds.value = await api<Refund[]>(`/sessions/${sessionId.value}/refunds`) }
  catch (error) { refundsError.value = notReadyText(error); refunds.value = [] }
  finally { refundsLoading.value = false }
}
async function loadReview() {
  reviewLoading.value = true; reviewError.value = ''
  try {
    reviewDetail.value = await api<ReviewDetail>(`/sessions/${sessionId.value}/review`)
    analysis.value = reviewDetail.value.review?.analysis ?? ''
    improvements.value = reviewDetail.value.review?.improvements ?? ''
  } catch (error) { reviewError.value = notReadyText(error); reviewDetail.value = null }
  finally { reviewLoading.value = false }
}
async function loadEvents() {
  try { events.value = await api<import('../../shared/contracts').TrainingEvent[]>(`/sessions/${sessionId.value}/events?after_id=0&limit=200`) }
  catch { events.value = [] }
}

async function refreshFulfillment() {
  await Promise.all([load(), loadOrders(), loadRefunds()])
}

onMounted(async () => {
  await load()
  await Promise.all([loadOrders(), loadEvents()])
})
watch(sessionId, async () => { activeTab.value = 'orders'; await load(); await Promise.all([loadOrders(), loadEvents()]) })
watch(activeTab, tab => {
  if (tab === 'refunds') void loadRefunds()
  if (tab === 'review') { void loadReview(); void loadRefunds(); void loadOrders() }
})

async function ship(order: Order) {
  await orderFeedback.run(async () => {
    await orderFeedback.write(`/orders/${order.id}/ship`, undefined)
    await refreshFulfillment()
  }, `订单 #${order.id} 已发货。`)
}
async function sign(order: Order) {
  await orderFeedback.run(async () => {
    await orderFeedback.write(`/orders/${order.id}/sign`, undefined)
    await refreshFulfillment()
  }, `订单 #${order.id} 已签收。`)
}
async function createRefund(order: Order) {
  const reason = (refundReasons.value[order.id] ?? '').trim()
  if (!reason) { refundFeedback.error.value = '请填写退款原因，客服处理时会看到。'; return }
  await refundFeedback.run(async () => {
    await refundFeedback.write(`/orders/${order.id}/refunds`, { reason })
    delete refundReasons.value[order.id]
    await refreshFulfillment()
    activeTab.value = 'refunds'
  }, `订单 #${order.id} 的退款工单已创建，等待客服处理。`)
}
async function resolve(refund: Refund, decision: 'approve' | 'reject') {
  const note = (resolveNotes.value[refund.id] ?? '').trim()
  if (!note) { refundFeedback.error.value = '请填写处理说明（同意或驳回都会记录）。'; return }
  await refundFeedback.run(async () => {
    await refundFeedback.write(`/refunds/${refund.id}/resolve`, { decision, handling_note: note })
    delete resolveNotes.value[refund.id]
    await refreshFulfillment()
  }, decision === 'approve' ? `退款已同意：${money(refund.amount_cents)} 已原路退回并回补库存。` : '退款已驳回：订单继续履约，资金与库存不变。')
}

async function saveReview() {
  await reviewFeedback.run(async () => {
    await reviewFeedback.write(`/sessions/${sessionId.value}/review`, { analysis: analysis.value, improvements: improvements.value }, 'PUT')
    await loadReview()
  }, '复盘草稿已保存。')
}
async function submitReview() {
  await reviewFeedback.run(async () => {
    await reviewFeedback.write(`/sessions/${sessionId.value}/review`, { analysis: analysis.value, improvements: improvements.value }, 'PUT')
    await reviewFeedback.write(`/sessions/${sessionId.value}/review/submit`, undefined)
    await Promise.all([load(), loadReview(), loadEvents()])
  }, '复盘已提交锁定：等待教师评分。')
}
function gotoFulfillment() { activeTab.value = 'orders' }
</script>

<template>
  <SessionNav :id="sessionId" />
  <div class="page-heading">
    <div>
      <p class="eyebrow">FULFILLMENT & REVIEW</p>
      <h1>履约与复盘</h1>
      <p>下播后完成发货签收与售后处理，再提交复盘；教师评分后在这里查看成绩。</p>
    </div>
    <StatusBadge v-if="detail" :tone="sessionStatus === 'ended' ? 'warning' : ['submitted', 'graded'].includes(sessionStatus) ? 'success' : 'neutral'">
      场次状态：{{ statusLabels[sessionStatus] ?? sessionStatus }}
    </StatusBadge>
  </div>

  <div v-if="loading" class="panel"><p class="text-muted">正在加载场次…</p></div>
  <AlertMessage v-else-if="loadError" tone="error">
    {{ loadError }}
    <template v-if="notReady">后端履约接口正在接入中；接口就绪后可点击重试。</template>
    <div style="margin-top:10px"><BaseButton variant="secondary" @click="load">重新加载</BaseButton></div>
  </AlertMessage>
  <template v-else-if="detail">
    <AlertMessage v-if="!canFulfill && !['submitted', 'graded'].includes(sessionStatus)" tone="info">
      当前场次为「{{ statusLabels[sessionStatus] ?? sessionStatus }}」：履约、售后与复盘在下播后开放。直播结束后这里会解锁。
    </AlertMessage>
    <AlertMessage v-if="['submitted', 'graded'].includes(sessionStatus)" tone="success">
      复盘已提交{{ sessionStatus === 'graded' ? '并完成教师评分' : '' }}：本场次经营与复盘数据已锁定，仅供查看。
    </AlertMessage>

    <div class="student-tabs" role="tablist">
      <button v-for="tab in tabs" :key="tab.key" :class="{ active: activeTab === tab.key }" @click="activeTab = tab.key">{{ tab.label }}</button>
    </div>

    <section v-show="activeTab === 'orders'" class="student-stack" aria-label="订单履约">
      <div class="panel">
        <div class="student-section-title">
          <h2>仿真订单（{{ orders.length }}）</h2>
          <span class="small text-muted">状态流转：待发货 → 已发货 → 已签收；签收／退款为终态</span>
        </div>
        <AlertMessage v-if="orderFeedback.error.value" tone="error">{{ orderFeedback.error.value }}</AlertMessage>
        <AlertMessage v-if="orderFeedback.notice.value" tone="success">{{ orderFeedback.notice.value }}</AlertMessage>
        <AlertMessage v-if="ordersError" tone="error">{{ ordersError }}（订单接口尚未就绪时无法展示真实订单，不做假数据）</AlertMessage>
        <EmptyState v-else-if="!ordersLoading && !orders.length" title="暂无订单" description="本场次还没有仿真成交；完成直播后订单会出现在这里。" />
        <div v-else class="table-wrap">
          <table :aria-busy="ordersLoading">
            <thead><tr><th>订单</th><th>买家（仿真）</th><th>商品</th><th>数量</th><th>单价</th><th>优惠</th><th>实付</th><th>状态</th><th>成交时间</th><th>操作</th></tr></thead>
            <tbody>
              <tr v-if="ordersLoading"><td colspan="10">正在加载订单…</td></tr>
              <template v-else>
                <tr v-for="order in orders" :key="order.id">
                  <td>#{{ order.id }}</td>
                  <td>{{ order.buyer_label }}</td>
                  <td>{{ productTitle(order.session_product_id) }}</td>
                  <td>{{ order.qty }}</td>
                  <td>{{ money(order.unit_sale_cents) }}</td>
                  <td>{{ order.discount_cents ? `-${money(order.discount_cents)}` : '—' }}</td>
                  <td><strong>{{ money(order.amount_cents) }}</strong></td>
                  <td><StatusBadge :tone="orderTone(order.status)">{{ statusLabels[order.status] ?? order.status }}</StatusBadge></td>
                  <td class="small text-muted">{{ dateTime(order.created_at) }}</td>
                  <td>
                    <div class="student-actions">
                      <BaseButton v-if="order.status === 'pending_shipment'" variant="secondary" :disabled="!canFulfill" :loading="orderFeedback.busy.value" @click="ship(order)">发货</BaseButton>
                      <BaseButton v-if="order.status === 'shipped'" variant="secondary" :disabled="!canFulfill" :loading="orderFeedback.busy.value" @click="sign(order)">签收</BaseButton>
                      <span v-if="['signed', 'refunded'].includes(order.status)" class="small text-muted">终态</span>
                    </div>
                    <div v-if="order.status === 'pending_shipment'" class="student-refund-inline">
                      <input v-model="refundReasons[order.id]" placeholder="未发货整单退款原因" :disabled="!canFulfill" />
                      <BaseButton variant="danger" :disabled="!canFulfill" :loading="refundFeedback.busy.value" @click="createRefund(order)">申请退款</BaseButton>
                    </div>
                  </td>
                </tr>
              </template>
            </tbody>
          </table>
        </div>
        <p class="student-caption">订单由后端规则仿真生成（受库存与直播状态约束），浏览器不产生正式订单；重复发货／签收不会产生新副作用。</p>
        <AlertMessage v-if="refundFeedback.error.value" tone="error" style="margin-top:10px">{{ refundFeedback.error.value }}</AlertMessage>
        <AlertMessage v-if="refundFeedback.notice.value" tone="success" style="margin-top:10px">{{ refundFeedback.notice.value }}</AlertMessage>
      </div>
    </section>

    <section v-show="activeTab === 'refunds'" class="student-stack" aria-label="售后工单">
      <div class="panel">
        <div class="student-section-title">
          <h2>退款工单（{{ refunds.length }}）</h2>
          <span class="small text-muted">仅未发货整单退款；同意后退款与库存回补只发生一次</span>
        </div>
        <AlertMessage v-if="refundsError" tone="error">{{ refundsError }}（售后接口尚未就绪时无法展示真实工单）</AlertMessage>
        <EmptyState v-else-if="!refundsLoading && !refunds.length" title="暂无退款工单" description="在订单页对未发货订单申请退款后，工单会出现在这里。" />
        <div v-else class="table-wrap">
          <table :aria-busy="refundsLoading">
            <thead><tr><th>工单</th><th>订单</th><th>退款金额</th><th>原因</th><th>状态</th><th>处理说明</th><th>操作</th></tr></thead>
            <tbody>
              <tr v-if="refundsLoading"><td colspan="7">正在加载工单…</td></tr>
              <template v-else>
                <tr v-for="refund in refunds" :key="refund.id">
                  <td>#{{ refund.id }}</td>
                  <td>#{{ refund.order_id }}</td>
                  <td><strong>{{ money(refund.amount_cents) }}</strong></td>
                  <td class="small">{{ refund.reason }}</td>
                  <td><StatusBadge :tone="refundTone(refund.status)">{{ statusLabels[refund.status] ?? refund.status }}</StatusBadge></td>
                  <td class="small text-muted">{{ refund.handling_note || '—' }}</td>
                  <td>
                    <template v-if="refund.status === 'pending'">
                      <div class="student-refund-inline">
                        <input v-model="resolveNotes[refund.id]" placeholder="客服处理说明" :disabled="!canFulfill" />
                        <BaseButton variant="secondary" :disabled="!canFulfill" :loading="refundFeedback.busy.value" @click="resolve(refund, 'approve')">同意退款</BaseButton>
                        <BaseButton variant="danger" :disabled="!canFulfill" :loading="refundFeedback.busy.value" @click="resolve(refund, 'reject')">驳回</BaseButton>
                      </div>
                    </template>
                    <span v-else class="small text-muted">已处理</span>
                  </td>
                </tr>
              </template>
            </tbody>
          </table>
        </div>
        <AlertMessage v-if="refundFeedback.error.value" tone="error" style="margin-top:10px">{{ refundFeedback.error.value }}</AlertMessage>
        <AlertMessage v-if="refundFeedback.notice.value" tone="success" style="margin-top:10px">{{ refundFeedback.notice.value }}</AlertMessage>
      </div>
    </section>

    <section v-show="activeTab === 'review'" class="student-stack" aria-label="复盘与成绩">
      <MetricsGrid :metrics="reviewDetail?.metrics ?? detail.metrics" />

      <div class="panel">
        <div class="student-section-title">
          <h2>规则复盘报告</h2>
          <span class="small text-muted">来源：后端规则报告（source={{ reviewDetail?.review?.source ?? 'rule' }}）</span>
        </div>
        <AlertMessage v-if="reviewError" tone="error">{{ reviewError }}（复盘接口尚未就绪时无法展示报告，不做前端拼凑）</AlertMessage>
        <p v-else-if="reviewLoading" class="text-muted small">正在加载复盘报告…</p>
        <template v-else-if="reviewDetail">
          <div class="table-wrap">
            <table>
              <thead><tr><th>评分维度</th><th>权重</th><th>系统分（0～100）</th></tr></thead>
              <tbody>
                <tr v-for="row in breakdownRows" :key="row.key"><td>{{ row.label }}</td><td>{{ typeof row.weight === 'number' ? `${row.weight}%` : '—' }}</td><td>{{ row.score }}</td></tr>
                <tr><td><strong>系统分合计</strong></td><td>100%</td><td><strong>{{ reviewDetail.breakdown.objective_score }}</strong></td></tr>
              </tbody>
            </table>
          </div>
          <p class="student-caption" style="margin-top:12px">评分依据在提交时冻结；规则报告为教学规则计算，不代表真实经营预测。任务规则版本：{{ task?.rules_version ?? '—' }}</p>
        </template>
      </div>

      <div class="panel">
        <div class="student-section-title">
          <h2>复盘分析与改进</h2>
          <StatusBadge :tone="reviewStatus === 'draft' ? 'warning' : 'success'">{{ { draft: '草稿', submitted: '已提交', graded: '已评分' }[reviewStatus] ?? reviewStatus }}</StatusBadge>
        </div>
        <AlertMessage v-if="reviewFeedback.error.value" tone="error">
          {{ reviewFeedback.error.value }}
          <template v-if="!fulfillmentDone">（存在未完成履约：{{ unfulfilledOrders.length }} 笔未终态订单、{{ pendingRefunds.length }} 笔待处理售后）</template>
        </AlertMessage>
        <AlertMessage v-if="reviewFeedback.notice.value" tone="success">{{ reviewFeedback.notice.value }}</AlertMessage>
        <template v-if="editableReview">
          <div class="student-form-grid">
            <div class="student-wide">
              <FormField label="经营分析" for-id="review-analysis" hint="结合指标与过程证据，分析货盘、定价、投流与互动的表现">
                <textarea id="review-analysis" v-model="analysis" rows="5" placeholder="例：引流款带来的进房转化较好，但利润款讲解时间不足…" />
              </FormField>
            </div>
            <div class="student-wide">
              <FormField label="改进措施" for-id="review-improvements" hint="下一次直播准备如何调整（选品、价格、脚本、投流或分工）">
                <textarea id="review-improvements" v-model="improvements" rows="5" placeholder="例：增加利润款专属讲解段，提前准备常见咨询回复…" />
              </FormField>
            </div>
          </div>
          <div class="student-muted-box" style="margin-bottom:16px">
            提交条件：全部订单为已签收／已退款，且无待处理退款工单。
            <template v-if="fulfillmentDone">当前已满足，可以提交。</template>
            <template v-else>当前不满足 —— <button class="text-button" type="button" @click="gotoFulfillment">去完成履约与售后 →</button></template>
            零订单场次也可提交，但经营指标会如实显示为零。
          </div>
          <div class="student-footer">
            <span class="small text-muted">提交后复盘锁定为只读，教师评分前可随时回来查看</span>
            <div class="student-actions">
              <BaseButton variant="secondary" :loading="reviewFeedback.busy.value" @click="saveReview">保存草稿</BaseButton>
              <BaseButton :disabled="!fulfillmentDone" :loading="reviewFeedback.busy.value" @click="submitReview">提交复盘</BaseButton>
            </div>
          </div>
        </template>
        <template v-else-if="reviewDetail?.review">
          <div class="student-grid">
            <div class="student-muted-box"><strong>经营分析</strong><p style="white-space:pre-wrap">{{ reviewDetail.review.analysis || '（未填写）' }}</p></div>
            <div class="student-muted-box"><strong>改进措施</strong><p style="white-space:pre-wrap">{{ reviewDetail.review.improvements || '（未填写）' }}</p></div>
          </div>
          <p class="student-caption" style="margin-top:12px">提交时间：{{ dateTime(reviewDetail.review.submitted_at) }} · 提交后内容只读</p>
        </template>
        <p v-else class="text-muted small">尚无复盘草稿：下播后填写分析与改进措施。</p>
      </div>

      <div class="panel">
        <div class="student-section-title">
          <h2>成绩</h2>
          <span class="small text-muted">综合分 = 系统分 × 70% + 教师主观分 × 30%</span>
        </div>
        <template v-if="grade">
          <div class="student-stats">
            <div><span>系统分</span><strong>{{ grade.objective_score }}</strong></div>
            <div><span>教师主观分</span><strong>{{ grade.subjective_score }}</strong></div>
            <div><span>综合分</span><strong>{{ grade.total_score }}</strong></div>
            <div><span>评分时间</span><strong style="font-size:13px">{{ dateTime(grade.graded_at) }}</strong></div>
          </div>
          <div class="student-muted-box" style="margin-top:14px"><strong>教师评语</strong><p style="white-space:pre-wrap">{{ grade.comment || '（未填写评语）' }}</p></div>
          <p class="student-caption" style="margin-top:10px">评分依据规则版本：{{ grade.rules_version }}</p>
        </template>
        <template v-else>
          <p class="student-caption">
            {{ reviewStatus === 'submitted' ? '复盘已提交，等待教师评分：教师给出主观分与评语后，综合分会显示在这里。' : '提交复盘并等待教师评分后，这里显示系统分、主观分、综合分与评语。' }}
          </p>
        </template>
      </div>

      <div class="panel">
        <div class="student-section-title">
          <h2>经营过程证据</h2>
          <BaseButton variant="secondary" @click="evidenceOpen = !evidenceOpen">{{ evidenceOpen ? '收起证据' : `展开证据（${events.length} 条）` }}</BaseButton>
        </div>
        <p class="student-caption">口播、回复、脚本执行、控制操作与合规提示均由服务端按操作人记录，供教师评分与竞赛追溯使用。</p>
        <template v-if="evidenceOpen">
          <AlertMessage v-if="violations.length" tone="info">本场合规提示 {{ violations.length }} 条（教学规则示例词命中，会计入合规评分）：</AlertMessage>
          <div class="student-evidence" style="margin-top:12px">
            <div v-for="event in events" :key="event.id" class="student-event" :style="['violation','compliance'].includes(event.type) ? 'border-color:#e0b96f;background:#fdf8ee' : ''">
              <div class="student-event-header">
                <span>{{ eventLabels[event.type] ?? event.type }}</span>
                <small>{{ event.actor_id == null ? '系统' : memberName(event.actor_id) }} · {{ dateTime(event.created_at) }}</small>
              </div>
              <p>{{ JSON.stringify(event.payload) }}</p>
            </div>
            <p v-if="!events.length" class="text-muted small">暂无过程记录。</p>
          </div>
        </template>
      </div>
    </section>
  </template>
  <EmptyState v-else title="未找到场次" description="请从「我的实训」进入正确的场次入口。" />
</template>

<style scoped>
.student-refund-inline{display:flex;gap:8px;align-items:center;margin-top:8px;flex-wrap:wrap}
.student-refund-inline input{padding:8px 10px;border:1px solid var(--line);border-radius:7px;font:inherit;font-size:12px;min-width:170px}
</style>
