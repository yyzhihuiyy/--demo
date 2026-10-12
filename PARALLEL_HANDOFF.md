# 后续任务交接

更新：2026-10-12。此文件替代旧“第一阶段新建 A/B/C”粘贴指令，保留模块接入信息。当前轮次只整理规划，不派发开发或子 Agent；后续从现有实现继续。

项目：`/Users/zhuihui_y/Desktop/直播运营虚拟仿真实训平台`。

## 续接顺序

先读 AGENTS → STATUS → MODULE_PROGRESS → DEVELOPMENT_PLAN，再读对应任务书和 CONTRACTS。旧分钟时限、占位登录、从零创建页面均已失效。

| 任务 | 已有基础 | 下一批交付 |
| --- | --- | --- |
| 101 | 登录准备、仿真订单签收、模型／DTO／metrics | 修截止等边界，补退款、复盘、评分；之后竞赛比较 |
| 102 | 四个学生页面、真实 API 客户端 | 用已可用接口验收准备直播，随 101 接售后复盘 |
| 103 | 智能体前后端、23 项替身测试 | 配置真实模型、两次预演到评审上架的浏览器验收 |
| 104 | 教师任务证据、竞赛榜单比较页面 | 修 5 个类型错误，接评分／比较／竞赛真实 API |
| 000／105 | 公共接入与测试脚本 | 统一契约版本、隔离数据库，逐阶段集成和四场景交付 |

## 固定接入

- 主入口 `backend/app/main.py` 统一加 `/api`，装配 core/agents 的 router 和生命周期。
- 数据库使用 `app.shared.db.Base / SessionLocal / DbSession / get_db`，不得另建用户库。
- 成功响应 `success(data)`；失败 `AppError(status, code, message, details)`；前端 `api` 已解包 data。
- 共享 DTO 源为 `backend/app/shared/schemas.py`；`frontend/src/shared/contracts.ts` 自动生成。当前文档版本 1.2，健康输出 1.1 是待修差异。
- 前端 `api<T>(path, options)`、`mutation<T>(path, body, method, key)`；身份 `useAuth()`，token 放 sessionStorage。
- `core/access.py` 已实现 `resolve_user(token, db)`、`check_session_access(user, session_id, db, *, write=False)`、`read_session_context(user, session_id, db)`。
- agents 通过 `app.shared.auth.CurrentUser / require_teacher_for_class / get_authorized_session_context` 接入，后两者实参分别为 `(user, class_id)` 与 `(user, session_id, db)`。
- 两模块保留 `router: APIRouter` 与 lifecycle 的 `MODULE_STATUS / async startup() / async shutdown()`；ORM 导入必须早于主入口建表。
- core startup 已幂等种入 fixtures、恢复 live 为 paused、启动统一仿真循环；不要再次实现种子或另起仿真。

## 交付格式

每批写明当前行为、文件、接口影响、测试命令及结果、临时库隔离方式、阻塞、下一步。模型要给真实 run_id／来源；不能粘贴密钥。前端构建必须包含类型检查。公共修改由负责者协调，不跨模块覆盖。
