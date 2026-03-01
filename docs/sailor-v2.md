# Sailor V2 设计文档（草案）

本文件目标：把 Sailor 从“能采集/能嗅探/能收藏”的工具，推进到“可持续演进、可验证、可运营”的完整系统。

范围说明（避免歧义）：
- 本文是设计与路线图，不包含代码改动。
- 讨论对象是当前仓库的 Sailor（FastAPI + React + SQLite，本地优先）。

文档状态：草案；后续章节会在落地过程中持续补全。

---

## 1. 总起：你要的“完整系统”是什么，以及 Sailor V2 为什么要这么做

这一章做三件事：
1) 把你的想法翻译成一个清晰、可执行的系统闭环；
2) 用“用户视角的端到端流程”把各模块串起来，降低跳跃；
3) 对照 Sailor 现状，解释 V2 还缺哪些关键支撑能力，以及为什么这些要优先做。

### 1.1 一页概览（本章总起）

你提出的完整系统，本质是一个“信息供应链闭环”（information supply chain loop）：

1) 主动发现（嗅探）
- 不是等信息来，而是主动在多渠道里搜索/筛选候选资源。
- 目标是把“候选集合”结构化：来源、标题、摘要、指标、发布时间、原始链接等。

2) 策展沉淀（入库/知识库）
- 不是把所有东西都塞进库，而是把“确实有价值”的资源沉淀到知识库（KB）。
- 这一步是系统的“质量闸门”：它决定库里的内容是否长期可用。

3) 渠道沉淀（晋升为订阅源，长期关注）
- 如果发现某条渠道持续高质量，那么把它从一次性嗅探结果，晋升为订阅源（持续采集与监控）。
- 这一步把“偶然发现”变成“稳定供给”。

4) 问答系统（QA，chat-to-db / chat-to-library）
- 当资源库变大，靠翻页/手动检索会崩溃；需要自然语言问答作为统一入口。
- QA 不只是聊天；核心是：能查到、查得准、可溯源、可复盘。

5) 长期分析（聚类/主题演化/报告）
- 对资源库做长期聚类、趋势变化与漂移监控，定期产出报告。
- 报告不是“为了报告”，而是反哺：嗅探策略、订阅策略、标签偏好、内容方向选择。

这五步不是并列功能，而是一个闭环：
- 嗅探 ->（挑选）-> 入库
- 入库 ->（发现稳定产出）-> 渠道晋升 -> 订阅持续采集
- 入库 + 订阅产出 -> QA 提问与决策
- QA/行为反馈 + 库增长 -> 长期聚类报告 -> 反哺嗅探/订阅/策展

一句话：你想把 Sailor 从“采集器 + 资料夹”，升级成“可持续运转的信息系统”。

---

### 1.2 把概念讲清楚：嗅探、订阅、资源库、知识库、Agent 工具模块分别是什么关系

为了避免后续设计中角色混乱，先把五个核心对象分清：

1) 嗅探（Sniffer）= 主动式发现
- 作用：在更大的信息面（多渠道）里快速找“可能有用”的候选，并把候选变成可操作的结构化结果。
- 输出：候选列表（结构化 SniffResult），通常包含噪声、重复、以及“暂时不确定价值”的边缘项。
- 特点：一次性、探索性、强调覆盖率与速度。
- V2 增强点（你提出的多 Agent）：
  - 把嗅探从“固定适配器并行搜索”，升级为“Plan Agent + Worker Agents”的编排式嗅探。
  - Plan Agent：理解用户 prompt，选择渠道、拆分任务、创建 Worker，并为每个 Worker 分配清晰任务与预算。
  - Worker Agent：对单一渠道执行读取/搜索/抽取/初步筛选，把输出压成结构化结果与证据（链接/片段/元信息）。
  - 汇聚器（Aggregator）：对多个 Worker 的输出做去重、归并、排序，并生成面向 UI 的摘要。

2) 订阅（Feeds / Unified Sources）= 被动式持续采集
- 作用：对被验证过的稳定渠道做长期监控与增量采集。
- 输出：持续新增的条目（RawEntry -> Resource）。
- 特点：长期、可调度、强调稳定性与可观测（失败率、延迟、产出）。

3) 资源库（Resources）= 统一的“候选+入库”资源集合
- 作用：把来自嗅探和订阅的内容统一成可查询的资源表（canonical_url 去重）。
- 输出：可检索、可分析的资源项，支持后续打标、评分、聚类。
- 特点：是系统的“中间层”；资源库可以包含“未入 KB 的 inbox”。

4) 知识库（Knowledge Base / KB）= 策展后的长期资产
- 作用：把“确定有价值/可复用”的资源编进主题库（KB items）。
- 输出：更高质量、更稳定的知识集合，用于深度报告与决策。
- 特点：有明确的主题边界与管理动作（收藏/移除/报告）。

5) Agent 工具模块（Tool Module）= Worker 的“手和脚”
- 作用：把“能做什么”标准化成一组稳定的 tool/function calls，供 Worker Agent 调用。
- 典型工具类型：
  - 渠道读取/搜索工具：读取某条 URL、在某个平台搜索、拉取转录/评论等。
  - Sailor 内部工具：把 RSS / 非 RSS 的订阅配置、统一源管理、以及现有 sniffer/channel 能力封装成可调用函数（例如 list sources、run source、import feeds 等）。
- 为什么单独抽出来：
  - 你要的是“多 Agent 嗅探”，而不是“多 prompt”。Worker 的价值来自可执行工具；工具的契约稳定与可审计，决定了系统是否可运营。
  - Agent-Reach 这类项目可以被放进 Tool Module：它更像“渠道能力控制面”（安装/诊断/建议怎么读），Worker 再按其建议调用上游工具完成读取。
    - 注意：Agent-Reach 本身不负责 plan/worker 编排；它更像“工具与就绪度”的提供者。

把它们连起来就是你说的“讲道理应该先嗅探、再入库、再订阅”的顺序：
- 嗅探给广覆盖候选；
- 入库/收藏是质量闸门；
- 晋升订阅源把高质量渠道固化为长期输入；
- QA 与长期报告则是“规模化后的必要能力”。

---

### 1.3 用一个具体场景把闭环走一遍（从“我今天想找资料”到“系统长期帮我”）

假设你在跟踪一个主题：例如“Agentic workflow / RAG 评测 / 向量数据库”。

1) 嗅探：先扩展视野（V2：Plan + Workers）
- 你输入的不是“渠道勾选 + 关键词”，而是一段更自然的目标描述：
  - 例如：“帮我找最近 30 天 RAG 评测相关的高质量资料，优先 GitHub/HN/博客，给出推荐理由与链接。”
- Plan Agent 做两件关键事：
  - 任务拆解：把你的目标拆成渠道维度的 Worker 任务（如 GitHub 搜 repo+issue、HN 搜帖子、RSS 搜特定 feed/关键词、Web/Exa 搜长文）。
  - 资源预算：为每个 Worker 限定 max_results、超时时间、可用工具集（tool allowlist），并基于 Agent-Reach doctor 结果做渠道可用性预检与降级（不可用就换渠道或降低信心）。
- Worker Agents 并行执行：
  - 每个 Worker 只负责一个渠道，通过 Tool Module 执行读取/搜索/抽取，做一轮“轻量筛选”（去广告/去重复/保留最相关 topN）。
  - Worker 输出结构化 SniffResult（title/url/snippet/metrics/published_at/source_evidence），并附上证据与可追溯信息（用到的 tool call、原始片段、置信度）。
- 汇聚器统一收敛：
  - 将各 Worker 输出做 URL canonicalize + 近重复合并 + 去重排序。
  - 生成面向 UI 的摘要（命中渠道分布、关键词聚合、时间分布、互动度 Top、以及“为什么推荐”）。
- 你对其中 3 条做 Deep Analyze：系统把它们转成 Resource，跑 LLM 分析（摘要、主题、评分、洞察）。

2) 策展：把“有用的”沉淀为资产
- 你把其中 1 条加入 KB（比如 KB: "RAG Evaluation"）。
- 这一步会产生行为记录，并反哺你的标签偏好（未来打标更准）。

3) 渠道晋升：把“偶然的好发现”变成稳定输入
- 你发现某个来源（例如一个高质量 blog / repo / newsletter 页面）连续两次嗅探都很优秀。
- 你点击 Convert to Source，把它登记为 Unified Source，并设置 schedule_minutes。
- 之后系统会定期拉取新内容并入库；你不用每次都再手动嗅探它。

补充（V2 的自动化边界）：
- 计划上可以让 Plan Agent/Workers 提出“晋升建议”（propose），例如：
  - “这个来源过去两次嗅探都贡献了高相关度结果，建议转为订阅源（source_type=web_page，schedule=6h）。”
- 但真正写入订阅配置（commit）建议仍走人类确认（HITL）：这能避免 agent 误把噪声渠道加入长期订阅，造成后续污染与成本浪费。

4) QA：当库变大，问答成为主入口
- 一周后你问：
  - “过去 30 天关于 RAG 评测的资源有哪些？按渠道分组列出 top 10。”
  - “有哪些资源被我加入了 KB，但评分低？为什么低？”
  - “这个月 GitHub 渠道里出现的新主题是什么？”
- 系统不是“随口回答”，而是：先把问题转成可执行查询（DB/索引），再基于结果做总结，并给出引用链接与资源 ID（可回溯）。

5) 长期报告：从“信息列表”升级到“结构化洞察”
- 每周生成报告：主题聚类、主题增速、漂移告警、新兴主题、代表资源、以及建议关注的渠道。
- 报告会反哺：
  - Sniffer packs 的关键词与渠道组合（更准地找新东西）
  - 订阅源的启停/降频/升频（更稳地持续关注）
  - 标签体系与偏好权重（更符合你真实兴趣）

这个例子想强调：V2 的价值不是“多几个按钮”，而是把这些动作串成一条可持续的工作流。

---

### 1.4 Sailor 已经做到哪一步（对照你的闭环，哪些已经具备、哪些是基础但未系统化）

先说结论：你描述的闭环里，Sailor 已经具备了 60%-70% 的“功能拼图”，尤其是“嗅探 -> 入库/收藏 -> 晋升订阅源”的主链路已经打通；但要变成“完整系统”，还缺关键的基础设施与一致性（数据分层、调度、查询、QA 安全、长期聚类）。

下面按闭环逐项对照：

1) 嗅探（主动发现）
- 已有：Sniffer 搜索、结果落库、规则摘要、对比总结、pack 管理、健康检查、定时执行。
- 已有闭环动作：
  - Deep Analyze：嗅探结果转 Resource 并触发文章分析。
  - Save to KB：嗅探结果一键收藏到 KB。
  - Convert to Source：嗅探结果一键登记为 Unified Source（这正是你说的“发现好渠道就加入订阅源长期关注”）。
- V2 需要补：多 Agent 嗅探的“编排层”与“工具层”。现有 Sniffer 更像固定适配器并行搜索；你提出的是 Plan Agent 动态拆解任务 + Worker 专注单渠道执行，并用 tool/function call 把能力标准化。
- 最小演进策略：先把现有“渠道适配器并行搜索”当作一类 WorkerTools（先补 run_id/provenance/tool_calls），再逐步引入 Agent-Reach 背后的更丰富渠道工具。

2) 订阅（长期采集）
- 已有：
  - RSS feeds 管理（传统 RSS 模型）。
  - Unified Sources（source_registry + run_log + item_index），支持多 source_type（rss/atom/jsonfeed/web_page/academic_api/opml/jsonl...）。
- 现状特点：单源 run 有完整 run_log，但按类型批量 run 的可观测性与一致性还不足；schedule_minutes 目前偏“配置字段”，尚未形成统一自动调度。

3) 资源库/知识库（沉淀）
- 已有：resources 表作为统一资源池，并区分 inbox（未入 KB）。
- 已有：KB 的 CRUD 与收藏关系（kb_items），收藏动作会反哺 tag weight（偏好学习的雏形）。

4) LLM 分析与报告（“智能层”已出现雏形）
- 已有：
  - 单篇文章 LLM 分析（ResourceAnalysis）：摘要、主题、评分、洞察。
  - KB 报告（cluster/association/summary）与 Trending 报告。
- 但注意：KB 的 “cluster/association” 目前是 LLM 生成报告，不是 embedding 聚类；并且有条数上限，无法覆盖长期大库。

5) 可观测性
- 已有：日志面板 + SSE 流式日志。
- 但更“系统级”的观测（调度延迟、失败率、数据新鲜度、QA/聚类的评测指标）还未形成。

---

### 1.5 V2 还缺什么：为什么这些是“必须补齐的地基”，而不是锦上添花

这一节会比“功能列表”更重要：因为你要的是长期演进的系统，最怕的不是缺功能，而是缺“让功能可持续”的底座。

我把缺口按“返工风险”排序（越靠前越建议先做）：

1) 数据分层与可回溯（Provenance / Lineage）
- 问题：当前 resources 同时承担“规范化权威文档”和“临时候选”两种语义；分析/报告产物分散在不同表里，缺少统一的派生产物抽象。
- 为什么要先补：
  - 一旦引入 embedding/聚类/QA，产物会快速增多；没有 lineage，未来很难回答：这份报告基于哪些输入？用了哪个模型版本？是否需要重跑？
  - 没有明确的 raw/canonical/derived 分层，去重、重跑、回放、评测都会变成“靠感觉”。
- V2 的方向（结合多 Agent 嗅探）：
  - 尽早把 RawCapture / CanonicalDocument / DerivedArtifact / ProvenanceEvent 作为稳定概念固化（不一定立刻大迁移，但至少先建立契约与最小表）。
  - 把“Plan Agent 产出的计划”和“每个 Worker 的 tool calls”也纳入可追溯链路：
    - 计划（plan）是一次运行的核心输入之一，必须可回放（否则你无法复现某次嗅探为什么这么搜）。
    - 工具调用（tool call）是事实来源：应记录 tool_name/tool_version/request/response 摘要/耗时/错误/重试次数，以及配置引用（不存 secret）。
  - 这能保证：UI 上展示的每一条 SniffResult 都有证据链（我为什么推荐、我从哪里读到的、读的时候渠道是否可用、用了什么工具版本）。

2) 统一执行与调度（Job Runner）
- 问题：现在存在多条“运行入口”：trending pipeline、sources run、feeds run、sniffer packs scheduler；它们的日志、状态、幂等与重试不一致。
- 为什么要先补：
  - 订阅要“长期关注”，就离不开可控的调度与失败治理。
  - QA/embedding/聚类这些后台任务也需要同一套执行框架，否则你会堆出很多“临时脚本”。
- V2 的方向（结合 plan/fan-out/fan-in）：
  - 把所有“运行”统一成 job：创建 -> 执行 -> 记录 run_id -> 可回放；先同步也可以，但契约要统一。
  - 多 Agent 嗅探天然是 DAG：Plan（单点）-> Workers（并发扇出）-> Aggregation（扇入汇总）。Job Runner 必须原生支持这种拓扑，而不是靠临时线程拼出来。
  - 工具层（Tool Module）要和 Job Runner 强绑定：
    - 工具调用要有预算/并发/超时/重试策略
    - 以及 policy（允许哪些 tool、哪些需要人工确认、哪些只允许 read-only）
  - 订阅配置相关的 tool call（例如写入 RSS/non-RSS sources）应当分为 propose 与 commit：
    - Worker/Plan 只能 propose（产出建议与证据）；
    - commit 由用户确认后由 Job Runner 执行并写入审计事件。

3) 查询能力（QA 的地基）
- 问题：资源查询目前主要按 topic/inbox；缺少全文检索、复杂过滤与聚合统计。
- 为什么要先补：
  - 你说的 QA（chat-to-db）如果直接跳到 NL2SQL，风险很高（幻觉、越权、不可控 SQL）。
  - 更稳的方式是先补“确定性 Query API/DSL + 索引（如 SQLite FTS5）”，让模型做“意图到 QueryPlan”的转换，而不是凭空造 SQL。
- V2 的方向：先让 DB 本身可查（FTS + filter/aggregate API），再让 LLM 做自然语言入口。

4) QA 系统的安全执行链路（gated NL2SQL / chat-to-db）
- 问题：目前没有 QA 路由、SQL 生成与校验、安全只读执行、引用溯源与评测。
- 为什么要先补：
  - 只要开始执行模型生成的查询，就必须 fail-closed（不确定就不执行），否则早晚会出数据污染或错误决策。
  - QA 还需要“可复盘”：能看见它用了哪些数据回答、跑了什么查询、耗时多少、结果行数多少。
- V2 的方向：采用 gated pipeline：schema linking -> constrained generation -> AST 校验/重写 -> read-only 执行（超时/限行）-> 带引用回答 -> 记录审计日志。

5) 长期聚类与报告（embedding + 增量分配 + 周期重建 + 漂移监控）
- 问题：现有 KB 报告主要是 LLM 生成，条数上限明显；无法对全库做增量主题演化。
- 为什么要先补：
  - 你想要“长期聚类产出报告”，就必须面对库增长、主题漂移、近重复、成本治理。
- V2 的方向：
  - 把 embedding 当作一类 DerivedArtifact 存储。
  - 先做“增量簇分配 + 每周重建”的双通路；再加 drift detector 与在线主题更新。

6) 去重与质量评分（决定自动化上限）
- 问题：当前去重主要靠 canonical_url；缺少近重复与质量评分框架。
- 为什么要补：
  - 没有去重与评分，你就无法稳定地做“自动入库”“自动晋升渠道”，系统会被转载/噪声淹没。
- V2 的方向：精确去重（URL/内容 hash）+ 近重复（MinHash/embedding 相似）双层；评分维度版本化、阈值可回溯。

---

### 1.6 V2 的目标态（高层架构草图）：把闭环变成可持续系统

从系统视角，V2 不是“再加几个页面”，而是把关键能力组织成清晰边界：

1) Acquisition（采集/发现）
- feeds / unified sources / sniffer 统一输出 RawCapture / RawEntry。
- V2 的 sniffer 由两层组成：
  - Orchestrator（Plan Agent + Worker Agents）：决定“去哪里找、怎么找、找多少”。
  - Tool Module：提供“怎么读/怎么搜”的标准化能力（含 Agent-Reach 提供的渠道能力与 Sailor 内部的 sources/feeds 工具）。

2) Curation（规范化/去重/评分）
- pipeline stages：normalize -> fetch/extract -> clean -> dedup -> score -> enrich。

3) Knowledge Core（资源库与知识库）
- canonical documents（resources）+ kb + tags + user_actions。

4) Query & QA（查询与问答）
- Query API/DSL + 索引（FTS/embedding）
- QA：把 NL 转为 QueryPlan 并可审计。

5) Source Lifecycle（渠道生命周期）
- 候选渠道 -> 晋升 -> 订阅 -> 监控 -> 降权/暂停/退役。

6) Analytics & Reporting（长期分析与报告）
- embedding 计算、聚类、主题演化、漂移监控、周期报告与回填。

横切能力（所有模块都要用同一套）：
- Job runner / scheduler（统一任务契约）
- Observability（metrics + logs + replay）
- Evaluation（QA 正确率、聚类一致性、晋升策略 precision/recall）
- Security（只读执行、审计、secret 边界）

一个简化的数据流示意：

```text
Sniffer/Search  ----\
                   \--> RawEntry/RawCapture --> Pipeline(Curation) --> Resources --> KB
Feeds/Sources  -----/                                         \--> DerivedArtifacts(analysis/embedding/cluster/report)

QA(Chat) --> QueryPlan --> (DB/FTS/Vector) --> Results --> Answer + Citations

Analytics(Weekly) --> Embedding/Clustering/Drift --> Reports --> Feedback -> Packs/Sources/Tags
```

---

### 1.7 落地方法论：怎样一步步实现，才能少走弯路

你关心的是“最少返工”。基于当前 Sailor 的形态（本地优先 + SQLite + FastAPI + React），我建议遵循三条原则：

原则 A：先把“契约”固定，再扩功能
- 先定义：资源主键策略、来源生命周期、artifact/事件 schema、job 状态机。
- 这样后面加 QA/聚类/调度时，是往既有框架里填模块，而不是重写底座。

原则 B：先做可验证的闭环，再做更聪明的自动化
- 先让系统可靠：可观测、可回放、可评测。
- 再做智能：embedding/聚类、晋升推荐。
- 最后做自动化：自动晋升、自动入库、自动降权。

原则 C：对 LLM 采取“可控输入、可控输出、可复盘”策略
- LLM 适合生成摘要/标签/报告文本，但关键链路（查询、调度、权限）必须有确定性校验。
- QA 尤其要 fail-closed：不确定就不执行/不回答。

本章到这里，你应该能把 V2 看成一个可执行的闭环系统，而不是一堆零散功能。

---

## 2. V2 数据模型与事件/工件（Raw / Canonical / Derived）

这一章的目标：把 V2 的“数据地基”讲清楚。

如果你要在嗅探里引入 Plan Agent + Worker Agents，并且让 Worker 通过各种工具（包括 Agent-Reach、Sailor RSS/非 RSS 配置工具）去读/搜/抽取，那么数据模型必须同时满足三点：
- 可追溯：任何结果都能回到“谁做的、怎么做的、用的什么工具、基于什么输入”。
- 可重跑：同一份输入/配置，在未来能重复执行或做差分回放。
- 可演进：工具/模型/策略会升级，旧数据不应被“语义漂移”悄悄污染。

### 2.1 四层数据分层：Raw / Canonical / Derived / Event

为了让系统可运营，V2 建议把所有数据严格分为四层，并在结构上表达出来：

1) RawCapture（原始采集层，不可变）
- 定义：一次“外部读取/搜索”的原始载荷与上下文。
- 来源：
  - Worker 调用某个渠道工具（例如 read URL、search GitHub、search Twitter）。
  - Sailor 自己采集 feed/source（抓到的原始条目/原始正文/原始 HTML）。
- 不可变原则：写入后不修改，只能追加版本。
- 价值：是所有“证据链”的起点，也是未来重跑/复现的依据。

2) CanonicalDocument（规范化层，面向查询）
- 定义：从 RawCapture/RawEntry 中抽取并规范化后的权威文档。
- 在 Sailor 里，它最接近现有的 `resources` 表（以 canonical_url 去重）。
- 重点：canonical_url 去重只是第一步；V2 需要明确“哪些字段是权威可更新、哪些字段是历史版本”。

3) DerivedArtifact（派生产物层，可重建）
- 定义：由模型/算法/规则在 CanonicalDocument 或 RawCapture 上生成的产物。
- 例子：ResourceAnalysis、embedding、cluster assignment、weekly report、QA answer、晋升建议。
- 原则：
  - 产物必须引用输入（input_ids）与产出者（produced_by_run/tool_call）。
  - 产物必须带版本（model_version/prompt_version/algorithm_version）。

4) ProvenanceEvent（事件层，append-only）
- 定义：记录“发生了什么”的事件流水账。
- 覆盖：job 生命周期、plan 生成、worker 分派、tool call 执行、policy 决策、产物生成。
- 为什么需要：没有事件，你就无法可靠做审计、回放、评测与运营指标。

### 2.2 核心实体（建议的最小集合）

为避免一次性改表过多，先定义最小但足够表达 V2 的实体集合（并允许渐进落库）：

1) Job / Run
- `Job`：一次可运行的工作单元（例如：sniffer 搜索一次、跑一个 source、生成一份周报）。
- `Run`：Job 的一次执行实例（带 run_id、状态、开始结束时间）。

2) AgentRun（Plan/Worker）
- `plan_run`：Plan Agent 的一次执行，输入是用户 prompt + 可用工具集 + 预算。
- `worker_run`：某个 Worker 的一次执行，输入是 plan 的子任务 + 渠道选择 + 工具 allowlist。

示例：PlanSpec（plan_run 的结构化输出，供 Job Runner 校验与回放）

```json
{
  "schema_version": "v1",
  "prompt": "Find high-quality RAG evaluation resources in last 30 days",
  "budget": {
    "max_workers": 4,
    "max_tool_calls": 20,
    "deadline_ms": 60000
  },
  "workers": [
    {
      "worker_id": "w_github",
      "channel": "github",
      "task": { "type": "search", "query": "rag evaluation", "time_range": "30d" },
      "tool_allowlist": ["github.search_repos", "github.search_issues"],
      "max_results": 20,
      "timeout_ms": 15000
    },
    {
      "worker_id": "w_hn",
      "channel": "hackernews",
      "task": { "type": "search", "query": "rag evaluation", "time_range": "30d" },
      "tool_allowlist": ["hn.search"],
      "max_results": 15,
      "timeout_ms": 10000
    }
  ],
  "aggregation": { "dedupe_by": ["canonical_url"], "top_k": 30 }
}
```

3) ToolCall
- 定义：一次工具调用的记录（这不是日志，而是结构化数据）。
- 最小字段建议：
  - tool_call_id, tool_name, tool_version
  - request_json（含 schema_version、idempotency_key）
  - status, started_at, finished_at, latency_ms
  - error_type/error_message（可归类）
  - output_ref（指向 raw capture 或摘要）
  - credential_ref（只存引用，不存 secret）

示例：ToolCall envelope（request/response 的最小形态，便于审计与缓存）

```json
{
  "tool_name": "github.search_repos",
  "tool_version": "2026-03-01",
  "schema_version": "v1",
  "idempotency_key": "sha256:...",
  "input": { "query": "rag evaluation", "limit": 10 }
}
```

```json
{
  "status": "ok",
  "items_count": 10,
  "capture_ref": "raw_capture:cap_01H...",
  "content_ref": "file:data/captures/cap_01H....json"
}
```

4) SniffQuery / SnifferPack / SniffResult
- 现有 SnifferQuery/SnifferPack/SniffResult 继续保留。
- V2 需要补两点：
  - `sniff_run` 与 `worker_run` 的关联（哪个 pack/prompt 触发的，跑了哪些 worker）。
  - 每条 SniffResult 必须能追溯到 tool_call_id/raw_capture_id（证据链）。
- 建议新增 SnifferRunLog（以及可选的 per-channel 子表）：
  - 语义对齐现有 SourceRunLog（create_run/finish_run/status/metadata）。
  - `sniff_results` 需要能关联 run_id（直接加字段或加一张 mapping 表），这样 deep-analyze/save-to-kb/convert-source 都能回到“这条结果来自哪次嗅探、哪个 worker、哪个 tool call”。

5) Source/Feed 与“工具化”接口
- V2 将 Sailor 内部的 RSS/non-RSS 配置能力显式纳入 Tool Module：
  - read-only：list sources/feeds、查看 run log、查看资源产出
  - side-effect：upsert source/feed、import OPML、run source/feed
- side-effect 工具建议默认只允许 propose（见第 3 章的 policy）。

### 2.3 ID 与幂等：先把“能重复执行”这件事做对

V2 强烈建议把 ID 与幂等作为“契约”先固定：

- `resource_id`：建议与 canonical_url 强绑定（例如 `res_` + sha1(canonical_url)[:12]），并确保任何入口（sniffer/source/feed）都使用同一规则。
- `job_id/run_id`：每次运行都生成唯一 run_id；同一 job 的重跑也有新 run_id。
- `idempotency_key`：对每个 tool call/step 生成稳定键（输入 + 工具版本 + 关键参数 hash），用于去重与缓存。

这样做的收益：
- 多次重试不会制造重复数据；
- 你可以做“差分回放”（比较两次 run 的结果差异）；
- 缓存命中可控（而不是靠运气）。

### 2.4 Tool Module 的版本化契约（你要的“tool function call”放在这里）

为了让 Worker Agent 真正可用，Tool Module 需要像 API 一样可治理。

建议每个工具都有一个 `ToolDescriptor`（工具描述），至少包含：
- `tool_name` / `tool_version`
- `schema_version`（request/response 的 JSON schema 版本）
- `capabilities`（read/search/extract/convert-source 等）
- `auth_requirements`（是否需要 cookie/token/proxy；但不包含 secret）
- `rate_limit` / `cost_model`（时间/配额/金钱成本的估算）
- `cache_policy`（可缓存吗，TTL 多久，key 由什么组成）
- `side_effect`（是否会写 Sailor DB 或修改订阅配置）

对 Agent-Reach 的定位建议：
- Agent-Reach 提供 doctor 与渠道清单（readiness），并给出“应该调用哪个上游工具”的路径。
- Sailor 的 Tool Module 可以把“读取/搜索”封装成稳定 tool call，同时在内部按 Agent-Reach 推荐调用上游工具。
- Agent-Reach 不提供 planner/worker runtime；计划、分派、重试与汇聚应由 Sailor 的 Orchestrator/Job Runner 负责。

### 2.5 ProvenanceEvent：事件设计（最小但够用）

建议先定义一套事件类型（event_type），并在 V2 里强制所有关键动作写事件：

- JobCreated / JobStarted / JobFinished
- PlanGenerated（包含 plan 摘要、预算、选用渠道）
- WorkerDispatched / WorkerFinished
- ToolCallStarted / ToolCallFinished
- PolicyDecision（allow/deny/require_confirm）
- RawCaptureStored（capture_ref + checksum）
- ReadinessSnapshotCaptured（渠道就绪度快照，例如 Agent-Reach doctor 输出）
- ResourceUpserted / KBItemAdded / SourceProposed / SourceCommitted
- ArtifactProduced（analysis/embedding/cluster/report/qa_answer）

事件最小字段建议：
- event_id, event_type, ts
- run_id（所属执行），parent_run_id（可选）
- actor（planner/worker/system/user）
- entity_refs（resource_id/tool_call_id/raw_capture_id/source_id...）
- payload_json（版本化）

### 2.6 SQLite 落地策略（渐进式，不要求一次到位）

你现在用 SQLite 且 schema 是“代码即 schema”。V2 不建议一口气重构全部表，而是：

1) 先新增几张“横切表”，不破坏现有业务表：
- `jobs`：job_id/type/status/created_at/started_at/finished_at/metadata_json
- `provenance_events`：event_id/run_id/event_type/ts/payload_json
- `tool_calls`：tool_call_id/run_id/tool_name/tool_version/request_json/status/output_ref/error
- `raw_captures`：capture_id/tool_call_id/channel/content_ref/checksum/content_type/created_at
- `derived_artifacts`：artifact_id/type/status/input_refs_json/content_json/version_fields

2) 然后逐步把既有产物“挂载”进 derived_artifacts：
- `resource_analyses`/`kb_reports` 初期可继续存在；中期可以作为 derived_artifacts 的具体 type 或视图。

3) 大 payload 不建议塞 DB
- raw HTML、长文本、视频转录等体积很大，建议落到文件系统（或对象存储），DB 只存 content_ref。

### 2.7 重要安全边界：不把 secret 混进 provenance

- ToolCall 里只存 `credential_ref`（例如“agent-reach profile 名称/渠道配置 ID”），不存 cookie/token。
- 若需要展示“为什么失败”，应展示 doctor 快照与错误类型，而不是把敏感内容打进事件。

本章的结论是：多 Agent 嗅探能否做成“系统”，不取决于 prompt，而取决于你是否把 ToolCall 与 provenance 当作一等公民。

## 3. 统一任务系统：Job Runner、调度、幂等与重试

这一章解决的是“系统如何持续运转”。

在 V2 里，几乎所有重要动作都应该是 job：
- 跑一次 sniffer（plan + workers + 汇总）
- 跑一个订阅源（source/feed）
- 对一批资源做分析/embedding
- 生成周报/月报

如果没有统一的 Job Runner，你会得到一堆彼此不一致的入口：有的能重试、有的不能；有的有日志、有的只有 print；有的能取消、有的只能等。

### 3.1 Job Runner 的设计目标

V2 的 Job Runner 需要同时满足：
- 统一契约：任何 job 都有同一套状态、日志、事件与可回放语义。
- 支持 DAG：尤其是 sniffer 的 plan -> fan-out workers -> fan-in aggregation。
- 有治理能力：并发、预算、超时、重试、缓存、降级。
- 可观测：能回答“为什么慢/为什么失败/成本多少/产出多少”。

### 3.2 关键概念与状态机（建议先写进契约）

1) Job 与 Step
- `Job`：一次工作单元（type + input）。
- `Step`：Job 的一个阶段（plan、worker、aggregate、commit 等）。

2) 状态机（最小集合）
- queued -> running -> succeeded
- queued/running -> failed
- queued/running -> cancelled

3) 错误语义（必须可分类）
- transient：网络波动、rate limit、临时 5xx（可重试）
- permanent：鉴权失败、参数错误、策略禁止（不重试或需要人工介入）
- partial：某些 worker 失败但整体可降级返回（sniffer 常见）

### 3.3 多 Agent 嗅探 = Job Runner 的“标杆用例”

一个典型 SnifferJob 的执行拓扑：

```text
SnifferJob(run_id)
  Step A: Plan(prompt)  ---------------------
              |                               \
              | fan-out                        \
  Step B1: Worker(GitHub) ----\                 \
  Step B2: Worker(HN) ---------+--> Step C: Aggregate --> Step D: PersistResults --> Done
  Step B3: Worker(RSS/Web) ----/                 /
              |                                 /
              | optional propose                /
           Step E: ProposeSource/KB actions ---
```

Runner 在这里要解决的不是“怎么并行”，而是：
- 并行多少（concurrency）
- 每个 worker 的预算与超时（budget/timeout）
- 哪些失败可忽略（partial success）
- 哪些动作必须人工确认（commit gating）

### 3.4 幂等、重试、缓存：避免“重试把系统打爆”

建议写一个“重试矩阵”，把工具按类型治理：

- 读取/搜索类工具（read/search）：
  - 默认可重试（指数退避 + jitter）
  - 必须有 idempotency_key
  - 结果可缓存（按工具 TTL）
- LLM 类工具（summarize/compare/tag/analyze）：
  - 重试次数要更保守（成本敏感）
  - 强制记录 prompt_version/model
  - 允许缓存（输入 hash -> 输出）
- 写入/副作用工具（upsert source/import feeds/run source）：
  - 默认不自动重试（除非幂等证明充分）
  - 需要 policy: require_confirm

### 3.5 调度（Scheduling）：把“配置字段”变成“系统能力”

当前 Sailor 已经有：
- sniffer packs 的 schedule（Timer-based）
- unified sources 的 schedule_minutes（目前更多是配置）

V2 建议统一为同一套调度模型：
- interval（每 N 分钟）
- cron（更灵活）
- manual（手动触发）

并且引入最小的“单实例安全”机制：
- 即使未来跑多个进程，也要避免重复调度同一 job（可以用 DB 锁/租约表）。

### 3.6 Policy 与安全护栏（把 Agent 的能力关进笼子）

你提出 Worker 能调用 Sailor 的 RSS/非 RSS 配置工具，这是非常强的能力；V2 必须加护栏。

建议 3 个强制插入点：

1) Plan validation（计划校验）
- Plan Agent 产出的任务先过校验：
  - 是否只使用 allowlist 工具
  - 是否超预算
  - 是否包含副作用动作

2) Pre-tool-call policy check（工具调用前策略检查）
- 对每次 ToolCall 做 allow/deny/require_confirm 决策，并写入 PolicyDecision 事件。

3) Commit gating（副作用动作必须确认）
- 把“写入订阅配置/批量运行”等动作拆成 propose 与 commit。
- 默认：agent 只能 propose，commit 需要用户确认或显式开关。

### 3.7 观测与评测：把系统从“能跑”变成“可运营”

Runner 应该天然产出这些指标（后续可做成面板）：
- per job：耗时、成功率、重试次数、成本估算（LLM tokens/工具调用次数）
- per channel：可用性（doctor）、失败原因分布、平均延迟
- per sniffer：接受率（用户收藏/晋升占比）、重复率、噪声率

评测建议从最小集合开始：
- sniffer：用户接受/忽略作为弱监督
- QA：execution-based correctness（后续章节写）
- clustering：coherence/漂移指标（后续章节写）

### 3.8 渐进式落地路线（避免“大爆炸”重构）

建议按 5 个 stage 逐步上线：

- Stage 0：先加 run_id + 事件与工具调用记录（provenance_events/tool_calls/raw_captures），并补齐 SnifferRunLog（对齐 SourceRunLog 语义）。不改业务逻辑，但先让关键动作“可追溯、可回放”。
- Stage 1：把 sources/feeds 的 run 统一走 Job Runner（先串行也行）。
- Stage 2：sniffer 引入单 worker（验证 tool module + provenance 链路）。
- Stage 3：sniffer 扩成多 worker 并发（加入预算、超时、partial success）。
- Stage 4：加入调度统一与 policy/confirm gate（把副作用能力安全放出来）。

本章的结论：Job Runner 不是“工程洁癖”，而是 V2 能否长期扩展 QA/聚类/自动晋升的前置条件。

### 3.9 显式三层分离：用 Tool Functions + Engine Classes + JobRunner 自动化实现业务逻辑（并对齐现状与实施顺序）

这一节的目标是把“分层”从口头共识变成**可执行的工程约束**：
- 显式定义数据层 / 逻辑层 / 业务层的边界与依赖方向；
- 用“类（class）与函数（function）”把每一层的职责固化为可复用的抽象单元；
- 用 JobRunner 把这些抽象单元自动化（可调度、可追溯、可回放、可部分成功）；
- 最后把当前 Sailor 的真实代码架构对齐到这套约束，并给出实现顺序。

三层分工（在本节中是硬边界）：
- 数据层系统（RSS/非 RSS acquisition + 存储）：负责“把世界变成稳定的数据”。它输出 canonical 数据与可解释的元信息（run log、错误率、重复率、更新频率等），但不做 Trending/推荐/晋升等业务决策。
- 逻辑层引擎（headless engines）：负责“把数据变成可复用的信号/队列/策略”。它输出可渲染的状态视图（inbox/review queue）与可追溯的派生建议（tags/scores/晋升 proposal），但不直接做外部采集。
- 业务层系统（用户面）：Sniffer/Trending/KB/QA 等，负责“把信号组织成用户体验”，并把用户行为回流到底层信号（偏好、策略、调度）。业务层不应该把采集塞进按钮里。

在 Sailor 里，三层分离要靠一个“唯一通道”落地：
- Tool Functions：把可执行能力标准化成函数（可审计、可版本化、可治理 side-effect）。
- Engine Classes：把业务/策略/视图计算写成引擎类（可复用、可重建、尽量纯）。
- JobRunner：把函数与引擎放进统一执行框架（jobs/events/tool_calls/schedules/confirms）。

为了便于落地，本节按分层与抽象展开：
- 3.9.0 先冻结一套“类与函数”的统一抽象（后续都以它为语义基准）。
- 3.9.1 对齐现有代码的“双轨制”（runner 路径 vs legacy 路径）。
- 3.9.2 以 RSS 引擎为例，定义数据层引擎的功能特性与契约（偏“做什么”，少量接口形状）。
- 3.9.3 定义逻辑层引擎分组与能力边界（偏“做什么”，用 Engine class 语义表述）。
- 3.9.4 定义业务层系统的职责与编排方式（偏“做什么”，用 Orchestrator + jobs 语义表述；以 Sniffer 为准则）。
- 3.9.5 给出优先级与实施顺序（把分层约束落到可执行的迁移路径）。

#### 3.9.0 统一抽象：类与函数（把业务逻辑写成可自动化、可追溯的单元）

分层要“显式”，关键在于：每一层都要能回答“我暴露什么（functions/classes）”“我依赖什么（allowed deps）”“我不允许什么（forbidden deps）”。

1) Tool Functions（I/O 的唯一执行接口）
- Tool Function 是一个版本化函数：输入/输出是 JSON schema，可记录 ToolCall，可被 PolicyGate 管控。
- 任何外部 I/O（HTTP、调用 CLI、调用 LLM、写订阅配置）都必须通过 Tool Function 发生。

2) Engine Classes（逻辑层的可复用计算单元）
- Engine 是一个“可重建的计算单元”：输入来自 canonical 数据 + 已记录的上下文；输出是 artifact（派生产物）。
- Engine 不直接做渠道采集；不直接绕过 Tool Functions 访问外部世界。

3) Orchestrators（业务层的编排单元）
- Orchestrator 把用户动作翻译为一个或多个 job（DAG 也可以），并把结果组织成 UI 可消费的视图。
- Orchestrator 不内嵌采集实现细节；它消费数据层与逻辑层的 outputs。

4) JobHandlers（自动化执行单元）
- JobHandler 把某个 Tool Function 或 Engine 绑定到 runner：执行 -> 写 events/tool_calls -> 产出 output。

建议用如下“语言无关”的接口形状来固化边界（示意，不是具体实现）：

```text
interface ToolFunction<I, O> {
  name: string
  toolVersion: string
  schemaVersion: string
  sideEffect: boolean
  call(ctx: RunContext, input: I): O
}

interface Engine<I, O> {
  name: string
  engineVersion: string
  compute(ctx: EngineContext, input: I): O   // 输出 artifact 或 view-model
}

interface Orchestrator<I, O> {
  start(ctx: RequestContext, input: I): JobId
  getResult(jobId: JobId): O
}

interface JobHandler<I, O> {
  jobType: string
  execute(ctx: RunContext, input: I): O
}
```

与安全/自动化的关系（必须写死的规则）：
- Side-effect 工具必须走 PolicyGate：require_confirm 时只生成 pending_confirm，不直接 commit。
- 追溯主键统一：events/tool_calls/raw_captures 的 run_id 以 job_id 为准；domain run_id 只能作为别名并可映射。
- 任何“业务按钮的一键 pipeline”必须是 orchestrator 编排多个 job（或一个 workflow job），并且每个 step 都能追溯。

类归属规则（你强调的“不会存在跨层的类”在这里落成硬约束）：
- 每个业务类必须归属且只归属一层：数据层 / 逻辑层 / 业务层。
- 一个类不得同时承担多层职责（例如：既做采集 I/O 又做 digest 视图；既做推荐排序又写入订阅配置）。
- 允许存在一组“平台/基础设施类”（JobRunner/Scheduler/PolicyGate/RunContext/JobRepository 等），它们是框架，不属于三层业务类；平台类必须不包含业务决策，只提供执行/记录/调度/策略执行能力。

三层类的角色定义（把 3.9.0 的抽象落到层级）：
- 数据层类 = Data ToolFunctions + Repositories/Collectors/Pipeline Stages + Data JobHandlers
  - 例：`sources.*`（CRUD/run/import_opml）、HTTP 抓取、feed 解析、raw capture 存储、canonical upsert。
  - 输出：canonical 数据（resources/source_item_index）+ 可解释元信息（run/tool_calls/raw_captures）。
- 逻辑层类 = Engine Classes + Logic JobHandlers
  - 例：`ResourceIntelligenceEngine`、`ReviewWorkflowEngine`、`PromotionEngine`、`DigestEngine`。
  - 输出：artifacts（tags/scores/review queue/promotion proposals/digests），必须可重建。
- 业务层类 = Orchestrators + Controllers（routers/pages 只做适配）
  - 例：`SnifferOrchestrator`、`TrendingOrchestrator`、`KnowledgeBaseOrchestrator`、`QAOrchestrator`。
  - 输出：job_id + view-model + proposals（可确认动作）。

依赖方向（禁止跨层 import 的具体化）：
- 业务层可以依赖：平台（JobRunner API）+ 逻辑层的 read models（view/artifacts 的读取接口）。
- 逻辑层可以依赖：数据层的只读接口（读取 canonical 数据）+ 平台（事件/追溯上下文）。
- 数据层可以依赖：平台（存储/执行上下文），但不得依赖业务层/逻辑层（避免把业务决策写进采集）。
- 平台层可以被各层依赖，但平台层不得反向依赖业务层（防止框架被业务污染）。

##### 3.9.0.1 Tool Functions 的落地形式（推荐：Pydantic models + ToolRegistry + RunContext.call_tool）

为了避免“所有 I/O 必须通过 Tool Function”变成口号，建议在 Sailor 中把 ToolFunction 形式化为一套**最小可强制的约定**：

1) 输入/输出用 Pydantic model 表达（并可导出 JSON Schema）
- 每个工具函数定义 `InputModel` 与 `OutputModel`：这既是 Python 侧的强类型约束，也是 schemaVersion 的来源。
- schema 版本化策略：
  - `schema_version` 是字符串（例如 `v1`、`v1.1`）；
  - 小版本只允许增加可选字段（向后兼容）；
  - 破坏性变更必须 bump 大版本并同时保留旧版本一段时间。

2) ToolDescriptor + ToolRegistry（工具注册表）
- 每个 ToolFunction 都要附带一个 descriptor：
  - `tool_name` / `tool_version` / `schema_version`
  - `side_effect: bool`（是否会写 DB / 改配置）
  - `cost_hint`（可选：预计耗时/调用成本）
  - `cache_policy`（可选：能否缓存、TTL、key 组成）
- ToolRegistry 提供：`register()`、`list_tools()`、`get(tool_name)`。

3) 唯一执行入口：RunContext.call_tool(...)
- 所有 ToolFunction 必须通过 `RunContext.call_tool(tool_name, input)` 执行：
  - 自动记录 ToolCall（started/finished/status/error/output_ref/idempotency_key）；
  - 自动执行 PolicyGate（见 3.9.0.3）：side-effect 工具在 require_confirm 时只创建 pending_confirm，不执行 commit；
  - 自动注入 run_id=job_id 的追溯语义。

4) 与现有 `SnifferToolModule` 的关系（避免“再造一套工具体系”）
- 推荐定位：
  - **channel-level search** 变成 ToolFunctions（例如 `sniffer.search_channel:github` / `sniffer.search_channel:hn`）。
  - `SnifferToolModule` 只保留“并发 fan-out/fan-in + 去重聚合”的 orchestration 角色（它不再私自做 I/O 记录与 policy）。
- 这样 Sniffer 的并发能力与 ToolCall/PolicyGate 可以同时成立，且不会出现两套注册机制。

##### 3.9.0.2 Orchestrator 的粒度规则（何时走 job，何时允许同步）

为了避免把所有操作都 job 化导致复杂度和延迟上升，建议采用一个简单可执行的判断规则：

1) 必须走 job（JobRunner）的操作
- 任何外部 I/O（HTTP/CLI/LLM）
- 预计耗时 > 1s 的操作
- 需要并发/重试/partial success 语义的操作
- 需要可回放/可审计的操作（例如一键 refresh、批量分析、定时 digest）

2) 允许同步直做的操作（但要守住审计边界）
- 纯 read-only：GET 列表/详情/状态（例如读取 channel registry、读取 KB 列表）
- 轻量 DB 写：例如仅写一行关联表（save-to-kb），可以同步执行，但必须写 ProvenanceEvent（否则审计断链）

3) 双模式接口（推荐）
- 对于“轻量但可能批量化”的动作，建议同时提供：
  - 同步版本（UX 快）：立即返回
  - 异步版本（自动化友好）：创建 job 返回 job_id

##### 3.9.0.3 平台层对齐（Stage 4）与 SQLite 单机约束（必须显式写清）

你已经有 `UnifiedScheduler + PolicyGate + jobs/events/tool_calls` 的骨架，但要让它真正成为“三层分离的地基”，必须把平台行为写成硬规则：

1) PolicyGate 必须接入 ToolFunction 的唯一执行边界
- 推荐接入点：`RunContext.call_tool(...)`（不要依赖每个 handler 手工调用 check，否则一定会漏）。
- require_confirm 的语义：创建 `pending_confirms` 并终止该 step（或进入 waiting_confirm 状态）；业务层 Orchestrator 再提供确认入口。

2) Scheduler 只负责 dispatch，不负责 inline 执行长任务
- 推荐：scheduler tick 只负责“锁定 schedule -> 创建 job”，执行交给 worker/线程池消费；避免 tick 被长任务阻塞。
- 如果短期仍同步执行：至少把 job_runner.run 放进线程池，并确保 lock TTL 与最大执行时长匹配，避免重复派发窗口。

3) SQLite 作为 default 的单机限制与治理策略
- 并发上限：即使 WAL，SQLite 仍是单写者；因此需要明确写入治理：
  - 开启 WAL + busy_timeout
  - 将 ToolCalls/Events 写入尽量串行化（或降低多线程同时写库）
- 数据膨胀治理：
  - `raw_captures` 默认落文件 + retention（3.9.2.3 已约束）
  - `jobs/provenance_events/tool_calls` 必须有归档/清理策略（按时间窗口滚动）
  - 查询必须走索引与分页（按 run_id/job_id 是主路径）


#### 3.9.1 现有代码架构（与本章概念的对照）

从 3.9.0 的抽象视角看，当前 Sailor 处于“半拉齐”的状态：
- 一部分业务已经具备 **Orchestrator -> JobRunner -> JobHandler** 的形态（并且开始记录 jobs/events/tool_calls）；
- 另一部分业务仍是 legacy：Router/Service 同时扮演 Orchestrator + Handler + Tool/Engine，直接在请求线程里做 I/O 与写库。

这就是双轨制的本质：不是“有没有功能”，而是“有没有统一的执行契约与抽象边界”。

1) 当前已经具备的 V2 runner 骨架（对应 3.9.0 的 JobRunner/JobHandler）
- 运行数据与追溯表：`sailor/sailor/core/storage/db.py`（`jobs` / `provenance_events` / `tool_calls` / `raw_captures` / `schedules` / `pending_confirms` / `sniffer_run_log`）。
- 运行仓储：`sailor/sailor/core/storage/job_repository.py`。
- 执行器：`sailor/sailor/core/runner/job_runner.py`。
- 已有 JobHandlers（可视为“把能力绑定到 runner 的执行单元”）：
  - `sailor/sailor/core/runner/source_handler.py`（job_type=`source_run`）：数据层 ingestion 的执行单元。
  - `sailor/sailor/core/runner/sniffer_handler.py`（job_type=`sniffer_search`）：业务层 Sniffer 的执行单元（内部做并行 channel 搜索）。
- 调度器：`sailor/sailor/core/runner/scheduler.py`（DB-backed schedule + lock）。
- 策略与确认门（抽象已存在，但尚未全面接入 ToolFunctions 的执行边界）：`sailor/sailor/core/runner/policy.py`。

2) 当前已经接近“业务层 Orchestrator”形态的入口（但仍需继续拉齐）
- Sniffer：`POST /sniffer/search`（`backend/app/routers/sniffer.py`）基本符合“业务入口只创建 job -> 查询结果”的方向。
- Sources：`POST /sources/{id}/run`（`backend/app/routers/sources.py`）基本符合“业务入口只创建 job -> runner 执行 ingestion”的方向。

3) 当前仍是 legacy 的入口（它们是双轨制的主要来源）
- Feeds：`backend/app/routers/feeds.py` 直接做 feedparser + pipeline + repo 写库（相当于把 ToolFunction + JobHandler 写在 router 里）。
- Trending：`backend/app/routers/trending.py` 的 `/trending/pipeline` 在请求内同步执行 ingestion + tagging + report 生成：
  - ingestion：`sailor/sailor/core/services/ingestion.py`
  - digest/report：`sailor/sailor/core/services/trending.py`
  - 这等于把 **Orchestrator + JobHandler + Engine** 混在一个端点里，并绕开 jobs/events/tool_calls。
- Tasks：`backend/app/routers/tasks.py` 是遗留接口，与当前模型/容器不对齐，属于应当下线/重写的路径。

4) 用 3.9.0 的抽象解决双轨制：我们要收敛到“唯一形态”
- 业务层入口（routers/pages）一律当作 Orchestrator：只负责创建 job（或 workflow job）、返回 `job_id`、提供 runs 列表与详情；不直接做采集与写库。
- 数据层 I/O 一律封装为 ToolFunctions（例如 `sources.run(...)`、`sniffer.search_channel(...)`、`llm.tag(...)`），并在 ToolCall 中可追溯。
- 逻辑层计算一律封装为 Engine Classes（例如 digest、评分、偏好更新、晋升建议），产物必须可重建。
- JobHandlers 负责把 ToolFunctions/Engines 接到 JobRunner：统一状态、错误语义、partial success、以及 events/tool_calls。

只要把 Trending/Feeds 的入口改造成这种形态，双轨制才会从结构上消失；否则修 bug 会永远在两套语义之间反复打补丁。

#### 3.9.2 数据层引擎：RSS 引擎（CRUD / 存储 / 抽象 / 自动化）

> 定位：RSS 引擎属于“数据层系统”（对齐 3.9 的三层分工），职责是**把外部世界的 feeds 变成稳定的 canonical 数据**，并提供可治理、可观测、可回放的契约。
>
> 非职责：RSS 引擎**不做 Trending/推荐/晋升决策**；它只输出数据与可解释的元信息（例如：错误率、重复率、更新频率、来源覆盖）。

这一节写的是“数据层 RSS 引擎需要具备哪些功能特性与数据设计”，以便后续把 legacy `/feeds` 收敛进 V2 runner，并让 agent/前端共享一套稳定接口。

##### 3.9.2.0 在 3.9.0 抽象中的定位：Tool Functions + SourceRunHandler

用 3.9.0 的语言，这个数据层 RSS 引擎需要明确对应两类抽象：

1) Tool Functions（数据层能力的对外接口）
- RSS 引擎对外暴露的能力应以 `sources.*`（feed-family）形式出现（见 3.9.2.6）。
- 这些 `sources.*` 都是 Tool Functions：可版本化、可审计、可被 PolicyGate 管理（尤其是 side-effect 类型的 `upsert/delete/run`）。

2) JobHandler（把 Tool Functions 放进 JobRunner 的执行单元）
- 运行 RSS ingestion 时，不应由前端/agent 直接同步调用“抓取+入库逻辑”，而应创建一个 job 并由 JobRunner 执行。
- 当前代码已经有数据层 ingestion 的 JobHandler：`sailor/sailor/core/runner/source_handler.py`（job_type=`source_run`）。
- 因此 RSS 引擎的执行语义应统一收敛到：
  - 业务层 Orchestrator 创建 `job_type=source_run`（输入包含 `source_id`）；
  - `SourceRunHandler` 执行 ingestion，并通过 ToolCalls/Events/RunLog 提供可追溯与可观测。

（补充背景可参考：`docs/sailor-v2-sources.md` 第 2 章。）

##### 3.9.2.1 数据层的统一抽象：SourceRecord 是 RSS 引擎的入口对象

当前代码里已有两套“源头目录”：

- legacy：`sailor/sailor/core/storage/db.py` 的 `rss_feeds`（对应 `sailor/sailor/backend/app/routers/feeds.py`）。
- v2：`sailor/sailor/core/storage/db.py` 的 `source_registry`（对应 `sailor/sailor/backend/app/routers/sources.py` + `source_run` JobRunner）。

V2 的 RSS 引擎建议以 **`source_registry` 为唯一真相（single source of truth）**，把 RSS/Atom/JSONFeed 都建模为统一的 `SourceRecord`：

- `source_id`：必须**确定性**（可由 `endpoint(xml_url)` 归一化后 hash 得到），以保证幂等 upsert。
- `source_type`：至少包含 `rss` / `atom` / `jsonfeed`（三者都属于 feed-family）。
- `endpoint`：feed URL（RSS/Atom/JSONFeed 的入口）。
- `config_json`：放 feed-family 的扩展字段（避免每次扩展都改 schema），例如：
  - `html_url`（站点主页）
  - `etag` / `last_modified`（HTTP 条件请求缓存）
  - `user_agent` / `headers`（必要时）
  - `parse_hints`（某些站点需要的解析提示，如正文字段优先级）
  - `groups` / `tags`：仅用于“源头目录”的用户自定义分组/标签（catalog annotations），不等同于资源标签体系；不应作为推荐/晋升的决策输入（见 3.9.2.5 归类与 profile）。

> 备注：现有抓取路径往往是“直接拉取 + 解析”，尚未把 `etag/last_modified` 作为数据层能力持久化与复用；因此在 V2 设计中应把它们视为标准字段补齐（否则会造成不必要的带宽与重复入库）。

legacy `rss_feeds` 的定位建议降级为：

- 兼容视图（UI/旧接口的平滑迁移），或一次性迁移后冻结。
- 不再承载“执行语义”（run 应迁移到 runner）。

##### 3.9.2.2 CRUD：源头目录（Feed Catalog）要支持的最小操作集

RSS 引擎的数据层 CRUD（以 `SourceRecord` 为对象）需要覆盖两类调用方：

1) **Agent tools func**：需要 idempotent、可组合、可审计。
2) **前端页面**：需要列表/详情/状态/资源列表的稳定字段。

建议把数据层能力显式拆成两类 Tool Functions（这能直接服务自动化与 agent）：

1) Catalog Tool Functions（目录层）
- 只负责“源头怎么存、如何管理”。
- 特征：对外暴露稳定 schema；幂等写入；可审计；多数属于 side-effect（写入 source_registry）。

2) Execution Tool Functions（执行层）
- 只负责“怎么拉取、怎么入库、如何记账”。
- 特征：必须返回 `job_id` 并可追溯 tool_calls/events；必须有清晰的失败语义（transient/permanent/partial）。

目录层最小操作（功能设计，不限定 HTTP 还是内部工具）：

- `sources.list(source_type_in=[rss, atom, jsonfeed])`：列出 feed-family sources。
- `sources.get(source_id)`：返回源头的全量配置（含 config_json）。
- `sources.upsert(source_id?, source_type, name, endpoint, config, enabled, schedule_minutes)`：幂等写入；支持 agent 重试。
- `sources.toggle(source_id, enabled)`：启停。
- `sources.delete(source_id)`：删除目录与索引（资源本体是否删除应谨慎，默认不删 resources）。
- `sources.import_opml(opml_text)`：批量导入（OPML 是 feed-family 的核心入口）。

CRUD 的数据层要求（避免“写脏数据”）：

- `endpoint` 必须 canonicalize（去掉尾部 `/`、去掉无意义 query）；否则同一 feed 会被重复创建。
- `source_id` 的生成规则必须稳定且可复用（用于 idempotency_key）。

##### 3.9.2.3 读取出来的数据怎么存：RawCapture -> Entry Index -> Resource

RSS 引擎的数据落库建议遵循 3 层结构（与 3.8 Stage0 的 provenance/tool_calls/raw_captures 对齐）：

1) **RawCapture（不可变）**：保存“这次抓到了什么”（可回放/可审计）。

- 表：`raw_captures`（已存在）。
- 内容：建议至少保存 feed 的原始 XML/JSON（或 gzip 后的内容引用）。
- 关联：每次 fetch 必须有 `tool_call_id`，并写 `tool_calls.output_ref` 指向 capture。

> 现状缺口：虽然表已存在，但当前代码并没有统一的 `raw_captures` 写入封装（缺 repository/RunContext helper）；如果希望 agent 可审计与可回放，需在数据层补齐 `save_raw_capture(...)` 并明确 `content_ref` 的存储策略（db/blob/file）。

> 非功能性约束（建议在数据层就写清楚，否则后期会拖垮本地库）：
> - RawCapture 默认应有保留策略：按时间（例如保留 N 天）、按每源保留最近 N 次、或按总大小滚动。
> - 默认可只保留 headers + 解析后的 entries 摘要；完整 payload（原始 XML/JSON）作为可选项。
> - `content_ref` 建议优先指向文件系统（或对象存储）；SQLite 只存引用 + checksum，避免 DB 膨胀。

2) **Entry Index（幂等索引）**：保存“这个源看到了哪些 item，以及它们映射到哪个 canonical 资源”。

- 表：`source_item_index`（已存在，PK: `(source_id, item_key)`）。
- `item_key`：建议使用“版本化幂等键”（例如 `v1:` 前缀）；优先使用 feed 的 `entry_id/guid`，否则退化为稳定 hash（推荐 `original_url + title + published_at` 的组合；不得仅依赖 canonical_url，因为 canonicalize 规则变化会破坏幂等）。
- 约束：`source_item_index.source_id` 应来自 `source_registry.source_id`（否则未来启用 SQLite FK 时会产生冲突）；legacy `/feeds` 若仍写 index，需要通过 feed->source 映射/迁移消除双轨。
- 语义：
  - 同一源重复抓到同一 item 时，只更新 `last_seen_at`（幂等）。
  - 同一资源被多个源抓到，会出现多行 index 指向同一个 `resource_id`（这是“跨源覆盖度/趋势强度”的关键基础信号）。

3) **Resource（canonical）**：保存“规范化后的可消费资源”。

- 表：`resources`（已存在，`canonical_url` 唯一）。
- 来源字段：
  - `resource_id` 必须确定性（当前 pipeline 已按 canonical_url 生成 `res_{sha1[:12]}`，可复用）。
  - `provenance_json` 必须至少包含：`source_id`、`entry_native_id(item_key)`、`captured_at`、`adapter_version`。

重要注意点（正确性/可追溯）：

- **published_at 必须在 collector 边界被解析为 datetime|None**（否则会触发 `.isoformat()` 崩溃，3.9.5 已有明确 P0）。
- `resources` 的 upsert 不应丢失“多源看见同一资源”的信息：
  - 资源表可以只记录 first_seen 的 provenance；
  - 多源关系以 `source_item_index` 为准（逻辑层做 join 统计）。

##### 3.9.2.4 执行与可观测：RunLog + ToolCalls + 失败语义

RSS 引擎的数据层必须对齐 V2 runner 的执行语义（3.9.1）：

- run_id 契约（必须统一，否则可观测会断链）：
  - `job_id` 是审计与追溯的主键：`provenance_events` / `tool_calls` / `raw_captures` 均以 `job_id` 作为 run_id。
  - `source_run_log.run_id` 是业务友好的运行历史 ID；但必须能反查到 `job_id`（例如在 `metadata_json` 写入 job_id，或提供显式字段）。

- 每次 run 必须产生：
  - `jobs` 生命周期（queued/running/succeeded/failed）
  - `provenance_events`（Started/Finished/Failed + PolicyDecision 可选）
  - `tool_calls`（至少 1 个 rss_fetch；必要时记录 parse/normalize 的摘要）

对于 feed-family sources，建议用 `source_run` 的既有 run log 语义（`source_run_log`）作为“业务侧可读的运行历史”，并在 `metadata_json` 里写入抓取统计：

- `http_status` / `etag` / `last_modified`
- `bytes`（原始响应大小）
- `entry_count`（解析到的条目数）
- `new_item_count`（首次见到的 item 数）
- `duplicate_ratio`（重复率）
- `parse_warning/bozo`（feedparser 警告摘要）

失败语义建议：

- transient：网络超时、DNS、临时 5xx、rate limit
- permanent：feed URL 404/403、长期解析失败（bozo 且无 entries）、配置缺失
- partial：单次 run 中多个 feeds 批量跑时，部分成功部分失败（用于批量执行工具）

##### 3.9.2.5 “不同源头”的归类（family classification）：把 ingestion method 归到可自动化的 function families

这里的“归类”指的是：**按接入方式与数据契约把源头归类**，从而可以抽象出可复用、可自动化的 functions（tools）。

建议在数据层把源头按 2 个维度聚类：

1) **接入方式聚类（决定 collector/解析/幂等策略）**

- feed-family：`rss` / `atom` / `jsonfeed`
- api-family：`api_json` / `api_xml` / `academic_api`
- file-family：`manual_file` / `jsonl` / `opml`
- page-family（最后手段）：`web_page` / `site_map`

这会自然导出一组“抽象工具函数族”（agent 可用）：

- Catalog：`sources.list` / `sources.upsert` / `sources.toggle` / `sources.delete` / `sources.import_opml`
- Execution：`sources.run_now(source_id)` / `sources.run_by_type(source_type)`
- Health：`sources.validate(source_id)`（fetch+parse 但不入库或只 dry-run）/ `sources.status_summary()`

2) **内容/主题画像（只产出元信息，不做业务决策）**

数据层可产出“可解释的 profile”，供逻辑层（3.9.3）与业务层（3.9.4）的系统消费：

- `items_per_day`（更新频率）
- `error_rate`（稳定性）
- `duplicate_ratio`（噪声）
- `domain`（按 endpoint/url 归一化）

可选（派生信号，默认不属于 RSS 引擎职责，但可以作为缓存）：
- `topic_histogram`：来自逻辑层“资源智能系统”的统计投影，必须带版本并可重建；不要把它当作 RSS ingestion 的硬契约输出。

存储方式建议（二选一）：

- 方案 A：新建 `source_profiles` / `source_stats_daily` 表（结构化、可查询）。
- 方案 B：把 profile 写进 `source_registry.config_json` 的 `profile` 字段（最快，但查询弱）。

##### 3.9.2.6 前后端渲染与 agent 调用的接口清单（功能视角）

为了让 UI 与 agent 共享同一套数据层能力，RSS 引擎至少应提供以下接口（HTTP 或 tools func 皆可）。

接口命名建议：以 `sources.*` 作为 canonical namespace（通过 `source_type in {rss,atom,jsonfeed}` 过滤 feed-family）。如需要，也可以提供 `rss.*` 作为薄 alias（只做预过滤，不引入第二套语义）。

- `sources.list(source_type_in=[rss, atom, jsonfeed])`：列出 feeds（含 enabled、schedule、last_run/last_error、错误计数、健康状态）
- `sources.upsert(...)`：新增/更新 feed（幂等）
- `sources.toggle(...)`：启用/禁用
- `sources.delete(...)`
- `sources.import_opml(...)`：批量导入
- `sources.run(source_id, mode=commit|dry_run)`：运行一次抓取入库（必须返回 `job_id`；调试/追溯以 job_id 查看 tool_calls/events；如需 domain run_id 可作为附加字段返回）
- `sources.runs(source_id)`：运行历史（业务视角）
- `sources.resources(source_id)`：该源产生/命中的资源列表（基于 `source_item_index` join `resources`）
- `sources.profile(source_id|group)`：返回统计 profile（用于后续逻辑层调度建议/降噪/策略；避免掺入强业务语义）

这一组接口的核心是：**CRUD 管源头、Run 产资源、Index 保幂等、Profile 供自动化。**

#### 3.9.3 逻辑层：引擎分组与能力边界（功能视角，先不谈实现）

本节聚焦逻辑层：用 3.9.0 的语言，逻辑层应该由一组 **Engine Classes** 构成。它们是“headless engines”——不关心 UI，也不关心外部采集；只消费数据层 canonical 数据与可追溯上下文，产出可复用的信号与派生产物。

逻辑层的共同特性（功能约束）：
- 输入：来自数据层的 canonical 数据（resources/source_item_index/tags/kb_items/user_actions/analyses 等）+ 运行上下文（jobs/events/tool_calls/schedules）。
- 输出：
  - 可渲染的状态视图/队列（view-model），例如 inbox/review queue；
  - 可追溯的派生信号/建议（artifacts），例如 tags/scores/recommendations/promotion proposals。
- 依赖限制：
  - 不直接做外部采集（HTTP/CLI/LLM 必须通过 Tool Functions 发生并可记录 ToolCall）；
  - 不把采集与业务入口混在一处（业务层 Orchestrator 只编排 job）。

在系统落地时，Engine 需要对应的 JobHandler 才能进入自动化（jobs/events/tool_calls）。因此每个 Engine 都应有一个“可 runner 化”的 job_type（或多个）。

##### 3.9.3.0 防止过度设计：引擎成熟度（maturity）与落地触发条件

为了避免逻辑层过早抽象导致“成本高、建错、难回收”，建议把 Engine 按成熟度分级：

- Phase 1（Required）：先落地 `ResourceIntelligenceEngine`
  - 原因：Trending/KB/QA 都依赖它的结构化信号；这是“信号工厂”，投入产出比最高。
  - 验收：对一批资源稳定产出 tags/analysis/scores/preference，并且可追溯 ToolCalls。

- Phase 2（Deferred）：`ReviewWorkflowEngine` 与 `PromotionEngine`
  - 触发条件：出现明确的用户流程/页面或指标需求（例如：review queue 页面、晋升建议的确认闭环）。
  - 在触发前：允许只保留“最小影子形态”（例如 read-only 报表/列表），不要提前引入完整的状态机与调度。


1) ReviewWorkflowEngine（资源工作流与分拣引擎，Deferred）
- 角色定位：这是“渲染与调度之间的桥”，把新入库资源组织成可处理的队列与任务。
- 主要能力（功能）：
  - 资源状态投影：把资源按生命周期投影成可渲染状态（inbox、已收藏、已忽略/已归档等）。
  - 审阅队列与任务：生成 review queue（快速扫读/深读/决定是否入 KB），并能表达优先级与原因。
  - 动作编排：把用户动作（加入 KB、忽略、标注、建议订阅）作为“工作流动作”，统一记录与回放。
  - 调度友好：能够表达“什么时候该做什么”（例如每天整理 inbox、每周回顾某 KB）。
 - 典型输出（面向业务层）：
  - `InboxView` / `ReviewQueue`（可分页、可筛选、可解释的队列）
  - `ReviewTask`（带优先级与理由）
 - 与其他 Engine 的耦合：
  - 依赖 `ResourceIntelligenceEngine` 的信号（分数/标签/近重复）来排序与降噪；
  - 不依赖业务层页面（Trending/KB/QA 只是消费它的 view-model）。
- runner 化建议（语义，不是实现）：对应一个 read-only job，例如 `job_type=workflow_refresh`（产出队列快照）。

> 备注：如果当前还没有明确的 review 页面/流程，这个 Engine 应保持 Deferred，不进入近期里程碑。

2) ResourceIntelligenceEngine（资源智能引擎：Tagging + Analysis + Scoring + Preference，Required）
- 你提出可以合并的部分就在这里：标签、偏好、分析、评分本质上都是“对资源的理解与量化”。
- 主要能力（功能）：
  - 标签体系与偏好画像：维护标签本体与偏好权重；把用户行为转为偏好更新。
  - 内容理解与结构化：摘要、要点、主题/实体、可检索字段。
  - 质量与价值信号：多维评分与推荐理由（用于排序、筛选、解释）。
  - 重复/噪声信号：输出近重复/转载倾向、低价值判定等（供工作流与业务层降噪）。
 - 重要边界：
  - 这是“可复用信号工厂”，它的输出应被 Trending/KB/QA 复用，而不是每个业务系统各自做一套评分逻辑。
  - LLM 调用（如自动打标、深度分析）必须通过 Tool Functions 发生，并以 ToolCall 记录（否则无法治理成本与回放）。
 - runner 化建议：对应一个或多个 batch job，例如：
  - `job_type=resource_intelligence_run`（对一批 resources 产出 tags/analyses/scores）
  - `job_type=preference_update`（把 user_actions 汇总更新偏好画像）

3) PromotionEngine（渠道/订阅策略引擎：Lifecycle & Promotion，Deferred）
- 角色定位：这是逻辑层里相对独立的一块，因为它的主对象是“渠道/来源”，而不是单条资源。
- 主要能力（功能）：
  - 晋升建议：把嗅探命中质量、重复率、订阅产出稳定性、用户收藏率等信号转成“建议晋升/建议降频/建议暂停”的 proposal。
  - 生命周期状态视图：candidate/approved/subscribed/paused/retired 等状态的投影与变化原因。
  - 策略解释：任何晋升/降权建议都要能解释（基于哪些证据与指标）。
 - 与业务层的耦合：
  - 业务层负责把 proposal 呈现给用户并做确认（commit gating）；
  - 逻辑层只产出建议与理由，默认不直接写订阅配置。
- runner 化建议：对应一个 proposal job，例如 `job_type=promotion_proposal_run`，输出一批“待确认动作”（写入 pending_confirms）。

> 备注：PromotionEngine 的第一阶段建议只产出 proposal（可解释、可回放），不进入自动 commit；确认闭环成熟后再逐步放开。

小结：逻辑层收敛后，你会得到“少而强”的 3 个系统：工作流（队列/调度桥）、资源智能（信号工厂）、渠道策略（来源治理）。它们共同为业务层提供稳定的能力地基。

#### 3.9.4 业务层：用户系统（功能视角，先不谈实现）

用 3.9.0 的语言，业务层不应只是“页面集合”，而应显式收敛为一组 **Orchestrators**：
- 它们负责把用户意图翻译为 job（或 job DAG/workflow），并把结果组织成 UI 视图；
- 它们不直接做外部采集，也不直接跑 Engine 的计算细节；
- 它们的核心产物是：`job_id`（可追溯）+ 可读的 view-model（可渲染）+ 可确认的 proposals（可治理）。

业务层的核心系统是 3 个（Trending/KB/QA）。但为了让“双轨制”真正收敛，必须以 Sniffer 的形态作为业务层准则：任何业务入口都要像 Sniffer 一样“Orchestrator -> job_id -> runs/detail -> events/tool_calls”。

0) SnifferOrchestrator（业务层准则模板）
- 目标：把“资源嗅探”做成业务层的标准模板，让其他业务系统照着对齐。
- 准则要点：
  - 涉及外部 I/O 或耗时 > 1s 的入口只创建 job 并返回 `job_id`；不在请求线程里做复杂 I/O（见 3.9.0.2）。
  - 纯 read-only 与轻量 DB 写允许同步，但必须写入必要的 ProvenanceEvent，避免出现“同步旁路导致审计断链”。
  - 运行历史可查（runs）；运行详情可查（events/tool_calls）；partial success 可解释。
  - 结果动作（deep-analyze/save-to-kb/convert-source）必须遵循同一套 ToolFunction/PolicyGate/Confirm 语义：
    - LLM/外部 I/O 动作走 job；
    - 副作用动作先 proposal，commit 走确认门；
    - 轻量动作即便同步也要写事件。

1) TrendingOrchestrator（Trending 与 Digest 业务系统）
- 目标：把资源流组织成可阅读、可回顾、可对比的趋势信息流。
 - 核心边界：Trending 不负责采集（不直接跑 RSS/非 RSS）；它只消费已入库资源 + 逻辑层信号（标签/分数/去重/偏好）。
 - 业务层编排语义：
  - “生成 digest”应对应一个逻辑层 Engine job（read-only 或可重建 artifact）。
  - “一键刷新”不是在同一个请求里同步做 ingestion+tagging+digest，而是 orchestrator 编排多个 job（可回放、可 backfill）。
- 主要能力（功能）：
  - 多时间窗 digest：24h/7d/30d 的新增与热点主题。
  - 聚合视图：按标签/来源/KB 分组，支持 topN 与环比变化。
  - 排序与解释：可解释的排序（为什么推荐/为什么在前）。
  - 行为闭环：一键加入 KB、忽略、标注、以及“建议订阅来源”（走 proposal）。

2) KnowledgeBaseOrchestrator（知识库业务系统）
- 目标：把资源库中的“有用子集”固化为长期资产，并提供 KB 维度的洞察。
- 核心边界：KB 是“策展层”，它不应承担采集逻辑；它消费资源与逻辑层信号，并产出 KB 画像与报告。
- 主要能力（功能）：
  - KB 边界管理：KB 的定义、描述与成员管理（收藏/移除/批量）。
  - KB 画像：主题/标签/来源/质量分布（以及变化）。
  - KB 报告：周期性总结（聚类/关联/总结）与版本化历史。
  - 反哺偏好：KB 层面的策展动作回流到偏好与推荐。

3) QAOrchestrator（查询与问答业务系统）
- 目标：把“访问资源库/知识库”从翻页筛选升级为自然语言入口，并做到可追溯。
- 核心边界：QA 不负责采集；它消费数据层（可查询的数据）+ 逻辑层（可复用的标签/评分/画像），并输出带证据的回答。
- 主要能力（功能）：
  - 面向数据的问答：筛选/聚合/对比（可解释的 QueryPlan）。
  - 面向内容的问答：对检索到的资源集合做摘要/对比/结论提炼。
  - 证据链输出：Answer 必须带 citations（资源链接/资源 ID/条件），可 drill-down。
  - 行为闭环：把“问答结果集”转为可操作对象（例如保存为一个 KB 清单/生成一份 digest/提出订阅建议）。

小结：业务层是三个 Orchestrators（Trending/KB/QA）。它们的共同要求是：
- “不要把采集塞进业务按钮”；
- 所有计算与 I/O 都通过 JobRunner 执行（Tool Functions + Engine Classes + JobHandlers），业务层只编排与渲染；
- 用户行为必须回流成逻辑层可消费的信号（偏好与策略），而不是散落在各页的私有逻辑。

#### 3.9.5 优先级与实施顺序（以 Sniffer 作为业务层基准，先修数据层与逻辑层）

这一节的目标不是“列出所有问题”，而是把问题改写成一个可执行的实现顺序。

排序原则（结合当前代码框架）：
- Sniffer 已经把“业务层如何接入 runner”跑通了一半：`POST /sniffer/search` 触发 job、可列 run 历史、可追溯 tool_calls/events（尽管目前仍有 run_id/resource_id 的已知缺口）。
- 因此我们把 Sniffer 当作业务层基准：其他业务（尤其 Trending）要逐步对齐到同一套 runner 语义与验收方式。
- 同时优先修“会写错数据/导致引用错位”的契约问题（这是数据层/逻辑层的根），再修 runner 语义一致性（自动化可追溯），最后才是体验/性能。

业务层基准（Sniffer Checklist，用于验收其他系统是否“像 Sniffer 一样可自动化/可观测”）：
- 一个业务入口触发一次运行时，必须：创建 `jobs` 记录并返回 `job_id`；支持 run 列表与 run 详情；支持查看 events/tool_calls。
- 运行结果必须可解释：partial success 需要明确哪些子任务成功/失败、失败原因是什么。
- 可回放/可审计：至少能从 job_id 追溯到输入（query/budget）、执行事件、工具调用与输出摘要。
- 最小回归测试（以 API 为准，不依赖 UI）：
  - 触发 run -> 轮询 job 状态 -> 读取 run detail -> 读取 events/tool_calls，且 run_id 语义一致。

下面按优先级给出实现顺序（每条都标注层次与锚点）：

实现顺序与“类归属规则”（3.9.0）对齐：
- S0：冻结 canonical 数据契约（数据层职责）并由平台层强制执行（避免脏数据污染全局）。
- S1：统一追溯/可观测语义（平台层职责）并在业务层 runs API 中正确呈现。
- S2：把 Trending 入口收敛为业务层 Orchestrator（只编排 jobs，不做采集/计算细节）。
- S3：把逻辑层能力落实为 Engine Classes + Logic JobHandlers（业务层只消费 artifacts/view-model）。
- S4：平台层加固（scheduler/policy/sqlite/logging）。
- S5：最小回归门槛（以 Sniffer 作为业务层准则）。

1) 优先级 S0：冻结 canonical 数据契约（全局正确性）——否则后面所有逻辑都会建立在脏数据上
- 层次：数据层（定义 canonical contract）+ 平台层（runner/存储强制执行）。逻辑层/业务层只消费该契约，不在自身类里“修补脏数据”。
- 必修项：
  - `Resource` 身份一致：任何入口（pipeline / sniffer / sources / feeds）对同一 canonical_url 必须得到同一 resource_id。
    - 现状冲突锚点：`sailor/sailor/backend/app/routers/sniffer.py`（随机 resource_id） vs `sailor/sailor/core/pipeline/stages.py`（确定性 res_xxx）+ `sailor/sailor/core/storage/repositories.py`（upsert 不更新 resource_id）。
  - `RawEntry.published_at` 类型一致：必须是 datetime|None，禁止字符串进入 upsert。
    - 高风险锚点：`sailor/sailor/core/sources/collectors.py`（atom published_at 透传字符串）；legacy feeds 也存在同类问题。
  - OPML 解析契约一致：统一使用 `parse_opml`，避免 import/调用分叉。
    - 锚点：`sailor/sailor/core/collector/opml_parser.py` 与调用方。
- Done（验收，参照 Sniffer）：
  - 任意入口 upsert 后，能稳定返回并引用同一个 resource_id；
  - published_at 不再出现运行时 `.isoformat()` 崩溃；
  - OPML ingestion 不再因函数名错误直接失败。

2) 优先级 S1：统一 runner 的 run_id 语义（可追溯性修复）——让“查看运行详情”真的能用
- 层次：平台层（JobRunner/Provenance/ToolCalls）+ 业务层（runs API）。
- 必修项：
  - 选定唯一 run_id 主键（建议 `job_id`），并强制：events/tool_calls/raw_captures 都在同一命名空间。
  - run 详情查询必须用同一 run_id：
    - `sniffer_run_log` 可以保留 domain run_id，但必须能映射回 job_id；run detail 的 events 查询要用 job_id。
  - handler 失败信息必须真实落库：不要依赖 job.error_message 的后写；handler 捕获异常时直接记录 exc。
- 现状冲突锚点：
  - `sailor/sailor/core/runner/job_runner.py`（run_id=job_id）
  - `sailor/sailor/core/runner/sniffer_handler.py`（另生成 sniffer_run_id）
  - `sailor/sailor/backend/app/routers/sniffer.py`（部分事件用 sniff_result_id 当 run_id）
  - `sailor/sailor/core/runner/source_handler.py`（失败写 run_log error 为空）
- Done（验收，参照 Sniffer）：
  - `GET /sniffer/runs/{id}` 能稳定返回该次运行的 events/tool_calls（不再空）；
  - sources 的 run 失败能看到明确 error_message。

3) 优先级 S2：把 Trending 从“混合 pipeline”拆成纯业务层系统（对齐 Sniffer 模式）
- 层次：业务层（Trending）+ 逻辑层（资源智能信号复用）。
- 问题根因：当前 `/trending/pipeline` 把采集（数据层）+ 打标（逻辑层）+ 生成 Trending 视图（业务层）混成一个 API。
  - 锚点：`sailor/sailor/backend/app/routers/trending.py` + `sailor/sailor/core/services/ingestion.py` + `sailor/sailor/core/services/trending.py`。
- 目标（以 Sniffer 业务层基准）：
  - Trending 作为业务层入口时，只消费已入库 resources + 逻辑层信号（tags/scores/preferences），不直接负责采集。
  - 如需“一键 pipeline”，应表现为“业务层编排（orchestrate）多个 job”，而不是把采集逻辑塞进 TrendingService。
  - Trending 的运行也应具备 Sniffer Checklist：返回 job_id、可列 runs、可查 events/tool_calls。

 - 推荐迁移路径（避免断裂，先对齐抽象，再拆代码）：
  - Step A（先做 read-only digest）：引入 `DigestEngine`（逻辑层 Engine），以“只读 canonical 数据”的方式生成 digest artifact（不触发采集）。
  - Step B（再做业务编排）：`TrendingOrchestrator` 编排 job：ingestion job（数据层）-> intelligence job（逻辑层）-> digest job（逻辑层）。
  - Step C（灰度/对比）：新旧 digest 并行计算（shadow），对比差异通过后切换读者；并支持 backfill（重算历史窗口）。
- Done（验收）：
  - Trending 生成可以独立运行（在已有资源上）；
  - 一键 pipeline 只是编排入口（可观测、可回放），且不再绕过 runner。

4) 优先级 S3：逻辑层三大系统补齐 runner 化边界（让业务层只“消费能力”）
- 层次：逻辑层（工作流/资源智能/渠道策略）。
- 目标：把 3.9.3 的逻辑层系统变成“可被业务层调用与复用”的引擎能力。
 - 优先顺序建议（对齐 3.9.3 maturity）：
  - Phase 1：只落地资源智能系统（`ResourceIntelligenceEngine`）的信号稳定输出（tags/analysis/scoring/preference），因为 Trending/KB/QA 都依赖它。
  - Phase 2：当出现明确 review 页面/流程时，再落地工作流系统（review queue）。
  - Phase 3：当出现明确晋升确认闭环时，再落地渠道策略系统（promotion proposals + confirm gate）。

5) 优先级 S4：自动化加固（scheduler/policy/sqlite/logging）——把系统从“能跑”变成“能长期跑”
- 层次：平台横切。
- 必修项：
  - scheduler 不应 inline 执行长任务（避免 tick 阻塞与锁 TTL 风险）。锚点：`sailor/sailor/core/runner/scheduler.py`。
  - PolicyGate 必须接入 ToolFunction 的唯一执行边界（推荐 `RunContext.call_tool`），否则 pending_confirms 形同虚设。锚点：`sailor/sailor/core/runner/policy.py`。
  - SQLite 并发策略必须明确（WAL/busy_timeout + 单写者治理），否则 scheduler + API + 多线程 tool_calls 易 locked。锚点：`sailor/sailor/core/storage/*`。
  - jobs/events/tool_calls/raw_captures 必须有膨胀治理：raw_captures 落文件 + retention；events/tool_calls 按时间窗口归档/清理；查询按 job_id 索引分页。
  - 日志 handler 安装应收敛为 startup hook，避免 import-time side effects。锚点：`sailor/sailor/backend/app/routers/logs.py` + `sailor/sailor/backend/app/main.py`。

6) 优先级 S5：用 Sniffer 作为回归基准补齐测试与验收脚本
- 层次：工程质量（但直接决定自动化的稳定性）。
- 目标：让“runner 对齐”有可自动验证的门槛，而不是靠手点。
- 建议最小集合：
  - Sniffer：search -> run detail -> events/tool_calls 的一致性测试；partial success 不崩。
  - Sources：source_run 失败能落 error_message；成功能落 fetched/processed。
  - Trending：生成 job 返回 job_id，run detail 可追溯，且不直接触发采集。

> 备注：当前仓库缺少标准化测试套件（未见 pytest/tests），存在 `utest/` 目录的脚本式冒烟验证。建议先用最小 smoke 脚本作为门槛，再逐步迁移到标准测试框架。

本节小结：实现顺序应围绕“先稳契约，再稳追溯，再收敛 Trending”，最后才是调度加固与测试完善；否则每推进一个新功能都会在 run_id/resource_id/published_at 上重复踩坑。

## 4. Follow / Digest：从 News（嗅探）到 Follow（长期关注）的 Trending 业务形态

这一章用“模块解耦”的方式，把你想做的 Trending（日报/周报/专题）讲清楚。

核心区别是主动性：

- 资源嗅探（Sniffer）更像 `news / search`：用户带着问题来“拉取”，一次性探索与发现。
- Trending（你描述的 Follow/Digest）更像 `follow / digest`：系统带着用户偏好去“推送”，持续关注与定期产出。

> 注：这里的 Trending 不再等价于“热度变化/榜单涨跌”。它更像“基于偏好的主动推荐（但可解释、可治理）”。

### 4.1 你要的 Follow/Digest，其实有三类输入信号（3 种不同源头形态）

你的 Trending 想做的是“融合多个榜单 + 固定长期渠道 + prompt 驱动检索”，它天然包含三类输入：

1) 长期渠道更新（Fixed channels）
- 典型：RSS feeds、Unified Sources（长期稳定、持续产出最新条目）。
- 产出形态：连续的“最新消息流”（new items）。

2) 榜单复制（Board copy）
- 典型：GitHub Trending、Hugging Face 的 models/spaces/papers 榜单等。
- 产出形态：周期性的“榜单快照”（snapshot list）。你不关心涨跌，只关心“这一期榜单长什么样”。

3) Prompt 驱动的研究检索（Agent research）
- 典型：用户预先写好 prompt/topic spec，agent 自行去 arXiv/OpenReview 检索相关论文并做 daily papers。
- 产出形态：周期性的“主题检索快照 + 精选编排”（topic snapshot -> curated issue）。

这三类输入的差别在于：更新方式（持续流 vs 快照 vs 主题检索）、可解释性（来自哪个 board/query）、以及质量控制（噪声/重复/相关性）。

### 4.2 成熟系统的关键：把 Trending/Digest 做成“产物（Issue）驱动”

日报/周报/专题不应该是一次性拼装出来的列表，而应该落到一个一等公民的产物：

- Issue（一份日报/周报/专题） = “时间窗 + 偏好配置 + 多源候选池融合 + 模板编排”的结果。

Follow 页/Trending 页只是 Issue 的不同视图：

- 最新一期（latest）
- 历史回放（history）
- 专题集合（topics）

这样做“成熟”的收益是：可回放、可审计、可解释、可迭代模板，并且天然支持“固定长期关注”。

### 4.3 用三层架构把你的想法拆清楚（数据层/逻辑层/业务层）

> 总原则：数据层做获取与规范化；逻辑层产出信号；业务层做编排与交付。

#### 4.3.1 数据层（Data Layer）：把外部世界变成可用候选（不做推荐决策）

数据层负责“获取 + 规范化 + 去重 + 存证”，产出候选 items 与来源证据：

- Channel Engine（长期渠道引擎）：读取长期渠道更新，产出 new items。
- Board Engine（榜单引擎）：抓取各平台榜单，产出 board snapshots。
- Research Engine（研究检索引擎）：按用户预设 prompt/topic spec 去学术源检索，产出 topic snapshots。

关键解耦点：数据层只负责“拿到数据并把它变成 canonical 形态”，不决定“哪些应该进日报/周报/专题”。

#### 4.3.2 逻辑层（Logic Layer）：把候选变成“带信号的候选”（可解释、可治理）

逻辑层为候选内容补齐结构化信号，供业务层做选材与编排（但不负责最终决策）：

- Intelligence / Tagging：标签、主题、摘要、类别（资讯/项目/论文）。
- Relevance Scoring（相关性）：按关键词/主题 prompt 输出“命中程度”。
- Quality / Safety Filters：域名黑名单、重复抑制、语言过滤、噪声控制。
- Entity Resolution（同物识别）：同一 repo/model/paper 在多个 board/渠道出现时合并为一个实体卡片（这是融合榜单“不脏”的关键）。

#### 4.3.3 业务层（Business Layer）：TrendingOrchestrator / DigestOrchestrator

业务层负责把“偏好 + 候选 + 信号”变成可消费的 Issue，并处理用户闭环：

- Preference & Topic Spec（偏好配置）：关键词/prompt、选择要跟的榜单包/渠道包、频率（日/周/专题）。
- Candidate Pool Builder（候选池融合）：融合三类输入（channels + boards + research），统一去重。
- Composer（编排器）：按模板编排为 Issue（日报/周报/专题不同 section/条数/摘要力度）。
- Delivery / Surfacing（呈现与分发）：UI 渲染 + 历史回放 +（可选）推送。
- Feedback Loop（反馈闭环）：收藏到 KB、屏蔽、pin、显式偏好，反哺偏好配置与下次编排。

### 4.4 这种 Trending（Follow/Digest）的几种成熟产品形态（不讨论榜单涨跌）

你明确不想做“热度变化/榜单变化”。在这个约束下，仍然有多种成熟但风格不同的落地形态：

1) Issue-First Follow（推荐主线）
- Follow/Trending 页展示各 Topic 的最新一期 Issue。
- 点进 Topic：日报/周报/专题的历史 issue。
- 榜单 copy 作为 issue 的一个 section（可按 topic 过滤到相关条目）。
- daily paper = 某个 Topic 的“论文 section”，由 Research Engine 供给。

2) Dual-Lane Issue（监控 + 发现，避免纯关键词漏新概念）
- Monitor lane：严格命中关键词/prompt（高精度）。
- Discover lane：允许相邻概念，但每条必须给解释（为什么推荐）。

3) Board-Pack Digest（多榜单融合成一个榜单，关键词只是过滤/加权）
- 用户主要选择“榜单包”，系统把多个榜单融合成一份列表。
- 关键词/prompt 用于过滤与加权，但不展示涨跌。

4) Research-First Daily Paper（学术优先）
- Daily paper 是主角：用户写 prompt，系统每天出一期论文精选。
- 其它榜单/渠道作为“旁证来源”（例如同一论文是否在 HF/PwC 出现、是否有关联实现 repo）。

### 4.5 一句话总结：Sniffer vs Follow/Digest

- Sniffer：`用户问题 -> 即时多渠道搜索 -> 临时结果 -> 深度分析/沉淀`
- Follow/Digest（你要的 Trending）：`用户偏好(关键词/prompt/榜单包/渠道包) -> 定时获取候选(渠道更新+榜单快照+学术检索) -> 逻辑层打信号(相关性/分类/去重) -> 业务层编排成日报/周报/专题 issue -> UI/投递 + 反馈反哺偏好`

## 5.（待写）QA：Query DSL、FTS/向量检索、gated NL2SQL、安全执行与评测

## 6.（待写）长期聚类与报告：增量分配、周期重建、漂移监控与报表模板

## 7.（待写）渠道生命周期：候选评分、晋升工作流、健康检查与降权策略
