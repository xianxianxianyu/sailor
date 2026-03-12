# Knowledge Base 模块

## 1. 作用

Knowledge Base 模块负责把资源沉淀为长期可复用知识，并在此基础上生成结构化报告。

当前 UI 对应：

- `frontend/src/pages/KBPage.tsx`

核心代码位置：

- `backend/app/routers/knowledge_bases.py`
- `backend/app/routers/reports.py`
- `core/storage/repositories.py`
- `core/storage/report_repository.py`
- `core/agent/kb_agent.py`
- `core/runner/app_job_handlers.py`

## 2. 核心对象

### 2.1 `KnowledgeBaseRepository`

- KB CRUD
- KB item 管理

### 2.2 `KBReportRepository`

- 保存 KB 报告
- 支持列出全部与读取 latest

### 2.3 `KBClusterAgent`

- 基于 KB 内资源生成 cluster / association / summary 等报告

## 3. 主要 job

- `kb_reports_generate`
- `sniffer_save_to_kb`

## 4. 对外接口

主要 API：

- `GET /knowledge-bases`
- `POST /knowledge-bases`
- `DELETE /knowledge-bases/{kb_id}`
- `GET /knowledge-bases/{kb_id}/items`
- `POST /knowledge-bases/{kb_id}/items`
- `DELETE /knowledge-bases/{kb_id}/items/{resource_id}`
- `POST /knowledge-bases/{kb_id}/reports`
- `GET /knowledge-bases/{kb_id}/reports`
- `GET /knowledge-bases/{kb_id}/reports/latest`

## 5. 运行链路

### 5.1 沉淀资源

资源可从 Sources、Sniffer 等入口加入 KB。KB 是“精选后的长期知识”，不是全量资源池。

### 5.2 生成报告

`POST /knowledge-bases/{kb_id}/reports` 创建 `kb_reports_generate` job，由 `KBClusterAgent` 生成报告并写入仓库。

## 6. 与其他模块的关系

- Sources / Sniffer / Intelligence 提供资源输入
- KG 可以把 KB 看作知识图谱的语义母体
- Follow 的部分输出也可沉淀到 KB

## 7. 当前事实

- KB 是当前系统里“从信息流到知识资产”的核心分界线
- 报告是按 KB 维度生成，不是全局系统报告
