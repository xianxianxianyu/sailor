# Sailor 统一源管理改造报告（2026-02-25）

## 1. 修改原因

本次改造的核心目标是：在不推翻现有 RSS 逻辑的前提下，为 Sailor 增加“统一源管理”能力，使 RSS 与非 RSS 都能做到本地可管理、可追踪、可回放。

具体驱动点：

- 现状仅有 `rss_feeds` 一等公民模型，非 RSS 仅有 seed/miniflux 入口状态，缺少统一注册表与运行日志。
- 你已明确倾向以 JSON 配置作为订阅源清单（而非仅 OPML）。
- 需要兼容现有 `/feeds/*` 与 `1.md` 工作流，避免破坏已有使用方式。
- 需要补齐执行可观测性（每个源的运行记录、错误统计、最近运行时间）。

---

## 2. 本次 Plan Tasks（执行清单）

本次实现按以下任务推进：

1. 新增统一源管理数据模型与 SQLite 表结构。
2. 实现 `SourceRepository` 与后端 `/sources` 接口（含本地 JSON 导入与单源运行）。
3. 接入容器与主路由，保持 `/feeds` 兼容。
4. 更新前端 `types/api/FeedPage`，支持统一源管理能力。
5. 运行后端语法检查、前端构建与接口冒烟验证。

---

## 3. 实际改造结果

### 3.1 数据层

- 新增表：
  - `source_registry`
  - `source_run_log`
  - `source_item_index`
- 保留 `rss_feeds` 不动。
- 新增索引以支持类型/状态查询、运行日志排序、canonical URL 查询。

### 3.2 后端 API

新增统一源接口（保留原 `/feeds/*`）：

- `GET /sources`
- `POST /sources`
- `PATCH /sources/{source_id}`
- `DELETE /sources/{source_id}`
- `GET /sources/status`
- `GET /sources/{source_id}/runs`
- `POST /sources/import-local`
- `POST /sources/{source_id}/run`

其中：

- `/sources/import-local` 默认读取 `SailorRSSConfig.json`，导入 `source_registry`，并把 RSS 同步回 `rss_feeds`。
- `/sources/{id}/run` 复用现有 pipeline 入库链路（RawEntry -> Pipeline -> Resource upsert）。

### 3.3 采集与 provenance

- 已支持最小三类 source 执行：`rss`、`web_page`、`manual_file`。
- `BuildResourceStage` 的 provenance 由 miniflux 偏置改为通用字段：
  - `source_type`
  - `source_id`
  - `entry_native_id`
  - `adapter_version`
  - `captured_at`

### 3.4 前端

- Feed 管理页升级为“RSS + 统一源”共存模式：
  - 保留 RSS 原有管理能力。
  - 新增统一源创建/启停/删除/立即运行。
  - 新增“同步 SailorRSSConfig.json”入口。

---

## 4. 修改文件清单

### 4.1 新增文件

- `backend/app/routers/sources.py`
- `core/storage/source_repository.py`
- `SailorRSSConfig.json`
- `docs/unified-source-change-report-2026-02-25.md`（本报告）

### 4.2 修改文件

- `backend/app/container.py`
- `backend/app/main.py`
- `backend/app/schemas.py`
- `core/models.py`
- `core/pipeline/stages.py`
- `core/storage/__init__.py`
- `core/storage/db.py`
- `frontend/src/api.ts`
- `frontend/src/pages/FeedPage.tsx`
- `frontend/src/types.ts`
- `frontend/tsconfig.app.tsbuildinfo`（构建产物更新）

---

## 5. 验证结果

已执行并通过：

- Python 语法编译：`python -m compileall backend core`
- 前端构建：`npm --prefix frontend run build`
- 接口冒烟：
  - `/sources/import-local` 返回 200，导入与 RSS 同步计数正常。
  - `manual_file` 源可创建、运行、删除。
  - 旧接口 `/feeds/source-status`、`/feeds` 返回 200（兼容性保留）。

---

## 6. 本次修复中遇到并已解决的问题

在实现过程中修复了两个接口 bug：

1. `/sources/import-local` 内对 `import_feeds` 返回值误用 `len()`，导致 500。
2. RSS 同步参数类型与 `feed_repository` 预期不一致导致异常。

现均已修复并完成回归验证。
