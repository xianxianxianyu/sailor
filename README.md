<p align="center">
  <img src="https://em-content.zobj.net/source/apple/391/sailboat_26f5.png" width="80" />
</p>

<h1 align="center">Sailor</h1>

<p align="center">
  <strong>你的个人技术信息雷达。一键抓取，智能打标，Trending 报告，知识库收藏。</strong>
</p>

<p align="center">
  <a href="#快速开始">快速开始</a> •
  <a href="#功能特性">功能特性</a> •
  <a href="#架构">架构</a> •
  <a href="#api-参考">API 参考</a> •
  <a href="#配置">配置</a> •
  <a href="#contributing">Contributing</a>
</p>

---

Sailor 从 RSS 和非 RSS 源持续采集技术文章，通过 LLM 智能打标分类，生成类似 GitHub Trending 的报告，让你在一个界面完成「发现 → 阅读 → 收藏 → 沉淀」的完整知识工作流。收藏行为会反哺回用户偏好，让推荐越用越准。

## 功能特性

🚀 **一键 Pipeline** — 点一个按钮完成抓取 → 打标 → 生成 Trending 报告的全流程

📊 **Trending 报告** — 按标签分组展示文章，类似 GitHub Trending，点击标题直达原文

🏷️ **LLM 智能打标** — 基于用户已有标签偏好 + 文章内容，由 LLM 动态分配标签，替代硬编码规则

📚 **知识库管理** — 创建多个知识库，从 Trending 中一键收藏文章，随时查看和管理

📡 **统一源管理** — RSS 与非 RSS 统一注册、运行、回放，支持 OPML 导入与本地 JSON 配置同步

🏷️ **标签云** — 权重驱动的标签可视化，越常用的标签越大，支持手动增删

🔄 **偏好反哺** — 收藏文章时自动提升相关标签权重，下次打标更贴合你的兴趣

🤖 **深度分析** — 可选的 LLM Agent 对文章做摘要、评分、洞察提取，对知识库做聚类分析

## Demo

```
┌─────────────────────────────────────────────────────────────────┐
│  Sailor                              [🚀 一键抓取]  [刷新]     │
├────────┬────────────────────────────────────────────────────────┤
│  📊 趋势│  Trending Report                                      │
│  🏷️ 标签│  共 45 篇文章，8 个标签                               │
│  📚 知识│                                                       │
│  📡 订阅│  ┌─ LLM ──────────────────────────────────────────┐  │
│        │  │ Building RAG Pipelines with LangChain       [+] │  │
│        │  │ Fine-tuning LLMs for Production             [+] │  │
│        │  └──────────────────────────────────────────────────┘  │
│        │                                                        │
│        │  ┌─ DevOps ────────────────────────────────────────┐  │
│        │  │ Kubernetes Gateway API Deep Dive             [+] │  │
│        │  └──────────────────────────────────────────────────┘  │
└────────┴────────────────────────────────────────────────────────┘
```

## 快速开始

### 前置条件

- Python 3.11+
- Node.js 18+
- （可选）OpenAI 兼容 API Key — 用于 LLM 智能打标和深度分析

### 一行命令启动桌面版（Electron）

```bash
cd sailor && npm run desktop:dev
```

说明：

- `npm run dev` 会自动触发 `predev`，完成根依赖、前端依赖、后端依赖安装。
- 启动后会并发运行：
  - 后端：`http://127.0.0.1:8000`
  - 前端：`http://localhost:5173`

打开 `http://localhost:5173`，点击 **🚀 一键抓取** 开始使用。

> 桌面版会在 Electron 中拉起前后端服务，适合本地一体化使用。

### 配置 LLM（推荐）

设置环境变量启用智能打标：

```bash
export OPENAI_API_KEY=sk-your-key
export OPENAI_BASE_URL=https://api.deepseek.com/v1   # 或其他兼容 API
export OPENAI_MODEL=deepseek-reasoner                  # 或 gpt-4o-mini
```

> Sailor 使用 OpenAI Chat Completions API 协议，兼容 DeepSeek、Ollama、vLLM 等任何兼容服务。

### 导入 / 同步订阅源

```bash
# 方式 1：在前端 📡 订阅源页面导入 OPML / 同步 SailorRSSConfig.json
# 方式 2：API 导入 OPML
curl -X POST http://localhost:8000/feeds/import-opml \
  -H "Content-Type: application/json" -d '{}'

# 方式 3：API 同步本地 JSON 源配置（默认 SailorRSSConfig.json）
curl -X POST http://localhost:8000/sources/import-local \
  -H "Content-Type: application/json" -d '{}'
```

## 架构

```
┌─────────────────────────────────────────────────────────────────────┐
│                     Frontend (React 19 + Vite 7)                     │
│                                                                      │
│  NavBar ──┬── TrendingPage   按 Tag 分组的文章列表 + 收藏到 KB      │
│           ├── TagPage        标签云 + 标签表格 + CRUD                │
│           ├── KBPage         知识库列表 + 收藏文章管理               │
│           ├── FeedPage       统一源管理 + OPML/JSON 同步 + 一键运行  │
│           └── LogPanel       历史日志 + 实时日志（SSE）              │
├─────────────────────────────────────────────────────────────────────┤
│                     Backend (FastAPI + SQLite)                        │
│                                                                      │
│  Routers ─── /trending /tags /knowledge-bases /feeds /sources        │
│              /resources /tasks /analyses /reports /logs              │
│                                                                      │
│  Services ── TrendingService (打标+分组)  IngestionService (抓取)    │
│                                                                      │
│  Agents ──── TaggingAgent (LLM智能打标)                              │
│              ArticleAnalysisAgent (深度分析)                         │
│              KBClusterAgent (知识库聚类)                              │
│                                                                      │
│  Collectors  LiveRSSCollector │ MinifluxCollector │ RSSCollector     │
│                                                                      │
│  Storage ─── SQLite (12 tables)                                      │
└─────────────────────────────────────────────────────────────────────┘
```

### 数据流

```
                    ┌─────────────┐
                    │  🚀 一键抓取 │
                    └──────┬──────┘
                           │
              ┌────────────▼────────────┐
              │    CollectionEngine      │
              │  RSS + Miniflux + Seed   │
              └────────────┬────────────┘
                           │
              ┌────────────▼────────────┐
              │   PreprocessPipeline     │
              │  Normalize → Extract →   │
              │  Clean → Enrich → Build  │
              └────────────┬────────────┘
                           │
              ┌────────────▼────────────┐
              │    TaggingAgent (LLM)    │
              │  读取用户已有标签偏好    │
              │  为每篇文章分配 1-4 标签 │
              └────────────┬────────────┘
                           │
              ┌────────────▼────────────┐
              │    TrendingService       │
              │  按 Tag 分组 + 排序     │
              │  → Trending Report      │
              └────────────┬────────────┘
                           │
              ┌────────────▼────────────┐
              │    用户浏览 + 收藏       │
              │  点击 [+] → 选择 KB     │
              │  → tag weight +1        │
              │  → 偏好反哺闭环         │
              └─────────────────────────┘
```

## 项目结构

```
sailor/
├── core/                           # 核心业务逻辑（不依赖 Web 框架）
│   ├── models.py                   # 领域模型
│   ├── collector/                  # 多源采集引擎
│   │   ├── base.py                 # Collector 抽象 + CollectionEngine
│   │   ├── live_rss_engine.py      # feedparser 实时 RSS 抓取
│   │   ├── miniflux_engine.py      # Miniflux API 采集
│   │   ├── rss_engine.py           # 本地 JSON seed 采集
│   │   └── opml_parser.py          # OPML 解析
│   ├── pipeline/                   # 预处理流水线
│   │   ├── base.py                 # Pipeline 基类
│   │   └── stages.py               # 5 个处理阶段
│   ├── agent/                      # LLM Agent
│   │   ├── base.py                 # LLMClient (urllib, 零依赖)
│   │   ├── tagging_agent.py        # 智能打标 Agent
│   │   ├── article_agent.py        # 文章深度分析 Agent
│   │   ├── kb_agent.py             # 知识库聚类 Agent
│   │   └── prompts.py              # Prompt 模板
│   ├── storage/                    # 数据持久化
│   │   ├── db.py                   # SQLite schema (12 tables)
│   │   ├── repositories.py         # Resource + KB 仓储
│   │   ├── tag_repository.py       # Tag + ResourceTag + UserAction
│   │   ├── feed_repository.py      # RSS Feed 仓储
│   │   ├── source_repository.py    # 统一源注册表 + 运行日志 + 回放索引
│   │   ├── analysis_repository.py  # 分析结果仓储
│   │   └── report_repository.py    # KB 报告仓储
│   └── services/
│       ├── ingestion.py            # 采集编排
│       └── trending.py             # Trending 报告生成
│
├── backend/                        # FastAPI Web 层
│   └── app/
│       ├── main.py                 # 入口 + 路由挂载
│       ├── container.py            # 依赖注入
│       ├── config.py               # 环境变量配置
│       ├── schemas.py              # Pydantic 模型
│       └── routers/                # 10 个路由模块
│           ├── trending.py         # Pipeline + Trending API
│           ├── tags.py             # 标签 CRUD
│           ├── knowledge_bases.py  # KB CRUD + 文章管理
│           ├── feeds.py            # RSS 源管理（兼容）
│           ├── sources.py          # 统一源管理（RSS + 非 RSS）
│           ├── resources.py        # 资源查询
│           ├── tasks.py            # 抓取 + 分析任务
│           ├── analyses.py         # 分析状态
│           ├── reports.py          # KB 报告
│           └── logs.py             # 历史日志 + SSE 实时流
│
└── frontend/                       # React 19 + TypeScript + Vite 7
    └── src/
        ├── App.tsx                 # NavBar + 页面路由
        ├── api.ts                  # API 调用封装
        ├── types.ts                # TypeScript 类型
        ├── styles.css              # 全局样式
        ├── components/
        │   └── NavBar.tsx          # 侧边导航栏
        └── pages/
            ├── TrendingPage.tsx    # 📊 Trending 报告
            ├── TagPage.tsx         # 🏷️ 标签管理
            ├── KBPage.tsx          # 📚 知识库管理
            └── FeedPage.tsx        # 📡 订阅源管理
```

## API 参考

### Pipeline & Trending

| Method | Endpoint | 说明 |
|--------|----------|------|
| `POST` | `/trending/pipeline` | 一键执行：抓取 → 打标 → Trending |
| `POST` | `/trending/generate` | 生成 Trending（触发 LLM 打标） |
| `GET` | `/trending` | 获取当前 Trending（不触发 LLM） |

### 标签

| Method | Endpoint | 说明 |
|--------|----------|------|
| `GET` | `/tags` | 所有标签（按权重排序） |
| `POST` | `/tags` | 创建标签 |
| `PUT` | `/tags/{tag_id}` | 更新标签 |
| `DELETE` | `/tags/{tag_id}` | 删除标签 |

### 知识库

| Method | Endpoint | 说明 |
|--------|----------|------|
| `GET` | `/knowledge-bases` | KB 列表 |
| `POST` | `/knowledge-bases` | 创建 KB |
| `DELETE` | `/knowledge-bases/{kb_id}` | 删除 KB |
| `GET` | `/knowledge-bases/{kb_id}/items` | KB 内文章 |
| `POST` | `/knowledge-bases/{kb_id}/items` | 收藏文章到 KB |
| `DELETE` | `/knowledge-bases/{kb_id}/items/{resource_id}` | 移除文章 |

### RSS 订阅源（兼容模式）

| Method | Endpoint | 说明 |
|--------|----------|------|
| `GET` | `/feeds` | Feed 列表 |
| `POST` | `/feeds` | 添加 RSS 源 |
| `DELETE` | `/feeds/{feed_id}` | 删除 Feed |
| `PATCH` | `/feeds/{feed_id}` | 启用/暂停 |
| `POST` | `/feeds/import-opml` | 导入 OPML |
| `GET` | `/feeds/source-status` | 源状态汇总 |

### 统一源管理（RSS + 非 RSS）

| Method | Endpoint | 说明 |
|--------|----------|------|
| `GET` | `/sources` | 统一源列表（支持按类型/启用状态筛选） |
| `POST` | `/sources` | 创建统一源 |
| `PATCH` | `/sources/{source_id}` | 更新统一源（启停/配置） |
| `DELETE` | `/sources/{source_id}` | 删除统一源 |
| `POST` | `/sources/import-local` | 从 `SailorRSSConfig.json` 导入/同步 |
| `POST` | `/sources/{source_id}/run` | 立即运行某个源 |
| `GET` | `/sources/{source_id}/resources` | 获取某个源抓取到的文章列表 |
| `GET` | `/sources/{source_id}/runs` | 获取某个源运行历史 |
| `GET` | `/sources/status` | 统一源状态汇总 |

### 资源 & 分析

| Method | Endpoint | 说明 |
|--------|----------|------|
| `GET` | `/resources` | 资源列表 |
| `POST` | `/tasks/run-ingestion` | 触发采集 |
| `POST` | `/tasks/run-analysis` | 触发 AI 分析 |
| `GET` | `/analyses/status` | 分析进度 |
| `POST` | `/knowledge-bases/{kb_id}/reports` | 生成 KB 报告 |

### 日志

| Method | Endpoint | 说明 |
|--------|----------|------|
| `GET` | `/logs` | 获取历史日志（支持 `limit`） |
| `GET` | `/logs/stream` | SSE 实时日志流 |


## 配置

所有配置通过环境变量注入，零配置即可启动（SQLite 自动创建）。

| 环境变量 | 默认值 | 说明 |
|----------|--------|------|
| `SAILOR_DB_PATH` | `data/sailor.db` | SQLite 数据库路径 |
| `SAILOR_SEED_FILE` | `data/seed_entries.json` | 本地种子文件路径 |
| `SAILOR_OPML_FILE` | `1.md` | OPML 导入文件路径 |
| `OPENAI_API_KEY` | — | OpenAI 兼容 API Key |
| `OPENAI_BASE_URL` | `https://api.openai.com/v1` | API 端点（支持 DeepSeek / Ollama / vLLM） |
| `OPENAI_MODEL` | `gpt-4o-mini` | 模型名称 |
| `MINIFLUX_BASE_URL` | — | Miniflux 实例地址 |
| `MINIFLUX_TOKEN` | — | Miniflux API Token |
| `CORS_ORIGINS` | `http://localhost:5173` | 允许的跨域来源（逗号分隔） |

> 不设置 `OPENAI_API_KEY` 时，智能打标和深度分析功能将跳过，其余功能正常使用。

## 数据库

SQLite，零运维，单文件部署。共 12 张表：

| 表名 | 用途 |
|------|------|
| `resources` | 采集到的文章/资源 |
| `knowledge_bases` | 用户创建的知识库 |
| `kb_items` | 知识库 ↔ 资源关联 |
| `rss_feeds` | RSS 订阅源 |
| `resource_analyses` | LLM 文章分析结果 |
| `kb_reports` | 知识库聚类报告 |
| `user_tags` | 用户标签（名称 + 颜色 + 权重） |
| `resource_tags` | 资源 ↔ 标签关联（auto / manual） |
| `user_actions` | 用户行为日志（收藏、打标等） |
| `source_registry` | 统一源注册表（RSS + 非 RSS） |
| `source_run_log` | 统一源运行日志 |
| `source_item_index` | 统一源抓取项索引（用于回放与按源查询） |

所有表在首次启动时自动创建，无需手动迁移。

## 技术栈

| 层 | 技术 |
|----|------|
| 前端 | React 19 · TypeScript · Vite 7 |
| 后端 | Python 3.11+ · FastAPI · Uvicorn |
| 数据库 | SQLite（零依赖） |
| LLM | OpenAI Chat Completions API（兼容协议） |
| RSS | feedparser · Miniflux API |
| HTTP | urllib（零第三方依赖的 LLM 客户端） |

## 设计决策

| 决策 | 理由 |
|------|------|
| SQLite 而非 PostgreSQL | 单用户场景，零运维，`cp` 即备份 |
| urllib 而非 httpx/requests | LLM 客户端零依赖，减少安装摩擦 |
| 标签权重而非协同过滤 | 单用户无需协同，权重简单有效 |
| 前端无路由库 | 4 个页面用 state 切换足够，避免引入 react-router |
| LLM 打标而非规则引擎 | 规则难以覆盖长尾，LLM 理解语义更灵活 |
| 偏好反哺闭环 | 收藏 → 权重提升 → 下次打标更准，无需显式配置 |

## Contributing

欢迎贡献！请遵循以下流程：

1. Fork 本仓库
2. 创建特性分支 (`git checkout -b feature/amazing-feature`)
3. 提交更改 (`git commit -m 'Add amazing feature'`)
4. 推送到分支 (`git push origin feature/amazing-feature`)
5. 创建 Pull Request

## License

[MIT](LICENSE)

---

<p align="center">
  Made with ⛵ by Sailor contributors
</p>
