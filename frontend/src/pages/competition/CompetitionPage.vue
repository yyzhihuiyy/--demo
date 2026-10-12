<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { api, notReadyText, percent, productRoles, scoreLabels, sortRuleText, statusLabels, useFeedback } from '../teacher/teacherWorkspace'
import type { Competition, CompetitionComparison, Leaderboard, LeaderboardEntry, Task } from '../../shared/contracts'
import { money, dateTime } from '../../shared/format'
import { useAuth } from '../../shared/auth'
import AlertMessage from '../../shared/components/AlertMessage.vue'
import BaseButton from '../../shared/components/BaseButton.vue'
import DataTable from '../../shared/components/DataTable.vue'
import EmptyState from '../../shared/components/EmptyState.vue'
import FormField from '../../shared/components/FormField.vue'
import StatusBadge from '../../shared/components/StatusBadge.vue'

const { user } = useAuth()
const isTeacher = computed(() => user.value?.role === 'teacher')

const loading = ref(true)
const loadError = ref('')
const loadNotReady = ref(false)
const competitions = ref<Competition[]>([])
const tasks = ref<Task[]>([])
const selectedId = ref<number | null>(null)

const selected = computed(() => competitions.value.find(item => item.id === selectedId.value) ?? null)
const competitionTone = (status: string) => status === 'published' ? 'success' : status === 'finished' ? 'neutral' : 'warning'
const draftTasks = computed(() => tasks.value.filter(task => task.status === 'draft'))
const taskTitle = (id: number) => tasks.value.find(task => task.id === id)?.title ?? `任务#${id}`

const createFeedback = useFeedback()
const createOpen = ref(false)
const createForm = ref({ task_id: 0, title: '' })

async function submitCreate() {
  const form = createForm.value
  if (!form.task_id) { createFeedback.error.value = '请选择一个草稿任务。'; return }
  if (!form.title.trim()) { createFeedback.error.value = '请填写竞赛标题。'; return }
  const created = await createFeedback.run(async () => {
    const competition = await createFeedback.write<Competition>('/competitions', { task_id: form.task_id, title: form.title.trim() })
    await load()
    return competition
  }, '竞赛已创建，将随任务发布一同冻结条件。')
  if (created) { createOpen.value = false; selectedId.value = created.id; await refreshSelected() }
}

const stage = ref<'provisional' | 'final'>('provisional')
const leaderboard = ref<Leaderboard | null>(null)
const leaderboardError = ref('')
const leaderboardNotReady = ref(false)
const leaderboardLoading = ref(false)

const entryColumns = computed(() => stage.value === 'provisional'
  ? [
      { key: 'rank', label: '名次' },
      { key: 'team', label: '小组' },
      { key: 'status', label: '完成状态' },
      { key: 'gmv', label: 'GMV' },
      { key: 'netSales', label: '净销售额' },
      { key: 'profit', label: '利润' },
      { key: 'objective', label: '系统分' },
    ]
  : [
      { key: 'rank', label: '名次' },
      { key: 'team', label: '小组' },
      { key: 'status', label: '完成状态' },
      { key: 'gmv', label: 'GMV' },
      { key: 'netSales', label: '净销售额' },
      { key: 'profit', label: '利润' },
      { key: 'objective', label: '系统分' },
      { key: 'subjective', label: '教师主观分' },
      { key: 'total', label: '综合分' },
    ])
function toRows(entries: LeaderboardEntry[] = []) {
  return entries.map((entry, index) => ({
    id: entry.team_id,
    rank: String(index + 1),
    team: entry.team_name,
    status: entry.status,
    gmv: money(entry.metrics.gmv_cents ?? 0),
    netSales: money(entry.metrics.net_sales_cents ?? 0),
    profit: money(entry.metrics.profit_cents ?? 0),
    objective: entry.objective_score == null ? '—' : String(entry.objective_score),
    subjective: entry.subjective_score == null ? '—' : String(entry.subjective_score),
    total: entry.total_score == null ? '—' : String(entry.total_score),
  }))
}
const entryRows = computed(() => toRows(leaderboard.value?.entries ?? []))
const pendingRows = computed(() => toRows(leaderboard.value?.pending_entries ?? []))

const pendingLabel = (status: string) => {
  if (status === 'ended') return '已下播未提交'
  if (status === 'submitted') return '待教师评分'
  if (status === 'graded') return '已评分'
  return statusLabels[status] ?? status
}
const weightLine = computed(() => {
  const weights = leaderboard.value?.score_weights
  return (Object.keys(scoreLabels) as (keyof typeof scoreLabels)[]).map(key => `${scoreLabels[key]} ${weights?.[key] ?? '—'}`).join(' / ')
})

async function loadLeaderboard() {
  if (!selectedId.value) { leaderboard.value = null; return }
  leaderboardLoading.value = true; leaderboardError.value = ''; leaderboardNotReady.value = false
  try {
    leaderboard.value = await api<Leaderboard>(`/competitions/${selectedId.value}/leaderboard?stage=${stage.value}`)
  } catch (error) {
    leaderboard.value = null
    leaderboardError.value = notReadyText(error)
    leaderboardNotReady.value = /尚未就绪/.test(leaderboardError.value)
  } finally { leaderboardLoading.value = false }
}
watch(stage, () => void loadLeaderboard())

const comparison = ref<CompetitionComparison | null>(null)
const comparisonError = ref('')
const comparisonNotReady = ref(false)
async function loadComparison() {
  if (!selectedId.value || !isTeacher.value) { comparison.value = null; return }
  comparisonError.value = ''; comparisonNotReady.value = false
  try {
    comparison.value = await api<CompetitionComparison>(`/competitions/${selectedId.value}/comparison`)
  } catch (error) {
    comparison.value = null
    comparisonError.value = notReadyText(error)
    comparisonNotReady.value = /尚未就绪/.test(comparisonError.value)
  }
}

async function refreshSelected() {
  await loadLeaderboard()
  if (isTeacher.value) await loadComparison()
}

async function load() {
  loading.value = true; loadError.value = ''; loadNotReady.value = false
  try {
    competitions.value = await api<Competition[]>('/competitions')
    tasks.value = isTeacher.value ? await api<Task[]>('/tasks') : []
    const list = competitions.value
    if (list.length && (!selectedId.value || !list.some(item => item.id === selectedId.value))) {
      selectedId.value = (list.find(item => item.status !== 'draft') ?? list[0]).id
    }
    if (!list.length) selectedId.value = null
    await refreshSelected()
  } catch (error) {
    loadError.value = notReadyText(error)
    loadNotReady.value = true
  } finally { loading.value = false }
}
onMounted(load)

async function select(id: number) {
  selectedId.value = id
  await refreshSelected()
}

const strategyColumns = [
  { key: 'team', label: '小组' },
  { key: 'selection', label: '选品理由' },
  { key: 'assortment', label: '货盘（定位×采购量）' },
  { key: 'priceBand', label: '直播价区间' },
  { key: 'promotion', label: '投流预算' },
  { key: 'coupon', label: '优惠券' },
]
const strategyRows = computed(() => (comparison.value?.teams ?? []).map(team => ({
  id: team.team_id,
  team: team.team_name,
  selection: team.preparation.research?.selection_reason || '未填写',
  assortment: (team.products ?? []).map(product => `${productRoles[product.positioning] ?? product.positioning}×${product.purchased_qty ?? 0}`).join('、') || '未选品',
  priceBand: (team.products ?? []).length
    ? `${money(Math.min(...(team.products ?? []).map(product => product.sale_price_cents)))} ~ ${money(Math.max(...(team.products ?? []).map(product => product.sale_price_cents)))}`
    : '—',
  promotion: money(team.preparation.promotion?.budget_cents ?? 0),
  coupon: money(team.preparation.coupon?.discount_cents ?? 0),
})))

const resultColumns = [
  { key: 'team', label: '小组' },
  { key: 'status', label: '状态' },
  { key: 'orders', label: '订单' },
  { key: 'signed', label: '已签收' },
  { key: 'replyRate', label: '回复率' },
  { key: 'violations', label: '违规' },
  { key: 'objective', label: '系统分' },
  { key: 'total', label: '综合分' },
  { key: 'evidence', label: '证据入口' },
]
const resultRows = computed(() => (comparison.value?.teams ?? []).map(team => ({
  id: team.team_id,
  team: team.team_name,
  status: statusLabels[team.status] ?? team.status,
  orders: String(team.metrics.order_count ?? 0),
  signed: String(team.metrics.signed_order_count ?? 0),
  replyRate: percent(team.metrics.reply_rate ?? null),
  violations: String(team.metrics.violation_count ?? 0),
  objective: team.breakdown ? String(team.breakdown.objective_score) : '未提交',
  total: team.grade ? String(team.grade.total_score) : '未评分',
  sessionId: team.session_id,
})))
</script>

<template>
  <div class="page-heading">
    <div>
      <p class="eyebrow">COMPETITION</p>
      <h1>竞赛与对比</h1>
      <p>同一任务相同初始条件下的组间排行与策略对比；全部数据来自后端统一汇总。</p>
    </div>
    <div class="heading-actions">
      <BaseButton variant="secondary" @click="load">刷新</BaseButton>
      <BaseButton v-if="isTeacher" @click="createOpen = !createOpen">创建竞赛</BaseButton>
    </div>
  </div>

  <div v-if="loading" class="panel"><p class="text-muted">正在加载竞赛数据…</p></div>
  <AlertMessage v-else-if="loadError" tone="error">
    {{ loadError }}
    <template v-if="loadNotReady">竞赛接口将在核心后端第三批交付后可用。</template>
    <div style="margin-top:10px"><BaseButton variant="secondary" @click="load">重新加载</BaseButton></div>
  </AlertMessage>
  <template v-else>
    <section class="panel" aria-label="竞赛列表">
      <div class="section-heading" style="margin:0 0 14px">
        <h2>班级竞赛</h2>
        <span class="small text-muted">{{ competitions.length }} 个竞赛</span>
      </div>
      <EmptyState v-if="!competitions.length" title="暂无竞赛"
        :description="isTeacher ? '在草稿任务上创建竞赛，随任务发布一同冻结条件。' : '教师创建并发布竞赛后，这里会显示公开排行榜。'" />
      <div v-else class="competition-list">
        <button v-for="item in competitions" :key="item.id" type="button"
          :class="['competition-item', { active: item.id === selectedId }]" @click="select(item.id)">
          <span class="item-title">{{ item.title }}</span>
          <span class="small text-muted">关联任务：{{ taskTitle(item.task_id) }}</span>
          <span class="item-meta">
            <StatusBadge :tone="competitionTone(item.status)">{{ statusLabels[item.status] ?? item.status }}</StatusBadge>
            <span class="small text-muted">{{ item.published_at ? `发布于 ${dateTime(item.published_at)}` : '未发布' }}</span>
          </span>
        </button>
      </div>

      <div v-if="createOpen" class="create-block">
        <h3>创建竞赛</h3>
        <p class="small text-muted" style="margin-bottom:12px">竞赛挂在草稿任务上：统一使用该任务的截止时间、市场条件与评分权重，随任务发布一同冻结，各组获得相同初始条件。</p>
        <div class="create-grid">
          <FormField label="选择草稿任务" for-id="competition-task">
            <select id="competition-task" v-model="createForm.task_id">
              <option :value="0" disabled>选择任务</option>
              <option v-for="task in draftTasks" :key="task.id" :value="task.id">{{ task.title }}（截止 {{ dateTime(task.ends_at) }}）</option>
            </select>
          </FormField>
          <FormField label="竞赛标题" for-id="competition-title">
            <input id="competition-title" v-model="createForm.title" maxlength="200" placeholder="例如：助农直播同场竞赛" />
          </FormField>
        </div>
        <p v-if="!draftTasks.length" class="small text-muted">当前没有草稿任务；请先在教学管理中创建任务。</p>
        <AlertMessage v-if="createFeedback.error.value" tone="error">{{ createFeedback.error.value }}</AlertMessage>
        <AlertMessage v-else-if="createFeedback.notice.value" tone="success">{{ createFeedback.notice.value }}</AlertMessage>
        <div class="heading-actions">
          <BaseButton :loading="createFeedback.busy.value" :disabled="!draftTasks.length" @click="submitCreate">创建竞赛</BaseButton>
        </div>
      </div>
    </section>

    <template v-if="selected">
      <section class="panel" aria-label="排行榜">
        <div class="section-heading" style="margin:0 0 14px">
          <h2>{{ selected.title }} · 排行榜</h2>
          <div class="stage-toggle" role="tablist">
            <button type="button" :class="['stage', { active: stage === 'provisional' }]" @click="stage = 'provisional'">临时榜（按系统分）</button>
            <button type="button" :class="['stage', { active: stage === 'final' }]" @click="stage = 'final'">最终榜（按综合分）</button>
          </div>
        </div>
        <AlertMessage v-if="leaderboardError" :tone="leaderboardNotReady ? 'info' : 'error'">
          {{ leaderboardError }}
          <template v-if="leaderboardNotReady">榜单汇总接口将在核心后端第三批交付后可用。</template>
          <div style="margin-top:10px"><BaseButton variant="secondary" @click="loadLeaderboard">重试</BaseButton></div>
        </AlertMessage>
        <div v-else-if="leaderboardLoading" class="text-muted small">正在读取榜单…</div>
        <template v-else-if="leaderboard">
          <div class="rule-grid">
            <div><span>规则版本</span><strong style="font-size:12px">{{ leaderboard.rules_version }}</strong></div>
            <div><span>统一截止时间</span><strong style="font-size:12px">{{ dateTime(leaderboard.deadline) }}</strong></div>
            <div><span>评分权重</span><strong style="font-size:12px">{{ weightLine }}</strong></div>
            <div><span>排序规则</span><strong style="font-size:12px">{{ sortRuleText }}</strong></div>
          </div>
          <p class="small text-muted" style="margin:10px 0">
            {{ stage === 'provisional' ? '临时榜按当前系统分排序，包含进行中的小组，不代表最终名次。' : '最终榜仅对已评分组按综合分（系统分×0.7 + 主观分×0.3）排序；未完成或未评分组不参与排名。' }}
          </p>
          <DataTable :columns="entryColumns" :rows="entryRows">
            <template #cell-status="{ row }">
              <StatusBadge tone="success">{{ statusLabels[String(row.status)] ?? row.status }}</StatusBadge>
            </template>
          </DataTable>
          <template v-if="pendingRows.length">
            <h3 class="pending-title">未完成 / 未评分小组（不参与排名）</h3>
            <DataTable :columns="entryColumns" :rows="pendingRows">
              <template #cell-status="{ row }">
                <StatusBadge tone="warning">{{ pendingLabel(String(row.status)) }}</StatusBadge>
              </template>
            </DataTable>
          </template>
          <p v-else-if="(leaderboard.entries ?? []).length" class="small text-muted">所有参赛组均已完成并评分。</p>
        </template>
        <EmptyState v-else title="暂无榜单数据" description="任务发布并产生经营数据后，这里会显示排行榜。" />
        <p class="small text-muted" style="margin-bottom:0">
          {{ isTeacher ? '名次与指标全部来自后端统一汇总；下方对比查看各组策略与证据。' : '学生端仅显示公开汇总排名；详细组间对比与证据仅教师可见。' }}
        </p>
      </section>

      <section v-if="isTeacher" class="panel" aria-label="组间对比">
        <div class="section-heading" style="margin:0 0 14px">
          <h2>组间对比</h2>
          <BaseButton variant="secondary" @click="loadComparison">重新读取</BaseButton>
        </div>
        <AlertMessage v-if="comparisonError" :tone="comparisonNotReady ? 'info' : 'error'">
          {{ comparisonError }}
          <template v-if="comparisonNotReady">对比汇总接口将在核心后端第三批交付后可用。</template>
          <div style="margin-top:10px"><BaseButton variant="secondary" @click="loadComparison">重试</BaseButton></div>
        </AlertMessage>
        <template v-else-if="comparison">
          <h3 class="pending-title">策略对比</h3>
          <DataTable :columns="strategyColumns" :rows="strategyRows" />
          <h3 class="pending-title">过程与结果对比</h3>
          <DataTable :columns="resultColumns" :rows="resultRows">
            <template #cell-evidence="{ row }">
              <RouterLink :to="`/teacher/sessions/${row.sessionId}/evidence`" class="text-button">查看证据</RouterLink>
            </template>
          </DataTable>
          <p class="small text-muted" style="margin-bottom:0">对比只能说明规则仿真中的关联，不宣称现实经营因果；证据入口进入各组场次的只读记录。</p>
        </template>
        <EmptyState v-else title="暂无可对比数据" description="各组产生经营数据后，这里会显示策略、过程与结果对比。" />
      </section>
    </template>
  </template>
</template>

<style scoped>
.heading-actions{display:flex;gap:10px;align-items:center;flex-wrap:wrap}
.competition-list{display:flex;flex-direction:column;gap:8px}
.competition-item{display:flex;flex-direction:column;gap:4px;text-align:left;border:1px solid var(--line);border-radius:10px;background:#fff;padding:12px 14px}
.competition-item.active{border-color:var(--accent);background:#e9f3ed}
.item-title{font-weight:600;font-size:14px}
.item-meta{display:flex;gap:10px;align-items:center}
.create-block{border-top:1px solid var(--line);margin-top:16px;padding-top:16px}
.create-block h3{font-size:14px;margin:0 0 8px}
.create-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:0 16px;max-width:820px}
.stage-toggle{display:flex;gap:6px}
.stage{border:1px solid var(--line);background:#fff;border-radius:20px;padding:7px 14px;font-size:12px;color:#5d6a63}
.stage.active{background:#e9f3ed;color:#17654d;font-weight:600;border-color:#bcd9c8}
.rule-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:10px 18px;font-size:12px}
.rule-grid span{display:block;color:var(--muted);margin-bottom:4px}
.pending-title{font-size:14px;margin:18px 0 10px}
</style>
