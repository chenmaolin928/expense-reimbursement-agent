# Policy Center 重构 — 上传即见 KB + 规则

**Date**: 2026-07-02
**Branch**: 0.0.3

## 问题

管理员上传 PDF 后，后端同时创建了 KnowledgeBase（ChromaDB 向量库）和 AI 解析草案，但前端只展示了 AI 规则草案——KB 创建结果（知识库名、chunk 数、文档数、搜索测试）完全看不到。管理员无法验证向量检索是否正常工作。

## 设计

### 布局：两栏 → 三栏

```
┌─ Top Bar ────────────────────────────────────────────┐
│  ← Admin    Policy Center                            │
├────────────┬────────────────────────┬────────────────┤
│ 左侧栏     │  中间主区域            │ 右侧面板       │
│ Policy 列表 │  Upload / Draft Editor │ KB 详情 + 搜索 │
│ (260px)    │  / Policy JSON        │ (340px)        │
│            │  / Publish Bar        │ 条件显示       │
└────────────┴────────────────────────┴────────────────┘
```

### 各区域详情

#### 左侧栏 (260px) — 不变
- Policy 列表、新建按钮 — 现有逻辑保持不变

#### 中间主区域 — 增强

**新增：上传成功摘要卡片**（上传 PDF 后立即出现在 Draft Editor 上方）
```
✅ KB 已创建: "Policy v1 - 公司报销制度"
   📄 1 文档 · 12 chunks · 384d 已索引
   KB ID: 3

🤖 AI 解析完成: 识别出 6 个费用类型
   ⚠️ 2 个低置信度项目需人工确认
```

**保留：Expense Types 卡片、Save Draft / Normalize 按钮、Policy JSON Preview、Publish Bar**

#### 右侧面板 (340px) — 新增

仅当选中 version 有 `kb_id` 时显示。

- **KB 摘要**：名称、状态、文档数
- **文档列表**：可展开查看 chunk 详情
- **搜索测试**：输入关键词，内嵌 ChromaDB 搜索，展示 top-5 结果（snippet + score）

### 数据流

- 上传完成 → `handleUpload` 返回 `PolicyUploadResponse`（包含 `kb_id`）
- 右侧面板用 `kb_id` 调 `/knowledge/bases/{kb_id}/documents` 获取文档列表
- 搜索测试调 `/knowledge/search?q=...&kb_id=...` 直接在对应 KB 内搜索

### AdminView 清理

- 移除旧的 Policy Center 区域（文本贴入 + AI Parse + Save to Repository + Active Policy read-only）
- 保留 KB 管理面板（创建 KB、上传文档、ChromaDB Stats、Search Debug）

### 不做的

- 不修改后端 API（所有端点已就绪）
- 不改动路由结构
