<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import {
  api, eventLabels, notReadyText, positions, productRoles, scriptKinds, statusLabels, useFeedback, useSession,
} from '../../features/student/workspace'
import type { LiveState, Metrics, SessionProduct, TrainingEvent, TrainingSession } from '../../shared/contracts'
import AlertMessage from '../../shared/components/AlertMessage.vue'
import BaseButton from '../../shared/components/BaseButton.vue'
import EmptyState from '../../shared/components/EmptyState.vue'
import SessionNav from '../../features/student/SessionNav.vue'
import MetricsGrid from '../../features/student/MetricsGrid.vue'
import StatusBadge from '../../shared/components/StatusBadge.vue'
import { useAuth } from '../../shared/auth'
import { dateTime, money } from '../../shared/format'

const route = useRoute()
const sessionId = computed(() => Number(route.params.id))
const { user } = useAuth()
const { detail, classroom, task, team, members, loading, loadError, notReady, load } = useSession(() => sessionId.value)

const live = ref<LiveState | null>(null)
const events = ref<TrainingEvent[]>([])
const lastEventId = ref(0)
const pollError = ref('')
const feedBox = ref<HTMLElement | null>(null)
let pollTimer: ReturnType<typeof setTimeout> | undefined
let polling = false

const speechText = ref('')
const announcementText = ref('')
const replyDrafts = ref<Record<number, string>>({})
const controlFeedback = useFeedback()
const actionFeedback = useFeedback()
const endArmed = ref(false)
let endArmTimer: ReturnType<typeof setTimeout> | undefined

const status = computed(() => live.value?.status ?? detail.value?.session.status ?? 'preparing')
const isLive = computed(() => status.value === 'live')
const isActive = computed(() => ['live', 'paused'].includes(status.value))
const ended = computed(() => ['ended', 'submitted', 'graded'].includes(status.value))
const statusTone = computed(() => status.value === 'live' ? 'success' : status.value === 'paused' ? 'warning' : 'neutral')
const products = computed<SessionProduct[]>(() => detail.value?.products ?? [])
const productById = computed(() => new Map(products.value.map(item => [item.id, item])))
const currentProduct = computed(() => live.value?.current_product ?? productById.value.get(detail.value?.session.current_product_id ?? -1) ?? null)
const myPosition = computed(() => members.value.find(member => member.user_id === user.value?.id)?.position)
const memberName = (userId: number) => classroom.value?.students.find(student => student.id === userId)?.username ?? `学员#${userId}`

const script = computed(() => detail.value?.preparation.script ?? [])
const couponCents = computed(() => detail.value?.preparation.coupon?.discount_cents ?? 0)
const executedScriptIds = computed(() => {
  const ids = new Set<string>()
  for (const event of events.value) if (event.type === 'execute_script') {
    const id = event.payload.script_id
    if (id != null) ids.add(String(id))
  }
  return ids
})
const repliedQuestionIds = computed(() => new Set(events.value.filter(event => event.type === 'reply').map(event => Number(event.payload.question_event_id))))
const pendingQuestions = computed(() => events.value.filter(event => event.type === 'audience_question' && !repliedQuestionIds.value.has(event.id)).slice(-12).reverse())
const violationCount = computed(() => events.value.filter(event => ['violation', 'compliance'].includes(event.type)).length)

function describe(event: TrainingEvent) {
  const payload = event.payload as Record<string, unknown>
  for (const key of ['text', 'question', 'message', 'content']) if (typeof payload[key] === 'string') return payload[key] as string
  if (event.type === 'select_product') {
    const product = productById.value.get(Number(payload.session_product_id))
    return `切换讲解商品：${product ? product.title : `场次商品 #${payload.session_product_id ?? '—'}`}`
  }
  if (event.type === 'execute_script') {
    const segment = script.value.find(item => item.id === payload.script_id)
    return `执行脚本段落：${segment ? scriptKinds[segment.kind] ?? segment.kind : String(payload.script_id ?? '')}`
  }
  if (event.type.includes('order')) {
    const parts = [`买家 ${payload.buyer_label ?? '—'}`]
    if (payload.qty != null) parts.push(`${payload.qty} 件`)
    if (typeof payload.amount_cents === 'number') parts.push(`实付 ${money(payload.amount_cents)}`)
    const title = payload.title ?? productById.value.get(Number(payload.session_product_id))?.title
    if (typeof title === 'string') parts.unshift(String(title))
    if (parts.length > 1) return `仿真成交 · ${parts.join(' · ')}`
  }
  if (event.type === 'issue_coupon') return '场控发放了场次优惠券'
  if (payload.action) {
    const labels: Record<string, string> = { start: '开始直播', pause: '暂停直播', resume: '恢复直播', end: '结束直播' }
    return labels[String(payload.action)] ?? String(payload.action)
  }
  return JSON.stringify(payload)
}
const actorLabel = (event: TrainingEvent) => event.actor_id == null ? '系统' : memberName(event.actor_id)
const tone = (event: TrainingEvent) => ['violation', 'compliance'].includes(event.type) ? 'violation' : event.type === 'audience_question' ? 'question' : event.source === 'rule' ? 'rule' : 'manual'

async function refresh() {
  try {
    const state = await api<LiveState>(`/sessions/${sessionId.value}/live-state`)
    live.value = state
    pollError.value = ''
    if (typeof state.latest_event_id === 'number' && state.latest_event_id > lastEventId.value) {
      const fresh = await api<TrainingEvent[]>(`/sessions/${sessionId.value}/events?after_id=${lastEventId.value}&limit=100`)
      appendEvents(fresh)
      lastEventId.value = Math.max(lastEventId.value, state.latest_event_id, ...fresh.map(event => event.id))
    }
  } catch (error) {
    pollError.value = notReadyText(error)
  }
}
function appendEvents(fresh: TrainingEvent[]) {
  if (!fresh.length) return
  const seen = new Set(events.value.map(event => event.id))
  events.value = [...events.value, ...fresh.filter(event => !seen.has(event.id))].slice(-300)
}
async function tickLoop() {
  await refresh()
  if (!polling) return
  if (ended.value) { polling = false; return }
  pollTimer = setTimeout(tickLoop, 2000)
}
function startPolling() { if (polling) return; polling = true; void tickLoop() }
function stopPolling() { polling = false; if (pollTimer) clearTimeout(pollTimer) }

onMounted(async () => {
  await load()
  if (!detail.value) return
  try {
    const history = await api<TrainingEvent[]>(`/sessions/${sessionId.value}/events?after_id=0&limit=200`)
    events.value = history.slice(-300)
    lastEventId.value = history.length ? history[history.length - 1].id : 0
  } catch (error) { pollError.value = notReadyText(error) }
  await refresh()
  startPolling()
})
async function reloadAll() {
  stopPolling(); events.value = []; lastEventId.value = 0; live.value = null
  await load()
  if (!detail.value) return
  try {
    const history = await api<TrainingEvent[]>(`/sessions/${sessionId.value}/events?after_id=0&limit=200`)
    events.value = history.slice(-300)
    lastEventId.value = history.length ? history[history.length - 1].id : 0
  } catch (error) { pollError.value = notReadyText(error) }
  await refresh()
  startPolling()
}
watch(sessionId, () => { void reloadAll() })
onUnmounted(() => { stopPolling(); if (endArmTimer) clearTimeout(endArmTimer) })

watch(() => events.value.length, async () => {
  await nextTick()
  if (feedBox.value) feedBox.value.scrollTop = feedBox.value.scrollHeight
})

async function control(action: 'start' | 'pause' | 'resume' | 'end') {
  await controlFeedback.run(async () => {
    const result = await controlFeedback.write<{ status: TrainingSession['status']; metrics: Metrics }>(`/sessions/${sessionId.value}/control`, { action })
    if (live.value) { live.value.status = result.status; live.value.metrics = result.metrics }
    await load()
    await refresh()
    if (action === 'end') stopPolling()
  }, { start: '直播已开始', pause: '直播已暂停，仿真与成交暂停', resume: '直播已恢复', end: '直播已结束，请前往履约与复盘' }[action])
  endArmed.value = false
}
function requestEnd() {
  if (!endArmed.value) {
    endArmed.value = true
    if (endArmTimer) clearTimeout(endArmTimer)
    endArmTimer = setTimeout(() => { endArmed.value = false }, 4000)
    return
  }
  if (endArmTimer) clearTimeout(endArmTimer)
  void control('end')
}

async function act(type: string, payload: Record<string, unknown>, success: string) {
  await actionFeedback.run(async () => {
    await actionFeedback.write(`/sessions/${sessionId.value}/actions`, { type, payload })
    await refresh()
  }, success)
}

function sendSpeech() {
  const text = speechText.value.trim()
  if (!text) { actionFeedback.error.value = '口播内容不能为空。'; return }
  void act('speech', { text }, '口播已保存并推送。').then(() => { if (!actionFeedback.error.value) speechText.value = '' })
}
function sendAnnouncement() {
  const text = announcementText.value.trim()
  if (!text) { actionFeedback.error.value = '公告内容不能为空。'; return }
  void act('announcement', { text }, '公告已更新。').then(() => { if (!actionFeedback.error.value) announcementText.value = '' })
}
function selectProduct(product: SessionProduct) {
  void act('select_product', { session_product_id: product.id }, `已切换讲解商品：${product.title}`)
}
function sendReply(question: TrainingEvent) {
  const text = (replyDrafts.value[question.id] ?? '').trim()
  if (!text) { actionFeedback.error.value = '回复内容不能为空。'; return }
  void act('reply', { question_event_id: question.id, text }, '回复已保存并推送。').then(() => { if (!actionFeedback.error.value) delete replyDrafts.value[question.id] })
}
function executeSegment(id: string) {
  void act('execute_script', { script_id: id }, '脚本段落已执行，已记录操作人与时间。')
}
</script>

<template>
  <SessionNav :id="sessionId" />
  <div class="page-heading">
    <div>
      <p class="eyebrow">LIVE STUDIO</p>
      <h1>直播工作台</h1>
      <p>深色直播间 · 与同组岗位协作完成口播、切品、优惠与观众互动（全部为教学仿真）。</p>
    </div>
    <StatusBadge v-if="detail" :tone="statusTone">场次：{{ statusLabels[status] ?? status }}</StatusBadge>
  </div>

  <div v-if="loading" class="panel"><p class="text-muted">正在加载场次…</p></div>
  <AlertMessage v-else-if="loadError" tone="error">
    {{ loadError }}
    <template v-if="notReady">后端直播接口正在接入中；接口就绪后可点击重试。</template>
    <div style="margin-top:10px"><BaseButton variant="secondary" @click="reloadAll">重新加载</BaseButton></div>
  </AlertMessage>
  <template v-else-if="detail">
    <AlertMessage v-if="status === 'preparing'" tone="info">
      场次仍在准备阶段：完成开播检查后才能开始直播。
      <RouterLink :to="`/sessions/${sessionId}/prepare`" class="text-button">→ 回到准备工作台</RouterLink>
    </AlertMessage>
    <AlertMessage v-if="ended" tone="success">
      直播已结束{{ status === 'submitted' ? '，复盘已提交' : status === 'graded' ? '，教师已完成评分' : '' }}：请前往履约与复盘处理订单与提交。
      <RouterLink :to="`/sessions/${sessionId}/review`" class="text-button">→ 进入履约与复盘</RouterLink>
    </AlertMessage>
    <AlertMessage v-if="pollError" tone="error">状态轮询异常：{{ pollError }}（页面会自动重试）</AlertMessage>

    <div class="live-root" :style="{ '--metric-bg':'#16221b','--metric-border':'#2a3a30','--metric-muted':'#7f9587','--metric-value':'#e8f3ec' }">
      <header class="live-head">
        <div class="live-title">
          <strong>{{ detail.preparation.room?.title || task?.title || '直播间' }}</strong>
          <span>{{ detail.preparation.room?.announcement || '（未设置公告，可在场控面板更新）' }}</span>
        </div>
        <div class="live-meta">
          <span>开播时间：{{ dateTime(detail.session.started_at) }}</span>
          <span class="live-dot" :data-live="isLive" />{{ statusLabels[status] ?? status }}
          <span v-if="violationCount" class="live-violation">合规提示 {{ violationCount }} 条</span>
        </div>
      </header>

      <div class="live-team">
        <span v-for="member in members" :key="member.user_id" class="live-member" :data-me="member.user_id === user?.id">
          {{ memberName(member.user_id) }} · {{ positions[member.position] ?? member.position }}
        </span>
        <span class="live-member live-member-note">当前登录：{{ user?.username }}{{ myPosition ? `（${positions[myPosition]}）` : '' }}</span>
      </div>

      <div class="live-grid">
        <section class="live-stage">
          <div class="live-video" aria-label="演示主播素材">
            <span class="live-video-mark">▶</span>
            <p>演示主播素材（教学占位 · 不进行真实推流）</p>
            <span class="live-video-emoji">{{ currentProduct ? '🛒' : '⏸' }}</span>
          </div>
          <div class="live-current">
            <template v-if="currentProduct">
              <div class="live-current-main">
                <strong>{{ currentProduct.title }}</strong>
                <span>{{ productRoles[currentProduct.positioning] }} · 直播价 {{ money(currentProduct.sale_price_cents) }}</span>
                <small>库存 {{ currentProduct.stock_qty ?? 0 }} / 已采购 {{ currentProduct.purchased_qty ?? 0 }} · 成本 {{ money(currentProduct.cost_cents) }}</small>
                <p v-if="currentProduct.selling_points">{{ currentProduct.selling_points }}</p>
              </div>
              <StatusBadge tone="success">讲解中</StatusBadge>
            </template>
            <p v-else class="live-empty-product">尚未选择讲解商品：直播中由场控点击下方商品卡切换。</p>
          </div>
          <div class="live-products">
            <button v-for="product in products" :key="product.id" type="button" class="live-product" :data-active="currentProduct?.id === product.id" :disabled="!isLive" @click="selectProduct(product)">
              <strong>{{ product.title }}</strong>
              <small>{{ productRoles[product.positioning] }} · {{ money(product.sale_price_cents) }} · 库存 {{ product.stock_qty ?? 0 }}</small>
            </button>
            <p v-if="!products.length" class="live-hint">货盘为空：请先在准备工作台保存货盘并采购。</p>
          </div>
        </section>

        <aside class="live-side">
          <div class="live-side-head"><strong>直播事件流</strong><span>观众、订单与组内操作（教学仿真）</span></div>
          <div ref="feedBox" class="live-feed">
            <p v-if="!events.length" class="live-hint">暂无事件；开播后观众咨询与仿真成交会出现在这里。</p>
            <div v-for="event in events" :key="event.id" class="live-event" :data-tone="tone(event)">
              <div class="live-event-head">
                <span>{{ eventLabels[event.type] ?? event.type }}</span>
                <small>{{ actorLabel(event) }} · {{ dateTime(event.created_at) }}</small>
              </div>
              <p>{{ describe(event) }}</p>
            </div>
          </div>
        </aside>
      </div>

      <MetricsGrid :metrics="live?.metrics ?? detail.metrics" live />

      <div class="live-controls">
        <div class="live-controls-left">
          <StatusBadge :tone="statusTone">{{ statusLabels[status] ?? status }}</StatusBadge>
          <span class="live-hint-inline">开始前需通过开播检查；暂停与结束后不再成交</span>
        </div>
        <div class="student-actions">
          <BaseButton :disabled="status !== 'preparing'" :loading="controlFeedback.busy.value" @click="control('start')">开始直播</BaseButton>
          <BaseButton variant="secondary" :disabled="status !== 'live'" :loading="controlFeedback.busy.value" @click="control('pause')">暂停</BaseButton>
          <BaseButton variant="secondary" :disabled="status !== 'paused'" :loading="controlFeedback.busy.value" @click="control('resume')">恢复</BaseButton>
          <BaseButton variant="danger" :disabled="!isActive" :loading="controlFeedback.busy.value" @click="requestEnd">{{ endArmed ? '再次点击确认结束' : '结束直播' }}</BaseButton>
        </div>
      </div>
      <AlertMessage v-if="controlFeedback.error.value" tone="error">{{ controlFeedback.error.value }}</AlertMessage>
      <AlertMessage v-if="controlFeedback.notice.value" tone="success">{{ controlFeedback.notice.value }}</AlertMessage>

      <div class="live-panels">
        <section class="live-panel">
          <div class="live-panel-head"><strong>主播 · 文字口播</strong><span v-if="myPosition === 'host'" class="live-you">你的岗位</span></div>
          <textarea v-model="speechText" rows="3" placeholder="输入口播话术：商品卖点、价格、活动提示…（含违规示例词会被记录合规提示）" :disabled="!isLive" />
          <div class="student-actions" style="margin-top:10px">
            <BaseButton :disabled="!isLive" :loading="actionFeedback.busy.value" @click="sendSpeech">推送口播</BaseButton>
            <span class="live-hint-inline">保存后带作者与时间进入事件流</span>
          </div>
        </section>

        <section class="live-panel">
          <div class="live-panel-head"><strong>主播 · 执行脚本</strong><span class="live-hint-inline">执行状态来自服务端事件</span></div>
          <div class="live-scripts">
            <div v-for="segment in script" :key="segment.id" class="live-script" :data-done="executedScriptIds.has(segment.id)">
              <div class="live-script-info">
                <strong>{{ scriptKinds[segment.kind] ?? segment.kind }}<template v-if="segment.kind === 'product' && segment.product_id"> · 商品 #{{ segment.product_id }}</template></strong>
                <small>{{ segment.text?.slice(0, 60) || '（未填写话术）' }}</small>
              </div>
              <BaseButton variant="secondary" :disabled="!isLive || executedScriptIds.has(segment.id)" @click="executeSegment(segment.id)">
                {{ executedScriptIds.has(segment.id) ? '已执行' : '执行' }}
              </BaseButton>
            </div>
            <p v-if="!script.length" class="live-hint">尚未保存脚本：请先在准备工作台填写四类段落。</p>
          </div>
        </section>

        <section class="live-panel">
          <div class="live-panel-head"><strong>场控 · 优惠券与公告</strong><span v-if="myPosition === 'control'" class="live-you">你的岗位</span></div>
          <p class="live-hint-inline">当前配置优惠券：{{ couponCents > 0 ? money(couponCents) : '未配置（0 元）' }}；发放后作用于后续成交。</p>
          <div class="student-actions" style="margin:10px 0">
            <BaseButton variant="secondary" :disabled="!isLive" :loading="actionFeedback.busy.value" @click="act('issue_coupon', {}, '优惠券已发放。')">发放优惠券</BaseButton>
          </div>
          <textarea v-model="announcementText" rows="2" placeholder="更新直播间公告…" :disabled="!isLive" />
          <div class="student-actions" style="margin-top:10px">
            <BaseButton :disabled="!isLive" :loading="actionFeedback.busy.value" @click="sendAnnouncement">更新公告</BaseButton>
          </div>
        </section>

        <section class="live-panel">
          <div class="live-panel-head"><strong>客服 · 观众咨询回复</strong><span v-if="myPosition === 'service'" class="live-you">你的岗位</span></div>
          <p v-if="!isLive && !pendingQuestions.length" class="live-hint">直播中的观众咨询会出现在这里，回复须引用具体问题。</p>
          <div class="live-questions">
            <div v-for="question in pendingQuestions" :key="question.id" class="live-question">
              <div class="live-event-head"><span>待回复咨询</span><small>{{ dateTime(question.created_at) }}</small></div>
              <p>{{ describe(question) }}</p>
              <textarea v-model="replyDrafts[question.id]" rows="2" placeholder="输入回复内容…" :disabled="!isLive" />
              <div class="student-actions" style="margin-top:8px">
                <BaseButton :disabled="!isLive" :loading="actionFeedback.busy.value" @click="sendReply(question)">发送回复</BaseButton>
              </div>
            </div>
            <p v-if="!pendingQuestions.length" class="live-hint">暂无待回复咨询。</p>
          </div>
        </section>
      </div>
      <AlertMessage v-if="actionFeedback.error.value" tone="error">{{ actionFeedback.error.value }}</AlertMessage>
      <AlertMessage v-if="actionFeedback.notice.value" tone="success">{{ actionFeedback.notice.value }}</AlertMessage>
      <p class="live-footnote">观众、订单与物流均为教学仿真数据；每 2 秒只读轮询，不在浏览器生成订单。</p>
    </div>
  </template>
  <EmptyState v-else title="未找到场次" description="请从「我的实训」进入正确的场次入口。" />
</template>

<style scoped>
.live-root{display:grid;gap:16px;background:#101711;border-radius:14px;padding:22px;color:#dcebe1;font-size:13px}
.live-head{display:flex;justify-content:space-between;gap:18px;flex-wrap:wrap;border-bottom:1px solid #233028;padding-bottom:16px}
.live-title{display:grid;gap:7px}
.live-title strong{font-size:20px;letter-spacing:.5px}
.live-title span{font-size:12px;color:#9db3a5}
.live-meta{display:flex;align-items:center;gap:14px;font-size:11px;color:#9db3a5;flex-wrap:wrap}
.live-dot{width:8px;height:8px;border-radius:50%;background:#6b7f72;display:inline-block}
.live-dot[data-live="true"]{background:#4cc98a;box-shadow:0 0 8px #4cc98a80}
.live-violation{color:#e8b96f;background:#3a2f1d;padding:4px 9px;border-radius:6px}
.live-team{display:flex;gap:8px;flex-wrap:wrap}
.live-member{font-size:11px;padding:6px 10px;border-radius:6px;background:#1b2620;color:#9db3a5;border:1px solid #27352c}
.live-member[data-me="true"]{background:#1f4433;color:#bfe8d2;border-color:#2f5c46;font-weight:600}
.live-member-note{border-style:dashed}
.live-grid{display:grid;grid-template-columns:minmax(0,1.5fr) minmax(0,1fr);gap:16px}
.live-stage{display:grid;gap:12px;align-content:start}
.live-video{position:relative;min-height:240px;border-radius:12px;background:radial-gradient(circle at 50% 40%,#24352b,#141d17 70%);display:grid;place-items:center;grid-gap:8px;padding:20px;text-align:center}
.live-video-mark{font-size:30px;color:#4e6a58}
.live-video p{font-size:12px;color:#87a08f;margin:0}
.live-video-emoji{font-size:44px}
.live-current{display:flex;align-items:flex-start;justify-content:space-between;gap:12px;background:#17221b;border:1px solid #27352c;border-radius:10px;padding:16px}
.live-current-main{display:grid;gap:6px}
.live-current-main strong{font-size:16px}
.live-current-main span{font-size:12px;color:#9db3a5}
.live-current-main small{font-size:11px;color:#7f9587}
.live-current-main p{margin:6px 0 0;font-size:12px;color:#b7cbbf}
.live-empty-product{font-size:12px;color:#87a08f;margin:0}
.live-products{display:grid;grid-template-columns:repeat(auto-fill,minmax(160px,1fr));gap:10px}
.live-product{display:grid;gap:5px;text-align:left;background:#17221b;border:1px solid #27352c;border-radius:9px;padding:11px 12px;color:#dcebe1;font:inherit}
.live-product strong{font-size:12px}
.live-product small{font-size:11px;color:#87a08f}
.live-product[data-active="true"]{border-color:#4cc98a;background:#1b3226}
.live-product:disabled{opacity:.5}
.live-side{display:flex;flex-direction:column;min-height:0}
.live-side-head{display:flex;justify-content:space-between;align-items:center;gap:10px;margin-bottom:10px}
.live-side-head strong{font-size:13px}
.live-side-head span{font-size:10px;color:#7f9587}
.live-feed{flex:1;max-height:430px;overflow-y:auto;display:grid;gap:8px;align-content:start;padding-right:4px}
.live-event{background:#141e17;border-left:3px solid #2f5c46;border-radius:0 8px 8px 0;padding:9px 12px}
.live-event[data-tone="question"]{border-left-color:#4c7fa0}
.live-event[data-tone="violation"]{border-left-color:#d9a353;background:#241d12}
.live-event[data-tone="rule"]{border-left-color:#54685c;opacity:.92}
.live-event-head{display:flex;justify-content:space-between;gap:10px;font-size:11px;color:#87a08f;margin-bottom:5px}
.live-event p{margin:0;font-size:12px;white-space:pre-wrap;overflow-wrap:anywhere;color:#cfe0d5}
.live-controls{display:flex;justify-content:space-between;align-items:center;gap:16px;flex-wrap:wrap;border-top:1px solid #233028;padding-top:16px}
.live-controls-left{display:flex;align-items:center;gap:12px;flex-wrap:wrap}
.live-hint{font-size:11px;color:#87a08f;margin:0}
.live-hint-inline{font-size:11px;color:#87a08f}
.live-panels{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px}
.live-panel{background:#141e17;border:1px solid #233028;border-radius:10px;padding:16px;display:grid;gap:10px;align-content:start}
.live-panel-head{display:flex;justify-content:space-between;align-items:center;gap:10px}
.live-panel-head strong{font-size:13px}
.live-you{font-size:10px;color:#4cc98a;border:1px solid #2f5c46;padding:3px 8px;border-radius:12px}
.live-scripts{display:grid;gap:8px;max-height:240px;overflow-y:auto}
.live-script{display:flex;align-items:center;justify-content:space-between;gap:12px;background:#17221b;border-radius:8px;padding:10px 12px}
.live-script[data-done="true"]{opacity:.62}
.live-script-info{display:grid;gap:4px;min-width:0}
.live-script-info strong{font-size:12px}
.live-script-info small{font-size:11px;color:#87a08f;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;max-width:320px}
.live-questions{display:grid;gap:10px;max-height:300px;overflow-y:auto}
.live-question{background:#17221b;border-radius:8px;padding:11px 12px;display:grid;gap:8px}
.live-footnote{margin:0;font-size:10px;color:#6f8275;text-align:center}
.live-root textarea,.live-root input{width:100%;background:#0e1510;border:1px solid #27352c;border-radius:7px;color:#dcebe1;font:inherit;font-size:12px;padding:9px 11px}
.live-root textarea:disabled,.live-root input:disabled{opacity:.55}
@media(max-width:1000px){.live-grid,.live-panels{grid-template-columns:1fr}}
</style>
