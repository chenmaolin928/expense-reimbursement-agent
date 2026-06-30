# Expense Reimbursement AI Agent

企业级 AI Agent 报销系统 — 基于 **LangGraph ReAct Agent** 架构，实现云端推理 + 本地执行的安全模式。

## 业务背景

模拟真实企业场景：员工通过聊天界面提交发票，AI Agent 自动识别发票信息、查询公司报销政策、自主决策是否可报销，并在确认后自动提交报销申请、触发审批流程、发送邮件通知。

## 核心架构：Cloud Brain, Local Hands

```
企业内网 (FastAPI)
  └── LangGraph ReAct Agent (Python 编排, 不含本地 LLM)
       ├── 6 个工具全部在本地注册和执行（不暴露内部 API）
       ├── 推理时调用云端 DeepSeek API（也可用 Mock 模式零依赖运行）
       └── 敏感数据（员工姓名/邮箱/部门/银行卡）永不出内网
```

## 技术栈

### 后端
| 技术 | 用途 |
|------|------|
| **Python 3.11+** | 主语言 |
| **FastAPI** | Web 框架，RESTful API + SSE 流式响应 |
| **LangChain + LangGraph** | ReAct Agent 编排框架 |
| **DeepSeek API** | 云端大模型推理引擎（支持 Mock 模式零依赖运行） |
| **SQLAlchemy 2.0 + SQLite** | ORM + 本地数据库，零配置 |
| **Pydantic v2** | 数据校验 & 云端决策协议 Schema |
| **pytest** | 单元测试 & 集成测试（38 个用例） |

### 前端
| 技术 | 用途 |
|------|------|
| **Vue 3** (Composition API + `<script setup>`) | UI 框架 |
| **TypeScript** | 类型安全 |
| **Vite 8** | 构建工具 & 开发服务器（API 代理） |
| **Pinia** | 状态管理 |
| **Vue Router 4** | 路由（Hash 模式） |
| **Axios** | HTTP 客户端 + 拦截器 |

### AI Agent 特征（真 Agent，非 RAG/工作流）

| 特征 | 实现 |
|------|------|
| **自主规划** | LLM 自主决定下一步调哪个工具，同一接口不同输入走不同路径 |
| **工具调用** | 6 个本地工具：scan_invoice / search_knowledge / check_status / submit_reimbursement / send_notification / ask_clarification |
| **推理循环** | 标准 ReAct 模式：Reasoning → Acting → Observing → 再推理 |
| **记忆与上下文** | LangGraph State 跨多轮保持对话历史 |
| **自主工具选择** | Agent 基于 System Prompt 自己选工具，非硬编码 DAG |
| **可观测性** | SSE 流式推送每一步 tool_call / tool_result / thinking 状态 |

## 功能模块

### 员工端（聊天界面）
- 类 ChatGPT 聊天 UI，支持多会话管理
- 上传发票图片/PDF，AI Agent 自动 OCR 识别（Mock 模式模拟）
- 自然语言对话：询问报销政策、提交报销、查询进度
- Agent 自主决策：发票扫描 → 政策查询 → 金额比对 → 用户确认 → 提交报销 → 邮件通知
- 实时 SSE 流式显示 Agent 推理过程

### 管理员端
- 知识库管理：创建知识库、上传报销政策文档
- 文档搜索：基于关键词的政策检索
- 仪表盘：报销统计、员工数量、总额统计
- PII 映射清理：过期敏感数据自动清理

### 数据安全
- 员工 PII（姓名/邮箱/部门/银行卡）存储在内网 SQLite，永不出内网
- 云端 LLM 只收到脱敏数据 + 公开的报销政策
- pii_mappings 表 7 天自动过期
- DeepSeek 只知道工具的名称和参数 Schema，不知道内部 API 地址和认证方式

## 快速开始

### 后端

```bash
cd backend
pip install -r requirements.txt
python seed.py              # 初始化数据库（3 个演示用户）
python -m app.main          # 启动 http://localhost:8000
```

无需配置 DeepSeek API Key — Mock 模式自动启用，Agent 完整 ReAct 循环可用。

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
python -m pytest tests/ -v  # 38 passed
```

### 演示账号

| 用户名 | 密码 | 角色 | 页面 |
|--------|------|------|------|
| `admin` | `admin123` | 管理员 | 知识库管理 + 统计面板 |
| `zhangwei` | `zhang123` | 员工 | 聊天报销界面 |

## 项目结构

```
├── backend/
│   ├── app/
│   │   ├── api/           # FastAPI 路由 (auth, chat, knowledge, expenses, reimbursements, admin)
│   │   ├── domain/        # 纯业务对象 (enums, interfaces)
│   │   ├── services/      # Agent, Tools, OCR, 脱敏, 报销状态机, 通知
│   │   ├── infrastructure/ # ORM, LLM Client, File Store
│   │   └── schemas/       # Pydantic DTO
│   ├── tests/             # pytest (38 tests)
│   └── seed.py            # 种子数据
├── frontend/
│   └── src/
│       ├── views/         # LoginView, ChatView, AdminView
│       ├── stores/        # Pinia (auth, chat)
│       ├── router/        # Vue Router
│       └── api/           # Axios 封装
└── CLAUDE.md              # 项目大脑文档
```


