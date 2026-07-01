<!-- superpowers-zh:begin (do not edit between these markers) -->
# Superpowers-ZH 中文增强版

本项目已安装 superpowers-zh 技能框架（20 个 skills）。

## 核心规则

1. **收到任务时，先检查是否有匹配的 skill** — 哪怕只有 1% 的可能性也要检查
2. **设计先于编码** — 收到功能需求时，先用 brainstorming skill 做需求分析
3. **测试先于实现** — 写代码前先写测试（TDD）
4. **验证先于完成** — 声称完成前必须运行验证命令

## 可用 Skills

Skills 位于 `.Codex/skills/` 目录，每个 skill 有独立的 `SKILL.md` 文件。

- **brainstorming**: 在任何创造性工作之前必须使用此技能——创建功能、构建组件、添加功能或修改行为。在实现之前先探索用户意图、需求和设计。
- **chinese-code-review**: 中文 review 沟通参考——话术模板、分级标注（必须修复/建议修改/仅供参考）、国内团队常见反模式应对。仅在用户显式 /chinese-code-review 时调用，不要根据上下文自动触发。
- **chinese-commit-conventions**: 中文 commit 与 changelog 配置参考——Conventional Commits 中文适配、commitlint/husky/commitizen 中文模板、conventional-changelog 中文配置。仅在用户显式 /chinese-commit-conventions 时调用，不要根据上下文自动触发。
- **chinese-documentation**: 中文文档排版参考——中英文空格、全半角标点、术语保留、链接格式、中文文案排版指北约定。仅在用户显式 /chinese-documentation 时调用，不要根据上下文自动触发。
- **chinese-git-workflow**: 国内 Git 平台配置参考——Gitee、Coding.net、极狐 GitLab、CNB 的 SSH/HTTPS/凭据/CI 接入差异与镜像同步配置。仅在用户显式 /chinese-git-workflow 时调用，不要根据上下文自动触发。
- **dispatching-parallel-agents**: 当面对 2 个以上可以独立进行、无共享状态或顺序依赖的任务时使用
- **executing-plans**: 当你有一份书面实现计划需要在单独的会话中执行，并设有审查检查点时使用
- **finishing-a-development-branch**: 当实现完成、所有测试通过、需要决定如何集成工作时使用——通过提供合并、PR 或清理等结构化选项来引导开发工作的收尾
- **mcp-builder**: MCP 服务器构建方法论 — 系统化构建生产级 MCP 工具，让 AI 助手连接外部能力
- **receiving-code-review**: 收到代码审查反馈后、实施建议之前使用，尤其当反馈不明确或技术上有疑问时——需要技术严谨性和验证，而非敷衍附和或盲目执行
- **requesting-code-review**: 完成任务、实现重要功能或合并前使用，用于验证工作成果是否符合要求
- **subagent-driven-development**: 当在当前会话中执行包含独立任务的实现计划时使用
- **systematic-debugging**: 遇到任何 bug、测试失败或异常行为时使用，在提出修复方案之前执行
- **test-driven-development**: 在实现任何功能或修复 bug 时使用，在编写实现代码之前
- **using-git-worktrees**: 当需要开始与当前工作区隔离的功能开发，或在执行实现计划之前使用——通过原生工具或 git worktree 回退机制确保隔离工作区存在
- **using-superpowers**: 在开始任何对话时使用——确立如何查找和使用技能，要求在任何响应（包括澄清性问题）之前调用 Skill 工具
- **verification-before-completion**: 在宣称工作完成、已修复或测试通过之前使用，在提交或创建 PR 之前——必须运行验证命令并确认输出后才能声称成功；始终用证据支撑断言
- **workflow-runner**: 在 Codex / OpenClaw / Cursor 中直接运行 agency-orchestrator YAML 工作流——无需 API key，使用当前会话的 LLM 作为执行引擎。当用户提供 .yaml 工作流文件或要求多角色协作完成任务时触发。
- **writing-plans**: 当你有规格说明或需求用于多步骤任务时使用，在动手写代码之前
- **writing-skills**: 当创建新技能、编辑现有技能或在部署前验证技能是否有效时使用

## 如何使用

当任务匹配某个 skill 时，使用 `Skill` 工具加载对应 skill 并严格遵循其流程。绝不要用 Read 工具读取 SKILL.md 文件。

如果你认为哪怕只有 1% 的可能性某个 skill 适用于你正在做的事情，你必须调用该 skill 检查。
<!-- superpowers-zh:end -->

---

# Expense Reimbursement AI Agent

## 项目定位

企业级 AI Agent 报销系统（简历项目）。**真 ReAct Agent**——LLM 自主决定工具调用链路，
不是 RAG 问答，不是硬编码 DAG 工作流。

## 技术栈

- Python 3.12+
- FastAPI (Web framework)
- LangChain + LangGraph (ReAct Agent)
- SQLAlchemy 2.0 + SQLite (无需外部配置)
- DeepSeek API (云端推理引擎)
- Vue 3 + Vite (前端, Phase 8)

## 架构模式: Cloud Brain, Local Hands

```
企业内网 (FastAPI)
  └─ LangGraph ReAct Agent (Python 编排, 不含 LLM)
       ├─ 工具全部在本地注册和执行
       ├─ 推理时调用 DeepSeek API
       └─ DeepSeek 返回 function_call → 本地执行 → 结果回传
DeepSeek 不知道: 工具 API 地址、认证、员工真实信息
```

## 目录结构

```
backend/app/
├── api/          # HTTP 路由 (FastAPI routers)
├── domain/       # 纯业务对象, 零外部依赖 (dataclass, enum, ABC)
├── services/     # 应用编排层 (Agent, Tools, OCR, 脱敏, 报销)
├── infrastructure/ # ORM, Repositories, LLM Client
└── schemas/      # Pydantic DTO (请求/响应/云端协议)
```

## 代码规范

- 文件命名: snake_case
- 类命名: PascalCase
- 函数/变量: snake_case
- 所有函数必须有 type hints
- Pydantic v2 风格 (`model_validate` 非 `parse_obj`)
- FastAPI dependency injection (`Depends`)
- 服务类通过 `Depends` 注入, 不做全局 singleton

## 安全红线

| 可发云端 | 绝不发云端 |
|---------|-----------|
| 公司报销政策 (知识库) | 员工姓名/ID/部门/邮箱/银行账号 |
| 脱敏后的发票数据 (商家/金额/品类/日期) | 内部 API 地址/认证/token |
| 工具定义 (函数名+参数schema) | 数据库连接字符串 |

## Git 约定

- 不自动 commit/push, 除非明确要求
- commit message 用简洁英文
- 删除文件/改密钥/force push 前必须确认

## 运行方式

```bash
cd backend
pip install -r requirements.txt
cp .env.example .env   # 编辑填入 DEEPSEEK_API_KEY
python -m app.main      # 或 uvicorn app.main:app --reload
```
