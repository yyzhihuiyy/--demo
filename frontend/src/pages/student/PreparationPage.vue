<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import {
  allowed, centsToYuanText, completePreparation, notReadyText, positiveCents, positions, productRoles,
  scriptKinds, statusLabels, useFeedback, useSession, yuanToCents, api,
  type MarketSample,
} from '../../features/student/workspace'
import type { Checklist, Preparation, Product, SessionProduct } from '../../shared/contracts'
import AlertMessage from '../../shared/components/AlertMessage.vue'
import BaseButton from '../../shared/components/BaseButton.vue'
import EmptyState from '../../shared/components/EmptyState.vue'
import FormField from '../../shared/components/FormField.vue'
import StatusBadge from '../../shared/components/StatusBadge.vue'
import SessionNav from '../../features/student/SessionNav.vue'
import { useAuth } from '../../shared/auth'
import { dateTime, money, percent } from '../../shared/format'
import { useRoute } from 'vue-router'

const route = useRoute()
const sessionId = computed(() => Number(route.params.id))
const { user } = useAuth()
const { detail, classroom, task, team, members, loading, loadError, notReady, load } = useSession(() => sessionId.value)

const tabs = [
  { key: 'brief', label: '01 任务说明' },
  { key: 'research', label: '02 市场调研' },
  { key: 'assortment', label: '03 货盘与采购' },
  { key: 'script', label: '04 策划脚本' },
  { key: 'promotion', label: '05 投流与优惠' },
  { key: 'room', label: '06 直播间装修' },
  { key: 'checklist', label: '07 开播检查' },
] as const
const activeTab = ref<string>('brief')

const prep = ref(completePreparation())
const version = ref(0)
const catalog = ref<Product[]>([])
const catalogError = ref('')
const market = ref<MarketSample | null>(null)
const marketError = ref('')
const checklist = ref<Checklist | null>(null)
const checklistError = ref('')
const checklistLoading = ref(false)

interface DraftRow {
  session_product_id: number | null
  product_id: number
  title: string
  cost_cents: number
  positioning: 'traffic' | 'profit' | 'image'
  selling_points: string
  priceInput: string
  saved_price_cents: number | null
  sort_order: number
  purchased_qty: number
  stock_qty: number
  reference_price_cents: number
}
const rows = ref<DraftRow[]>([])
const purchaseQty = ref<Record<number, string>>({})
const promotionBudgetInput = ref('0')
const couponInput = ref('0')

const prepFeedback = useFeedback()
const assortmentFeedback = useFeedback()
const purchaseFeedback = useFeedback()
const conflictReloadHint = '组员已保存了更新的内容，为避免覆盖，请点击重新加载后再修改。'

const editable = computed(() => allowed(detail.value, 'edit_preparation', ['preparing']))
const catalogById = computed(() => new Map(catalog.value.map(product => [product.id, product])))
const cashBalance = computed(() => detail.value?.metrics.cash_balance_cents ?? null)
const initialBudget = computed(() => detail.value?.session.initial_budget_cents ?? null)

function rebuildRows(products: SessionProduct[]) {
  rows.value = products.map(item => ({
    session_product_id: item.id,
    product_id: item.product_id,
    title: item.title,
    cost_cents: item.cost_cents,
    positioning: item.positioning,
    selling_points: item.selling_points ?? '',
    priceInput: centsToYuanText(item.sale_price_cents),
    saved_price_cents: item.sale_price_cents,
    sort_order: item.sort_order ?? 0,
    purchased_qty: item.purchased_qty ?? 0,
    stock_qty: item.stock_qty ?? 0,
    reference_price_cents: catalogById.value.get(item.product_id)?.reference_price_cents ?? item.cost_cents,
  }))
  purchaseQty.value = {}
}

function syncForm() {
  prep.value = completePreparation(detail.value?.preparation)
  version.value = detail.value?.session.preparation_version ?? 0
  promotionBudgetInput.value = centsToYuanText(prep.value.promotion.budget_cents ?? 0)
  couponInput.value = centsToYuanText(prep.value.coupon.discount_cents ?? 0)
}

async function reloadAll() {
  await load()
  if (detail.value) { syncForm(); rebuildRows(detail.value.products) }
  prepFeedback.error.value = ''; prepFeedback.notice.value = ''
}

onMounted(async () => {
  await load()
  if (detail.value) { syncForm(); rebuildRows(detail.value.products) }
  const [catalogResult, marketResult] = await Promise.allSettled([api<Product[]>('/products'), api<MarketSample>('/market-sample')])
  if (catalogResult.status === 'fulfilled') {
    catalog.value = catalogResult.value
    if (detail.value) rebuildRows(detail.value.products)
  } else catalogError.value = notReadyText(catalogResult.reason)
  if (marketResult.status === 'fulfilled') market.value = marketResult.value
  else marketError.value = notReadyText(marketResult.reason)
})
watch(sessionId, () => { void reloadAll() })

async function savePreparation() {
  const budgetCents = yuanToCents(promotionBudgetInput.value || '0')
  const couponCents = yuanToCents(couponInput.value || '0')
  if (!Number.isInteger(budgetCents) || budgetCents < 0 || !Number.isInteger(couponCents) || couponCents < 0) {
    prepFeedback.error.value = '投流预算与优惠券金额需为不小于 0 的有效金额。'; return
  }
  await prepFeedback.run(async () => {
    const result = await prepFeedback.write<{ preparation: Preparation; version: number }>(
      `/sessions/${sessionId.value}/preparation`,
      {
        research: prep.value.research,
        plan: prep.value.plan,
        script: prep.value.script,
        promotion: { channel: 'simulated_feed', budget_cents: budgetCents, audience: prep.value.promotion.audience ?? '' },
        room: prep.value.room,
        coupon: { discount_cents: couponCents },
        expected_version: version.value,
      },
      'PUT',
    )
    prep.value = completePreparation(result.preparation)
    version.value = result.version
    if (detail.value) detail.value.session.preparation_version = result.version
    await load()
    syncForm()
  }, '准备内容已保存，组员刷新后可见。')
}

function addProduct(product: Product) {
  if (rows.value.some(row => row.product_id === product.id)) return
  rows.value.push({
    session_product_id: null, product_id: product.id, title: product.title, cost_cents: product.cost_cents,
    positioning: 'profit', selling_points: product.selling_points ?? '', priceInput: centsToYuanText(product.reference_price_cents),
    saved_price_cents: null, sort_order: rows.value.length + 1, purchased_qty: 0, stock_qty: 0,
    reference_price_cents: product.reference_price_cents,
  })
}
function removeRow(row: DraftRow) {
  if (row.purchased_qty > 0) { assortmentFeedback.error.value = '已采购的商品不能从货盘移除，只能调整后续采购。'; return }
  rows.value = rows.value.filter(item => item.product_id !== row.product_id)
}

const validRows = computed(() => rows.value.map(row => ({ row, price: positiveCents(row.priceInput) })).filter(entry => entry.price !== null))
const invalidPriceRows = computed(() => rows.value.length - validRows.value.length)

async function saveAssortment() {
  if (!rows.value.length) { assortmentFeedback.error.value = '请先从商品库选择商品组成货盘。'; return }
  if (invalidPriceRows.value > 0) { assortmentFeedback.error.value = '存在无效直播价：请为每件商品填写大于 0 的价格（单位：元）。'; return }
  await assortmentFeedback.run(async () => {
    const result = await assortmentFeedback.write<{ products: SessionProduct[] }>(
      `/sessions/${sessionId.value}/assortment`,
      { items: rows.value.map(row => ({
        product_id: row.product_id, positioning: row.positioning, selling_points: row.selling_points,
        sale_price_cents: positiveCents(row.priceInput) as number, sort_order: row.sort_order,
      })) },
      'PUT',
    )
    if (detail.value) detail.value.products = result.products
    rebuildRows(result.products)
  }, '货盘已保存，可以继续追加采购。')
}

async function submitPurchase() {
  const items = rows.value
    .filter(row => row.session_product_id !== null)
    .map(row => ({ row, qty: Number(purchaseQty.value[row.session_product_id as number] ?? 0) }))
    .filter(entry => Number.isInteger(entry.qty) && entry.qty > 0)
  if (!items.length) { purchaseFeedback.error.value = '请先为已保存的货盘商品填写采购数量（正整数）。'; return }
  await purchaseFeedback.run(async () => {
    const result = await purchaseFeedback.write<{ products: SessionProduct[]; cash_balance_cents: number }>(
      `/sessions/${sessionId.value}/purchases`,
      { items: items.map(entry => ({ session_product_id: entry.row.session_product_id, qty: entry.qty })) },
    )
    if (detail.value) {
      detail.value.products = result.products
      detail.value.metrics.cash_balance_cents = result.cash_balance_cents
    }
    rebuildRows(result.products)
  }, '采购已执行：资金已扣除、库存已增加。')
}

const purchaseCost = computed(() => rows.value.reduce((sum, row) => sum + row.purchased_qty * row.cost_cents, 0))
const estimatedMargin = computed(() => validRows.value.reduce((sum, entry) => sum + (entry.price as number) * entry.row.purchased_qty, 0) - purchaseCost.value)
const unsavedCount = computed(() => rows.value.filter(row => row.session_product_id === null).length)

function addScriptSegment() {
  const count = prep.value.script.filter(segment => segment.kind === 'product').length
  prep.value.script.push({ id: `product-${count + 1}-${Date.now() % 1000}`, kind: 'product', product_id: null, text: '' })
}
function removeScriptSegment(id: string) {
  if (prep.value.script.length <= 4) { prepFeedback.error.value = '开场、讲解、互动、收尾四类段落不可删除。'; return }
  prep.value.script = prep.value.script.filter(segment => segment.id !== id)
}

async function loadChecklist() {
  checklistLoading.value = true; checklistError.value = ''
  try { checklist.value = await api<Checklist>(`/sessions/${sessionId.value}/checklist`) }
  catch (error) { checklistError.value = notReadyText(error); checklist.value = null }
  finally { checklistLoading.value = false }
}
watch(activeTab, tab => { if (tab === 'checklist') void loadChecklist() })

function targetTab(target: string) {
  const value = target.toLowerCase()
  if (value.includes('research')) return 'research'
  if (value.includes('assortment') || value.includes('product') || value.includes('purchase') || value.includes('stock') || value.includes('price')) return 'assortment'
  if (value.includes('script')) return 'script'
  if (value.includes('promotion') || value.includes('coupon')) return 'promotion'
  if (value.includes('room') || value.includes('title') || value.includes('announcement') || value.includes('decor')) return 'room'
  return 'brief'
}
const failedItems = computed(() => checklist.value?.items.filter(item => !item.passed) ?? [])
const memberName = (userId: number) => classroom.value?.students.find(student => student.id === userId)?.username ?? `学员#${userId}`
</script>

<template>
  <SessionNav :id="sessionId" />
  <div class="page-heading">
    <div>
      <p class="eyebrow">PREPARATION</p>
      <h1>经营准备</h1>
      <p>调研、货盘采购、脚本、投流与直播间装修；保存后同组共享，开播前完成逐项检查。</p>
    </div>
    <StatusBadge v-if="detail" :tone="detail.session.status === 'preparing' ? 'warning' : 'neutral'">
      场次状态：{{ statusLabels[detail.session.status] ?? detail.session.status }}
    </StatusBadge>
  </div>

  <div v-if="loading" class="panel"><p class="text-muted">正在加载场次…</p></div>
  <AlertMessage v-else-if="loadError" tone="error">
    {{ loadError }}
    <template v-if="notReady">后端经营接口正在接入中；接口就绪后可点击重试。</template>
    <div style="margin-top:10px"><BaseButton variant="secondary" @click="reloadAll">重新加载</BaseButton></div>
  </AlertMessage>
  <template v-else-if="detail">
    <AlertMessage v-if="!editable" tone="info">
      当前场次为「{{ statusLabels[detail.session.status] ?? detail.session.status }}」，准备内容已锁定：以下表单仅可查看，如需调整请回到对应阶段或联系教师。
    </AlertMessage>
    <AlertMessage v-if="prepFeedback.conflict.value" tone="error">{{ conflictReloadHint }}<div style="margin-top:10px"><BaseButton variant="secondary" @click="reloadAll">重新加载最新内容</BaseButton></div></AlertMessage>

    <div class="student-tabs" role="tablist">
      <button v-for="tab in tabs" :key="tab.key" :class="{ active: activeTab === tab.key }" @click="activeTab = tab.key">{{ tab.label }}</button>
    </div>

    <section v-show="activeTab === 'brief'" class="student-stack" aria-label="任务说明">
      <div class="panel">
        <div class="student-section-title"><h2>{{ task?.title ?? '实训任务' }}</h2><span class="small text-muted">教学仿真任务 · 规则版本 {{ task?.rules_version ?? '—' }}</span></div>
        <p class="student-caption">{{ task?.description || '暂无任务说明' }}</p>
        <div class="student-stats" style="margin:18px 0">
          <div><span>目标人群</span><strong style="font-size:13px">{{ task?.target_audience || '—' }}</strong></div>
          <div><span>初始预算</span><strong>{{ money(initialBudget ?? 0) }}</strong></div>
          <div><span>当前资金余额</span><strong>{{ cashBalance == null ? '—' : money(cashBalance) }}</strong></div>
          <div><span>GMV 目标</span><strong>{{ money(task?.target_gmv_cents ?? 0) }}</strong></div>
          <div><span>任务时间</span><strong style="font-size:12px">{{ dateTime(task?.starts_at) }} ～ {{ dateTime(task?.ends_at) }}</strong></div>
        </div>
        <p class="student-caption">任务由教师发布后规则冻结；所有金额、观众与订单均为教学仿真数据。</p>
      </div>
      <div class="panel">
        <div class="student-section-title"><h2>小组与岗位</h2></div>
        <p v-if="team" class="student-caption" style="margin-bottom:12px">{{ team.name }} · 同组账号读写同一场次，操作记录按登录身份保存。</p>
        <div class="student-actions">
          <span v-for="member in members" :key="member.user_id" class="student-member" :style="member.user_id === user?.id ? 'background:#dff0e4;color:#1f6b49;font-weight:600' : ''">
            {{ memberName(member.user_id) }} · {{ positions[member.position] ?? member.position }}
          </span>
        </div>
        <p v-if="!members.length" class="student-caption">尚未查询到小组成员（接口数据待接入）。</p>
      </div>
    </section>

    <fieldset class="student-readonly" :disabled="!editable">
      <section v-show="activeTab === 'research'" class="student-stack" aria-label="市场调研">
        <div class="panel">
          <div class="student-section-title"><h2>市场调研参考</h2><span class="small text-muted">来源：教学样例（source={{ market?.source ?? 'sample' }}）</span></div>
          <AlertMessage v-if="marketError" tone="error">{{ marketError }}（调研样例接口尚未就绪时，可先填写下方判断，接口就绪后刷新查看）</AlertMessage>
          <template v-else-if="market">
            <p class="student-caption">{{ market.notice ?? '以下为教学样例数据，并非实时市场数据，仅用于练习判断。' }}</p>
            <div class="table-wrap">
              <table>
                <thead><tr><th>品类</th><th>热度</th><th>价格带</th></tr></thead>
                <tbody>
                  <tr v-for="category in market.categories" :key="category.name"><td>{{ category.name }}</td><td>{{ category.heat }}</td><td>{{ category.price_band }}</td></tr>
                  <tr v-if="!market.categories.length"><td colspan="3" class="text-muted">暂无样例</td></tr>
                </tbody>
              </table>
            </div>
            <div class="student-stats" style="margin-top:16px">
              <div v-for="audience in market.audience" :key="audience.name"><span>{{ audience.name }}</span><strong>{{ percent(audience.share) }}</strong></div>
            </div>
          </template>
          <p v-else class="text-muted small">正在加载调研样例…</p>
        </div>
        <div class="panel">
          <div class="student-section-title"><h2>调研纪要与选品理由</h2><span class="small text-muted">保存写入本场次，教师端可查看</span></div>
          <AlertMessage v-if="prepFeedback.error.value" tone="error">{{ prepFeedback.error.value }}</AlertMessage>
          <AlertMessage v-if="prepFeedback.notice.value" tone="success">{{ prepFeedback.notice.value }}</AlertMessage>
          <div class="student-form-grid">
            <FormField label="目标客群判断" for-id="research-audience" hint="例：以家庭采购为主，价格敏感、注重产地与品质">
              <textarea id="research-audience" v-model="prep.research.audience" rows="3" />
            </FormField>
            <FormField label="竞品判断" for-id="research-competitor" hint="记录同类直播间价格与卖点的观察结论">
              <textarea id="research-competitor" v-model="prep.research.competitor_notes" rows="3" />
            </FormField>
            <FormField label="价格带判断" for-id="research-price" hint="结合样例价格带，判断可接受售价区间">
              <textarea id="research-price" v-model="prep.research.price_notes" rows="3" />
            </FormField>
            <FormField label="选品理由" for-id="research-reason" hint="说明为什么选择这些商品进入货盘">
              <textarea id="research-reason" v-model="prep.research.selection_reason" rows="3" />
            </FormField>
          </div>
          <div class="student-footer">
            <span class="small text-muted">当前版本 v{{ version }} · 保存使用乐观锁，冲突时会提示重新加载</span>
            <BaseButton :loading="prepFeedback.busy.value" :disabled="!editable" @click="savePreparation">保存调研纪要</BaseButton>
          </div>
        </div>
      </section>

      <section v-show="activeTab === 'assortment'" class="student-stack" aria-label="货盘与采购">
        <div class="panel">
          <div class="student-section-title">
            <h2>商品库（教学预置）</h2>
            <span class="small text-muted">成本与供应商固定 · 已选 {{ rows.length }} 件</span>
          </div>
          <AlertMessage v-if="catalogError" tone="error">{{ catalogError }}</AlertMessage>
          <template v-else>
            <div class="student-product-list">
              <div v-for="product in catalog" :key="product.id" class="student-product-item">
                <span class="student-product-emoji">{{ product.image_or_placeholder || '🛒' }}</span>
                <div class="student-product-info">
                  <strong>{{ product.title }}</strong>
                  <small>{{ product.category }} · 成本 {{ money(product.cost_cents) }} · 参考价 {{ money(product.reference_price_cents) }}</small>
                  <small class="text-muted">{{ product.selling_points }}</small>
                </div>
                <BaseButton variant="secondary" :disabled="rows.some(row => row.product_id === product.id) || !editable" @click="addProduct(product)">
                  {{ rows.some(row => row.product_id === product.id) ? '已入货盘' : '选入货盘' }}
                </BaseButton>
              </div>
            </div>
            <p v-if="!catalog.length" class="text-muted small">正在加载商品库…</p>
          </template>
        </div>

        <div class="panel">
          <div class="student-section-title">
            <h2>三类货盘 · 定价与采购</h2>
            <span class="small text-muted">余额不足时后端会拒绝采购</span>
          </div>
          <AlertMessage v-if="assortmentFeedback.error.value" tone="error">{{ assortmentFeedback.error.value }}</AlertMessage>
          <AlertMessage v-if="assortmentFeedback.notice.value" tone="success">{{ assortmentFeedback.notice.value }}</AlertMessage>
          <AlertMessage v-if="unsavedCount" tone="info">有 {{ unsavedCount }} 件新选商品尚未保存货盘；保存货盘后才能采购。</AlertMessage>
          <EmptyState v-if="!rows.length" title="货盘为空" description="先从上方商品库选入商品，配置引流款／利润款／形象款定位与直播价。" />
          <div v-else class="table-wrap">
            <table>
              <thead><tr><th>商品</th><th>定位</th><th>卖点（可编辑）</th><th>直播价（元）</th><th>讲解顺序</th><th>成本</th><th>已采购／库存</th><th>追加采购数量</th><th>单品预计毛利</th><th></th></tr></thead>
              <tbody>
                <tr v-for="row in rows" :key="row.product_id">
                  <td><strong>{{ row.title }}</strong><br /><small class="text-muted">参考价 {{ money(row.reference_price_cents) }}</small></td>
                  <td>
                    <select v-model="row.positioning" :disabled="!editable">
                      <option v-for="(label, key) in productRoles" :key="key" :value="key">{{ label }}</option>
                    </select>
                  </td>
                  <td><textarea v-model="row.selling_points" rows="2" style="min-width:170px" :disabled="!editable" /></td>
                  <td><input v-model="row.priceInput" type="number" min="0.01" step="0.01" style="width:90px" :disabled="!editable" /></td>
                  <td><input v-model.number="row.sort_order" type="number" min="1" step="1" style="width:64px" :disabled="!editable" /></td>
                  <td>{{ money(row.cost_cents) }}</td>
                  <td>{{ row.purchased_qty }} / {{ row.stock_qty }}</td>
                  <td>
                    <input v-if="row.session_product_id" v-model="purchaseQty[row.session_product_id ?? 0]" type="number" min="1" step="1" placeholder="0" style="width:70px" :disabled="!editable" />
                    <span v-else class="small text-muted">先保存货盘</span>
                  </td>
                  <td>{{ row.purchased_qty > 0 && positiveCents(row.priceInput) ? money((positiveCents(row.priceInput) as number) * row.purchased_qty - row.cost_cents * row.purchased_qty) : '—' }}</td>
                  <td><button v-if="editable" class="text-button" type="button" @click="removeRow(row)">移除</button></td>
                </tr>
              </tbody>
            </table>
          </div>
          <div class="student-stats" style="margin:18px 0">
            <div><span>初始预算</span><strong>{{ money(initialBudget ?? 0) }}</strong></div>
            <div><span>已投入采购成本</span><strong>{{ money(purchaseCost) }}</strong></div>
            <div><span>当前资金余额（服务端）</span><strong>{{ cashBalance == null ? '—' : money(cashBalance) }}</strong></div>
            <div><span>组合预计毛利</span><strong>{{ money(estimatedMargin) }} *</strong></div>
          </div>
          <p class="student-caption">* 预计毛利为估算值：假设已采购库存全部按当前直播价售出，仅供决策参考，不代表实际经营利润。</p>
          <div class="student-footer">
            <span class="small text-muted">先保存货盘，再追加采购；采购立即扣减资金</span>
            <div class="student-actions">
              <BaseButton variant="secondary" :loading="assortmentFeedback.busy.value" :disabled="!editable" @click="saveAssortment">保存货盘</BaseButton>
              <BaseButton :loading="purchaseFeedback.busy.value" :disabled="!editable" @click="submitPurchase">执行采购</BaseButton>
            </div>
          </div>
          <AlertMessage v-if="purchaseFeedback.error.value" tone="error" style="margin-top:12px">{{ purchaseFeedback.error.value }}</AlertMessage>
          <AlertMessage v-if="purchaseFeedback.notice.value" tone="success" style="margin-top:12px">{{ purchaseFeedback.notice.value }}</AlertMessage>
        </div>
      </section>

      <section v-show="activeTab === 'script'" class="student-stack" aria-label="策划脚本">
        <div class="panel">
          <div class="student-section-title">
            <h2>直播策划与脚本</h2>
            <BaseButton variant="secondary" :disabled="!editable" @click="addScriptSegment">＋ 添加讲解段</BaseButton>
          </div>
          <p class="student-caption">开场、商品讲解、互动、收尾四类段落必填；讲解段需关联货盘中的商品（使用商品库编号），直播时逐段执行。</p>
          <AlertMessage v-if="prepFeedback.error.value" tone="error">{{ prepFeedback.error.value }}</AlertMessage>
          <AlertMessage v-if="prepFeedback.notice.value" tone="success">{{ prepFeedback.notice.value }}</AlertMessage>
          <div class="student-form-grid">
            <FormField label="直播主题" for-id="plan-theme"><input id="plan-theme" v-model="prep.plan.theme" :disabled="!editable" /></FormField>
            <FormField label="目标客群" for-id="plan-audience"><input id="plan-audience" v-model="prep.plan.target_audience" :disabled="!editable" /></FormField>
          </div>
          <div class="student-stack">
            <div v-for="segment in prep.script" :key="segment.id" class="student-muted-box">
              <div class="student-actions" style="margin-bottom:10px">
                <strong>{{ scriptKinds[segment.kind] ?? segment.kind }}</strong>
                <select v-if="segment.kind === 'product'" v-model="segment.product_id" :disabled="!editable" style="width:auto">
                  <option :value="null">请选择关联商品</option>
                  <option v-for="product in catalog" :key="product.id" :value="product.id">{{ product.id }} · {{ product.title }}</option>
                </select>
                <span class="small text-muted">段落 ID：{{ segment.id }}</span>
                <button v-if="editable && segment.kind === 'product' && prep.script.length > 4" class="text-button" type="button" @click="removeScriptSegment(segment.id)">删除该讲解段</button>
              </div>
              <textarea v-model="segment.text" rows="3" :disabled="!editable" :placeholder="segment.kind === 'product' ? '写入该商品的讲解话术：卖点、价格、使用场景…' : '写入该段落话术…'" />
            </div>
          </div>
          <div class="student-footer">
            <span class="small text-muted">讲解段未关联商品或文本为空，可能无法通过开播检查</span>
            <BaseButton :loading="prepFeedback.busy.value" :disabled="!editable" @click="savePreparation">保存策划与脚本</BaseButton>
          </div>
        </div>
      </section>

      <section v-show="activeTab === 'promotion'" class="student-stack" aria-label="投流与优惠">
        <div class="panel">
          <div class="student-section-title"><h2>投流计划（单渠道）</h2><span class="small text-muted">教学仿真渠道 simulated_feed</span></div>
          <p class="student-caption">投流预算在准备阶段受剩余资金约束；首次开始直播时一次性扣除全部预算，恢复直播不重复扣款。投流会影响仿真进房人数。</p>
          <AlertMessage v-if="prepFeedback.error.value" tone="error">{{ prepFeedback.error.value }}</AlertMessage>
          <AlertMessage v-if="prepFeedback.notice.value" tone="success">{{ prepFeedback.notice.value }}</AlertMessage>
          <div class="student-form-grid">
            <FormField label="投流预算（元）" for-id="promotion-budget" :hint="`当前资金余额 ${cashBalance == null ? '—' : money(cashBalance)}；预算不能超过剩余资金`">
              <input id="promotion-budget" v-model="promotionBudgetInput" type="number" min="0" step="0.01" :disabled="!editable" />
            </FormField>
            <FormField label="投放目标人群" for-id="promotion-audience" hint="例：家庭采购人群">
              <input id="promotion-audience" v-model="prep.promotion.audience" :disabled="!editable" />
            </FormField>
          </div>
          <div class="student-section-title" style="margin-top:26px"><h3>优惠券（场次级固定减额）</h3></div>
          <p class="student-caption">整场直播共用一张固定减额券，作用于后续成交；订单会保存原价、优惠与实付快照，实付至少 0.01 元。</p>
          <div class="student-form-grid">
            <FormField label="优惠券金额（元）" for-id="coupon-discount" hint="填 0 表示不发券；直播中由场控触发发放">
              <input id="coupon-discount" v-model="couponInput" type="number" min="0" step="0.01" :disabled="!editable" />
            </FormField>
          </div>
          <div class="student-footer">
            <span class="small text-muted">保存后写入本场次配置</span>
            <BaseButton :loading="prepFeedback.busy.value" :disabled="!editable" @click="savePreparation">保存投流与优惠</BaseButton>
          </div>
        </div>
      </section>

      <section v-show="activeTab === 'room'" class="student-stack" aria-label="直播间装修">
        <div class="panel">
          <div class="student-section-title"><h2>直播间装修</h2><span class="small text-muted">固定模板 · 准备页与直播页共用</span></div>
          <AlertMessage v-if="prepFeedback.error.value" tone="error">{{ prepFeedback.error.value }}</AlertMessage>
          <AlertMessage v-if="prepFeedback.notice.value" tone="success">{{ prepFeedback.notice.value }}</AlertMessage>
          <div class="student-form-grid">
            <FormField label="房间主题模板" for-id="room-theme" hint="本版固定为助农模板">
              <input id="room-theme" :value="prep.room.theme === 'agriculture' ? '助农主题模板' : prep.room.theme" disabled />
            </FormField>
            <FormField label="直播间标题" for-id="room-title" hint="开播检查要求标题非空">
              <input id="room-title" v-model="prep.room.title" :disabled="!editable" placeholder="例：产地直供 · 助农专场" />
            </FormField>
            <div class="student-wide">
              <FormField label="直播间公告" for-id="room-announcement" hint="直播页顶部常驻展示，直播中可由场控更新">
                <textarea id="room-announcement" v-model="prep.room.announcement" rows="2" :disabled="!editable" placeholder="例：全场包邮 · 下单后 48 小时内发货" />
              </FormField>
            </div>
          </div>
          <div class="student-section-title" style="margin-top:26px"><h3>装修预览</h3></div>
          <div class="student-room-preview">
            <div class="student-room-banner"><strong>{{ prep.room.title || '（未设置直播间标题）' }}</strong><span>{{ prep.room.announcement || '（未设置公告）' }}</span></div>
            <div class="student-room-cards">
              <div v-for="row in [...rows].sort((a, b) => a.sort_order - b.sort_order).slice(0, 6)" :key="row.product_id" class="student-room-card">
                <span>{{ catalogById.get(row.product_id)?.image_or_placeholder || '🛒' }}</span>
                <strong>{{ row.title }}</strong>
                <small>{{ productRoles[row.positioning] }} · {{ positiveCents(row.priceInput) ? money(positiveCents(row.priceInput) as number) : '未定价' }}</small>
              </div>
              <p v-if="!rows.length" class="small text-muted">货盘保存后，商品卡会出现在这里。</p>
            </div>
          </div>
          <div class="student-footer">
            <span class="small text-muted">演示主播素材为固定占位，不提供自定义上传</span>
            <BaseButton :loading="prepFeedback.busy.value" :disabled="!editable" @click="savePreparation">保存直播间装修</BaseButton>
          </div>
        </div>
      </section>

      <section v-show="activeTab === 'checklist'" class="student-stack" aria-label="开播检查">
        <div class="panel">
          <div class="student-section-title">
            <h2>开播检查</h2>
            <BaseButton variant="secondary" :loading="checklistLoading" @click="loadChecklist">刷新检查结果</BaseButton>
          </div>
          <AlertMessage v-if="checklistError" tone="error">{{ checklistError }}（检查接口尚未就绪时，请完成各页签保存后再试）</AlertMessage>
          <template v-else-if="checklist">
            <p class="student-caption">
              共 {{ checklist.items.length }} 项检查；
              <template v-if="checklist.can_start">全部通过，可以进入直播工作台开始直播。</template>
              <template v-else>尚有 {{ failedItems.length }} 项未通过，点击「去调整」跳到对应页签。</template>
            </p>
            <div class="student-stack" style="margin-top:16px">
              <div v-for="item in checklist.items" :key="item.key" class="student-check-item" :data-passed="item.passed">
                <StatusBadge :tone="item.passed ? 'success' : 'danger'">{{ item.passed ? '通过' : '未通过' }}</StatusBadge>
                <div style="flex:1">
                  <strong class="small">{{ item.message }}</strong>
                  <small class="text-muted" style="display:block;margin-top:4px">检查项 {{ item.key }} · 目标 {{ item.target }}</small>
                </div>
                <BaseButton v-if="!item.passed" variant="secondary" @click="activeTab = targetTab(item.target)">去调整</BaseButton>
              </div>
            </div>
            <div class="student-footer">
              <span class="small text-muted">开始直播在直播工作台执行，此处仅校验准备完整性</span>
              <RouterLink v-if="checklist.can_start" :to="`/sessions/${sessionId}/live`"><BaseButton>进入直播工作台</BaseButton></RouterLink>
            </div>
          </template>
          <p v-else class="text-muted small">正在加载检查结果…</p>
        </div>
      </section>
    </fieldset>
  </template>
</template>

<style scoped>
.student-product-list{display:grid;gap:10px}
.student-product-item{display:flex;align-items:center;gap:14px;border:1px solid var(--line);border-radius:9px;padding:12px 14px}
.student-product-emoji{font-size:26px}
.student-product-info{flex:1;display:grid;gap:3px}
.student-product-info strong{font-size:13px}
.student-product-info small{font-size:11px;color:var(--muted)}
.student-room-preview{border:1px solid var(--line);border-radius:12px;overflow:hidden}
.student-room-banner{background:linear-gradient(120deg,#1e4d3a,#2f7a55);color:#eef7f0;padding:22px 24px;display:grid;gap:8px}
.student-room-banner strong{font-size:18px}
.student-room-banner span{font-size:12px;opacity:.85}
.student-room-cards{display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:12px;padding:16px;background:#f4f8f4}
.student-room-card{background:#fff;border:1px solid var(--line);border-radius:9px;padding:12px;text-align:center;display:grid;gap:6px}
.student-room-card span{font-size:28px}
.student-room-card strong{font-size:12px}
.student-room-card small{font-size:11px;color:var(--muted)}
.student-check-item{display:flex;align-items:center;gap:14px;border:1px solid var(--line);border-radius:9px;padding:12px 14px}
.student-check-item[data-passed="false"]{border-color:#e7c6c6;background:#fdf7f7}
input,select,textarea{width:100%;padding:9px 11px;border:1px solid var(--line);border-radius:7px;font:inherit;font-size:13px;background:#fff}
input:disabled,select:disabled,textarea:disabled{background:#f2f5f2;color:#8b968f}
</style>
