# Expense Reimbursement AI Agent

企业级 AI Agent 报销系统 — 基于 **LangGraph ReAct Agent**（Plan-Act-Observe 循环），Cloud Brain, Local Hands 安全模式。

## 架构全景

```
┌──────────────────────────────────────────────────────────────┐
│                    Vue 3 前端 (ChatView)                       │
│  SSE 流式: thinking / plan / tool_call / tool_result          │
│           / invoice_card / policy_card / supplement_form      │
│           / confirmation_request / knowledge_refs / message   │
└──────────────────────────┬───────────────────────────────────┘
                           │ POST /api/v1/chat (SSE)
┌──────────────────────────▼───────────────────────────────────┐
│                    FastAPI 后端                                │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │  LangGraph ReAct Agent (PAO)                             │ │
│  │  START → plan → act ↔ tools → observe → (act | END)     │ │
│  │  SessionAgentManager (LRU 隔离) + astream_events(v2)     │ │
│  └─────────────────────────────────────────────────────────┘ │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │  LLM Security Gateway (统一安全瓶颈)                      │ │
│  │  EnterpriseDataSanitizer + LocalContextStore              │ │
│  │  默认拒绝 → 白名单放行 → 令牌化 → 本地暂存               │ │
│  └─────────────────────────────────────────────────────────┘ │
│  ┌───────────┬───────────┬──────────┬──────────┬──────────┐ │
│  │ OCR       │ 知识库    │ 脱敏     │ 报销     │ 通知     │ │
│  │ PaddleOCR │ ChromaDB  │ PII映射  │ 状态机   │ Email    │ │
│  │ 真实扫描  │ 语义搜索  │ ENT-tok  │ Create   │ 模拟     │ │
│  └─────┬─────┴─────┬─────┴────┬─────┴────┬─────┴────┬─────┘ │
│  ┌─────▼───────────▼──────────▼──────────▼──────────▼──────┐ │
│  │       SQLite (9 tables) + ChromaDB (384d vectors)        │ │
│  │  employees / users / chat_sessions / chat_messages       │ │
│  │  knowledge_bases / knowledge_documents                   │ │
│  │  expense_reports / expense_items / pii_mappings          │ │
│  │  notification_log / status_transitions                   │ │
│  └──────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────┘
```

## 技术栈

### 后端
| 技术 | 用途 |
|------|------|
| **Python 3.12+** | 主语言 |
| **FastAPI** | Web 框架，RESTful API + SSE 流式响应 |
| **LangChain + LangGraph** | ReAct Agent 编排（plan → act ↔ tools → observe） |
| **DeepSeek API** | 云端 LLM 推理（Mock 模式零依赖运行） |
| **SQLAlchemy 2.0 + SQLite** | ORM + 本地数据库，零配置 |
| **ChromaDB** | 嵌入式向量数据库，知识库语义搜索 |
| **sentence-transformers** | 本地 embedding 模型（paraphrase-multilingual-MiniLM-L12-v2，384d） |
| **PaddleOCR** | 中文发票 OCR（ch + 图像增强管线） |
| **Pydantic v2** | 数据校验 & Schema |
| **pydantic-settings** | 分组配置管理（App / DB / DeepSeek / KB / OCR / Agent / PII / Storage） |
| **pytest** | 测试框架 |

### 前端
| 技术 | 用途 |
|------|------|
| **Vue 3** (Composition API + `<script setup>`) | UI 框架 |
| **TypeScript 6.0** | 类型安全 |
| **Vite 8** | 构建工具 |
| **Pinia 3** | 状态管理 |
| **Vue Router 4** | 路由（Hash 模式） |
| **Axios** | HTTP 请求封装 |

## Agent 特征

| 特征 | 实现 |
|------|------|
| **显式规划** | Plan 节点 LLM 生成 JSON 执行计划，列出步骤 + 工具 + 参数 |
| **自主决策** | Act 节点 LLM 自主决定调用哪个工具，Mock 模式模拟完整 ReAct 链 |
| **结果观察** | Observe 节点评估工具结果，标记步骤 done/failed，支持重规划 |
| **PAO 循环** | Plan → Act → Observe → (Act | END)，硬上限 20 轮 |
| **流式思考** | astream_events("v2") 推送 token 级流式 thinking |
| **会话隔离** | SessionAgentManager 每会话独立 LLM 实例，LRU 淘汰（最多 50 会话 / 1 小时空闲） |
| **智能意图识别** | 政策咨询 vs 报销请求自动分流，无需追问用户 |

## 工具清单

| 工具 | 说明 | 实现 |
|------|------|------|
| `scan_invoice` | OCR 扫描发票：提取金额/商户/日期/品类 | PaddleOCR 真实实现，文件不存在回退 mock |
| `search_knowledge` | 语义搜索公司报销政策 | ChromaDB + sentence-transformers，返回相关度分数 |
| `check_reimbursement_status` | 查询报销单审批进度 + 状态时间线 | 真实 DB 查询 status_transitions |
| `submit_reimbursement` | 提交报销申请 | 写 ExpenseReport + ExpenseItem + 状态流转 |
| `send_notification` | 发送邮件通知 | 写 NotificationLog（外部邮件 API mock） |

所有工具通过 `BaseTool` 抽象基类注册，ToolContext 注入 user_id / employee_id / user_email / security_gateway。

## 数据安全（三层架构）

```
用户消息 / OCR 结果 / 对话历史
        │
        ▼
┌───────────────────────────┐
│   LLMSecurityGateway      │  ← 统一瓶颈：一切发往 LLM 的数据必经此处
│   build_user_message()    │
│   build_ocr_result()      │
│   build_tool_result()     │
│   build_history()         │
└──────────┬────────────────┘
           │
           ▼
┌───────────────────────────┐
│   EnterpriseDataSanitizer │  ← 白名单过滤 + PII 令牌化
│   ALLOWED_INVOICE_FIELDS  │     默认拒绝，显式允许
│   ALLOWED_POLICY_FIELDS   │     手机/身份证/邮箱/银行账号 → TOKEN-xxx
│   ALLOWED_WORKFLOW_FIELDS │     商户名 → VENDOR-xxx
└──────────┬────────────────┘
           │
           ▼
┌───────────────────────────┐
│   LocalContextStore       │  ← Session 级本地存储，LLM 永不可见
│   invoice / tokens /      │     真实 OCR raw_text 仅存此处
│   vendors / supplement    │     令牌映射仅存此处
└───────────────────────────┘
```

| 可发云端 | 绝不发云端 |
|---------|-----------|
| 公司报销政策（知识库文档） | 员工姓名/ID/部门/邮箱/银行账号 |
| 脱敏后的发票数据（金额/品类/日期） | 商户真实名称（令牌化为 VENDOR-xxx） |
| 工具定义（函数名 + 参数 schema） | OCR raw_text（可能含税号等信息） |
| ChromaDB embedding 向量 | 内部 API 地址/认证/token |
| 令牌化字段（TOKEN-xxx / VENDOR-xxx） | 数据库连接字符串 / PII 映射表 |

## 报销状态机

```
DRAFT → SUBMITTED → MANAGER_APPROVAL → FINANCE_APPROVAL → APPROVED → PAID
                       ↘                      ↘
                       REJECTED              REJECTED
```

每步状态变更写入 `status_transitions` 表（不可变审计日志）。

## 知识库 Chunk ID 体系

```
格式: kb-{kb_id}-doc-{doc_id}-chunk-{idx:04d}

示例: kb-1-doc-3-chunk-0002
      ↑       ↑       ↑
      知识库   文档    分块序号（0-index）
```

- **按文档更新**：`ChromaDB.delete(where={"doc_id": X})` → 重新分块 → embedding → 入库
- **按知识库清理**：删除知识库时批量清除所有关联 chunks
- **自描述 ID**：chunk_id 包含完整来源信息，调试/审计可追溯

## 快速开始

### 后端

```bash
cd backend
pip install -r requirements.txt
python seed.py              # 初始化数据库（演示用户 + 示例知识库）
python -m app.main          # 启动 http://localhost:8000
```

无需配置 DeepSeek API Key — Mock 模式自动启用，Agent 完整 PAO 循环可用。

如需真实 DeepSeek：
```bash
cp .env.example .env        # 编辑 DEEPSEEK_API_KEY=sk-your-key
```

### 前端

```bash
cd frontend
npm install
npm run dev                 # 启动 http://localhost:5173
```

### 测试

```bash
cd backend
python -m pytest tests/ -v
```

### 演示账号

| 用户名 | 密码 | 角色 |
|--------|------|------|
| `admin` | `admin123` | 管理员（知识库管理 + 统计面板） |
| `zhangwei` | `zhang123` | 员工（聊天报销） |

## 项目结构

```
├── backend/
│   ├── app/
│   │   ├── api/                     # FastAPI 路由（7 个模块）
│   │   │   ├── auth.py              #   登录/注册
│   │   │   ├── chat.py              #   Agent 聊天 (SSE) + 会话 CRUD + 文件上传
│   │   │   ├── knowledge.py         #   知识库上传/搜索/文档管理
│   │   │   ├── employees.py         #   员工管理
│   │   │   ├── expenses.py          #   报销单管理
│   │   │   ├── reimbursements.py    #   报销审批/状态流转
│   │   │   └── admin.py             #   管理后台统计
│   │   ├── domain/                  # 纯业务对象
│   │   │   └── enums.py             #   UserRole, ReportStatus, ExpenseCategory 等
│   │   ├── services/                # 应用编排层
│   │   │   ├── agent_service.py     #   ReAct Agent 图构建 + run_agent SSE 事件生成
│   │   │   ├── session_agent.py     #   SessionAgentManager (会话级 LLM 隔离 + LRU)
│   │   │   ├── session_service.py   #   会话 CRUD + 消息管理
│   │   │   ├── ocr_service.py       #   PaddleOCR + Mock 双模式
│   │   │   ├── knowledge_service.py #   ChromaDB 知识库（分块/embedding/搜索）
│   │   │   ├── reimbursement_service.py  # 报销状态机
│   │   │   ├── desensitization_service.py # PII 脱敏 (batch/token)
│   │   │   ├── llm_security_gateway.py   # 安全网关（统一瓶颈）
│   │   │   ├── enterprise_data_sanitizer.py # PII 检测 + 白名单过滤 + 令牌化
│   │   │   ├── local_context_store.py     # Session 级安全上下文存储
│   │   │   ├── invoice_card_service.py    # 发票卡片 SSE 事件构建
│   │   │   ├── policy_card_service.py     # 政策卡片 + 判责 SSE 事件构建
│   │   │   ├── notification_service.py    # 邮件通知
│   │   │   └── tools/                # 5 个 Agent 工具
│   │   │       ├── base.py           #   BaseTool + ToolContext
│   │   │       ├── scan_invoice.py
│   │   │       ├── search_knowledge.py
│   │   │       ├── submit_reimbursement.py
│   │   │       ├── check_status.py
│   │   │       └── send_notification.py
│   │   ├── infrastructure/           # 基础设施层
│   │   │   ├── orm.py                #   SQLAlchemy 9 表模型
│   │   │   └── llm_client.py         #   DeepSeek + Mock LLM（含 ReAct 模拟器）
│   │   ├── schemas/                  # Pydantic DTO
│   │   ├── config.py                 # pydantic-settings 分组配置
│   │   └── main.py                   # FastAPI 入口 + CORS + lifespan
│   ├── data/
│   │   ├── chroma/                   # ChromaDB 持久化向量数据
│   │   └── invoices/                 # 上传的发票文件
│   ├── tests/                        # pytest
│   └── seed.py                       # 种子数据
├── frontend/
│   └── src/
│       ├── views/                    # LoginView, ChatView, AdminView
│       ├── components/               # InvoiceCard, PolicyCard, CorrectionForm, SupplementForm
│       ├── stores/                   # Pinia (auth, chat)
│       ├── router/                   # Vue Router
│       └── api/                      # Axios 封装
├── docs/
│   └── plan.md                       # 实现计划
└── CLAUDE.md                         # 项目指令文件
```

## SSE 事件协议

| 事件类型 | 触发时机 | 前端渲染 |
|---------|---------|---------|
| `plan` | Plan 节点完成 | 步骤列表（可折叠） |
| `thinking` | LLM token 流式输出 | 打字机效果 |
| `tool_call` | LLM 决定调用工具 | 工具状态指示器 |
| `tool_result` | 工具执行完成 | 工具结果（脱敏版） |
| `plan_step_update` | Observe 节点标记步骤 | 步骤状态更新 |
| `invoice_card` | OCR 扫描完成 | 发票信息卡片 |
| `policy_card` | 政策匹配完成 | 政策判责卡片（含 verdict + breakdown） |
| `supplement_form` | OCR 信息不完整 | 补充表单（商家/金额/品类） |
| `confirmation_request` | 政策匹配通过 | 确认/修正/取消按钮 |
| `knowledge_refs` | 纯政策咨询 | 可折叠来源引用 |
| `message` | LLM 最终回复 | 聊天气泡 |
| `done` | Agent 循环结束 | 停止加载动画 |

## 实现路线（8 个 Phase）

| Phase | 内容 | 状态 |
|-------|------|------|
| 1 | 修复聊天消息重复 bug（values→updates + 前端 assistantStarted） | ✅ |
| 2 | PaddleOCR 真实发票扫描 + 图像增强管线 | ✅ |
| 3 | BaseTool 抽象基类 + 5 个工具拆分 | ✅ |
| 4 | pydantic-settings 分组配置 + .env.example | ✅ |
| 5 | astream_events token 级流式 + 前端 thinking 渲染 | ✅ |
| 6 | Plan-Act-Observe 循环 + ReAct Agent 图 | ✅ |
| 7 | SessionAgentManager 会话级 LLM 隔离 + LRU 淘汰 | ✅ |
| 8 | ChromaDB 语义搜索 + Chunk ID 体系 + LLM Security Gateway 三层架构 | ✅ |
