# Sailor

你的个人技术信息雷达：采集技术内容、LLM 智能打标、知识库收藏与沉淀。

Sailor 是一个本地优先（SQLite）的技术信息工作台，后端基于 FastAPI，前端基于 React。它支持 RSS / 统一源采集、可选 LLM 深度分析、知识库聚类报告和日志流。

## 功能概览

- 多源采集：`RSS`、统一源（含 `rss/atom/jsonfeed/web_page/academic_api/...`）
- 智能打标：基于现有标签偏好 + 文章内容，自动分配 1-4 个标签
- 知识库管理：创建 KB、收藏文章、移除文章
- 深度分析：单篇文章 LLM 摘要/评分/洞察；KB 级别报告（cluster/association/summary）
- 配置中心：前端可直接配置 LLM（含连通性测试、`auto_analyze`）
- 可观测性：历史日志 + SSE 实时日志流

## 当前前端可见页面

`App` 当前挂载 4 个主页面 + 2 个全局面板：

- 趋势（Trending）
- 标签（Tag Cloud + CRUD）
- 知识库（KB CRUD + 条目管理）
- 订阅源（统一源列表/运行/查看资源）
- 全局：日志面板、LLM 设置弹窗

> 说明：代码中存在部分 API 能力（如 full pipeline、OPML/本地源同步）当前不一定有显式按钮直达；可直接调用 API。

## 快速开始

### 前置条件

- Python 3.11+
- Node.js 18+

### 1) 安装依赖

```bash
npm install
cd frontend && npm install
cd ..
pip install -r backend/requirements.txt
```

### 2) Web 开发模式（推荐）

```bash
npm run dev
```

默认启动：

- 后端：`http://127.0.0.1:8000`
- 前端：`http://localhost:5173`

### 3) Electron 桌面模式（开发态）

```bash
npm run desktop:dev
```

桌面模式会在 Electron 内拉起并等待后端/前端开发服务就绪后加载页面。它本质上是 dev server 封装，不是打包产物流程。

## LLM 配置

Sailor 使用 OpenAI Chat Completions 兼容协议，可接 DeepSeek / OpenAI / Ollama / vLLM 等。

### 方式 A：环境变量

```bash
export OPENAI_API_KEY=sk-xxx
export OPENAI_BASE_URL=https://api.deepseek.com/v1
export OPENAI_MODEL=deepseek-chat
```

### 方式 B：前端配置页（推荐）

- 打开右上角配置（设置）
- 调用后端：`GET/PUT/POST /settings/llm*`
- API Key 写入系统 keyring，非密钥配置写入 `data/llm_config.json`

`data/llm_config.json` 示例：

```json
{
  "provider": "deepseek",
  "base_url": "https://api.deepseek.com",
  "model": "deepseek-chat",
  "temperature": 0.3,
  "max_tokens": 4000,
  "auto_analyze": true
}
```

## 架构与数据流

### 分层

- `frontend/`：React 19 + TypeScript + Vite
- `backend/app/`：FastAPI 路由与依赖注入
- `core/`：采集器、流水线、Agent、仓储、服务层
- `data/`：SQLite 与运行时配置
- `electron/`：桌面开发启动器

### 主流程（后端）

1. Collector 采集 entries
2. Pipeline 处理（Normalize -> Extract/Clean -> Enrich -> Build）
3. 资源入库（`resources`）+ 源索引（`source_item_index`）
4. 可选：LLM 打标（`TaggingAgent`）
5. 可选：LLM 深度分析（`ArticleAnalysisAgent`）
6. 收藏到 KB 后触发偏好权重反馈（tag weight +1）

## 项目结构

```text
sailor/
├── backend/
│   └── app/
│       ├── main.py
│       ├── container.py
│       ├── config.py
│       ├── schemas.py
│       └── routers/
│           ├── analyses.py
│           ├── feeds.py
│           ├── knowledge_bases.py
│           ├── logs.py
│           ├── reports.py
│           ├── resources.py
│           ├── settings.py
│           ├── sources.py
│           ├── tags.py
│           ├── tasks.py
│           └── trending.py
├── core/
│   ├── agent/
│   ├── collector/
│   ├── pipeline/
│   ├── services/
│   └── storage/
├── frontend/
├── electron/
├── data/
└── README.md
```

## API 参考

以下为当前后端实际挂载的路由（按模块分组）。

### 健康检查

| Method | Endpoint | 说明 |
|---|---|---|
| `GET` | `/healthz` | 服务健康状态 |

### Trending

| Method | Endpoint | 说明 |
|---|---|---|
| `GET` | `/trending` | 获取当前 Trending（不触发打标） |
| `POST` | `/trending/generate` | 生成 Trending（会对未打标资源触发打标） |
| `POST` | `/trending/pipeline` | 一次执行采集 + 打标 + Trending |

### 资源与分析

| Method | Endpoint | 说明 |
|---|---|---|
| `GET` | `/resources` | 资源列表（支持 `topic`、`status`） |
| `GET` | `/resources/{resource_id}` | 资源详情 |
| `GET` | `/resources/{resource_id}/knowledge-bases` | 资源所属 KB |
| `POST` | `/resources/{resource_id}/analyze` | 单篇资源深度分析 |
| `GET` | `/resources/{resource_id}/analysis` | 获取单篇分析结果 |
| `POST` | `/tasks/run-analysis` | 批量分析任务 |
| `GET` | `/analyses/status` | 分析状态统计 |

### 知识库与报告

| Method | Endpoint | 说明 |
|---|---|---|
| `GET` | `/knowledge-bases` | KB 列表 |
| `POST` | `/knowledge-bases` | 创建 KB |
| `DELETE` | `/knowledge-bases/{kb_id}` | 删除 KB |
| `GET` | `/knowledge-bases/{kb_id}/items` | KB 条目列表 |
| `POST` | `/knowledge-bases/{kb_id}/items` | 添加条目到 KB |
| `DELETE` | `/knowledge-bases/{kb_id}/items/{resource_id}` | 移除 KB 条目 |
| `POST` | `/knowledge-bases/{kb_id}/reports` | 生成 KB 报告 |
| `GET` | `/knowledge-bases/{kb_id}/reports` | 获取 KB 报告列表 |
| `GET` | `/knowledge-bases/{kb_id}/reports/latest` | 获取每类最新报告 |

### 标签

| Method | Endpoint | 说明 |
|---|---|---|
| `GET` | `/tags` | 标签列表 |
| `POST` | `/tags` | 创建标签 |
| `PUT` | `/tags/{tag_id}` | 更新标签 |
| `DELETE` | `/tags/{tag_id}` | 删除标签 |
| `GET` | `/tags/{tag_id}/resources` | 某标签下资源 |
| `POST` | `/tags/resource/{resource_id}/{tag_id}` | 手动给资源打标签 |
| `GET` | `/tags/resource/{resource_id}` | 查询资源标签 |

### RSS 兼容源

| Method | Endpoint | 说明 |
|---|---|---|
| `GET` | `/feeds` | RSS 源列表 |
| `POST` | `/feeds` | 添加 RSS 源 |
| `PATCH` | `/feeds/{feed_id}` | 更新/启停 RSS 源 |
| `DELETE` | `/feeds/{feed_id}` | 删除 RSS 源 |
| `POST` | `/feeds/{feed_id}/run` | 运行单个 RSS 源 |
| `GET` | `/feeds/{feed_id}/resources` | RSS 源抓取结果 |
| `POST` | `/feeds/import-opml` | 导入 OPML |
| `GET` | `/feeds/source-status` | 源状态汇总 |

### 统一源管理

| Method | Endpoint | 说明 |
|---|---|---|
| `GET` | `/sources` | 统一源列表（支持过滤） |
| `POST` | `/sources` | 创建统一源 |
| `PATCH` | `/sources/{source_id}` | 更新统一源 |
| `DELETE` | `/sources/{source_id}` | 删除统一源 |
| `POST` | `/sources/{source_id}/run` | 运行单个统一源 |
| `POST` | `/sources/run-by-type/{source_type}` | 按类型批量运行 |
| `GET` | `/sources/{source_id}/runs` | 运行历史 |
| `GET` | `/sources/{source_id}/resources` | 源抓取资源 |
| `POST` | `/sources/import-local` | 从本地 JSON 同步源 |
| `GET` | `/sources/status` | 统一源状态统计 |

### 设置与日志

| Method | Endpoint | 说明 |
|---|---|---|
| `GET` | `/settings/llm` | 获取 LLM 设置 |
| `PUT` | `/settings/llm` | 保存并热重载 LLM 设置 |
| `POST` | `/settings/llm/test` | 测试 LLM 连通性 |
| `GET` | `/logs` | 获取历史日志 |
| `GET` | `/logs/stream` | SSE 实时日志流 |

### 任务（兼容/开发中）

| Method | Endpoint | 说明 |
|---|---|---|
| `POST` | `/tasks/run-ingestion` | 采集任务接口（当前实现存在旧字段兼容问题） |
| `GET` | `/tasks/main-flow` | 主流程任务信息 |
| `GET` | `/tasks/ingestion-status` | 采集状态接口（当前实现存在依赖字段问题） |

## 配置

环境变量（`backend/app/config.py`）：

| 变量 | 默认值 | 说明 |
|---|---|---|
| `SAILOR_DB_PATH` | `data/sailor.db` | SQLite 路径 |
| `SAILOR_SEED_FILE` | `data/seed_entries.json` | seed 数据路径 |
| `SAILOR_OPML_FILE` | `1.md` | OPML 默认路径 |
| `OPENAI_API_KEY` | - | LLM API Key |
| `OPENAI_BASE_URL` | `https://api.openai.com/v1` | 兼容网关地址 |
| `OPENAI_MODEL` | `gpt-4o-mini` | 模型名 |
| `MINIFLUX_BASE_URL` | - | Miniflux 实例地址 |
| `MINIFLUX_TOKEN` | - | Miniflux token |
| `CORS_ORIGINS` | `http://localhost:5173` | CORS 来源列表 |

## 数据库

默认 SQLite，共 12 张表：

- `resources`
- `knowledge_bases`
- `kb_items`
- `rss_feeds`
- `source_registry`
- `source_run_log`
- `source_item_index`
- `resource_analyses`
- `kb_reports`
- `user_tags`
- `user_actions`
- `resource_tags`

首次启动自动建表。

## 已知限制

- `tasks` 路由中的部分采集状态实现仍保留旧字段引用，推荐优先使用 `/trending/pipeline`、`/sources/*/run`、`/feeds/*/run`。
- `backend/requirements.txt` 当前未声明部分可选采集依赖（如某些 source type 需要的第三方包），如启用对应类型请按需补装。
- 前端中存在部分未挂载组件/未显式入口的能力，API 可直接使用。

## 技术栈

- Frontend: React 19, TypeScript, Vite 7
- Backend: FastAPI, Uvicorn, Pydantic
- Storage: SQLite
- LLM: OpenAI-compatible Chat Completions API

## License

MIT
