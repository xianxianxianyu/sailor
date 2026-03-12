# Sailor 前端功能 Pipeline 优先级审查

> 按「前端功能能否跑通」的关键路径排序。
> P0 = 不通则全站瘫痪，P1 = 核心价值循环，P2 = 追踪监控，P3 = 增强功能。

---

## 关键数据流（决定优先级的依据）

```
LLM 配置 (P0-前置)
    ↓ 所有分析/图谱/深度功能依赖此

Source 创建/导入 (P0)
    ↓ POST /sources, /sources/import-local, /sources/import-opml
Source 运行 (P0)
    ↓ POST /sources/{id}/run → 产出 Resource
Tag 定义 (P0)
    ↓ POST /tags → 趋势分组依赖 tag
Pipeline / 趋势生成 (P0)
    ↓ POST /trending/pipeline → 抓取+打标+生成报告
趋势展示 (P0)
    ↓ GET /trending → TrendingReport

搜索发现 (P1)
    ↓ POST /sniffer/search → 搜索结果
    ├→ 保存到 KB (P1)
    └→ 转为源 (P1) → 回到 Source 循环

KB 管理 (P1)
    ↓ CRUD + items
KG 图谱 (P1, 依赖 LLM)
    ↓ 自动建边

Board 看板 (P2)
    ↓ 快照抓取外部平台
Research Program (P2)
    ↓ 研究方向管理
Follow 追踪 (P2, 依赖 Board + Research)
    ↓ 对比生成 Issue

Sniffer Packs / 深度分析 / 对比 (P3)
KB 报告 (P3)
日志 (P3)
```

---

## P0 — 基础管线（断则全站不可用）

### P0.1 LLM 配置

前端所有涉及 LLM 的功能（深度分析、对比、KG 建边、KB 报告、Pipeline 中的打标）都依赖此配置正确。

| 功能 | API | 方法 | 后端逻辑 |
|---|---|---|---|
| 获取设置 | `/settings/llm` | GET | 读取 LLM 配置 |
| 更新设置 | `/settings/llm` | PUT | 写入 provider/api_key/base_url/model/temperature/max_tokens |
| 测试连接 | `/settings/llm/test` | POST | 实际调用 LLM API 验证连通性 |

风险：如果 LLM 不可用，Pipeline 的「打标」步骤会失败，趋势报告为空。

### P0.2 订阅源 CRUD + 导入

Source 是整个系统的数据入口。没有 Source → 没有 Resource → 趋势为空 → 前端空白。

| 功能 | API | 方法 | 后端逻辑 |
|---|---|---|---|
| 获取源列表 | `/sources` | GET | 查询 source 表，支持 source_type/enabled_only 过滤 |
| 获取源状态 | `/sources/status` | GET | 聚合统计 total/enabled/errored |
| 创建源 | `/sources` | POST | 验证参数 → 插入 source 表 |
| 更新源 | `/sources/{source_id}` | PATCH | 更新 name/endpoint/config/enabled/schedule |
| 删除源 | `/sources/{source_id}` | DELETE | 删除 source 记录（Resource 保留）|
| 导入本地配置 | `/sources/import-local` | POST | 解析 SailorRSSConfig.json → 批量创建 |
| 导入 OPML | `/sources/import-opml` | POST | 解析 OPML XML → 批量创建 RSS/Atom 源 |

支持类型：rss, atom, json_feed, academic_api, rest_api, web_scraping, opml, jsonl, local_file

### P0.3 源执行（产出 Resource）

| 功能 | API | 方法 | 后端逻辑 |
|---|---|---|---|
| 运行单个源 | `/sources/{source_id}/run` | POST | 创建 source_run job → adapter 抓取 → 解析 → 创建 Resource |
| 运行历史 | `/sources/{source_id}/runs` | GET | 查询 run 历史 |
| 源产出资源 | `/sources/{source_id}/resources` | GET | 按 source 过滤 resource 表 |

副作用：网络请求 + Resource 创建。这是数据进入系统的唯一正式通道。

<!-- PLACEHOLDER_P0_REST -->

### P0.4 标签定义

Tag 是趋势分组的依据。没有 Tag → Pipeline 打标无目标 → 趋势报告 groups 为空。

| 功能 | API | 方法 | 后端逻辑 |
|---|---|---|---|
| 获取标签列表 | `/tags` | GET | 查询 tags 表 |
| 创建标签 | `/tags` | POST | 插入 tags 表，body: { name, color } |
| 删除标签 | `/tags/{tag_id}` | DELETE | 删除 tag（已打标 Resource 的 topics 不自动清理）|

注意：Tag 的 weight 字段影响趋势排序权重，但当前前端创建时不设置 weight。

### P0.5 Pipeline + 趋势

这是前端核心价值的终点：用户看到按标签分组的趋势内容。

| 功能 | API | 方法 | 后端逻辑 |
|---|---|---|---|
| 执行完整 Pipeline | `/trending/pipeline` | POST | 串行：抓取所有 enabled 源 → 处理 → 按 tag 打标 → 生成报告 |
| 单独生成趋势 | `/trending/generate` | POST | 扫描 inbox Resource → 按 Tag 匹配分组 → 覆盖旧报告 |
| 获取趋势报告 | `/trending` | GET | 返回最近一次 TrendingReport |
| 收藏到 KB | `/knowledge-bases/{kb_id}/items` | POST | Resource 加入 KB → 触发 kg_add_node job |

Pipeline 内部执行链：
1. 遍历所有 enabled Source → 调用各 adapter 抓取 → 产出 Resource
2. 对新 Resource 做 LLM 分析（摘要、topics、scores）— **依赖 LLM**
3. 按 UserTag 匹配 Resource 的 topics → 打标分组
4. 生成 TrendingReport 持久化

风险点：
- Pipeline 是同步阻塞操作，无进度反馈，前端只能等
- 如果 Source 数量多或网络慢，可能超时
- LLM 不可用时打标步骤失败

---

## P1 — 核心价值循环（搜索发现 + 知识沉淀）

### P1.1 搜索（Sniffer 核心）

用户主动发现内容的入口，独立于 Pipeline 的被动抓取。

| 功能 | API | 方法 | 后端逻辑 |
|---|---|---|---|
| 获取频道列表 | `/sniffer/channels` | GET | 返回注册的 channel 配置 |
| 执行搜索 | `/sniffer/search` | POST | 并发调用 channel adapter → 聚合 → 生成 summary |
| 频道健康 | `/sniffer/channels/health` | GET | 检查各 adapter 可用性 |

请求体：`{ keyword, channels[], time_range, sort_by, max_results_per_channel }`
返回：`SearchResponse` = results[] + summary（关键词聚类、时间分布、engagement 排名）

后端关键：搜索结果临时存储在内存/缓存中，后续的深度分析/保存/转源都依赖 result_id 能找到这条结果。

### P1.2 搜索结果操作

| 功能 | API | 方法 | 后端逻辑 |
|---|---|---|---|
| 保存到 KB | `/sniffer/results/{result_id}/save-to-kb` | POST | SniffResult → Resource → 加入 KB → 触发 kg_add_node |
| 转为订阅源 | `/sniffer/results/{result_id}/convert-source` | POST | 从 URL 推断 source_type → 创建 SourceRecord |

风险：result_id 是临时的，如果后端重启或缓存过期，这两个操作会 404。

### P1.3 知识库 CRUD

KB 是用户沉淀内容的核心容器。

| 功能 | API | 方法 | 后端逻辑 |
|---|---|---|---|
| 获取 KB 列表 | `/knowledge-bases` | GET | 查询 kb 表 |
| 创建 KB | `/knowledge-bases` | POST | 插入 kb 表 |
| 删除 KB | `/knowledge-bases/{kb_id}` | DELETE | 删除 kb + kb_items + KG 图谱数据 |
| 获取 KB 文章 | `/knowledge-bases/{kb_id}/items` | GET | JOIN kb_items + resources |
| 移除文章 | `/knowledge-bases/{kb_id}/items/{resource_id}` | DELETE | 删除关联（Resource 保留）|
| 添加文章 | `/knowledge-bases/{kb_id}/items` | POST | 关联 + 触发 kg_add_node job |

### P1.4 知识图谱

依赖 LLM 自动分析文章间关联，是 KB 的高级功能。

| 功能 | API | 方法 | 后端逻辑 |
|---|---|---|---|
| 获取图谱 | `/knowledge-bases/{kb_id}/graph` | GET | 查询 kg_nodes + kg_edges，支持 full/local 模式 |
| 节点详情 | `/knowledge-bases/{kb_id}/graph/nodes/{node_id}` | GET | 节点 + 邻居列表，分页 |
| 创建边 | `/knowledge-bases/{kb_id}/graph/edges` | POST | 手动连接两节点 |
| 删除边 | `/knowledge-bases/{kb_id}/graph/edges/{a}/{b}` | DELETE | 标记 edge status=deleted |
| 冻结边 | `/knowledge-bases/{kb_id}/graph/edges/{a}/{b}/freeze` | POST | frozen=1，不被 relink 覆盖 |
| 解冻边 | `/knowledge-bases/{kb_id}/graph/edges/{a}/{b}/unfreeze` | POST | frozen=0 |
| 重链接节点 | `/knowledge-bases/{kb_id}/graph/nodes/{node_id}/relink` | POST | kg_relink_node job → LLM 重算关联 → 更新边 |
| 操作历史 | `/knowledge-bases/{kb_id}/graph/history` | GET | KG job 执行记录 |

依赖链：KB 至少 2 个 items + LLM 可用 → 才有图谱数据。

<!-- PLACEHOLDER_P2 -->

---

## P2 — 追踪监控（Board + Research + Follow）

这三个功能形成一条链：Board/Research 是数据源，Follow 是聚合对比器。

### P2.1 看板 (Board)

监控外部平台趋势（GitHub Trending、HuggingFace Trending），为 Follow 提供对比数据。

| 功能 | API | 方法 | 后端逻辑 |
|---|---|---|---|
| 获取 Board 列表 | `/boards` | GET | 查询 boards 表 |
| 创建 Board | `/boards` | POST | 插入 boards 表，body: { provider, kind, name, enabled } |
| 更新 Board | `/boards/{board_id}` | PATCH | 更新 enabled 等字段 |
| 删除 Board | `/boards/{board_id}` | DELETE | 删除 board + 关联 snapshots |
| 触发快照 | `/boards/{board_id}/snapshot` | POST | board_snapshot job → 爬取外部平台 → 存储 snapshot + items |
| 最新快照 | `/boards/{board_id}/snapshots/latest` | GET | 查询最新 snapshot |
| 快照内容 | `/boards/snapshots/{snapshot_id}/items` | GET | 查询 snapshot_items |

provider 类型：github, huggingface
副作用：网络爬取外部平台，依赖目标站点可达。

### P2.2 研究方向 (Research Program)

定义研究方向，关联 source_ids，为 Follow 提供另一维度的数据源。

| 功能 | API | 方法 | 后端逻辑 |
|---|---|---|---|
| 获取列表 | `/research-programs` | GET | 查询 research_programs 表 |
| 创建 | `/research-programs` | POST | 插入，body: { name, description?, enabled } |
| 更新 | `/research-programs/{program_id}` | PATCH | 更新 enabled/description 等 |
| 删除 | `/research-programs/{program_id}` | DELETE | 删除 program 记录 |

注意：当前前端创建 Research Program 时只有 name/description/enabled，没有 source_ids 选择 UI。这意味着创建出来的 program 没有关联数据源，Follow 运行时该 program 不会产出内容。

### P2.3 Follow 追踪

聚合 Board + Research Program 的数据，按时间窗口对比变化，生成 Issue。

| 功能 | API | 方法 | 后端逻辑 |
|---|---|---|---|
| 获取 Follow 列表 | `/follows` | GET | 查询 follows 表 |
| 创建 Follow | `/follows` | POST | 关联 board_ids + program_ids + window_policy |
| 更新 Follow | `/follows/{follow_id}` | PATCH | 更新 enabled 等 |
| 删除 Follow | `/follows/{follow_id}` | DELETE | 删除 follow + 关联 issues |
| 触发运行 | `/follows/{follow_id}/run` | POST | follow_run job → 按 window_policy 定时间窗 → 遍历 boards/programs → 对比快照 → 生成 IssueSnapshot |
| Issue 历史 | `/follows/{follow_id}/issues` | GET | 查询 issue snapshots |

Follow 运行的内部逻辑：
1. 根据 window_policy (daily/weekly/monthly) 确定 since/until 时间窗
2. 对每个关联的 Board：获取当前快照 vs 上次快照 → diff 出 new_items / removed_items
3. 对每个关联的 Research Program：获取时间窗内的新数据
4. 汇总为 IssueSnapshot，每个数据源一个 section

依赖链：
- 必须先有 Board（且至少做过一次 snapshot）或 Research Program
- Follow 运行可能触发 Board 重新抓取快照

---

## P3 — 增强功能

### P3.1 深度分析 + 对比（Sniffer 增强）

| 功能 | API | 方法 | 后端逻辑 |
|---|---|---|---|
| 深度分析 | `/sniffer/results/{result_id}/deep-analyze` | POST | LLM 分析单条结果 → ResourceAnalysis |
| 对比分析 | `/sniffer/compare` | POST | LLM 对比多条结果 → CompareSummary |

依赖 LLM 可用 + result_id 未过期。

### P3.2 搜索包 (Sniffer Packs)

| 功能 | API | 方法 | 后端逻辑 |
|---|---|---|---|
| 列表 | `/sniffer/packs` | GET | 查询 packs 表 |
| 创建 | `/sniffer/packs` | POST | 保存搜索参数 |
| 删除 | `/sniffer/packs/{pack_id}` | DELETE | 删除 pack |
| 执行 | `/sniffer/packs/{pack_id}/run` | POST | 用 pack 参数重新搜索 |
| 导入 | `/sniffer/packs/import` | POST | 导入 pack 配置 |
| 导出 | `/sniffer/packs/{pack_id}/export` | GET | 导出 pack 配置 |
| 定时 | `/sniffer/packs/{pack_id}/schedule` | PATCH | 设置 cron 定时 |

### P3.3 KB 报告

| 功能 | API | 方法 | 后端逻辑 |
|---|---|---|---|
| 生成报告 | `/knowledge-bases/{kb_id}/reports` | POST | LLM 汇总 KB 内文章 → 结构化报告 |
| 获取报告 | `/knowledge-bases/{kb_id}/reports` | GET | 查询报告列表 |
| 最新报告 | `/knowledge-bases/{kb_id}/reports/latest` | GET | 查询最新报告 |

当前状态：api.ts 有定义，但前端页面未调用。

### P3.4 日志

| 功能 | API | 方法 | 后端逻辑 |
|---|---|---|---|
| 历史日志 | `/logs` | GET | 内存 deque 读取 |
| 实时流 | `/logs/stream` | GET (SSE) | EventSource 推送 |

### P3.5 资源直接操作（被多页面间接使用）

| 功能 | API | 方法 | 后端逻辑 |
|---|---|---|---|
| 资源列表 | `/resources` | GET | 按 status/topic 过滤 |
| 资源详情 | `/resources/{resource_id}` | GET | 单条查询 |
| 资源所属 KB | `/resources/{resource_id}/knowledge-bases` | GET | 查询关联 |
| 单条 LLM 分析 | `/resources/{resource_id}/analyze` | POST | LLM 分析 → ResourceAnalysis |

---

## 总结：后端验证检查清单

按优先级排列，逐项验证后端是否能正确响应：

```
P0 验证（必须全部通过才能使用）:
  □ GET  /settings/llm              → 返回 LLMSettings
  □ PUT  /settings/llm              → 更新成功
  □ POST /settings/llm/test         → { success: true }
  □ POST /sources                   → 创建 Source 成功
  □ GET  /sources                   → 返回 SourceRecord[]
  □ POST /sources/{id}/run          → 运行成功，产出 Resource
  □ POST /tags                      → 创建 Tag 成功
  □ GET  /tags                      → 返回 UserTag[]
  □ POST /trending/pipeline         → 返回 PipelineResult（collected>0, tagged>0）
  □ GET  /trending                  → 返回非空 TrendingReport

P1 验证（核心功能）:
  □ GET  /sniffer/channels          → 返回 ChannelInfo[]（至少1个）
  □ POST /sniffer/search            → 返回 SearchResponse
  □ POST /sniffer/results/{id}/save-to-kb → 保存成功
  □ POST /knowledge-bases           → 创建 KB 成功
  □ GET  /knowledge-bases/{id}/items → 返回 KBItemResource[]
  □ GET  /knowledge-bases/{id}/graph → 返回 KGGraph

P2 验证（追踪功能）:
  □ POST /boards                    → 创建 Board 成功
  □ POST /boards/{id}/snapshot      → 快照抓取成功
  □ GET  /boards/{id}/snapshots/latest → 返回 BoardSnapshot
  □ POST /research-programs         → 创建成功
  □ POST /follows                   → 创建 Follow 成功
  □ POST /follows/{id}/run          → 运行成功
  □ GET  /follows/{id}/issues       → 返回 IssueSnapshot[]

P3 验证（增强功能）:
  □ POST /sniffer/results/{id}/deep-analyze → 返回 ResourceAnalysis
  □ POST /sniffer/compare           → 返回 CompareSummary
  □ GET  /sniffer/packs             → 返回 SnifferPack[]
  □ GET  /logs                      → 返回 LogEntry[]
```

