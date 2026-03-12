# Sniffer 模块

## 1. 作用

Sniffer 是主动搜索模块，面向“用户带着问题去找信息”。

当前 UI 对应：

- `frontend/src/pages/DiscoverPage.tsx`
- `frontend/src/pages/SnifferPage.tsx`

核心代码位置：

- `backend/app/routers/sniffer.py`
- `core/runner/sniffer_handler.py`
- `core/sniffer/tool_module.py`
- `core/sniffer/summary_engine.py`
- `core/sniffer/adapters/*`
- `core/storage/sniffer_repository.py`

## 2. 核心对象

### 2.1 `SnifferHandler`

执行 `sniffer_search` job：

1. 读取查询参数
2. 并发调用各 channel adapter
3. 去重并保存结果
4. 生成 summary
5. 返回 `result_ids + summary`

### 2.2 `SnifferToolModule`

- 做多 channel fan-out / fan-in
- 控制并发与 budget
- 记录成功/失败 channel

### 2.3 Adapters

当前内置 channel：

- `github`
- `hackernews`
- `rss`

其中 `rss` 不是去互联网搜索 RSS，而是对本地 `resources` 做检索。

### 2.4 `PackManager`

- 管理 Sniffer Pack
- 本质上是保存好的查询模板

## 3. 对外接口

主要 API：

- `POST /sniffer/search`
- `GET /sniffer/jobs/{job_id}`
- `GET /sniffer/channels`
- `GET /sniffer/runs`
- `GET /sniffer/runs/{run_id}`
- `GET /sniffer/packs`
- `POST /sniffer/packs`
- `POST /sniffer/packs/{pack_id}/run`
- `POST /sniffer/results/{result_id}/deep-analyze`
- `POST /sniffer/compare`
- `POST /sniffer/results/{result_id}/save-to-kb`
- `POST /sniffer/results/{result_id}/convert-source`

## 4. 运行链路

### 4.1 一次搜索

1. 前端发 `POST /sniffer/search`
2. 后端创建 `sniffer_search` job
3. worker 执行 `SnifferHandler`
4. 完成后通过 `/sniffer/jobs/{job_id}` 读取最终 `SearchResponse`

### 4.2 搜索包

Sniffer Pack 是查询模板的持久化形式，用于重复运行和定时运行。

### 4.3 搜索结果后续动作

每条结果可继续：

- 深度分析
- 多结果对比
- 收藏到 KB
- 转为长期 source

这些动作大多也走 job 模式。

## 5. 与其他模块的关系

- 可把结果转为 Sources，进入长期采集
- 可把结果保存到 KB
- 可调用 Intelligence 做深度分析

## 6. 当前事实

- Sniffer 是当前 Discover 页的核心模块
- Sniffer 更像“即时研究入口”，而不是长期订阅系统
- 如果以后做“研究报告”，更合理的落点仍然是以 Sniffer 搜索结果为输入继续生成，而不是再造一个独立页面
