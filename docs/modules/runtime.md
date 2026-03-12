# Runtime 模块

## 1. 作用

Runtime 模块负责整个系统的统一执行语义：

- job 创建、执行、重试、取消
- worker 消费队列
- scheduler 定时创建 job
- policy / confirm gate
- events / tool calls / raw captures / artifacts 的追踪

核心代码位置：

- `core/runner/job_runner.py`
- `core/runner/handlers.py`
- `core/runner/scheduler.py`
- `backend/worker.py`
- `backend/app/routers/jobs.py`
- `backend/app/routers/confirms.py`
- `core/artifact/repository.py`

## 2. 核心对象

### 2.1 `JobRunner`

- 统一调度各类 handler
- 管理 `queued -> running -> terminal` 生命周期
- 负责 transient retry、失败落库、取消落库

### 2.2 `RunContext`

- 统一写入 `provenance_events`
- 统一记录 `tool_calls`
- 提供 `raise_if_cancel_requested()` 做协作取消
- 提供 `save_raw_capture()` 做原始抓取物落盘

### 2.3 Worker

- 独立进程，轮询 `queued` job
- 当前模型是单 consumer 循环
- 收到 `SIGINT/SIGTERM` 时会停止拉新任务，并对当前运行任务发起 `cancel_requested`

### 2.4 `UnifiedScheduler`

- 负责把 schedule 变成 job
- 自己不做重任务执行
- 当前整合了 sniffer pack、sources、follow 等定时入口

### 2.5 `PolicyGate`

- 对 side-effect 工具调用给出 `allow / deny / require_confirm`
- `require_confirm` 时会创建待确认记录，由 confirms API 继续处理

## 3. 统一 job 契约

### 3.1 当前注册的主要 job 类型

- `source_run`
- `paper_source_run`
- `sniffer_search`
- `batch_tag`
- `resource_intelligence_run`
- `resource_analyze`
- `analysis_run`
- `kb_reports_generate`
- `sniffer_deep_analyze`
- `sniffer_compare`
- `sniffer_save_to_kb`
- `sniffer_convert_source`
- `board_snapshot`
- `board_run`
- `research_snapshot`
- `research_run`
- `issue_compose`
- `follow_run`
- `kg_add_node`
- `kg_relink_node`

实际注册关系以 `backend/app/container.py` 为准。

### 3.2 读状态接口

- `GET /jobs/{job_id}`
- `GET /jobs/{job_id}/events`
- `POST /jobs/{job_id}/cancel`

## 4. 可追踪数据

Runtime 统一沉淀以下数据：

- `jobs`：状态与输入输出
- `provenance_events`：阶段事件
- `tool_calls`：工具级调用
- `raw_captures`：外部抓取原文或原始响应
- `artifacts`：可复用产物，如 `board_bundle`、`research_bundle`、`issue_snapshot`

## 5. 取消与确认

### 5.1 取消

- `queued` job：直接转 `cancelled`
- `running` job：先写 `cancel_requested=true`
- handler 在检查点读取该标志后，以 `JobCancelled` 协作退出

### 5.2 确认

- 某些工具调用可被标记为 `require_confirm`
- Runtime 会创建待确认记录而不是直接执行
- 确认系统属于 runtime 的一部分，不属于某个业务模块

## 6. 当前约束

- 当前 worker 仍是单进程、单循环；长任务会阻塞后续任务
- 模块是否“job 化”要看具体 router 和 handler，仍在持续向统一契约收敛
- Runtime 是全系统底座，业务文档不再重复描述 job 细节时，以本文件为准
