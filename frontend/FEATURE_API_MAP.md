# Sailor 前端功能 → 后端接口 → 业务逻辑 全景图

> 本文档逐页、逐功能梳理前端每个操作对应的后端 API、业务层处理逻辑和数据流向。
> 目的：确认前后端是否对齐，发现断裂点。

---

## 1. 发现页 (Discover) — Sniffer + Trending

### 1.1 搜索 Tab (SnifferPage)

#### 1.1.1 获取可用搜索频道
- **前端动作**: 页面加载时拉取频道列表，用于搜索表单的 checkbox
- **API**: `GET /sniffer/channels`
- **返回**: `ChannelInfo[]` — channel_id, name, description, media_types
- **后端逻辑**: 读取 sniffer 注册的 channel 配置，纯读取无副作用

#### 1.1.2 执行搜索
- **前端动作**: 用户输入关键词、选择频道、时间范围、排序方式，点击搜索
- **API**: `POST /sniffer/search`
- **请求体**: `{ keyword, channels[], time_range, sort_by, max_results_per_channel }`
- **返回**: `SearchResponse` — results: SniffResult[], summary: SearchSummary
- **后端逻辑**: 创建 `sniffer_search` job → 并发调用各 channel adapter 抓取 → 聚合结果 → 生成 summary（关键词聚类、时间分布、engagement 排名）
- **副作用**: 搜索结果临时存储（用于后续深度分析/对比/保存）

#### 1.1.3 深度分析单条结果
- **前端动作**: 点击结果卡片的「深度分析」按钮
- **API**: `POST /sniffer/results/{result_id}/deep-analyze`
- **返回**: `ResourceAnalysis` — summary, topics, scores, insights
- **后端逻辑**: 调用 LLM 对单条 SniffResult 做深度分析 → 返回结构化分析结果
- **副作用**: 消耗 LLM token

#### 1.1.4 对比多条结果
- **前端动作**: 勾选多条结果，点击「对比」
- **API**: `POST /sniffer/compare`
- **请求体**: `{ result_ids: string[] }`
- **返回**: `CompareSummary`
- **后端逻辑**: 调用 LLM 对选中结果做对比分析
- **副作用**: 消耗 LLM token

#### 1.1.5 保存结果到知识库
- **前端动作**: 点击结果的「保存到 KB」，选择目标知识库
- **API**: `POST /sniffer/results/{result_id}/save-to-kb`
- **请求体**: `{ kb_id }`
- **返回**: `{ saved: boolean, resource_id }`
- **后端逻辑**: SniffResult → 转为 Resource 持久化 → 加入 KB → 触发 `kg_add_node` job（知识图谱节点创建）
- **副作用**: 创建 Resource 记录、KB 关联、KG 节点

#### 1.1.6 转换为订阅源
- **前端动作**: 点击结果的「转为源」
- **API**: `POST /sniffer/results/{result_id}/convert-source`
- **请求体**: `{ name? }`
- **返回**: `{ converted: boolean, source_id }`
- **后端逻辑**: 从 SniffResult 的 URL 推断 source_type → 创建 SourceRecord
- **副作用**: 创建新的 Source 记录

#### 1.1.7 搜索包管理 (Sniffer Packs)
- **列表**: `GET /sniffer/packs` → `SnifferPack[]`
- **创建**: `POST /sniffer/packs` → 保存搜索参数为可复用 pack
- **删除**: `DELETE /sniffer/packs/{pack_id}`
- **执行**: `POST /sniffer/packs/{pack_id}/run` → 用 pack 的参数重新搜索
- **导入**: `POST /sniffer/packs/import`
- **导出**: `GET /sniffer/packs/{pack_id}/export`
- **定时**: `PATCH /sniffer/packs/{pack_id}/schedule` → 设置 cron 定时执行
- **后端逻辑**: Pack 是搜索参数的持久化快照，run 时等同于 1.1.2 的搜索流程

#### 1.1.8 频道健康检查
- **API**: `GET /sniffer/channels/health`
- **返回**: `ChannelHealth[]`
- **后端逻辑**: 检查各 channel adapter 的可用性

<!-- PLACEHOLDER_SECTION_2 -->

### 1.2 趋势 Tab (TrendingPage)

#### 1.2.1 获取趋势报告
- **前端动作**: Tab 切换到趋势时，展示 App 层传入的 `report` prop
- **API**: `GET /trending`
- **返回**: `TrendingReport` — groups: TrendingGroup[], total_resources, total_tags
- **后端逻辑**: 读取最近一次生成的趋势报告，按 tag 分组返回资源列表
- **调用时机**: App.tsx 的 `handleRefresh()` 或 pipeline 完成后自动拉取

#### 1.2.2 生成趋势报告
- **前端动作**: （当前由 pipeline 触发，非直接 UI 按钮）
- **API**: `POST /trending/generate`
- **返回**: `TrendingReport`
- **后端逻辑**: 扫描所有 inbox 状态的 Resource → 按 UserTag 匹配分组 → 生成报告
- **副作用**: 覆盖旧报告

#### 1.2.3 执行完整 Pipeline
- **前端动作**: App 层的 `handlePipeline()`（hero 区域按钮，当前未在 UI 显示但代码存在）
- **API**: `POST /trending/pipeline`
- **返回**: `PipelineResult` — { collected, processed, tagged }
- **后端逻辑**: 串行执行：抓取所有 enabled 源 → 处理资源 → 按 tag 打标 → 生成趋势报告
- **副作用**: 大量 I/O，可能耗时较长

#### 1.2.4 添加趋势项到知识库
- **前端动作**: 点击趋势项的「收藏」按钮，弹出 KB 选择器
- **API**: `POST /knowledge-bases/{kb_id}/items`
- **请求体**: `{ resource_id }`
- **返回**: void
- **后端逻辑**: 将 Resource 加入 KB → 触发 `kg_add_node` job
- **副作用**: KB 关联、KG 节点创建

---

## 2. 订阅源页 (Feeds) — FeedPage

### 2.1 源列表与状态

#### 2.1.1 获取源列表
- **前端动作**: 页面加载
- **API**: `GET /sources?source_type=&enabled_only=`
- **返回**: `SourceRecord[]`
- **后端逻辑**: 查询 source 表，支持按类型和启用状态过滤

#### 2.1.2 获取源状态汇总
- **前端动作**: 页面加载，显示状态栏（总数/启用/错误）
- **API**: `GET /sources/status`
- **返回**: `SourceStatus` — { total, enabled, errored, last_run_at }
- **后端逻辑**: 聚合查询 source 表统计

### 2.2 源 CRUD

#### 2.2.1 创建源
- **前端动作**: 填写表单（名称、类型、endpoint、配置项），点击创建
- **API**: `POST /sources`
- **请求体**: `{ source_id?, source_type, name, endpoint?, config?, enabled?, schedule_minutes? }`
- **返回**: `SourceRecord`
- **后端逻辑**: 验证参数 → 插入 source 表
- **支持类型**: rss, atom, json_feed, academic_api, rest_api, web_scraping, opml, jsonl, local_file
- **config 字段**: 根据 source_type 不同，包含 api_headers, jsonpath, xml_path, css_selector 等

#### 2.2.2 更新源（启用/禁用）
- **前端动作**: 点击启用/禁用开关
- **API**: `PATCH /sources/{source_id}`
- **请求体**: `{ enabled: boolean }`
- **返回**: `SourceRecord`
- **后端逻辑**: 更新 source 表 enabled 字段

#### 2.2.3 删除源
- **前端动作**: 点击删除按钮
- **API**: `DELETE /sources/{source_id}`
- **后端逻辑**: 删除 source 记录（关联的 resource 不删除）

### 2.3 源执行

#### 2.3.1 手动执行单个源
- **前端动作**: 点击「运行」按钮
- **API**: `POST /sources/{source_id}/run`
- **返回**: `{ run_id, source_id, status, fetched_count, processed_count }`
- **后端逻辑**: 创建 `source_run` job → 调用对应 adapter 抓取 → 解析内容 → 创建/更新 Resource 记录
- **副作用**: 网络请求、Resource 创建

#### 2.3.2 查看运行历史
- **前端动作**: 选中源后查看详情
- **API**: `GET /sources/{source_id}/runs?limit=20`
- **返回**: `SourceRun[]`
- **后端逻辑**: 查询 run 历史表

#### 2.3.3 查看源产出的资源
- **前端动作**: 选中源后查看资源列表
- **API**: `GET /sources/{source_id}/resources?limit=50&offset=0`
- **返回**: `SourceResource[]`
- **后端逻辑**: 查询 resource 表按 source 过滤

### 2.4 批量导入

#### 2.4.1 导入本地配置
- **前端动作**: 点击「同步本地配置」
- **API**: `POST /sources/import-local`
- **请求体**: `{ config_file? }` — 默认读取 SailorRSSConfig.json
- **返回**: `{ imported, total_parsed }`
- **后端逻辑**: 解析本地 JSON 配置文件 → 批量创建 Source 记录

#### 2.4.2 导入 OPML
- **前端动作**: 点击「导入 OPML」
- **API**: `POST /sources/import-opml`
- **请求体**: `{ opml_file? }`
- **返回**: `{ imported, total_parsed }`
- **后端逻辑**: 解析 OPML XML → 提取 RSS/Atom URL → 批量创建 Source 记录

<!-- PLACEHOLDER_SECTION_3 -->

---

## 3. 知识库页 (KB) — KBPage + TagPage

### 3.1 文章 Tab (KBPage 原有)

#### 3.1.1 获取知识库列表
- **前端动作**: 页面加载
- **API**: `GET /knowledge-bases`
- **返回**: `KnowledgeBase[]` — { kb_id, name, description }
- **后端逻辑**: 查询 kb 表

#### 3.1.2 创建知识库
- **前端动作**: 点击「+ 创建知识库」，填写名称和描述
- **API**: `POST /knowledge-bases`
- **请求体**: `{ name, description? }`
- **返回**: `KnowledgeBase`
- **后端逻辑**: 插入 kb 表

#### 3.1.3 删除知识库
- **前端动作**: 点击知识库卡片上的 × 按钮
- **API**: `DELETE /knowledge-bases/{kb_id}`
- **后端逻辑**: 删除 kb 记录及关联的 kb_items、KG 图谱数据

#### 3.1.4 获取 KB 内文章列表
- **前端动作**: 选中某个 KB 后加载
- **API**: `GET /knowledge-bases/{kb_id}/items`
- **返回**: `KBItemResource[]` — { resource_id, title, original_url, summary, topics, added_at }
- **后端逻辑**: JOIN 查询 kb_items + resources 表

#### 3.1.5 移除 KB 内文章
- **前端动作**: 点击文章卡片的「移除」按钮
- **API**: `DELETE /knowledge-bases/{kb_id}/items/{resource_id}`
- **后端逻辑**: 删除 kb_items 关联记录（Resource 本身不删除）

### 3.2 图谱 Tab (KBGraphView)

#### 3.2.1 获取知识图谱
- **前端动作**: 切换到 Graph tab
- **API**: `GET /knowledge-bases/{kb_id}/graph?mode=full|local&start_node_id=&depth=&limit=`
- **返回**: `KGGraph` — { nodes: KGNode[], edges: KGEdge[] }
- **后端逻辑**: 查询 kg_nodes + kg_edges 表，支持全图和局部模式

#### 3.2.2 获取节点详情
- **前端动作**: 点击图谱中的节点
- **API**: `GET /knowledge-bases/{kb_id}/graph/nodes/{node_id}?page=&page_size=`
- **返回**: `KGNodeDetail` — { node, neighbors[], total_neighbors, page, page_size }
- **后端逻辑**: 查询节点及其邻居关系

#### 3.2.3 创建边
- **前端动作**: 手动连接两个节点
- **API**: `POST /knowledge-bases/{kb_id}/graph/edges`
- **请求体**: `{ node_a_id, node_b_id, reason, reason_type? }`
- **返回**: `KGEdge`
- **后端逻辑**: 插入 kg_edges 表

#### 3.2.4 删除边
- **API**: `DELETE /knowledge-bases/{kb_id}/graph/edges/{node_a_id}/{node_b_id}`
- **后端逻辑**: 标记 edge status 为 deleted

#### 3.2.5 冻结/解冻边
- **冻结**: `POST /knowledge-bases/{kb_id}/graph/edges/{node_a_id}/{node_b_id}/freeze`
- **解冻**: `POST /knowledge-bases/{kb_id}/graph/edges/{node_a_id}/{node_b_id}/unfreeze`
- **后端逻辑**: 设置 edge 的 frozen 标志，冻结的边不会被自动重链接覆盖

#### 3.2.6 重链接节点
- **前端动作**: 对某节点触发重新计算关联
- **API**: `POST /knowledge-bases/{kb_id}/graph/nodes/{node_id}/relink`
- **返回**: `{ job_id, status }`
- **后端逻辑**: 创建 `kg_relink_node` job → LLM 重新分析节点与其他节点的关系 → 更新边
- **副作用**: 消耗 LLM token，可能增删边

#### 3.2.7 图谱操作历史
- **API**: `GET /knowledge-bases/{kb_id}/graph/history?limit=50`
- **返回**: job 历史列表
- **后端逻辑**: 查询 kg 相关 job 的执行记录

### 3.3 标签 Tab (TagPage — 新增到 KB 页)

#### 3.3.1 获取标签列表
- **前端动作**: Tab 切换到标签时加载
- **API**: `GET /tags`
- **返回**: `UserTag[]` — { tag_id, name, color, weight, created_at }
- **后端逻辑**: 查询 tags 表

#### 3.3.2 创建标签
- **前端动作**: 输入标签名和颜色，点击添加
- **API**: `POST /tags`
- **请求体**: `{ name, color }`
- **返回**: `UserTag`
- **后端逻辑**: 插入 tags 表，默认 weight=0

#### 3.3.3 删除标签
- **前端动作**: 点击标签的删除按钮
- **API**: `DELETE /tags/{tag_id}`
- **后端逻辑**: 删除 tag 记录。注意：已打标的 Resource 的 topics 字段不会自动清理

<!-- PLACEHOLDER_SECTION_4 -->

---

## 4. 追踪页 (Follow) — FollowTab + BoardPage + ResearchPage

### 4.1 关注 Tab (FollowTab)

#### 4.1.1 获取 Follow 列表
- **前端动作**: 页面加载
- **API**: `GET /follows`
- **返回**: `Follow[]` — { follow_id, name, description, board_ids, research_program_ids, window_policy, enabled, last_run_at, error_count, last_error }
- **后端逻辑**: 查询 follows 表

#### 4.1.2 获取 Board 和 Research Program 选项（用于创建表单）
- **前端动作**: 页面加载时并行拉取
- **API**: `GET /boards` + `GET /research-programs`
- **返回**: `Board[]` + `ResearchProgram[]`
- **后端逻辑**: 分别查询 boards 和 research_programs 表，提供选项列表

#### 4.1.3 创建 Follow
- **前端动作**: 填写名称、描述、选择 boards/programs、窗口策略、启用状态
- **API**: `POST /follows`
- **请求体**: `{ name, description?, board_ids[], research_program_ids[], window_policy, enabled }`
- **返回**: `Follow`
- **后端逻辑**: 插入 follows 表，关联 board_ids 和 program_ids
- **window_policy**: daily / weekly / monthly — 决定每次运行时的时间窗口

#### 4.1.4 启用/禁用 Follow
- **前端动作**: 点击「启用」/「禁用」按钮
- **API**: `PATCH /follows/{follow_id}`
- **请求体**: `{ enabled: boolean }`
- **返回**: `Follow`
- **后端逻辑**: 更新 follows 表 enabled 字段

#### 4.1.5 删除 Follow
- **前端动作**: 点击「删除」按钮
- **API**: `DELETE /follows/{follow_id}`
- **后端逻辑**: 删除 follow 记录及关联的 issues

#### 4.1.6 手动触发 Follow 运行
- **前端动作**: 点击「立即运行」
- **API**: `POST /follows/{follow_id}/run`
- **返回**: `{ job_id, follow_id, status, error_message? }`
- **后端逻辑**: 创建 `follow_run` job → 按 window_policy 确定时间窗口 → 遍历关联的 boards 和 research_programs → 对比上次快照与当前数据 → 生成 IssueSnapshot（包含 new_items 和 removed_items）
- **副作用**: 可能触发 board snapshot 抓取、research program 执行；生成 issue artifact

#### 4.1.7 查看 Issue 历史
- **前端动作**: 选中 Follow 后自动加载
- **API**: `GET /follows/{follow_id}/issues?limit=5`
- **返回**: `IssueSnapshot[]` — { issue_id, follow_id, created_at, window: { since, until }, sections[] }
- **后端逻辑**: 查询 artifacts 表中 follow 关联的 issue snapshots
- **sections 结构**: 每个 section 对应一个数据源（board 或 research program），包含 source_id, source_name, section_type, new_items[], removed_items[]

### 4.2 看板 Tab (BoardPage)

#### 4.2.1 获取 Board 列表
- **前端动作**: Tab 切换到看板时加载
- **API**: `GET /boards`
- **返回**: `Board[]` — { board_id, provider, kind, name, config, enabled, last_run_at }
- **后端逻辑**: 查询 boards 表

#### 4.2.2 创建 Board
- **前端动作**: 选择 provider（github/huggingface）和 kind（trending），输入名称
- **API**: `POST /boards`
- **请求体**: `{ provider, kind, name, enabled }`
- **返回**: `Board`
- **后端逻辑**: 插入 boards 表
- **provider 类型**: github（GitHub Trending）、huggingface（HuggingFace Trending）

#### 4.2.3 启用/禁用 Board
- **API**: `PATCH /boards/{board_id}`
- **请求体**: `{ enabled: boolean }`
- **后端逻辑**: 更新 boards 表

#### 4.2.4 删除 Board
- **API**: `DELETE /boards/{board_id}`
- **后端逻辑**: 删除 board 及关联 snapshots

#### 4.2.5 触发快照抓取
- **前端动作**: 点击「抓取快照」
- **API**: `POST /boards/{board_id}/snapshot`
- **返回**: `{ job_id, snapshot_id, status, error_message? }`
- **后端逻辑**: 创建 `board_snapshot` job → 调用对应 provider adapter（如 GitHub Trending scraper）→ 抓取当前排行榜 → 存储为 BoardSnapshot + BoardSnapshotItems
- **副作用**: 网络请求（爬取外部平台）

#### 4.2.6 获取最新快照
- **前端动作**: 选中 Board 后自动加载
- **API**: `GET /boards/{board_id}/snapshots/latest`
- **返回**: `BoardSnapshot | null` — { snapshot_id, board_id, captured_at, item_count }
- **后端逻辑**: 查询最新一条 snapshot

#### 4.2.7 获取快照内容
- **前端动作**: 展示快照详情
- **API**: `GET /boards/snapshots/{snapshot_id}/items?limit=50`
- **返回**: `BoardSnapshotItem[]` — { snapshot_id, item_key, source_order, title?, url?, meta? }
- **后端逻辑**: 查询 snapshot_items 表

### 4.3 研究 Tab (ResearchPage)

#### 4.3.1 获取 Research Program 列表
- **前端动作**: Tab 切换到研究时加载
- **API**: `GET /research-programs`
- **返回**: `ResearchProgram[]` — { program_id, name, description, source_ids[], enabled, last_run_at }
- **后端逻辑**: 查询 research_programs 表

#### 4.3.2 创建 Research Program
- **前端动作**: 输入名称和描述
- **API**: `POST /research-programs`
- **请求体**: `{ name, description?, enabled }`
- **返回**: `ResearchProgram`
- **后端逻辑**: 插入 research_programs 表

#### 4.3.3 启用/禁用 Research Program
- **API**: `PATCH /research-programs/{program_id}`
- **请求体**: `{ enabled: boolean }`
- **后端逻辑**: 更新 research_programs 表

#### 4.3.4 删除 Research Program
- **API**: `DELETE /research-programs/{program_id}`
- **后端逻辑**: 删除 program 记录

---

## 5. 全局功能（非页面绑定）

### 5.1 LLM 配置 (LLMSettingsModal)
- **获取设置**: `GET /settings/llm` → `LLMSettings`
- **更新设置**: `PUT /settings/llm` → `{ provider, api_key?, base_url, model, temperature, max_tokens }`
- **测试连接**: `POST /settings/llm/test` → `{ success, message }`
- **后端逻辑**: 读写 LLM 配置，test 时实际调用 LLM API 验证连通性

### 5.2 日志 (LogPanel)
- **获取历史日志**: `GET /logs?limit=50` → `LogEntry[]`
- **实时日志流**: `GET /logs/stream` → SSE EventSource
- **后端逻辑**: 内存 deque 存储日志，SSE 推送新日志

### 5.3 资源相关（被多个页面间接使用）
- **资源列表**: `GET /resources?status=inbox&topic=` → `Resource[]`
- **资源详情**: `GET /resources/{resource_id}`
- **资源所属 KB**: `GET /resources/{resource_id}/knowledge-bases` → `KnowledgeBase[]`
- **单条分析**: `POST /resources/{resource_id}/analyze` → `ResourceAnalysis`
- **批量分析**: `POST /tasks/run-analysis` → `{ analyzed_count, failed_count }`
- **分析状态**: `GET /analyses/status` → `AnalysisStatus`

### 5.4 KB 报告（前端 api.ts 有定义但当前页面未直接使用）
- **生成报告**: `POST /knowledge-bases/{kb_id}/reports` → `KBReport[]`
- **获取报告**: `GET /knowledge-bases/{kb_id}/reports` → `KBReport[]`
- **最新报告**: `GET /knowledge-bases/{kb_id}/reports/latest` → `KBReport[]`
- **后端逻辑**: LLM 分析 KB 内所有文章 → 生成结构化报告

### 5.5 确认流程（前端未使用但后端存在）
- **列表**: `GET /confirms?status=&limit=`
- **详情**: `GET /confirms/{confirm_id}`
- **审批**: `POST /confirms/{confirm_id}/resolve`
- **后端逻辑**: 某些 job 执行前需要人工确认，当前前端未接入此流程

### 5.6 论文源（后端存在但前端未接入）
- **CRUD**: `/paper-sources` 系列接口
- **执行**: `POST /paper-sources/{source_id}/run`
- **论文详情**: `GET /papers/{paper_id}`
- **后端逻辑**: 学术论文抓取和管理，当前前端无对应 UI

---

## 6. 数据流向总结

```
用户搜索 (Sniffer)
    ↓ POST /sniffer/search
    ↓ 搜索结果 (临时)
    ├→ 深度分析 → LLM
    ├→ 保存到 KB → Resource + KG Node
    └→ 转为源 → Source Record
                    ↓ POST /sources/{id}/run
                    ↓ 抓取内容 → Resource
                                    ↓
用户标签 (Tags) ←──── 趋势生成 (Trending) ←── Resource 池
    ↓                       ↓
    └── 匹配分组 ──→ TrendingReport

KB 收藏
    ↓ POST /kb/{id}/items
    ├→ KG 节点创建 (kg_add_node job)
    ├→ KG 边自动生成 (LLM 分析关联)
    └→ KB 报告生成 (LLM 汇总)

Board 看板
    ↓ POST /boards/{id}/snapshot
    ↓ 爬取外部平台 → BoardSnapshot
    └→ Follow 对比 → IssueSnapshot (new/removed items)

Research Program
    ↓ 关联 source_ids
    └→ Follow 对比 → IssueSnapshot
```

---

## 7. 前后端断裂点分析

### 7.1 前端调用了但后端可能缺失的
| 前端 API 调用 | 风险点 |
|---|---|
| `POST /trending/pipeline` | 重量级操作，串行执行所有源抓取+分析+打标，无进度反馈 |
| `POST /sniffer/results/{id}/save-to-kb` | 依赖临时 result 存储，如果 result 过期会 404 |
| `POST /sniffer/results/{id}/convert-source` | 需要 URL 到 source_type 的推断逻辑 |

### 7.2 后端存在但前端未接入的
| 后端接口 | 说明 |
|---|---|
| `/confirms/*` | 确认审批流程，前端无 UI |
| `/paper-sources/*`, `/papers/*` | 学术论文管理，前端无页面 |
| `/settings/embedding` | 嵌入模型配置，前端只有 LLM 配置 |
| `/settings/llm/status` | LLM 状态统计，前端未展示 |
| `POST /boards/{id}/run` | Board 运行（区别于 snapshot），前端只用了 snapshot |
| `GET /follows/{id}/runs` | Follow 运行历史，前端只展示 issues |
| `GET /follows/{id}/issue` (单数) | 获取最新单条 issue，前端用的是 issues 列表 |
| `POST /tasks/run-ingestion` | 独立的抓取任务，前端用 pipeline 代替 |
| `GET /tasks/main-flow` | 主流程任务列表，前端未使用 |
| `GET /tasks/ingestion-status` | 抓取状态，前端未展示 |
| `POST /tasks/run-analysis` | 批量分析，前端未直接触发 |
| `GET /analyses/status` | 分析统计，前端未展示 |
| `POST /knowledge-bases/{kb_id}/reports` | KB 报告生成，前端 api.ts 有但页面未调用 |

### 7.3 业务逻辑依赖链
| 操作 | 依赖 |
|---|---|
| 趋势生成 | 需要先有 Resource（来自 Source 抓取）+ 有 Tag 定义 |
| Follow 运行 | 需要先有 Board（且有 snapshot）或 Research Program |
| KG 图谱 | 需要先有 KB + 至少 2 个 items + LLM 可用 |
| 深度分析/对比 | 需要 LLM 配置正确且可用 |
| Board 快照 | 需要网络可达外部平台（GitHub/HuggingFace）|



