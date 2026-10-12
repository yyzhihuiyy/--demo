<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import {
  api, eventLabels, notReadyText, positions, productRoles, scoreLabels, statusLabels,
  type ClassroomData, type TaskDetail,
} from './teacherWorkspace'
import type { SessionDetail, Task, TaskComparison, TrainingSession } from '../../shared/contracts'
import { money, dateTime, percent } from '../../shared/format'
import AlertMessage from '../../shared/components/AlertMessage.vue'
import BaseButton from '../../shared/components/BaseButton.vue'
import DataTable from '../../shared/components/DataTable.vue'
import EmptyState from '../../shared/components/EmptyState.vue'
import StatusBadge from '../../shared/components/StatusBadge.vue'

const route = useRoute()
const taskId = computed(() => Number(route.params.id))

const loading = ref(true)
const loadError = ref('')
const loadNotReady = ref(false)
const taskDetail = ref<TaskDetail | null>(null)
const classroom = ref<ClassroomData | null>(null)
const sessionDetails = ref<Record<number, SessionDetail>>({})
const comparison = ref<TaskComparison | null>(null)
const comparisonError = ref('')
const comparisonNotReady = ref(false)

const task = computed<Task | null>(() => taskDetail.value?.task ?? null)
const teamName = (id: number) => classroom.value?.teams.find(team => team.id === id)?.name ?? `小组#${id}`
const memberText = (session: TrainingSession) => {
  const team = classroom.value?.teams.find(item => item.id === session.team_id)
  return (team?.members ?? []).map(member => {
    const student = classroom.value?.students.find(item => item.id === member.user_id)
    return `${student?.username ?? `学员#${member.user_id}`}（${positions[member.position] ?? member.position}）`
  }).join('、') || '—'
}
const sessionTone = (status: string) => status === 'live' ? 'success' : ['paused', 'preparing'].includes(status) ? 'warning' : ['submitted', 'graded'].includes(status) ? 'success' : 'neutral'
const taskTone = (status: string) => status === 'published' ? 'success' : status === 'closed' ? 'neutral' : 'warning'

const groups = computed(() => (taskDetail.value?.sessions ?? []).map(session => ({
  session,
  detail: sessionDetails.value[session.id] ?? null,
})))

const productColumns = [
  { key: 'title', label: '商品' },
  { key: 'positioning', label: '货盘角色' },
  { key: 'cost', label: '成本' },
  { key: 'price', label: '直播价' },
  { key: 'qty', label: '采购／库存' },
  { key: 'margin', label: '单品预计毛利' },
]
function productRows(detail: SessionDetail) {
  return detail.products.map(product => ({
    id: product.id,
    title: product.title,
    positioning: productRoles[product.positioning] ?? product.positioning,
    cost: money(product.cost_cents),
    price: money(product.sale_price_cents),
    qty: `${product.purchased_qty ?? 0} / ${product.stock_qty ?? 0}`,
    margin: money(Math.max(0, product.sale_price_cents - product.cost_cents) * (product.purchased_qty ?? 0)),
  }))
}
const estimatedMargin = (detail: SessionDetail) => detail.products.reduce(
  (sum, product) => sum + Math.max(0, product.sale_price_cents - product.cost_cents) * (product.purchased_qty ?? 0), 0)

const comparisonTeams = computed(() => comparison.value?.teams ?? [])
const comparisonColumns = [
  { key: 'team', label: '小组' },
  { key: 'status', label: '状态' },
  { key: 'gmv', label: 'GMV' },
  { key: 'netSales', label: '净销售额' },
  { key: 'profit', label: '利润' },
  { key: 'orders', label: '订单' },
  { key: 'replyRate', label: '回复率' },
  { key: 'violations', label: '违规' },
  { key: 'objective', label: '系统分' },
]
const comparisonRows = computed(() => comparisonTeams.value.map(team => ({
  id: team.team_id,
  team: team.team_name,
  status: statusLabels[team.status] ?? team.status,
  gmv: money(team.metrics.gmv_cents ?? 0),
  netSales: money(team.metrics.net_sales_cents ?? 0),
  profit: money(team.metrics.profit_cents ?? 0),
  orders: String(team.metrics.order_count ?? 0),
  replyRate: percent(team.metrics.reply_rate ?? null),
  violations: String(team.metrics.violation_count ?? 0),
  objective: team.breakdown ? String(team.breakdown.objective_score) : '未提交',
})))
const weightRows = computed(() => {
  const weights = task.value?.score_weights
  return (Object.keys(scoreLabels) as (keyof typeof scoreLabels)[]).map(key => ({
    key, label: scoreLabels[key], weight: weights?.[key] ?? '—',
  }))
})
const gradeOf = (teamId: number) => comparisonTeams.value.find(team => team.team_id === teamId)?.grade ?? null

async function loadComparison() {
  comparisonError.value = ''; comparisonNotReady.value = false
  try { comparison.value = await api<TaskComparison>(`/tasks/${taskId.value}/comparison`) }
  catch (error) {
    comparison.value = null
    comparisonError.value = notReadyText(error)
    comparisonNotReady.value = error instanceof Error && /尚未就绪/.test(error.message)
  }
}
async function loadSessions() {
  const sessions = taskDetail.value?.sessions ?? []
  const results = await Promise.allSettled(sessions.map(session => api<SessionDetail>(`/sessions/${session.id}`)))
  results.forEach((result, index) => {
    if (result.status === 'fulfilled') sessionDetails.value[sessions[index].id] = result.value
  })
}
async function load() {
  if (!Number.isInteger(taskId.value) || taskId.value <= 0) { loadError.value = '任务地址不正确'; loading.value = false; return }
  loading.value = true; loadError.value = ''; loadNotReady.value = false
  try {
    const [detail, classroomData] = await Promise.all([
      api<TaskDetail>(`/tasks/${taskId.value}`), api<ClassroomData>('/classroom'),
    ])
    taskDetail.value = detail
    classroom.value = classroomData
    await loadSessions()
    await loadComparison()
  } catch (error) {
    loadError.value = notReadyText(error)
    loadNotReady.value = true
    taskDetail.value = null
  } finally { loading.value = false }
}
onMounted(load)
watch(taskId, load)
</script>

<template>
  <div class="page-heading">
    <div>
      <p class="eyebrow">TEACHER CENTER</p>
      <h1>{{ task?.title ?? '任务详情' }}</h1>
      <p v-if="task">各组准备进度、经营方案与评分入口；数据来自各场次真实保存记录。</p>
    </div>
    <div class="heading-actions">
      <RouterLink to="/teacher"><BaseButton variant="secondary">返回教学管理</BaseButton></RouterLink>
      <BaseButton variant="secondary" @click="load">刷新</BaseButton>
    </div>
  </div>

  <div v-if="loading" class="panel"><p class="text-muted">正在加载任务与各组数据…</p></div>
  <AlertMessage v-else-if="loadError" tone="error">
    {{ loadError }}
    <template v-if="loadNotReady">后端接口正在接入中，稍后可点击重试。</template>
    <div style="margin-top:10px"><BaseButton variant="secondary" @click="load">重新加载</BaseButton></div>
  </AlertMessage>
  <template v-else-if="task">
    <section class="panel" aria-label="任务信息">
      <div class="section-heading" style="margin:0 0 14px">
        <h2>任务与规则</h2>
        <StatusBadge :tone="taskTone(task.status)">{{ statusLabels[task.status] ?? task.status }}</StatusBadge>
      </div>
      <p style="margin-bottom:14px">{{ task.description || '暂无任务说明' }}</p>
      <div class="task-stats">
        <div><span>目标人群</span><strong style="font-size:13px">{{ task.target_audience || '—' }}</strong></div>
        <div><span>初始预算</span><strong>{{ money(task.initial_budget_cents ?? 0) }}</strong></div>
        <div><span>GMV 目标</span><strong>{{ money(task.target_gmv_cents ?? 0) }}</strong></div>
        <div><span>市场热度／难度</span><strong>{{ task.market_heat ?? 1 }} / {{ task.difficulty ?? 1 }}</strong></div>
        <div><span>任务时间</span><strong style="font-size:12px">{{ dateTime(task.starts_at) }} ～ {{ dateTime(task.ends_at) }}</strong></div>
        <div><span>规则版本</span><strong style="font-size:12px">{{ task.rules_version ?? '—' }}</strong></div>
      </div>
      <div class="task-stats" style="margin-top:12px">
        <div v-for="row in weightRows" :key="row.key"><span>{{ row.label }}权重</span><strong>{{ row.weight }}</strong></div>
      </div>
      <p class="small text-muted" style="margin-bottom:0">
        {{ task.status === 'draft' ? '任务仍是草稿：发布前可编辑，学生端不可见。' : '任务已发布：评分权重、市场条件与截止时间已随发布冻结。' }}
      </p>
    </section>

    <section aria-label="各组方案">
      <div class="section-heading">
        <h2>各组准备与经营方案</h2>
        <span class="small text-muted">{{ groups.length }} 个小组</span>
      </div>
      <EmptyState v-if="!groups.length" title="本任务暂无小组场次" description="发布任务后，每个参赛小组会自动创建一个共享场次。" />
      <div class="group-stack">
        <article v-for="group in groups" :key="group.session.id" class="panel group-card">
          <div class="section-heading" style="margin:0 0 12px">
            <h3>{{ teamName(group.session.team_id) }}</h3>
            <div class="heading-actions">
              <StatusBadge :tone="sessionTone(group.session.status)">{{ statusLabels[group.session.status] ?? group.session.status }}</StatusBadge>
              <RouterLink :to="`/teacher/sessions/${group.session.id}/evidence`">
                <BaseButton :variant="group.session.status === 'submitted' ? 'primary' : 'secondary'">
                  {{ group.session.status === 'submitted' ? '去评分与查看证据' : '查看证据' }}
                </BaseButton>
              </RouterLink>
            </div>
          </div>
          <p class="small text-muted" style="margin-bottom:12px">场次 #{{ group.session.id }} · 成员：{{ memberText(group.session) }}</p>

          <template v-if="group.detail">
            <div class="task-stats">
              <div><span>调研人群</span><strong style="font-size:12px">{{ group.detail.preparation.research?.audience || '未填写' }}</strong></div>
              <div><span>直播间主题</span><strong style="font-size:12px">{{ group.detail.preparation.plan?.theme || '未填写' }}</strong></div>
              <div><span>投流预算</span><strong>{{ money(group.detail.preparation.promotion?.budget_cents ?? 0) }}</strong></div>
              <div><span>资金余额</span><strong>{{ money(group.detail.metrics.cash_balance_cents ?? 0) }}</strong></div>
              <div><span>组合预计毛利 *</span><strong>{{ money(estimatedMargin(group.detail)) }}</strong></div>
            </div>
            <p class="small text-muted" style="margin:10px 0">* 预计毛利为估算值：假设已采购库存全部按当前直播价售出，仅供参考，不代表实际利润。</p>
            <div v-if="group.detail.products.length" class="table-wrap">
              <DataTable :columns="productColumns" :rows="productRows(group.detail)" />
            </div>
            <p v-else class="small text-muted">该组尚未选入货盘商品。</p>
            <details class="research-details">
              <summary>调研与选品理由原文</summary>
              <div class="research-grid">
                <p><strong>竞品判断：</strong>{{ group.detail.preparation.research?.competitor_notes || '未填写' }}</p>
                <p><strong>价格判断：</strong>{{ group.detail.preparation.research?.price_notes || '未填写' }}</p>
                <p><strong>选品理由：</strong>{{ group.detail.preparation.research?.selection_reason || '未填写' }}</p>
              </div>
            </details>
          </template>
          <p v-else class="small text-muted">场次数据加载中或暂不可读。</p>

          <template v-if="gradeOf(group.session.team_id)">
            <div class="grade-summary">
              <span>已评分：系统分 {{ gradeOf(group.session.team_id)!.objective_score }} · 主观分 {{ gradeOf(group.session.team_id)!.subjective_score }} · 综合分 {{ gradeOf(group.session.team_id)!.total_score }}</span>
              <span class="small text-muted">评语：{{ gradeOf(group.session.team_id)!.comment || '—' }}</span>
            </div>
          </template>
        </article>
      </div>
    </section>

    <section aria-label="组间对比">
      <div class="section-heading">
        <h2>组间结果对比</h2>
        <span class="small text-muted">数据与排序来自后端统一汇总</span>
      </div>
      <AlertMessage v-if="comparisonError" :tone="comparisonNotReady ? 'info' : 'error'">
        {{ comparisonError }}
        <template v-if="comparisonNotReady">对比汇总接口将在核心后端第三批交付后可用；上方各组方案已直接读取场次数据。</template>
        <div style="margin-top:10px"><BaseButton variant="secondary" @click="loadComparison">重试</BaseButton></div>
      </AlertMessage>
      <template v-else-if="comparisonTeams.length">
        <DataTable :columns="comparisonColumns" :rows="comparisonRows" />
        <p class="small text-muted" style="margin-top:10px">
          系统分 = 各维度分按任务权重加权（CONTRACTS.md 6.2）；“未提交”表示该组尚未提交复盘，不参与评分排序。
        </p>
        <div v-for="team in comparisonTeams" :key="team.team_id" class="breakdown-line">
          <details>
            <summary>{{ team.team_name }} · 维度分依据</summary>
            <div class="research-grid">
              <template v-if="team.breakdown">
                <p v-for="row in weightRows" :key="row.key">{{ row.label }}：{{ team.breakdown[row.key as keyof typeof team.breakdown] }}（权重 {{ row.weight }}）</p>
                <p>系统分合计：{{ team.breakdown.objective_score }}</p>
              </template>
              <p v-else>该组尚未提交复盘，暂无维度分。</p>
              <p v-for="link in team.evidence_links" :key="link.kind">
                证据入口：<RouterLink :to="`/teacher/sessions/${link.session_id}/evidence`" class="text-button">{{ link.label }}（{{ eventLabels[link.kind] ?? link.kind }}）</RouterLink>
              </p>
            </div>
          </details>
        </div>
      </template>
      <EmptyState v-else title="暂无可对比数据" description="各组提交复盘后，这里会显示统一汇总的组间结果对比。" />
    </section>
  </template>
</template>

<style scoped>
.heading-actions{display:flex;gap:10px;align-items:center;flex-wrap:wrap}
.group-stack{display:flex;flex-direction:column;gap:16px}
.group-card{border-left:3px solid #8db79a}
.task-stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px 18px;font-size:12px}
.task-stats span{display:block;color:var(--muted);margin-bottom:4px}
.research-details summary,.breakdown-line summary{cursor:pointer;font-size:13px;color:var(--accent)}
.research-grid{display:flex;flex-direction:column;gap:8px;margin-top:10px;font-size:13px;line-height:1.7}
.grade-summary{display:flex;flex-direction:column;gap:4px;border-top:1px solid var(--line);margin-top:14px;padding-top:12px;font-size:13px}
.breakdown-line{margin-top:8px}
</style>
