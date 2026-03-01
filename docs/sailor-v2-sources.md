# Sailor V2 Sources

本文用于两件事：

1. **第 1 章**：把“技术趋势/项目趋势/AI 论文趋势”站点按数据接入方式聚类（RSS/结构化读取/官方 API/第三方），并结合 Sailor 现有实现给出**接入可行性与推荐路径**，便于后续用 multi-agent + tools func call 去落地。
2. **第 2 章**：设计一个把“旧世界（legacy path）RSS feeds”系统化的方案，要求：
   - 有接口供 agent 调用 tools func（可审计、可控）
   - 有接口供前后端渲染（列表/详情/状态/资源列表）
   - 支持 CRUD
   - 对齐 `D:\code\sailor\docs\sailor-v2.md` 的 **3.9.1 V2 runner** 与“旧世界”的现状

> 备注：本文是设计与评估文档，不直接修改代码。

---

## 第 1 章：趋势站点接入调研 + 可行性评估（聚类）

### 1.1 目标与输出

你收集的候选站点覆盖三类需求：

- **开发者新闻与讨论**：类似 Hacker News（HN）的“链接聚合 + 讨论热度”。
- **开源/工具趋势**：类似 GitHub Trending 的“项目发现/热度榜”。
- **AI/ML 论文与项目趋势**：类似 Hugging Face Papers / Daily Papers 的“论文热度 + 代码实现 + 模型/space 推荐”。

本章输出：

- 按接入方式聚类：哪些能用 RSS/Atom/JSONFeed；哪些能结构化读取；哪些必须官方 API；哪些适合走第三方。
- 对每一类给出 Sailor 推荐接入路径（尽量复用现有模块）。
- 给出优先级建议（先做什么，为什么）。

### 1.2 Sailor 现有实现（决定“怎么接”的关键约束）

这里不是重新讲架构，只列“会直接影响接入策略”的事实：

- Sailor 已有 **RSS/Atom 抓取与入库能力**（feedparser + pipeline），并支持 OPML 导入。
- Sailor 的 Sniffer 里 `rss` 渠道并不是“去外网搜 RSS”，而是**对本地 `resources` 表做关键词检索**（因此：想用 RSS 扩站点，核心是“先入库 resources”）。
- Sailor 已有 **Miniflux 拉取**能力（可作为第三方 RSS 生成/聚合的入口，例如 RSSHub -> Miniflux -> Sailor）。
- Sailor 已内建 **arXiv 结构化采集**（学术 API 侧），也能直接用 arXiv 的 RSS/Atom。

### 1.3 聚类标准（四类 + 一个最后手段）

为了后续 agent 能自动决策接入策略，建议把站点归到以下类别：

1. **RSS/Atom/JSONFeed（原生）**：稳定、成本最低，适合作为“趋势语料库”的底座。
2. **结构化读取（公共/弱鉴权）**：有公开 API/Atom Query/稳定 JSON，不需要密钥或仅需极少配置。
3. **官方 API（需要 key/OAuth）**：结构化强，但要做密钥管理、速率限制、合规。
4. **第三方方法**：RSSHub、Miniflux、Apify 等，把“无 RSS/无 API 的站点”转成可消费的 feed/JSON。
5. **HTML 抓取（最后手段）**：脆弱、维护成本高、易触发反爬/合规问题。

同时还要区分两种产品形态：

- **Search 型**（用户输入关键词实时搜）：更适合做 Sniffer channel（按 query 拉取）。
- **Digest 型**（每天/每小时榜单）：更适合做 Source 定时入库，然后在本地做搜索/聚类/摘要。

### 1.4 A 类：原生 RSS/Atom（优先级最高）

这类站点适合最先接入：实现简单、稳定，且 Sailor 已经有完整 RSS 采集链路。

已确认可用的 feed（本轮调研中实际抓取验证过）：

| 站点 | 类型 | Feed URL | 适合用途 | 推荐接入 |
|---|---|---|---|---|
| Lobsters | RSS 2.0 | https://lobste.rs/rss | 高质量工程讨论（HN-like） | 作为 RSS feed 入库 -> 本地检索 |
| Slashdot | RSS 1.0/RDF | https://rss.slashdot.org/Slashdot/slashdotMain | 老牌科技新闻/评论热度 | RSS 入库（注意 description 清洗） |
| Reddit r/programming | Atom | https://www.reddit.com/r/programming/.rss | 热点链接/讨论（噪声相对高） | Atom 入库（外链需从 HTML 抽取可选） |
| DEV.to | RSS 2.0 | https://dev.to/feed | Web/前端内容丰富 | RSS 入库（建议后续按 tag feed 降噪） |
| HackerNoon | RSS 2.0 | https://hackernoon.com/feed | 创业/区块链偏多 | RSS 入库（content:encoded 很长） |
| InfoQ | RSS 2.0 | https://www.infoq.com/rss/ | 架构/工程实践资讯 | RSS 入库 |
| Techmeme | RSS 2.0 | https://www.techmeme.com/feed.xml | 科技头条聚合 | RSS 入库 |
| LWN.net | RSS 2.0 | https://lwn.net/headlines/rss | Linux/OSS 深度资讯 | RSS 入库（标注付费内容） |
| Ars Technica | RSS 2.0 | https://feeds.arstechnica.com/arstechnica/index | 科技媒体资讯 | RSS 入库（可能含全文 HTML） |
| Habr | RSS 2.0 | https://habr.com/en/rss/all/all/ | 大型工程社区 | RSS 入库（建议选分类/话题 feed） |
| JavaScript Weekly | RSS 2.0 | https://javascriptweekly.com/rss | 高信噪比周刊 | RSS 入库（每期一条 or 拆链接二选一） |
| arXiv 分类流 | RSS 2.0 | https://arxiv.org/rss/cs.LG | 论文最新流（非关键词） | RSS 入库 |

推荐路径（Sailor 侧）：

- **最佳实践**：把 feed 作为“Source（订阅源）”定时跑，入 `resources`，再由 Sniffer 的本地检索能力完成“关键词发现”。
- 若你需要“实时按关键词跨站搜”，RSS 本身不支持 query，这类站点不适合作为 Sniffer channel（除非你做本地语料库策略）。

### 1.5 B 类：结构化读取（公共/弱鉴权）

这类站点通常提供结构化接口（Atom Query / REST），适合做 Search 型与 Digest 型两种形态。

| 站点 | 结构化接口 | 适合用途 | 推荐接入 |
|---|---|---|---|
| arXiv Query | Atom API（公开） | 关键词论文检索（Search 型） | 做 Sniffer channel 或做 Source 定时 query 入库 |
| OpenReview | 官方 API v2（公开读取为主） | 会议投稿/评审/最新论文 | 更适合 Digest（按 venue/时间窗定时入库） |

备注：这类接口的优势是字段完整（作者、时间、类别、链接等），非常适合 Sailor 作为“长期语料库 + 结构化索引”。

### 1.6 C 类：官方 API（需要 key/OAuth）

这类接入通常“结构化强 + 合规要求高 + 需要密钥”。建议先用 Digest 型（定时跑）降低频率与失败面。

| 站点 | 官方接口 | 适合用途 | 推荐接入 |
|---|---|---|---|
| Product Hunt | GraphQL v2（OAuth/token） https://api.producthunt.com/v2/docs | 产品/工具趋势榜 | 优先做 Digest（每天一次）入库；再做更细粒度搜索 |
| GitHub（非 Trending） | 官方 REST/GraphQL | repo 搜索、topic、近期高 star | 用 API 做“近似 Trending”的可配置策略 |

备注：

- GitHub Trending 本身没有官方 API，想要“同款榜单”要么 HTML 抓取，要么用 API 做近似指标（例如：最近 N 天创建/活跃、star 增量等）。

### 1.7 D 类：第三方方法（推荐的“降本扩展”策略）

典型场景：站点无 RSS、无公开 API、页面强 JS 或反爬，自己写爬虫成本高。

推荐组合：

- **RSSHub/其他 feed 生成** -> **Miniflux** -> **Sailor MinifluxCollector**

在 Sailor 中，这条路的价值是：

- 不需要为每个站点写专用 adapter/collector。
- 接入点统一（Miniflux API），错误、重试、队列都在同一层。

适合走第三方的候选（需要进一步确认具体路由/可用性）：

- Indie Hackers（本轮测试 `https://www.indiehackers.com/feed.xml` 不是 RSS）
- daily.dev（偏个性化）
- Designer News
- 以及很多“榜单类页面”（没有稳定 API 的情况下）

### 1.8 E 类：HTML 抓取（最后手段）

只有当以下条件都满足时才建议：

- 该站点对产品价值极高
- 无 RSS/无 API/第三方方案不可用
- 能接受长期维护（DOM 改动、反爬、合规风险）

典型：GitHub Trending HTML 抓取。

### 1.9 站点矩阵（把你给的清单落到聚类与推荐路径）

说明：下表以“推荐路径”为主；未在本轮验证的项标注为“待验证”。

| 站点 | 聚类 | 推荐路径（Sailor） | 备注 |
|---|---|---|---|
| Hacker News | 结构化/站内接口 | 已有 Sniffer channel（hackernews） | 现有实现即可 |
| GitHub Trending | HTML 抓取（最后手段） | 优先用 GitHub API 做近似趋势；或第三方 | Trending 无官方 API |
| Lobsters | RSS | RSS 入库 -> 本地检索 | 已验证 feed |
| Slashdot | RSS | RSS 入库 -> 本地检索 | 已验证 feed |
| Reddit r/programming | Atom | Atom 入库 -> 本地检索 | 已验证 feed |
| DEV.to | RSS | RSS 入库 -> 本地检索 | 已验证 feed |
| HackerNoon | RSS | RSS 入库 -> 本地检索 | 已验证 feed |
| InfoQ | RSS | RSS 入库 -> 本地检索 | 已验证 feed |
| Techmeme | RSS | RSS 入库 -> 本地检索 | 已验证 feed |
| LWN.net | RSS | RSS 入库 -> 本地检索 | 已验证 feed（含付费标记） |
| Ars Technica | RSS | RSS 入库 -> 本地检索 | 已验证 feed |
| Habr | RSS | RSS 入库 -> 本地检索 | 已验证 feed |
| JavaScript Weekly | RSS | RSS 入库（issue 级） | 已验证 feed |
| Papers with Code | 官方/半官方 API（待确认） | 优先 API；否则第三方/抓取 | 存在官方 client，但接口需确认 |
| Hugging Face Papers | 半结构化（页面/内部 API 待发现） | 优先第三方或 scrape（谨慎） | 本轮测试 `/api/papers/trending` 404 |
| arXiv | RSS + Atom API | RSS 入库（类别流）+ Atom API（关键词） | Atom Query 已验证可用 |
| OpenReview | 官方 API | Digest/按 venue 定时入库 | API v2 文档已确认 |
| Product Hunt | 官方 API（GraphQL） | Digest（每日）入库 | 需要 token |
| Indie Hackers | 第三方/抓取 | RSSHub->Miniflux->入库（优先） | feed 未确认 |
| daily.dev | 第三方/账号/抓取 | 第三方优先 | 个性化强 |
| AlternativeTo | 结构化不明确 | 第三方/抓取（谨慎） | 待验证 |
| BetaList/OpenHunts | 结构化不明确 | 第三方/抓取（谨慎） | 待验证 |
| OpenRead/SciSpace | 官方接口不明确 | 先别接；或第三方 | 待验证 |
| Replicate/Kaggle | 官方 API | 若要接，走官方 API（token） | 更偏能力平台，不一定是“趋势源” |

### 1.10 建议优先级（面向落地）

按“投入/回报/稳定性”排序：

1. **先接 RSS/Atom**：快速扩充语料库（低成本、高稳定）。
2. **再接 arXiv（Atom Query）与 OpenReview（API）**：AI 论文趋势的主干最先跑通。
3. **再接 Product Hunt（GraphQL）**：做“每日趋势 digest”最稳。
4. **缺口用第三方补齐（RSSHub->Miniflux）**：避免写大量站点爬虫。
5. **最后才考虑 HTML 抓取（GitHub Trending 等）**：维护成本最高。

---

## 第 2 章：RSS 系统方案（把 feed-family 收敛到 Sources + JobRunner）

> 本章的目标：用 V2 的三层与平台抽象（Tool Functions / Engines / Orchestrators / JobRunner）来重建 RSS 的“系统语义”，并让 legacy `/feeds` 退化为兼容视图（shim），从结构上消灭双轨制。

### 2.1 背景：为什么 RSS 必须收敛（对齐 3.9 的显式分层）

在 Sailor V2 的框架里：
- RSS/Atom/JSONFeed 属于数据层（Sources 的 feed-family），负责 acquisition + canonicalization + 幂等入库。
- Trending/KB/QA 属于业务层/逻辑层，不应该在按钮里直接“跑 RSS”。

现实约束：前端已有 Feed 管理页并依赖 `/feeds`，所以迁移必须做到：
- 外部接口（UI）尽量不变；
- 真实执行路径（run）必须统一进入 JobRunner（可追溯/可调度/可回放）。

### 2.2 RSS 系统目标（拆成可验收项）

RSS 系统需要满足：
- **目录能力（Catalog）**：CRUD、OPML 导入、状态字段可渲染。
- **执行能力（Execution）**：run 单/批、可查询运行历史、失败语义清晰（transient/permanent/partial）。
- **可追溯（Traceability）**：jobs + events + tool_calls +（可选）raw_captures。
- **可调度（Scheduling）**：与 UnifiedScheduler 同语义（interval/cron/锁）。
- **可工具化（Tools）**：对 agent 暴露稳定的 Tool Functions（默认 `sources.*`，RSS 只是 source_type 的子集）。

### 2.3 现有资产（你已经有的东西）

1) Sources 系统（新世界）
- API：`/sources` 已能 CRUD/run，且 run 走 JobRunner（`job_type=source_run`）。
- 存储：`source_registry/source_run_log/source_item_index`。
- 采集：`core/sources/collectors.py` 已支持 `rss/atom/jsonfeed`。

2) legacy feeds（旧世界）
- API：`/feeds`（FeedRepository + 直连 feedparser）。
- 存储：`rss_feeds`。

3) 平台层
- JobRunner/RunContext/tool_calls/provenance_events。
- UnifiedScheduler 已能调度 sources。

### 2.4 方案总览（唯一真相 + 兼容视图）

结论（推荐的唯一方案）：

1) 单一真相：feed-family 的唯一真相是 `SourceRecord`
- RSS/Atom/JSONFeed 都表示为 `SourceRecord(source_type in {rss,atom,jsonfeed})`。
- `rss_feeds` 仅作为兼容视图/迁移对象，不再承载“run 语义”。

2) 兼容层：保留 `/feeds`，但把它变成 Sources 的“RSS 子集视图（shim）”
- `/feeds` 的 CRUD 实际读写 `source_registry`（对外保持原字段即可）。
- `/feeds/{id}/run` 只做一件事：创建 `job_type=source_run` 并返回 `job_id`。

3) 执行层：feed-family run 全部复用 SourceRunHandler（不再引入 rss_feed_run）
- 不再新增 `rss_feed_run` 这套平行 job_type。
- 所有 ingestion 执行语义统一在 `source_run`（便于 scheduler 与追溯一致）。

### 2.5 数据落库契约（必须统一，否则会再次双轨制）

RSS ingestion 的数据落库采用三段式：

1) RawCapture（不可变，可回放）
- 保存本次抓取到的原始 XML（或摘要）到 `raw_captures`，payload 建议落文件，DB 存 `content_ref + checksum`。
- 必须有 retention（按天/按次数/按总大小滚动）。

2) Entry Index（幂等索引）
- `source_item_index` 以 `(source_id, item_key)` 作为幂等键。
- item_key 建议版本化：`v1:<guid>`；无 guid 时用稳定 hash（例如 `original_url + title + published_at`），不要只依赖 canonical_url。

3) Resource（canonical 文档）
- `resources.canonical_url` 唯一；`resource_id` 必须确定性（pipeline 已按 canonical_url 生成）。
- provenance 必须包含：source_id、item_key、captured_at、adapter_version。

### 2.6 Tool Functions（给 UI/agent 的稳定接口）

命名与边界（推荐）：
- canonical namespace：`sources.*`
- RSS 只是：`source_type in {rss,atom,jsonfeed}` 的筛选条件
- 如需要，可提供 `rss.*` 作为薄 alias（只做预过滤，不引入第二套语义）

最小工具面：
- `sources.list(source_type_in=[rss,atom,jsonfeed])`
- `sources.get(source_id)`
- `sources.upsert(...)`（side-effect，默认 require_confirm）
- `sources.toggle(source_id, enabled)`（side-effect）
- `sources.delete(source_id)`（side-effect）
- `sources.import_opml(opml_text|file_ref)`（side-effect）
- `sources.run(source_id, mode=commit|dry_run)`（必须返回 job_id）
- `sources.runs(source_id)`（运行历史）
- `sources.resources(source_id)`（join source_item_index + resources）
- `sources.profile(source_id|group)`（只输出元信息，不做业务决策）

### 2.7 RSS 解析与时间字段（数据质量的关键收敛点）

RSS/Atom 的发布时间字段在真实世界里非常脏：
- RSS 常见 RFC822；Atom 常见 ISO8601；有的只有 parsed struct。

建议：
- 以 feedparser 的 `published_parsed/updated_parsed` 为主；字符串解析为辅。
- 解析失败可以置 None（类型必须安全），但要在 profile 里记录“日期缺失比例”，避免业务层误判趋势。

### 2.8 渐进落地建议（最短路径，避免断裂）

按收益/风险排序：

1) 先把 `/feeds/{id}/run` 变成 shim：内部转为 `source_run` job（对外保持 API 兼容）。
2) 把 `/feeds` 的 CRUD 逐步改为读写 `source_registry`（feed-family 视图）。
3) 补齐 run history（基于 jobs/source_run_log）与 run detail（events/tool_calls）。
4) scheduler 只需要调度 sources：无需为 feeds 单独扩展 schedule_type。
5) 最后才考虑：删除或只读保留 `rss_feeds`（迁移完成后）。

---

## 第 3 章：学术源方案（arXiv + OpenReview）

本章目标：把“论文趋势”这条主干跑通，并与 Sources/JobRunner 的语义完全一致。

### 3.1 统一抽象（对齐 Sources 数据层）：academic_api + platform

建议把学术源统一表示为：
- `SourceRecord.source_type = "academic_api"`
- `config.platform in {"arxiv", "openreview"}`

这样：
- CRUD/调度/运行历史复用 Sources 体系；
- 执行统一走 `job_type=source_run`；
- item_key 仍由 `RawEntry.entry_id` 决定（写入 source_item_index）。

### 3.2 arXiv 方案

#### 3.2.1 MVP（最快落地）：Atom Query / arxiv 库

定位：用于“快速拉最近 N 条”，适合趋势跟踪与轻量 backfill，不作为大规模同步的唯一方案。

配置建议（config_json）：
- `platform: "arxiv"`
- `query`: arXiv query 语法（例如 `all:AI AND (cat:cs.AI OR cat:cs.LG)`）
- `categories`: 可选（如 ["cs.AI", "cs.LG"]，用于拼 query）
- `max_results`: N（默认 20-100）

幂等与 key 设计：
- 推荐 paper-level key：`item_key = v1:arxiv:<base_id>`（去掉 vN）。
- 如你需要版本：可额外存 `version=vN` 到 provenance 或 raw capture（canonical resource 仍按 base_id 聚合）。

注意事项（必须写进系统契约）：
- arXiv legacy API 速率限制：全局 1 请求 / 3 秒，单连接。
- Atom API 更像“查询接口”，不是“增量同步接口”；新旧数据都可能被你重复拉取，因此必须依赖 item_key + resource upsert 幂等。

#### 3.2.2 稳健增量同步（推荐成为系统 of record）：OAI-PMH

定位：用于“可回放、可 backfill、可增量同步”的系统级采集。

核心机制：
- 端点：`https://oaipmh.arxiv.org/oai`
- 通过 `ListRecords` + `resumptionToken` 分页。
- 用 OAI 的 `datestamp` 做增量游标，但注意 granularity 为日期级（YYYY-MM-DD），必须 overlap（例如回退 2 天）以防漏数。

key 设计：
- `item_key = v1:arxiv:<base_id>` 作为 paper-level 幂等键。
- 版本历史（如需要）可以在 raw capture 或派生产物里保留（不要把 version 作为主键导致重复 papers）。

更新/撤稿（withdraw）语义：
- 撤稿会产生新版本并在 comments 字段体现原因；因此同一 base_id 会更新（upsert）。
- OAI datestamp 代表记录修改时间，不等价于投稿时间。

调度建议：
- OAI 增量每天跑一次（避开 nightly 更新窗口，增加 overlap）。

### 3.3 OpenReview 方案（API v2 优先）

#### 3.3.1 数据模型与 key

OpenReview 的基本对象是 Note（submission/review/comment/decision 都是 Note）。

稳定 key：
- `item_key = v1:openreview:note:<note.id>`（note.id 是稳定唯一 id）。

重要字段语义：
- `note.forum` 是 thread root id。
- `note.id == note.forum` 表示 submission（paper），否则是 reply（review/comment/etc）。
- `tcdate/tmdate` 是创建/修改时间（毫秒）。
- 可见性由 readers 控制；content 字段可能局部不可见，必须容忍字段缺失。

#### 3.3.2 Backfill（一次性拉全量）

推荐输入：`venue_id`（例如 `ICLR.cc/2024/Conference`）。

流程：
1) 读取 venue group 的 `submission_name`，拼 submission invitation id。
2) 分页拉 submissions：`GET /notes?invitation=<submission_inv>&details=replies&limit=1000&offset=...`
3) 写入：
  - submission note 作为 paper
  - replies（review/comment/decision）可选：
    - MVP 可以只落 raw capture（或作为 artifact），先不全部进入 resources，避免噪声；
    - 若需要全文检索评论，再把 replies 也映射为 resources（但要明确 media_type）。

#### 3.3.3 Incremental（推荐）：Edits 作为 change feed

OpenReview v2 的 Edits 是变更流：`GET /notes/edits?domain=<venue_id>...`。

状态建议：
- `last_tcdate_seen`（ms）+ `lookback_ms`（例如 5-30 分钟）防止边界漏数。

调度建议：
- 活跃期（投稿/评审）：10-30 分钟一次。
- 归档期：每天或每周。

#### 3.3.4 常见坑（必须写进设计）

- API v1/v2 兼容：旧 venue 可能仍需要 v1，需做版本探测与 fallback。
- replies 并不总在一个“全局 Official_Review invitation”下，优先用 `details=replies` 或 `forum=<id>` 拉回复。
- readers/字段可见性：公开抓取看不到 reviewer-only 内容是正常行为，不应当报错。
- note.id 随机且不按时间排序：不要把 after=id 当“增量游标”，增量要靠 edits/tcdate。

### 3.4 与现有代码的对齐（现状 + 扩展点）

已存在：
- arXiv：`core/collector/arxiv_engine.py`（使用 python arxiv 库，delay_seconds=3）。
- Sources dispatch：`core/sources/collectors.py` 的 `_collect_academic_entries` 已支持 `platform==arxiv`。

待补齐：
- OpenReview：在 `_collect_academic_entries` 增加 `platform==openreview` 分支，实现 `OpenReviewCollector` 并返回 `list[RawEntry]`。
- arXiv 的 provenance/source_id：当前 ArxivCollector 内部硬编码 feed_id/source_id，建议改为由 SourceRecord 传入并写入 RawEntry.feed_id（保证 provenance.source_id 正确）。
