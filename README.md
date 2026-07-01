# Expense Reimbursement AI Agent

企业级 AI Agent 报销系统 — 基于 **LangGraph Plan-Act-Observe Agent** 架构，Cloud Brain, Local Hands 安全模式。

## 架构全景

```
┌──────────────────────────────────────────────────────────────────┐
│                    Vue 3 前端 (ChatView)                          │
│  SSE 流式: thinking / tool_call / tool_result / plan / message   │
└──────────────────────────┬───────────────────────────────────────┘
                           │ POST /api/v1/chat (SSE)
┌──────────────────────────▼───────────────────────────────────────┐
│                    FastAPI 后端                                   │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │  LangGraph PAO Agent                                       │  │
│  │  START → plan → act ↔ tools → observe → (act | END)       │  │
│  │  SessionAgentManager (LRU 隔离) + astream_events 流式      │  │
│  └────────────────────────────────────────────────────────────┘  │
│  ┌──────────┬──────────┬──────────┬──────────┬──────────────┐  │
│  │ OCR      │ 知识库   │ 脱敏     │ 报销     │ 通知         │  │
│  │ EasyOCR  │ ChromaDB │ PII映射  │ Create   │ Email模拟    │  │
│  │ 真实扫描  │ 语义搜索 │ ENT-tok  │ Report   │              │  │
│  └────┬─────┴────┬─────┴────┬─────┴────┬─────┴──────┬───────┘  │
│       │          │          │          │            │          │
│  ┌────▼──────────▼──────────▼──────────▼────────────▼─────┐    │
│  │           SQLite (9 tables) + ChromaDB (向量)           │    │
│  │  employees / users / chat_sessions / chat_messages     │    │
│  │  knowledge_bases / knowledge_documents                 │    │
│  │  expense_reports / expense_items / pii_mappings        │    │
│  │  notification_log / status_transitions                 │    │
│  │  chroma/knowledge_chunks (384d embeddings)             │    │
│  └────────────────────────────────────────────────────────┘    │
└──────────────────────────────────────────────────────────────────┘
```

## 技术栈

### 后端
| 技术 | 用途 |
|------|------|
| **Python 3.11+** | 主语言 |
| **FastAPI** | Web 框架，RESTful API + SSE 流式响应 |
| **LangChain + LangGraph** | PAO Agent 编排（plan → act → observe 循环） |
| **DeepSeek API** | 云端 LLM 推理（必须显式配置 API Key） |
| **SQLAlchemy 2.0 + SQLite** | ORM + 本地数据库，零配置 |
| **ChromaDB** | 嵌入式向量数据库，知识库语义搜索 |
| **sentence-transformers** | 本地 embedding 模型（paraphrase-multilingual-MiniLM-L12-v2，118MB） |
| **EasyOCR** | 中文发票 OCR（zh_sim + en） |
| **Pydantic v2** | 数据校验 & Schema |
| **pytest** | 39 个测试用例 |

### 前端
| 技术 | 用途 |
|------|------|
| **Vue 3** (Composition API) | UI 框架 |
| **TypeScript** | 类型安全 |
| **Vite** | 构建工具 |
| **Pinia** | 状态管理 |
| **Vue Router 4** | 路由（Hash 模式） |

## Agent 特征（真 Agent，非 RAG/硬编码工作流）

| 特征 | 实现 |
|------|------|
| **显式规划** | Plan 节点生成执行计划，列出步骤 + 工具 + 参数 |
| **自主执行** | Act 节点 LLM 自主决定调哪个工具 |
| **结果观察** | Observe 节点评估工具结果，标记步骤 done/failed，计划可重规划 |
| **PAO 循环** | Plan → Act → Observe → (继续Act | 结束) |
| **流式思考** | astream_events("v2") 推送 token 级流式 thinking |
| **会话隔离** | SessionAgentManager LRU 隔离，每会话独立 LLM 上下文 |

## 工具清单

| 工具 | 说明 | 状态 |
|------|------|------|
| `scan_invoice` | OCR 扫描发票：提取金额/商户/日期/品类 | EasyOCR 真实实现，文件不存在回退 mock |
| `search_knowledge` | 语义搜索公司报销政策 | ChromaDB + embedding，返回相关度分数 |
| `check_reimbursement_status` | 查询报销单审批进度 | 真实 DB 查询 |
| `submit_reimbursement` | 提交报销申请 | 写 ExpenseReport + 状态流转 |
| `send_notification` | 发送邮件通知 | 写 NotificationLog（外部邮件 API mock） |

## 知识库 Chunk ID 体系

```
格式: kb-{kb_id}-doc-{doc_id}-chunk-{idx:04d}

示例: kb-1-doc-3-chunk-0002
      ↑       ↑       ↑
      知识库   文档    分块序号（0-index）
```

- **按文档更新**：`ChromaDB.delete(where={"doc_id": X})` → 重新分块 → embedding → 入库，不碰其他文档
- **按知识库清理**：删除知识库时批量清除所有关联 chunks
- **自描述 ID**：chunk_id 包含完整来源信息，调试/审计可追溯

## 数据安全红线

| 可发云端 | 绝不发云端 |
|---------|-----------|
| 公司报销政策（知识库文档） | 员工姓名/ID/部门/邮箱/银行账号 |
| 脱敏后的发票数据（商家/金额/品类/日期） | 内部 API 地址/认证/token |
| 工具定义（函数名 + 参数 schema） | 数据库连接字符串 |
| ChromaDB 查询 embedding | PII 映射表 |

## 快速开始

### 后端

```bash
cd backend
pip install -r requirements.txt
python seed.py              # 初始化数据库（演示用户 + 示例知识库）
python -m app.main          # 启动 http://localhost:8000
```

```bash
cp .env.example .env        # 编辑 DEEPSEEK_API_KEY=sk-your-key
# 可选: OCR_ENGINE=easyocr  （默认已开启真实 OCR）
```

未配置 `DEEPSEEK_API_KEY` 时，后端会直接报错，运行时不会再自动回退到 mock 模式。

### 前端

```bash
cd frontend
npm install
npm run dev                 # 启动 http://localhost:5173
```

### 测试

```bash
cd backend
python -m pytest tests/ -v  # 39 passed
```

### 验证知识库分块质量

```bash
# 上传政策文档后查看返回的 chunks_preview（前5段）
curl -X POST http://localhost:8000/api/v1/knowledge/bases/1/documents \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@报销政策.pdf"

# 查看全部 chunks + chunk IDs
curl http://localhost:8000/api/v1/knowledge/documents/1/chunks

# 语义搜索
curl "http://localhost:8000/api/v1/knowledge/search?q=餐补标准"
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
│   │   ├── api/              # FastAPI 路由 (auth, chat, knowledge, admin)
│   │   ├── domain/           # 纯业务对象 (enums)
│   │   ├── services/         # Agent, Tools, OCR, 脱敏, 知识库, 会话管理
│   │   │   └── tools/        # 5 个工具 (BaseTool 抽象基类)
│   │   ├── infrastructure/   # ORM, LLM Client (DeepSeek 运行时，测试可显式注入 fake model)
│   │   └── schemas/          # Pydantic DTO
│   ├── data/
│   │   ├── chroma/           # ChromaDB 持久化向量数据
│   │   └── invoices/         # 上传的发票文件
│   ├── tests/                # pytest (39 tests)
│   └── seed.py               # 种子数据
├── frontend/
│   └── src/
│       ├── views/            # LoginView, ChatView, AdminView
│       ├── stores/           # Pinia (auth, chat)
│       ├── router/           # Vue Router
│       └── api/              # Axios 封装
└── CLAUDE.md                 # 项目指令文件
```

## 实现路线（8 个 Phase）

| Phase | 内容 | 状态 |
|-------|------|------|
| 1 | 修复聊天消息重复 bug（values→updates + 前端 assistantStarted） | ✅ |
| 2b | 知识库 BM25 关键词搜索（已升级为 ChromaDB Phase 8） | ✅ |
| 2a | EasyOCR 真实发票扫描（文件不存在回退 mock） | ✅ |
| 3 | BaseTool 抽象基类 + 5 个工具拆分 | ✅ |
| 4 | pydantic-settings 分组配置 + .env.example | ✅ |
| 5 | astream_events token 级流式 + 前端 thinking 渲染 | ✅ |
| 6 | Plan-Act-Observe 循环（plan → act ↔ tools → observe） | ✅ |
| 7 | SessionAgentManager 会话级 LLM 隔离 + LRU 淘汰 | ✅ |
| 8 | ChromaDB 语义搜索 + Chunk ID 体系 + chunks 预览 API | ✅ |
