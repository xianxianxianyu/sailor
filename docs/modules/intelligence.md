# Intelligence 模块

## 1. 作用

Intelligence 模块负责对资源做智能加工，当前包括：

- 自动打标
- 单篇文章分析
- 批量分析
- 组合式资源智能处理

核心代码位置：

- `core/agent/tagging_agent.py`
- `core/agent/article_agent.py`
- `core/engines/intelligence.py`
- `core/runner/tagging_handler.py`
- `core/runner/intelligence_handler.py`
- `core/runner/app_job_handlers.py`
- `backend/app/routers/analyses.py`
- `backend/app/routers/tags.py`

## 2. 子能力

### 2.1 Tagging

- 负责给资源生成 tag
- 依赖 `TaggingAgent`
- 输出写入 `tags` 与资源标签关系表

### 2.2 Article Analysis

- 负责单篇文章摘要、主题、评分、洞察
- 依赖 `ArticleAnalysisAgent`
- 输出写入 `resource_analysis`

### 2.3 Resource Intelligence

- 由 `ResourceIntelligenceEngine` 组合 tagging 和 analysis
- 适合做更完整的资源处理链路

## 3. 主要 job

- `batch_tag`
- `resource_analyze`
- `analysis_run`
- `resource_intelligence_run`

## 4. 对外接口

主要 API：

- `POST /resources/{resource_id}/analyze`
- `GET /resources/{resource_id}/analysis`
- `GET /analyses/status`
- `GET /tags`
- `POST /tags`
- `DELETE /tags/{tag_id}`

## 5. 运行链路

### 5.1 打标

资源进入系统后，可通过 `TaggingAgent` 自动生成标签，再写回 tag 表与资源关联表。

### 5.2 分析

单条分析和批量分析都通过 job 执行，前端按 job 状态读取结果。

### 5.3 智能处理

`ResourceIntelligenceEngine` 是 Intelligence 模块的组合入口，用于把多个智能动作串起来。

## 6. 与其他模块的关系

- Sources 与 Sniffer 为 Intelligence 提供资源输入
- KB 消费已分析资源
- KG 可消费分析结果做链接推断

## 7. 当前事实

- Tagging 是按资源逐条调用 LLM，长批次时成本明显
- 分析与打标都已经接入协作取消，不再适合在 Router 中直接同步执行
