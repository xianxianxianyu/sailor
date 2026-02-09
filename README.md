# Sailor

**Sailor** 是一个面向技术从业者的个人信息雷达系统。它从 RSS 订阅源持续采集技术文章，经过预处理流水线清洗入库，再由 LLM Agent 进行智能分析（摘要、评分、主题分类、知识库推荐），最终在 Web 界面上呈现一个可扫描、可归档、可洞察的技术阅读工作台。

## 为什么做 Sailor

每天有大量高质量的技术博客在更新，但散落在几十个 RSS 源里。手动逐篇阅读效率低，容易错过高价值内容。Sailor 要解决的问题是：

1. **采集** — 把分散的 RSS 源统一拉取，去重后写入本地数据库
2. **理解** — 用 LLM 对每篇文章生成中文摘要、打分、提取关键洞察
3. **组织** — 将文章归档到知识库，由 LLM 对知识库做聚类分析和知识总结
4. **呈现** — 在一个干净的 Web 界面上完成「扫描 → 细读 → 归档 → 洞察」的完整工作流

## 架构总览

```
┌─────────────────────────────────────────────────────────────────┐
│                        Frontend (React + Vite)                  │
│  ┌──────────┐  ┌──────────────┐  ┌───────────┐  ┌───────────┐  │
│  │ Resource  │  │   Detail +   │  │   Task    │  │ KB Report │  │
│  │   Feed    │  │ AnalysisPanel│  │   Panel   │  │   Panel   │  │
│  └──────────┘  └──────────────┘  └───────────┘  └───────────┘  │
└────────────────────────────┬────────────────────────────────────┘
                             │ HTTP / JSON
┌────────────────────────────▼────────────────────────────────────┐
│                     Backend (FastAPI)                            │
│  /resources  /knowledge-bases  /feeds  /tasks  /analyses        │
└──────┬──────────────┬──────────────┬────────────────────────────┘
       │              │              │
┌──────▼──────┐ ┌─────▼─────┐ ┌─────▼──────┐
│  Ingestion  │ │  Agent 1  │ │  Agent 2   │
│  Service    │ │  Article  │ │  KB Cluster│
│             │ │  Analysis │ │  Analysis  │
└──────┬──────┘ └─────┬─────┘ └─────┬──────┘
       │              │              │
┌──────▼──────────────▼──────────────▼────────────────────────────┐
│                        Core Layer                               │
│  ┌───────────┐  ┌──────────┐  ┌──────────┐  ┌───────────────┐  │
│  │ Collector  │  │ Pipeline │  │  Agent   │  │   Storage     │  │
│  │ Engine     │  │ Stages   │  │  (LLM)   │  │   (SQLite)    │  │
│  └───────────┘  └──────────┘  └──────────┘  └───────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

### 数据流

```
RSS Feeds ──┐
Seed JSON ──┼──▶ CollectionEngine ──▶ Pipeline ──▶ resources 表
Miniflux  ──┘    (去重合并)          (清洗/富化)

resources 表 ──▶ Agent 1 (LLM) ──▶ resource_analyses 表
                 (摘要/评分/分类)

kb_items 表 ──▶ Agent 2 (LLM) ──▶ kb_reports 表
                (聚类/关联/总结)
```

## 项目结构

```
sailor/
├── 1.md                          # 92 个 RSS 源（OPML 格式）
├── data/
│   └── seed_entries.json         # 3 条本地种子数据（离线测试用）
│
├── core/                         # 核心业务逻辑（不依赖 Web 框架）
│   ├── models.py                 # 领域模型：RawEntry, Resource, KnowledgeBase,
│   │                             #   RSSFeed, ResourceAnalysis, KBReport
│   ├── collector/
│   │   ├── base.py               # Collector 抽象基类 + CollectionEngine
│   │   ├── rss_engine.py         # 本地 JSON seed 采集器
│   │   ├── miniflux_engine.py    # Miniflux API 采集器
│   │   ├── opml_parser.py        # OPML XML 解析（支持双段去重）
│   │   └── live_rss_engine.py    # feedparser 实时 RSS 抓取器
│   ├── pipeline/
│   │   ├── base.py               # Pipeline 基类 + PipelineContext
│   │   ├── stages.py             # Normalize → Extract → Clean → Enrich → Build
│   │   └── default_pipeline.py   # 默认流水线组装
│   ├── agent/
│   │   ├── base.py               # LLMClient（urllib 调用 OpenAI API）
│   │   ├── prompts.py            # 所有 Prompt 模板
│   │   ├── article_agent.py      # Agent 1：文章分析
│   │   └── kb_agent.py           # Agent 2：知识库聚类分析
│   ├── storage/
│   │   ├── db.py                 # SQLite 连接 + 6 张表的 Schema
│   │   ├── repositories.py       # Resource / KnowledgeBase 仓储
│   │   ├── feed_repository.py    # RSS Feed 仓储
│   │   ├── analysis_repository.py # 分析结果仓储
│   │   └── report_repository.py  # KB 报告仓储
│   ├── services/
│   │   └── ingestion.py          # 采集 → 流水线 → 入库编排
│   └── tasks/
│       ├── models.py             # MainFlowTask 数据类
│       └── planner.py            # 主流程任务规划器
│
├── backend/                      # FastAPI Web 层
│   ├── .env.example              # 环境变量模板
│   ├── requirements.txt          # Python 依赖
│   └── app/
│       ├── config.py             # 配置加载（环境变量）
│       ├── container.py          # 依赖注入容器
│       ├── main.py               # FastAPI 入口 + 路由挂载
│       ├── schemas.py            # Pydantic 请求/响应模型
│       └── routers/
│           ├── resources.py      # GET /resources, GET /resources/{id}
│           ├── knowledge_bases.py # GET /knowledge-bases, POST /{kb_id}/items
│           ├── tasks.py          # POST /tasks/run-ingestion, GET /tasks/main-flow
│           ├── feeds.py          # POST /feeds/import-opml, GET /feeds
│           ├── analyses.py       # POST /tasks/run-analysis, GET /analyses/status
│           └── reports.py        # POST /{kb_id}/reports, GET /{kb_id}/reports
│
└── frontend/                     # React + TypeScript + Vite
    └── src/
        ├── App.tsx               # 主应用（Feed + Detail + Tasks + Reports）
        ├── api.ts                # 后端 API 调用封装
        ├── types.ts              # TypeScript 类型定义
        ├── styles.css            # 全局样式
        └── components/
            ├── ResourceCard.tsx   # 资源卡片（含评分徽章）
            ├── AnalysisPanel.tsx  # AI 分析结果展示
            ├── KBReportPanel.tsx  # 知识库报告展示
            ├── KBPickerModal.tsx  # 知识库选择弹窗
            └── TaskPanel.tsx      # 任务面板
```

## 快速开始

### 前置条件

- Python 3.11+
- Node.js 18+
- （可选）OpenAI API Key — 用于 AI 分析功能

### 1. 启动后端

```bash
cd sailor

# 创建虚拟环境
conda create -n sailor python=3.11 -y
conda activate sailor

# 安装依赖
pip install -r backend/requirements.txt

# （可选）配置 OpenAI，启用 AI 分析功能
set OPENAI_API_KEY=sk-your-key-here
# 如果使用兼容 OpenAI 的第三方服务：
# set OPENAI_BASE_URL=https://your-provider.com/v1
# set OPENAI_MODEL=gpt-4o-mini

# 启动
uvicorn backend.app.main:app --reload
```

后端默认地址：`http://localhost:8000`

### 2. 启动前端

```bash
cd sailor/frontend
npm install
npm run dev
```

前端默认地址：`http://localhost:5173`

### 3. 基本工作流

打开浏览器访问 `http://localhost:5173`，页面加载时会自动触发一次采集（从本地 seed 数据）。

**导入 RSS 源并采集真实文章：**

```bash
# 导入 1.md 中的 92 个 RSS 源
curl -X POST http://localhost:8000/feeds/import-opml -H "Content-Type: application/json" -d "{}"

# 再次触发采集（现在会包含实时 RSS 抓取）
curl -X POST http://localhost:8000/tasks/run-ingestion
```

**运行 AI 分析（需要 OpenAI API Key）：**

```bash
# 对所有资源运行 Agent 1 分析
curl -X POST http://localhost:8000/tasks/run-analysis

# 查看分析进度
curl http://localhost:8000/analyses/status
```

**生成知识库报告：**

先在前端将一些文章归档到知识库（至少 3 篇），然后：

```bash
# 对某个知识库生成聚类/关联/总结报告
curl -X POST http://localhost:8000/knowledge-bases/kb_llm/reports
```

也可以直接在前端的 KB Reports 面板中选择知识库并点击 "Generate Reports"。

## API 一览

### 资源管理
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/resources?status=inbox` | 列出收件箱资源 |
| GET | `/resources/{resource_id}` | 获取单个资源 |
| GET | `/resources/{resource_id}/knowledge-bases` | 资源所属的知识库 |
| GET | `/resources/{resource_id}/analysis` | 获取资源的 AI 分析结果 |

### 知识库
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/knowledge-bases` | 列出所有知识库 |
| POST | `/knowledge-bases/{kb_id}/items` | 归档资源到知识库 |

### Feed 管理
| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/feeds/import-opml` | 导入 OPML 文件中的 RSS 源 |
| GET | `/feeds` | 列出所有 Feed |
| PATCH | `/feeds/{feed_id}?enabled=true` | 启用/禁用 Feed |

### 任务与分析
| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/tasks/run-ingestion` | 触发采集 + 入库 |
| POST | `/tasks/run-analysis` | 触发 AI 批量分析 |
| GET | `/analyses/status` | 分析进度概览 |
| GET | `/tasks/main-flow` | 主流程任务列表 |

### KB 报告
| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/knowledge-bases/{kb_id}/reports` | 生成聚类/关联/总结报告 |
| GET | `/knowledge-bases/{kb_id}/reports` | 获取所有报告 |
| GET | `/knowledge-bases/{kb_id}/reports/latest` | 获取最新一轮报告 |

## 环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `SAILOR_DB_PATH` | `./data/sailor.db` | SQLite 数据库路径 |
| `SAILOR_SEED_FILE` | `./data/seed_entries.json` | 本地种子数据文件 |
| `SAILOR_OPML_FILE` | `./1.md` | OPML RSS 源文件 |
| `MINIFLUX_BASE_URL` | （空） | Miniflux 实例地址 |
| `MINIFLUX_TOKEN` | （空） | Miniflux API Token |
| `OPENAI_API_KEY` | （空） | OpenAI API Key |
| `OPENAI_BASE_URL` | `https://api.openai.com/v1` | OpenAI 兼容 API 地址 |
| `OPENAI_MODEL` | `gpt-4o-mini` | 使用的模型 |
| `CORS_ORIGINS` | `http://localhost:5173` | 允许的前端来源 |
| `VITE_API_BASE` | `http://localhost:8000` | 前端连接的后端地址 |

## 数据库

SQLite，共 6 张表：

| 表 | 用途 |
|----|------|
| `resources` | 经过流水线处理的文章资源 |
| `knowledge_bases` | 知识库（默认 3 个：LLM Notes / Platform / Product Engineering） |
| `kb_items` | 资源与知识库的归档关系 |
| `rss_feeds` | RSS 订阅源管理 |
| `resource_analyses` | Agent 1 的文章分析结果 |
| `kb_reports` | Agent 2 的知识库报告 |

## 采集引擎

Sailor 支持三种数据源，由 `CollectionEngine` 统一调度并按 `source + url` 去重：

| 采集器 | 数据源 | 说明 |
|--------|--------|------|
| `RSSCollector` | `seed_entries.json` | 本地 JSON 种子数据，离线测试用 |
| `MinifluxCollector` | Miniflux API | 需要配置 `MINIFLUX_BASE_URL` 和 `MINIFLUX_TOKEN` |
| `LiveRSSCollector` | 真实 RSS Feed | 基于 feedparser，抓取 `rss_feeds` 表中启用的源 |

## AI Agent

两个 Agent 均通过 OpenAI Chat Completions API 调用，使用 `urllib` 实现（不依赖 openai SDK），支持任何 OpenAI 兼容的 API 服务。

### Agent 1：文章分析

对每篇文章生成：
- **中文摘要**（200 字以内）
- **主题标签**（如 LLM, DevOps, Security）
- **三维评分**（depth 深度 / utility 实用性 / novelty 新颖性，1-10 分）
- **知识库推荐**（推荐归档到哪个 KB，附置信度和理由）
- **关键洞察**（核心论点 / 技术要点 / 实践建议）

触发方式：`POST /tasks/run-analysis`（手动触发，可控制成本）

### Agent 2：知识库聚类分析

对知识库内的文章生成三种报告：
- **聚类报告** — 主题聚类、热门话题、新兴趋势
- **关联报告** — 文章间关联关系、推荐阅读路径
- **总结报告** — 知识总结、知识空白、发展建议

前提：KB 内至少 3 篇已分析的文章。输入不传全文，只传摘要 + 主题，控制 token 成本。

触发方式：`POST /knowledge-bases/{kb_id}/reports`

## 设计决策

- **手动触发分析**：避免自动调用 LLM 产生意外费用，用户完全控制分析时机
- **urllib 而非 openai SDK**：与项目中 MinifluxCollector 风格一致，减少依赖
- **SQLite 单文件数据库**：零配置，适合个人工具场景
- **gpt-4o-mini 默认模型**：成本低、速度快，92 个 Feed 全量分析约 $0.5-1.0
- **OPML 双段去重**：`1.md` 包含英文版和中文版两段 OPML，解析时按 xmlUrl 去重取首次出现的版本
