# 数据与接口契约 v1.2

本文是两小时 MVP 的工程约定。TASK-000 已落实共享基础、主路由注册和共享 Pydantic DTO；经营与智能体业务实现仍由后续任务完成。后续变更由主控更新版本并同步各任务。原 Word 没有规定本文的接口名称、公式或默认分值。

版本记录：v1.1＝TASK-000 初始 45 个 DTO。v1.2＝主控于 2026-10-12 追加教师端/竞赛端响应 DTO（CompetitionCreate、Competition、LeaderboardEntry、Leaderboard、EvidenceLink、ComparisonTeam、TaskComparison、CompetitionComparison），仅新增、不改既有字段；影响 TASK-101 第三批（竞赛/对比/评分路由按此返回）与 TASK-104 页面类型。前端 `shared/contracts.ts` 已随本版重新生成。

## 0 已落实的代码与消歧约定

- 接入方式与签名见 [PARALLEL_HANDOFF.md](PARALLEL_HANDOFF.md)，公共 DTO 唯一源为 `backend/app/shared/schemas.py`。
- 前端 `shared/contracts.ts` 由上述 Python 模型生成。主控更新模型后，依次在根目录运行 `backend/.venv/bin/python scripts/export_contracts.py`、在 frontend 运行 `npm run contracts`。子任务不手改生成文件。
- `TrainingSession` 是公开 DTO 名称，避免与 SQLAlchemy Session 重名；事件 DTO 为 `TrainingEvent`。
- `/auth/me` 的 data 直接为 User。小组成员从 `/classroom` 查询，不把 memberships 临时塞进 User。
- 列表接口 `/tasks`、`/products`、`/competitions`、场次 `/events`、`/orders`、`/refunds`，以及智能体相关 GET 列表的 data 直接是数组；前端 api() 已拆除 data 包装。
- `/classroom` 的 data 为 `{classroom: {id,name,teacher_id}, teams: Team[], students: User[]}`；学生只返回授权所需成员，不暴露密码或凭证。
- 单对象创建／修改通常直接返回对象；明确的组合返回保持表格所列对象结构。`GET /sessions/{id}` 返回 SessionDetail，`GET .../review` 返回 ReviewDetail，`GET .../live-state` 返回 LiveState。
- `PUT /assortment` 请求为 `{items: AssortmentItem[]}`，返回 `{products: SessionProduct[]}`；`PUT /preparation` 返回 `{preparation: Preparation, version: number}`。
- `Product.id` 是商品库 ID；`SessionProduct.id` 是场次货盘 ID。采购、订单和 `select_product.payload.session_product_id` 使用后者；脚本的 product_id 使用前者。`TrainingSession.current_product_id` 引用当前 SessionProduct.id。
- `actions` 的 `state_version` 为该场最新事件 ID；准备表单的 version 是独立乐观锁版本，二者不能混用。
- `speech/announcement` payload 为 `{text}`，`reply` 为 `{question_event_id,text}`，`execute_script` 为 `{script_id}`，`issue_coupon` 为 `{}`；具体允许状态与必填约束仍由 A 校验。
- 默认市场热度和难度为 1，可配范围 0.1～3；所有比例指标用 0～1 数值，前端格式化成百分比。
- 导入路径已经固定为 `app.shared.auth`、`app.shared.db`、`app.shared.errors`。A 在 `core/access.py` 实现委托函数，C 只调用公共适配层。
- 当前账号、经营 API 与智能体业务均未完成；已经存在的占位不能作为业务验收通过的证据。

## 1 通用约定

- API 前缀 `/api`，UTF-8 JSON；主键统一为正整数，时间为带时区 ISO 8601，服务端存 UTC、界面按本地时区显示。
- 金额字段以 `_cents` 结尾，整数分；数量为非负整数；成交数量必须为正。
- 成功返回 `{ "data": ... }`；失败返回 `{ "error": { "code": "...", "message": "...", "details": {} } }`。
- 未登录 401；无权访问 403；不存在 404；状态冲突／重复版本 409；输入非法 422；模型服务故障 503。
- 不要求复杂分页；事件读取支持 `after_id` 与 `limit`，列表可按任务／场次筛选。
- 登录凭证按账号隔离，前端使用每标签页独立的 sessionStorage，便于多账号演示；服务端验证凭证和用户归属。密码保存哈希，不存明文。
- 学生读写本组经营场次，教师读所带班级并操作任务／评价；教师不能代写学生口播和回复证据。
- 学生可查看班级竞赛的公开汇总排名，不可据此读取其他组的完整场次、口播、订单或未上架智能体。详细组间比较仅教师可读。
- 采购、开播扣款、仿真成交、退款及提交必须原子执行；涉及金额的创建接口接受 `Idempotency-Key`，同一用户、动作和键不能重复产生副作用。
- 准备配置使用 `version` 和 `expected_version` 防止组员旧表单覆盖新内容；冲突提示刷新。事件采用追加记录，不整段覆盖。

## 2 最小数据对象

可用关系表保存主对象，用 JSON 保存低频配置。下表是逻辑对象，不要求为了表数量单独建每一种配置表。

| 对象 | 核心字段 | 归属／写入者 |
| --- | --- | --- |
| User | id, username, password_hash, role, class_id, active | A；角色 teacher/student |
| Classroom | id, name, teacher_id | A；预置一个 |
| Team / Member | id, class_id, name；user_id, position | A；岗位 host/control/service/operations |
| Task | id, class_id, teacher_id, title, description, target_audience, initial_budget_cents, target_gmv_cents, market_heat, difficulty, starts_at, ends_at, score_weights, status, rules_version | A；教师创建 |
| TaskTeam | task_id, team_id | A；发布时冻结参赛组与成员 |
| Session | id, task_id, team_id, status, rule_snapshot, preparation_json, preparation_version, initial_budget_cents, started_at, ended_at, live_elapsed_seconds, current_product_id | A；每任务每组一场，唯一约束 |
| Product | id, title, category, cost_cents, reference_price_cents, selling_points, supplier, image_or_placeholder | A；8 件预置商品，成本固定 |
| SessionProduct | id, session_id, product_id, positioning, selling_points, sale_price_cents, purchased_qty, stock_qty, sort_order | A；positioning 为 traffic/profit/image |
| CashEntry | id, session_id, kind, amount_cents, reference_type, reference_id, created_at | A；采购／投流／成交／退款资金流水 |
| Event | id, session_id, type, actor_id, source, payload_json, created_at | A；追加式记录，source 为 manual/rule |
| SimTick | id, session_id, tick_index, metrics_json, created_at | A；(session_id, tick_index) 唯一 |
| Order | id, session_id, session_product_id, buyer_label, qty, unit_cost_cents, unit_sale_cents, discount_cents, amount_cents, status, created_at | A；成交价格和成本快照 |
| Refund | id, order_id, reason, status, handler_id, handling_note, amount_cents | A；每单最多一个退款工单 |
| Review | id, session_id, status, analysis, improvements, metrics_snapshot, objective_breakdown, rule_snapshot, submitted_at | A；学生草稿／提交 |
| Grade | id, session_id, teacher_id, objective_score, subjective_score, total_score, comment, rules_version, graded_at | A；每场一份 |
| Competition | id, task_id, title, status, rule_snapshot, published_at | A；每任务最多一个竞赛 |
| AgentAssignment | id, class_id, teacher_id, task_id?, title, instructions, rubric_json, status | C；教师作业 |
| AgentDraft / Version | id, owner_id, assignment_id, name, duties, boundaries, instructions, knowledge_cards；version_id, immutable_config | C；保存时生成版本 |
| AgentRun | id, owner_id, agent_id?, version_id?, config_snapshot, question, session_id?, context_snapshot, context_sources, output, source, model, duration_ms, status, error, created_at | C；预演含未保存快照 |
| AgentSubmission | id, assignment_id, owner_id, version_id, run_ids, improvement_notes, status, grade?, comment?, reviewer_id? | C；提交时冻结内容 |
| AgentPublication | id, class_id, submission_id, version_id, published_at | C；发布具体不可变版本 |

用户角色与组内岗位分开；岗位用于分工与记录，不额外建设复杂权限矩阵。小组成员在所属任务发布后锁定，本版不处理训练中换组。

## 3 公共身份与模块集成

- 主控创建数据库连接、公共模型基类（若所选 ORM 需要）、应用配置和路由注册入口；单后端进程运行。
- A 导出 `get_current_user`、`require_teacher_for_class`、`require_session_access` 以及 `get_authorized_session_context(user, session_id)`。
- 最终导入路径由 TASK-000 固定到公共适配层；C 不直接查询密码或复制鉴权逻辑。
- 场次上下文只返回授权商品、价格、库存、卖点、最近咨询和班级信息；不返回密钥、密码或其他组证据。
- C 导出智能体路由和自己的建表入口，主控一次性注册。
- GET 为只读；启动仿真、创建订单等副作用不放入 GET。

## 4 状态与锁定

### 4.1 核心状态

```text
Task: draft → published → closed
Session: preparing → live ⇄ paused → ended → submitted → graded
                                      ↑
                          live 或 paused 均可结束
Order: pending_shipment → shipped → signed
                    └─ 同意退款 → refunded
Refund: pending → approved / rejected
Review: draft → submitted → graded
Competition: draft → published → finished
```

- Session 只有 live 可产生成交；paused 不推进仿真、不计有效直播时长，恢复时不补算暂停时间。
- preparing 可修改准备和追加采购；live/paused 只接受直播控制与互动，不改采购成本和准备表单；优惠采用事先配置、直播触发的模式。
- live/paused 可切当前商品；口播、回复、发券和公告只在 live 接受。
- ended 可履约、处理退款、编辑复盘；submitted/graded 后所有经营及复盘写入锁定，仅允许教师评分和读取。
- 只有全部订单 signed/refunded 且无 pending 售后时可提交复盘；零订单场次可提交但指标明确为零，不强造销售。
- signed/refunded 为终态；重复请求可返回原结果或 409，但不能产生新的资金或库存变化。
- 所有时间限制由后端判断；任务到期后停止学生经营／作业写入，结束尚在直播的场次。未提交者标为超时，教师仍能查看和评分已提交记录。
- 竞赛使用统一 deadline；演示任务给足时限，不在演示中途到期。时限异常通过单独测试覆盖。
- 服务重启时，将遗留 live 场次暂停并记录系统恢复事件，避免无观众页面时补算大量历史成交。

### 4.2 智能体状态

```text
Assignment: draft → published
Submission: submitted → approved / returned
Publication: 对 approved 的指定版本发布
Run: running → succeeded / failed
```

退回后重新保存版本并创建新提交，旧提交和预演保留。允许继续编辑自己的草稿，但不能修改已提交快照和已上架版本。

## 5 金额、库存与仿真

### 5.1 统一计算口径

- `purchase_cost = Σ(采购数量 × 成本分)`；采购即扣款，可多次追加，不能超预算。
- 投流计划在准备阶段校验剩余资金；首次开始直播时一次性扣除全部投流预算，恢复直播不重复扣。界面说明为本次训练固定投流成本。
- `GMV = Σ订单成交金额`，包含后来退款的订单；`refund_total = Σ已批准退款金额`。
- `net_sales = GMV - refund_total`。
- `cash_balance = initial_budget - purchase_cost - promotion_spend + GMV - refund_total`。
- `sold_cost = Σ未退款订单数量 × 成交时成本`。
- `profit = net_sales - sold_cost - promotion_spend`；这是扣投流后的模拟经营利润，不包含未售库存价值，不等于现金余额。
- `stock = purchased_qty - 全部已生成订单数量 + 已退款回补数量`，任何时刻不得为负。
- 仅未发货整单退款，同意时全额退成交实付金额并回补对应数量；驳回不动资金与库存，订单继续履约；不做部分退款和退货物流。
- 优惠券为一张场次级固定减额券，作用于后续成交，实付至少 1 分；订单保存原价、优惠和实付快照。
- 原始采购、订单、退款与资金流水是审计依据，报表不能来自前端独立累计。

### 5.2 仿真最低要求

- 后端一个生命周期任务定时推进所有 live 场次，建议每 3 秒一轮；前端每约 2 秒轮询状态。
- 每场保存 tick_index，唯一约束避免同一轮重复成交；多客户端观看不增加仿真轮数。
- 使用可配置固定种子与版本化规则便于测试；同一竞赛使用相同规则、市场基础条件及随机序列机制。
- 基础进房受热度、难度、投流影响；点击与购买概率受当前商品价格、优惠、已执行讲解和最近有效回复影响。
- 所有概率限制在合法区间，不允许负访客或负点击；价格影响采用有上下限的简单公式。
- 无库存、无当前商品、暂停、结束、到期都不能生成订单；不能为保证演示强制超卖。
- 事件保存影响因素摘要，能展示“本轮投流／价格／互动因素”，不需要复杂推理系统。
- 具体系数由 A 在第一次仿真交付时写入代码常量并记录规则版本；属于教学假设，不能宣传为真实预测模型。

## 6 统计与评分

### 6.1 指标

单一后端汇总函数向直播、复盘、教师端和竞赛供数。返回 `gmv_cents, refund_cents, net_sales_cents, profit_cents, cash_balance_cents, order_count, refunded_order_count, cumulative_entries, product_clicks, audience_question_count, replied_question_count, violation_count, signed_order_count`。

累计进房按仿真人次计算，不伪装成去重真实访客。转化率为订单数／累计进房人次；回复率按已回复的独立问题数／问题总数。分母为零时返回 null，界面显示“暂无样本”。

### 6.2 评分默认值

以下为本 MVP 工程默认值，教师发布前可改维度权重，权重之和必须为 100；发布后冻结。原 Word 只规定可配置评分，未规定这些公式。

| 维度 | 默认权重 | 系统分 0～100 的最小计算 |
| --- | --- | --- |
| 过程 | 25 | 准备检查完成比例 × 50 + 四类脚本段已执行比例 × 50 |
| 经营 | 25 | min(净销售额／正数目标 GMV, 1) × 100 |
| 服务 | 20 | 终态订单比例 × 50 + 已回复问题比例 × 50；无订单／问题对应部分计 0 并注明样本不足 |
| 合规 | 15 | max(0, 100 - 20 × 命中的独立违规事件数) |
| 复盘 | 15 | 非空分析 50 + 非空改进措施 50；只是完成度，质量交给教师评价 |

- `objective_score = Σ(维度分 × 权重 / 100)`。
- `total_score = round(objective_score × 0.7 + subjective_score × 0.3, 2)`；教师主观分 0～100，附评语。
- 教师打分前，综合分为 null；不能把缺失主观分当 0 混入最终排名。
- 临时榜统一按系统分排序；最终榜仅对已评分组按综合分排序，其他组单列待评／超时状态。
- 同分依次按净销售额、较少违规、组 ID 稳定排序，并在界面显示规则。
- 提交时冻结报告、维度依据、规则与指标快照；评分引用此快照。规则报告必须显示 `source=rule`。

## 7 核心 API 清单

此清单是模块间最小路由约定。基础对象字段见第 2 节，写请求只接受可编辑字段，身份与计算字段由后端产生。TASK-000 补齐实际请求／响应类型，不允许前后端各猜字段。

| 方法与路径 | 用途／请求要点 | 返回要点 |
| --- | --- | --- |
| POST `/auth/login` | username, password | token, user |
| GET `/auth/me` | 当前登录 | user, team memberships |
| GET `/classroom` | 当前班级；教师可读可选学生 | class, teams, students |
| POST `/teams` | name, members[{user_id, position}] | team |
| PUT `/teams/{id}` | 发布前更新成员岗位 | team |
| GET/POST `/tasks` | 列表／教师创建草稿 | tasks / task |
| PUT `/tasks/{id}` | 仅草稿可编辑，含 team_ids | task |
| POST `/tasks/{id}/publish` | 校验规则并冻结，为每组创建唯一 preparing 场次 | task, session_ids |
| GET `/tasks/{id}` | 任务及本人入口／教师各组入口 | task, sessions |
| GET `/products` | 预置商品筛选 | products |
| GET `/market-sample` | 教学调研样例 | categories, audience, source=sample |
| GET `/sessions/{id}` | 场次、准备、货盘、余额、权限 | session, preparation, products, metrics, capabilities |
| PUT `/sessions/{id}/preparation` | expected_version, research, plan, script, promotion, room, coupon | preparation, version |
| PUT `/sessions/{id}/assortment` | preparing，商品定位、卖点、价格、顺序；不得移除已采购项 | products |
| POST `/sessions/{id}/purchases` | items[{session_product_id, qty}]；幂等 | products, cash_balance_cents |
| GET `/sessions/{id}/checklist` | 开播缺失项 | items[{key, passed, message, target}], can_start |
| POST `/sessions/{id}/control` | action=start/pause/resume/end | status, metrics |
| POST `/sessions/{id}/actions` | type, payload；作者取身份 | event, state_version |
| GET `/sessions/{id}/live-state` | 只读，轮询 | status, current_product, metrics, latest_event_id |
| GET `/sessions/{id}/events` | after_id, limit | events |
| GET `/sessions/{id}/orders` | status 可选 | orders |
| POST `/orders/{id}/ship` | pending_shipment | order |
| POST `/orders/{id}/sign` | shipped | order |
| POST `/orders/{id}/refunds` | reason；未发货，幂等 | refund |
| GET `/sessions/{id}/refunds` | 当前场次售后 | refunds |
| POST `/refunds/{id}/resolve` | decision=approve/reject, handling_note | refund, order, metrics |
| GET `/sessions/{id}/review` | 草稿／已提交报告及成绩 | review, metrics, breakdown, grade |
| PUT `/sessions/{id}/review` | analysis, improvements；仅 ended | review |
| POST `/sessions/{id}/review/submit` | 校验履约、时间和正文；幂等 | immutable review |
| POST `/sessions/{id}/grade` | 教师 subjective_score, comment；仅已提交 | grade（Grade DTO） |
| GET `/tasks/{id}/comparison` | 教师方案／结果对比，仅该任务教师 | TaskComparison：`{task, teams[{team_id, team_name, session_id, status, preparation, products, metrics, breakdown, grade, evidence_links}]}`，products 为该组场次货盘（含定位、价格、采购与库存） |
| POST `/competitions` | task_id, title；任务为草稿，参数引用任务 | competition（Competition DTO） |
| GET `/competitions` | 班级竞赛列表 | competitions（data 直接是数组） |
| GET `/competitions/{id}/leaderboard?stage=provisional\|final` | stage 缺省 provisional；学生仅返回公开汇总字段 | Leaderboard：`{stage, rules_version, score_weights, deadline, entries[], pending_entries[]}`，Entry 为 `{team_id, team_name, session_id, status, metrics, objective_score, subjective_score, total_score}`；临时榜 entries 按系统分排，最终榜仅已评分组按综合分排，未完成／未评分组全部进 pending_entries |
| GET `/competitions/{id}/comparison` | 教师详细比较，仅教师 | CompetitionComparison：`{competition, teams[同 TaskComparison.teams（含 preparation、products、metrics、breakdown、grade、evidence_links）]}` |

直播 action 只允许：`select_product, issue_coupon, announcement, speech, reply, execute_script`。`reply` 必须引用本场观众问题 event_id；`execute_script` 引用本场脚本段 ID。payload 在服务端按类型校验。

竞赛与对比补充（v1.2）：

- 榜单排序规则同 6.2：同分依次按净销售额、较少违规、组 ID 稳定排序；后端返回排好序的 entries，前端不做二次排序，也不内置任何静态名次。
- `EvidenceLink.kind` 建议取 `events`（口播/回复/脚本/合规事件）、`orders`（订单记录）、`review`（复盘报告）；`label` 为界面显示文案，前端据此生成只读证据入口链接。
- 学生访问 leaderboard 只返回公开汇总（组名、状态、关键指标与名次），不返回其他组 preparation 明细、事件与订单；comparison 两接口仅教师可用。

准备 JSON 最小形状：

```json
{
  "expected_version": 0,
  "research": {"audience": "", "competitor_notes": "", "price_notes": "", "selection_reason": ""},
  "plan": {"theme": "", "target_audience": ""},
  "script": [{"id": "opening", "kind": "opening", "product_id": null, "text": ""}],
  "promotion": {"channel": "simulated_feed", "budget_cents": 0, "audience": ""},
  "room": {"theme": "agriculture", "title": "", "announcement": ""},
  "coupon": {"discount_cents": 100}
}
```

示例只展示形状，不能以空文本通过开播检查；脚本需要 opening/product/interaction/closing 四类，讲解段关联已入货盘的商品。

## 8 智能体 API 与模型边界

| 方法与路径 | 用途 | 返回要点 |
| --- | --- | --- |
| GET/POST `/agent-assignments` | 已发布作业列表／教师创建草稿 | assignments / assignment |
| PUT `/agent-assignments/{id}` | 草稿说明与评价标准 | assignment |
| POST `/agent-assignments/{id}/publish` | 发布到本班 | assignment |
| GET/POST `/agents` | 自己的草稿列表／创建客服配置 | agents / agent |
| PUT `/agents/{id}` | 保存当前配置，形成不可变版本 | agent, version |
| GET `/agents/{id}/versions` | 本人／已提交作业的教师读取 | versions |
| POST `/agent-runs` | agent_id?, config, question, session_id?；支持未保存配置 | run |
| GET `/agent-runs` | 本人记录；教师按提交授权读取 | runs |
| POST `/agent-submissions` | assignment_id, version_id, run_ids, improvement_notes | submission |
| GET `/agent-submissions` | 学生本人／教师本班 | submissions |
| POST `/agent-submissions/{id}/review` | decision=approve/return, grade, comment | submission |
| POST `/agent-submissions/{id}/publish` | 只对 approved，发布具体版本 | publication |
| GET `/agent-publications` | 本班上架列表 | publications with immutable config |
| POST `/agent-publications/{id}/preview` | question, session_id?；配置来自上架版本 | run，作者为当前试用者 |

- 配置包括 `name, duties, boundaries, instructions, knowledge_cards[{title, content}]`。
- 预演把平台约束、当前配置、知识卡、授权商品上下文与问题分层组织；知识卡作为参考资料，不作为覆盖系统规则的指令。
- 仅使用一个后端模型适配器；环境变量名为 `LLM_BASE_URL, LLM_API_KEY, LLM_MODEL`。TASK-000 根据实际服务验证协议，不假设任意 URL 都兼容。
- 设置约 20 秒超时和界面等待反馈；调用失败保存 failed 记录，返回可读错误，可手动重试。
- `source=model/rule`，模型名与耗时如实记录；调用失败生成的规则文本不能标成 model。
- 运行必须保存当次完整配置快照；未保存预演的 version_id 可为 null。提交时可附历史配置试验记录，但选定最终版本至少要有一次匹配配置的成功模型预演。
- 原始密钥、认证头不得进入日志；只读上下文失败不能退而读取其他组或全库数据。
- 预演不能执行退款、发言或其他经营写入；工具编排与自动采纳不在本版。

## 9 最小演示数据

- 1 个班级，1 个教师，2 个示例小组，每组至少主播、场控、客服三个不同学生账号；运营可兼任。
- 8 件农产品，覆盖多个价格带；至少各一件适合引流、利润和形象展示的商品；固定供应商和成本。
- 一个可直接查看的示例任务与一个可新建任务入口；默认预算 100000 分、GMV 目标 50000 分、截止时间足够演示。
- 两组有不同货盘、价格或投流方案；竞赛相同的是起始条件和规则，不强行固定相同结果。
- 一个客服模板、商品知识卡，以及咨询／售后两类问题；真实预演历史必须来自真实运行，不能种子化伪造 source=model。
- 可提供明确标注的历史示例帮助快速演示，但至少一次验收必须从新任务走到最终评分。
- 种子初始化幂等，不能每次启动清空用户数据；重置演示数据为显式独立操作，不默认执行。
