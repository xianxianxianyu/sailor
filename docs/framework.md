# Sailor 框架总览

## 1. 定位

Sailor 当前是一个“本地优先的信息采集与研究工作台”：

- 数据存储以 `SQLite` 为中心；
- Web API 由 `FastAPI` 提供；
- 前端 UI 由 `React + Vite` 提供；
- 所有重操作统一交给独立 `Worker` 消费；
- LLM 能力通过统一配置引擎注入到各个 Agent / Engine。

当前真实装配入口：

- 后端入口：`backend/app/main.py`
- 依赖装配：`backend/app/container.py`
- Worker 入口：`backend/worker.py`

## 2. 系统分层

### 2.1 UI 层

- 代码位置：`frontend/src`
- 当前主要页面：`DiscoverPage`、`FeedPage`、`KBPage`、`FollowPage`
- 主要职责：发起 API 调用、轮询 job、展示运行结果，不直接做重计算

### 2.2 API 层

- 代码位置：`backend/app/routers`
- 主要职责：参数校验、轻量编排、创建 job、读取结果
- 约束：Router 不直接执行长耗时逻辑，重操作尽量统一下沉到 JobRunner

### 2.3 Runtime 层

- 代码位置：`core/runner`、`backend/worker.py`
- 主要职责：job 生命周期、调度、取消、确认门禁、事件与工具调用追踪
- 核心对象：`JobRunner`、`RunContext`、`UnifiedScheduler`、`PolicyGate`

### 2.4 Domain 层

当前主模块：

- Sources
- Sniffer
- Intelligence
- Knowledge Base
- KG
- Board
- Research
- Follow
- LLM Config

这些模块中的重操作通过 job handler、engine、agent 执行。

### 2.5 Storage 层

- 代码位置：`core/storage`、`core/artifact`
- 主要职责：SQLite 表读写、artifact 持久化、运行日志与追踪数据保存

## 3. 统一执行契约

### 3.1 读写分离

- 读操作通常同步返回，例如列表、详情、状态查询
- 重操作通常返回 `job_id`，由 worker 异步执行

### 3.2 Job 生命周期

标准状态：

- `queued`
- `running`
- `succeeded`
- `failed`
- `cancelled`

前后端通过 `/jobs/{job_id}` 读取状态，通过 `/jobs/{job_id}/events` 读取执行事件。

### 3.3 可追踪性

Runtime 会统一记录：

- `jobs`
- `provenance_events`
- `tool_calls`
- `raw_captures`
- `artifacts`

这套数据是系统排障、回放、审计的基础。

### 3.4 协作取消与确认门禁

- 运行中 job 可通过 `/jobs/{job_id}/cancel` 发起取消请求
- handler 通过 `RunContext.raise_if_cancel_requested()` 协作退出
- 对需要人工确认的动作，`PolicyGate` 会落 `pending_confirm`，再由确认接口继续

## 4. 当前模块地图

- Runtime：`docs/modules/runtime.md`
- Sources：`docs/modules/sources.md`
- Sniffer：`docs/modules/sniffer.md`
- Intelligence：`docs/modules/intelligence.md`
- Knowledge Base：`docs/modules/knowledge-base.md`
- KG：`docs/modules/kg.md`
- Board：`docs/modules/board.md`
- Research：`docs/modules/research.md`
- Follow：`docs/modules/follow.md`
- LLM Config：`docs/modules/llm-config.md`

## 5. 当前系统事实

- `Discover` 页面当前就是 `Sniffer` 工作台，不再包含独立 `Trending` 页面
- `FeedPage` 这个名字是历史沿用，实际管理的是统一 `Sources`
- `Follow` 是当前最高层业务模块，依赖 `Board`、`Research`、`Artifact` 与 Runtime
- `Trending` 相关旧设计文档很多，但当前代码主干已经不再把它作为独立系统入口

## 6. 开发入口

推荐开发命令：

```bash
npm run dev
```

这个命令会同时启动：

- `uvicorn backend.app.main:app`
- `frontend` dev server
- `python -m backend.worker`

没有 worker 时，所有异步 job 都会一直停在 `queued`。
