# 直播运营虚拟仿真实训平台 MVP 外部记忆

本目录保存两小时 MVP 的有效需求、开发计划、并行任务和验收标准。后续开发优先读取本目录，无需反复解析原 Word。

- 创建日期：2026-10-12。
- 原始材料：[直播运营虚拟仿真实训平台软件功能介绍](../直播运营虚拟仿真实训平台软件功能介绍_脱敏面试题.docx)。原文件未修改。
- 用户最终要求：原 Word 第 19 章四个重点演示场景涉及的核心功能必须开发；其余功能尽量删减。
- 交付边界：Vue + FastAPI + SQLite，本机浏览器演示；所有交易、观众和物流都是教学仿真。
- 当前成果：四个重点场景的演示流程已接通。两组任务、规则仿真订单、签收／退款、复盘评分、竞赛对比以及客服智能体真实模型预演／审核上架均已通过实际接口验证。
- 当前范围：以本机教学演示为目标；非流程完善与生产部署暂缓。实际状态见 `STATUS.md`，直接演示步骤见 `DEMO_WALKTHROUGH.md`。

## 现在运行

依赖已安装在项目内。前端开发预览：<http://127.0.0.1:5173/>；后端接口文档：<http://127.0.0.1:8000/docs>。当前服务已启动；如已经停止，分别在两个终端运行：

```sh
cd /Users/zhuihui_y/Desktop/直播运营虚拟仿真实训平台
sh scripts/dev-backend.sh
```

```sh
cd /Users/zhuihui_y/Desktop/直播运营虚拟仿真实训平台
sh scripts/dev-frontend.sh
```

新环境安装：Python 3.12 创建 `backend/.venv` 后运行 `backend/.venv/bin/python -m pip install -r backend/requirements.lock.txt`；前端在 `frontend` 中运行 `npm ci`。本机验证使用 Node 24.20.0、Python 3.12.14。

验证命令：在项目根目录运行 `sh scripts/check.sh`。本轮隔离数据库回归为 48 项后端测试通过，Vue 类型检查和生产构建通过；本机实际 API 已走完四场景，并在浏览器核对教师工作台、最终榜、两组对比、场次证据和智能体上架列表。

模型配置：从 `backend/.env` 读取 `LLM_BASE_URL`、`LLM_API_KEY`、`LLM_MODEL`，可运行 `backend/.venv/bin/python scripts/check_model.py --probe` 验证。本轮 probe 成功，且真实预演、提交、审核上架和同班试用已经完成。密钥不得写进任务书或聊天。

账号种子位于 `backend/fixtures/demo.json`：`teacher`，甲组 `a_host/a_control/a_service`，乙组 `b_host/b_control/b_service`，演示密码 `demo1234`。账号已实际入库并可登录。

数据库路径为 `backend/data/platform.db`，按后端目录解析，不随终端工作目录变化；启动不会清空数据。当前保留种子任务及本轮四场景联调记录。

## 快速读取顺序

1. [STATUS.md](STATUS.md)：当前状态、阻塞和下一步。
2. [MVP_REQUIREMENTS.md](MVP_REQUIREMENTS.md)：四个场景的有效需求与删减范围。
3. [DEMO_WALKTHROUGH.md](DEMO_WALKTHROUGH.md)：账号、已完成演示数据和从新任务演示的操作顺序。
4. [DEVELOPMENT_PLAN.md](DEVELOPMENT_PLAN.md)：后续非流程工作与文件归属。
5. [CONTRACTS.md](CONTRACTS.md)：数据、状态、接口和计算口径；跨模块开发的统一依据。
6. 只读取自己负责的 `tasks/TASK-*.md`。

智能体开发只需重点读取需求 S4、契约第 1～3、8～9 节及 TASK-103；学生界面重点读取 S1/S2 与 TASK-102；教师端重点读取 S1/S3 与 TASK-104。无需每轮全量读取所有文件。

## 文件索引

| 文件 | 用途 |
| --- | --- |
| [AGENTS.md](AGENTS.md) | 后续开发者／Agent 的执行与外部记忆维护规则 |
| [MVP_REQUIREMENTS.md](MVP_REQUIREMENTS.md) | 从 Word 提取并按已确认范围裁剪后的任务书 |
| [DEVELOPMENT_PLAN.md](DEVELOPMENT_PLAN.md) | 开发顺序、并行分工、检查点和降级策略 |
| [CONTRACTS.md](CONTRACTS.md) | 统一业务模型、接口、统计、评分和集成约定 |
| [ACCEPTANCE.md](ACCEPTANCE.md) | 四个场景操作验收与关键异常检查 |
| [DECISIONS.md](DECISIONS.md) | 已确认范围、工程默认选择、未验证前提 |
| [STATUS.md](STATUS.md) | 唯一的全局进度入口 |
| [DEMO_WALKTHROUGH.md](DEMO_WALKTHROUGH.md) | 四场景演示账号、已有结果和操作顺序 |
| [MODULE_PROGRESS.md](MODULE_PROGRESS.md) | 修复前代码核查基线，非当前缺口清单 |
| [PARALLEL_HANDOFF.md](PARALLEL_HANDOFF.md) | 后续模块接入点与交付格式 |
| [TASK-000](tasks/TASK-000-foundation.md) | 主控：骨架、公共契约与模型连通验证 |
| [TASK-101](tasks/TASK-101-core-backend.md) | A：核心业务后端 |
| [TASK-102](tasks/TASK-102-student-ui.md) | B：学生工作台 |
| [TASK-103](tasks/TASK-103-agent-workshop.md) | C：客服智能体教学模块 |
| [TASK-104](tasks/TASK-104-teacher-competition.md) | 主控：教师管理与竞赛对比 |
| [TASK-105](tasks/TASK-105-integration.md) | 主控：持续联调与最终交付 |

## 一条演示主线

教师创建“助农直播实训与竞赛”任务 → 两组学生调研选品 → 准备脚本、投流与直播间 → 多角色协作直播 → 订单履约及退款 → 提交复盘 → 教师评分与组间对比 → 客服智能体两次预演、提交、审核上架。

四个场景共用同一任务、小组和场次数据；智能体教学通过只读上下文接入场次，不替代经营流程。

## 使用原则

- 当前用户新指令优先，其次本目录裁剪后的需求，再次原 Word 的扩展描述。
- 四场景流程接口、分值计算和演示数据均已落地；仍需区分“演示流程已通过”和“全量产品验收已通过”，当前边界以 STATUS.md 为准。
- `TODO / IN_PROGRESS / BLOCKED / DONE` 只记录真实状态；未验证事项不能写成“已通过”。
- 不恢复已明确删减的功能；不以静态截图、硬编码排名或固定预演答案代替核心流程。
