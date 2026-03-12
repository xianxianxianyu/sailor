# Sources 模块

## 1. 作用

Sources 模块负责统一管理长期数据源，并把外部内容入库为 `resources`。

当前 UI 对应：

- `frontend/src/pages/FeedPage.tsx`

核心代码位置：

- `backend/app/routers/sources.py`
- `backend/app/routers/resources.py`
- `core/storage/source_repository.py`
- `core/storage/repositories.py`
- `core/runner/source_handler.py`
- `core/pipeline/*`

## 2. 核心职责

- 维护 `source_registry`
- 维护 `source_runs`
- 维护 `source_item_index`
- 执行 source run
- 通过 pipeline 把原始条目转成标准 `Resource`

## 3. 关键对象

### 3.1 `SourceRepository`

- source 的 CRUD
- run 记录
- source 与 resource 的索引映射

### 3.2 `ResourceRepository`

- 系统通用资源表
- Sources、Sniffer、Research 等模块都会向这里写入或读取

### 3.3 `SourceHandler`

执行 `source_run` job 的 handler，主流程：

1. 读取 source 配置
2. 调用 collector 抓取 entries
3. 通过 preprocess pipeline 规范化
4. upsert 到 `resources`
5. 写 `source_item_index` 和 run log

## 4. 对外接口

主要 API：

- `GET /sources`
- `POST /sources`
- `PATCH /sources/{source_id}`
- `DELETE /sources/{source_id}`
- `POST /sources/{source_id}/run`
- `POST /sources/run-by-type/{source_type}`
- `GET /sources/{source_id}/runs`
- `GET /sources/{source_id}/resources`
- `POST /sources/import-local`
- `POST /sources/import-opml`
- `GET /sources/status`
- `GET /resources`

## 5. 运行链路

### 5.1 管理 source

用户在 Feed 页面创建、编辑、启停 source，后端落到 `source_registry`。

### 5.2 运行 source

`POST /sources/{source_id}/run` 会创建 `source_run` job，worker 执行 `SourceHandler`。

### 5.3 入库资源

抓取出的原始条目经 pipeline 处理后写入 `resources`，并更新 source 到 resource 的索引。

## 6. 与其他模块的关系

- Sniffer 的 `rss` channel 会搜索本地 `resources`
- Intelligence 会对 `resources` 做 tagging / analysis
- KB 会把 `resources` 收藏为长期知识项

## 7. 当前事实

- UI 名叫 `FeedPage`，但实际管理的已经是统一 Sources
- 旧 `feeds` 语义已不再作为当前框架主路径
- Sources 是当前“长期供给”模块，区别于 Sniffer 的“一次性主动搜索”
