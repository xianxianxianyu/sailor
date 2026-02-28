# Sailor 资源嗅探页面（Resource Sniffer）设计文档

## 0. 定位与核心理念

资源嗅探页面是 Sailor 的第五个页面（🔍 嗅探），定位为**主动式高质量资源发现引擎**。

与现有"订阅源"页面的区别：
- **订阅源**：被动等待 — 配置好源后定期拉取，是"信息找我"
- **资源嗅探**：主动搜索 — 类似谷歌搜索框，跨平台搜索高质量资源，是"我找信息"

核心用户故事：
> 我想搜索某个主题的高质量内容，系统帮我同时在知乎、小红书、抖音、RSS 源、
> 非 RSS 站点等多个渠道搜索，返回结构化结果，我可以对结果做智能摘要分析，
> 也可以一键将优质资源转为订阅源或收藏到知识库。

---

## 1. 三大核心模块

参考 ClawFeed 的 `解耦` 与 `可复用` 设计哲学，资源嗅探拆分为三个独立模块：

```
┌─────────────────────────────────────────────────────────┐
│                   Resource Sniffer Page                   │
│                                                           │
│  ┌─────────────┐  ┌──────────────┐  ┌────────────────┐  │
│  │  渠道探测    │  │  智能摘要     │  │  嗅探包        │  │
│  │  Channel     │→│  Summary      │  │  Sniffer Pack  │  │
│  │  Probe       │  │  Engine       │  │  Config        │  │
│  └─────────────┘  └──────────────┘  └────────────────┘  │
│        ↓                ↓                   ↓            │
│   多源并行搜索     结果深度分析        搜索配置资产化     │
└─────────────────────────────────────────────────────────┘
```

---

## 2. 模块一：渠道探测系统（Channel Probe）

### 2.1 职责

跨多个平台并行搜索，将异构结果标准化为统一的 `SniffResult` 结构。

### 2.2 支持的渠道类型

| 渠道 | 类型 | 接入方式 | 优先级 |
|------|------|----------|--------|
| RSS/Atom 源 | 标准协议 | 直接解析 feed XML | P0 |
| 知乎 | 非 RSS | API / 网页抓取 | P0 |
| 小红书 | 非 RSS | API / 网页抓取 | P0 |
| 抖音 | 非 RSS | API / 网页抓取 | P1 |
| GitHub | API | gh CLI / REST API | P0 |
| arXiv / Scholar | 学术 API | REST API | P1 |
| Hacker News | API | REST API | P0 |
| Twitter/X | 非 RSS | xreach / API | P1 |
| Reddit | API | REST API | P1 |
| 通用网页 | 非 RSS | Jina Reader / 爬虫 | P0 |

### 2.3 核心数据结构

```typescript
// 嗅探结果（标准化输出）
type SniffResult = {
  result_id: string;
  channel: string;           // "zhihu" | "xiaohongshu" | "douyin" | "rss" | "github" | ...
  title: string;
  url: string;
  snippet: string;           // 摘要片段（搜索结果级别）
  author: string | null;
  published_at: string | null;
  media_type: "article" | "video" | "post" | "repo" | "paper" | "discussion";
  metrics: {                 // 各平台的质量信号
    likes?: number;
    comments?: number;
    shares?: number;
    stars?: number;
    citations?: number;
  };
  raw_data: Record<string, unknown>;  // 原始平台数据，供后续分析
};
```

### 2.4 渠道适配器接口（参考 Agent Reach 插件化设计）

```typescript
// 每个渠道实现此接口，注册到 ChannelRegistry
interface ChannelAdapter {
  channel_id: string;                    // "zhihu" | "xiaohongshu" | ...
  display_name: string;                  // "知乎"
  icon: string;                          // 渠道图标
  tier: "free" | "auth_required" | "premium";  // 接入门槛
  media_types: string[];                 // 该渠道产出的内容类型

  // 健康检查（参考 Agent Reach doctor）
  check(): Promise<{
    status: "ok" | "warn" | "off";
    message: string;
  }>;

  // 执行搜索
  search(query: SniffQuery): Promise<SniffResult[]>;
}

// 搜索请求
type SniffQuery = {
  keyword: string;                       // 搜索关键词
  channels: string[];                    // 指定搜索渠道，空 = 全部
  time_range?: "24h" | "7d" | "30d" | "all";
  sort_by?: "relevance" | "time" | "popularity";
  max_results_per_channel?: number;      // 每渠道最大结果数，默认 10
  filters?: {
    media_type?: string[];               // 过滤内容类型
    min_likes?: number;                  // 最低点赞数
    language?: string;                   // 语言过滤
  };
};
```

### 2.5 渠道注册表（Channel Registry）

```typescript
// 注册式管理，新增渠道无需改分派逻辑
class ChannelRegistry {
  private adapters: Map<string, ChannelAdapter> = new Map();

  register(adapter: ChannelAdapter): void;
  get(channelId: string): ChannelAdapter | undefined;
  getAll(): ChannelAdapter[];
  getAvailable(): Promise<ChannelAdapter[]>;  // 只返回 check() = ok 的

  // 并行搜索所有指定渠道
  async searchAll(query: SniffQuery): Promise<{
    results: SniffResult[];
    channel_status: Record<string, { status: string; count: number; elapsed_ms: number }>;
  }>;
}
```

### 2.6 与现有订阅源系统的关系

```
┌──────────────────────────────────────────────────────────────┐
│  渠道探测 (Channel Probe)                                     │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐    │
│  │ 知乎      │  │ 小红书    │  │ RSS      │  │ GitHub   │    │
│  │ Adapter   │  │ Adapter   │  │ Adapter  │  │ Adapter  │    │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘    │
│       └──────────────┴─────────────┴──────────────┘          │
│                          ↓                                    │
│                   SniffResult[]                               │
│                     ↓         ↓                               │
│            ┌────────┘         └────────┐                      │
│     智能摘要分析              一键转为订阅源                    │
│     (Summary Engine)         (→ FeedPage Source)              │
└──────────────────────────────────────────────────────────────┘
```

嗅探到的优质资源可以：
1. 直接收藏到知识库（复用现有 KB 系统）
2. 一键转为订阅源（写入现有 `sources` 表，进入 FeedPage 管理）
3. 进入智能摘要分析（模块二）

---

## 3. 模块二：智能摘要引擎（Summary Engine）

### 3.1 职责

对嗅探结果进行深度分析，生成结构化摘要。参考 ClawFeed 的"Prompt 与 Runtime 解耦"设计，摘要引擎本身不绑定特定 LLM，而是通过模板 + 可替换后端实现。

### 3.2 与现有 summary 功能的关系

Sailor 现有的 `ResourceAnalysis` 已经具备单条资源分析能力（summary、topics、scores、insights）。智能摘要引擎在此基础上做三层扩展：

```
现有能力                          嗅探摘要引擎扩展
─────────                        ──────────────────
单条 Resource 分析                → 批量嗅探结果快速摘要（轻量级）
  ↓ analyzeResource()            → 选中结果深度分析（复用现有 pipeline）
  ↓ ResourceAnalysis             → 跨结果对比摘要（新增）
```

### 3.3 三层摘要策略

#### 层级 1：搜索摘要（Search Summary）— 轻量、实时

搜索完成后自动生成，不调用 LLM，基于 snippet + metrics 做规则化排序和聚合。

```typescript
type SearchSummary = {
  query: string;
  total_results: number;
  channel_breakdown: Record<string, number>;  // 各渠道命中数
  top_results: SniffResult[];                 // 按综合评分排序的 Top N
  keyword_clusters: string[];                 // 从结果中提取的关键词聚类
  time_distribution: {                        // 时间分布
    period: string;
    count: number;
  }[];
};
```

#### 层级 2：深度摘要（Deep Summary）— 单条精读，调用 LLM

用户选中某条结果后触发，复用现有 `analyzeResource` 链路。流程：

```
SniffResult → 全文抓取(Jina/爬虫) → 写入 Resource 表 → analyzeResource()
                                                          ↓
                                                    ResourceAnalysis
                                                    (summary/topics/scores/insights)
```

这里完全复用 Sailor 已有的分析 pipeline，不重复造轮子。

#### 层级 3：对比摘要（Compare Summary）— 多条横评，调用 LLM

用户勾选多条结果后触发，生成跨资源的对比分析报告。

```typescript
type CompareSummary = {
  query: string;
  compared_items: string[];                   // 参与对比的 result_id 列表
  consensus: string[];                        // 各资源的共识观点
  divergence: string[];                       // 分歧观点
  quality_ranking: {                          // 质量排名
    result_id: string;
    title: string;
    score: number;
    reason: string;
  }[];
  recommendation: string;                     // 综合推荐建议
  model: string;
  prompt_tokens: number;
  completion_tokens: number;
};
```

### 3.4 Prompt 模板化（参考 ClawFeed）

摘要 Prompt 不硬编码在代码中，而是抽为独立模板文件，支持版本管理：

```
sailor/
  core/
    prompts/
      sniffer-deep-summary.md       # 深度摘要 prompt
      sniffer-compare-summary.md    # 对比摘要 prompt
      sniffer-quality-score.md      # 质量评分 prompt
```

模板变量示例（`sniffer-deep-summary.md`）：

```markdown
你是一个资源分析专家。请对以下内容生成结构化摘要。

## 来源信息
- 平台：{{channel}}
- 标题：{{title}}
- 作者：{{author}}
- 发布时间：{{published_at}}

## 正文内容
{{content}}

## 输出要求
请返回 JSON 格式：
{
  "summary": "200字以内的核心摘要",
  "topics": ["主题标签1", "主题标签2"],
  "quality_scores": { "depth": 0-10, "utility": 0-10, "novelty": 0-10 },
  "key_insights": ["核心观点1", "核心观点2"],
  "actionable_items": ["可执行建议1"]
}
```

### 3.5 摘要缓存与去重

```typescript
// 避免重复分析同一 URL
type SummaryCache = {
  url_hash: string;          // URL 的 SHA256
  summary_type: "search" | "deep" | "compare";
  result: SearchSummary | ResourceAnalysis | CompareSummary;
  created_at: string;
  ttl_hours: number;         // 缓存有效期
};
```

---

## 4. 模块三：嗅探包配置系统（Sniffer Pack）

### 4.1 职责

将"搜索意图"资产化为可复用、可分享、可导入导出的配置包。参考 ClawFeed 的 Source Pack 设计，把一次性搜索行为沉淀为可持续运行的嗅探策略。

### 4.2 核心概念

```
一次搜索 = 关键词 + 渠道选择 + 过滤条件 + 排序偏好
    ↓ 保存为
嗅探包 (Sniffer Pack) = 可命名、可复用、可定时执行的搜索配置
    ↓ 进一步
嗅探包市场 = 用户之间分享嗅探包（导入/导出 JSON）
```

### 4.3 数据结构

```typescript
type SnifferPack = {
  pack_id: string;
  name: string;                          // "AI 前沿论文追踪"
  description: string;
  icon: string;                          // 自定义图标
  version: number;                       // 配置版本号

  // 搜索配置
  queries: SnifferPackQuery[];           // 支持多组关键词

  // 渠道配置
  channels: {
    channel_id: string;
    enabled: boolean;
    channel_config?: Record<string, unknown>;  // 渠道级别的特殊配置
  }[];

  // 结果处理配置
  post_processing: {
    auto_summary: boolean;               // 搜索后自动生成搜索摘要
    auto_deep_analyze: boolean;          // 对 Top N 自动做深度分析
    auto_save_to_kb?: string;            // 自动收藏到指定知识库
    auto_convert_source?: boolean;       // 自动将高质量结果转为订阅源
    quality_threshold?: number;          // 质量阈值，低于此分数的结果过滤掉
  };

  // 调度配置
  schedule: {
    enabled: boolean;
    cron?: string;                       // cron 表达式，如 "0 9 * * *" 每天9点
    last_run_at?: string;
    next_run_at?: string;
  };

  // 元信息
  created_at: string;
  updated_at: string;
  run_count: number;                     // 累计执行次数
  last_result_count: number;             // 上次执行结果数
};

type SnifferPackQuery = {
  keyword: string;
  time_range: "24h" | "7d" | "30d" | "all";
  sort_by: "relevance" | "time" | "popularity";
  max_results_per_channel: number;
  filters?: {
    media_type?: string[];
    min_likes?: number;
    language?: string;
  };
};
```

### 4.4 导入导出格式

```jsonc
// sniffer-pack-ai-papers.json
{
  "sailor_sniffer_pack": "1.0",
  "name": "AI 前沿论文追踪",
  "description": "每日追踪 arXiv、GitHub、知乎上的 AI/LLM 相关高质量内容",
  "queries": [
    { "keyword": "LLM agent framework", "time_range": "7d", "sort_by": "relevance", "max_results_per_channel": 5 },
    { "keyword": "RAG retrieval augmented", "time_range": "7d", "sort_by": "time", "max_results_per_channel": 5 }
  ],
  "channels": [
    { "channel_id": "arxiv", "enabled": true },
    { "channel_id": "github", "enabled": true },
    { "channel_id": "zhihu", "enabled": true },
    { "channel_id": "hackernews", "enabled": true }
  ],
  "post_processing": {
    "auto_summary": true,
    "auto_deep_analyze": false,
    "quality_threshold": 6
  }
}
```

### 4.5 预置嗅探包（开箱即用）

| 嗅探包名称 | 渠道 | 关键词策略 | 用途 |
|-----------|------|-----------|------|
| AI 前沿追踪 | arXiv + GitHub + 知乎 + HN | LLM/Agent/RAG | 追踪 AI 领域最新进展 |
| 技术博客精选 | RSS + HN + Reddit | 按用户标签动态生成 | 发现高质量技术文章 |
| 中文互联网热点 | 知乎 + 小红书 + 抖音 | 热门话题 | 追踪中文社区讨论 |
| 开源项目发现 | GitHub + HN + Reddit | trending/new release | 发现新兴开源项目 |

### 4.6 与现有系统的联动

```
┌─────────────────────────────────────────────────────────────┐
│  Sniffer Pack                                                │
│                                                               │
│  ┌─────────────┐     ┌──────────────┐     ┌──────────────┐  │
│  │ 手动搜索     │     │ 定时执行      │     │ 导入/导出    │  │
│  │ → 保存为 Pack│     │ → cron 调度   │     │ → JSON 文件  │  │
│  └──────┬──────┘     └──────┬───────┘     └──────┬───────┘  │
│         └──────────────────┼──────────────────────┘          │
│                            ↓                                  │
│                    Channel Probe 执行搜索                     │
│                            ↓                                  │
│                    Summary Engine 分析                        │
│                            ↓                                  │
│              ┌─────────────┼─────────────┐                   │
│              ↓             ↓             ↓                    │
│         收藏到 KB     转为订阅源     生成报告                  │
│        (KBPage)     (FeedPage)    (TrendingPage)             │
└─────────────────────────────────────────────────────────────┘
```

<!-- CONTINUE_MARKER -->

---

## 5. 前端页面设计

### 5.1 导航栏变更

在现有四个页面之后新增第五个导航项：

```typescript
// NavBar.tsx 变更
export type ViewId = "trending" | "tags" | "kb" | "feeds" | "sniffer";

const NAV_ITEMS: NavItem[] = [
  { id: "trending", icon: "📊", label: "趋势" },
  { id: "tags",     icon: "🏷️", label: "标签" },
  { id: "kb",       icon: "📚", label: "知识库" },
  { id: "feeds",    icon: "📡", label: "订阅源" },
  { id: "sniffer",  icon: "🔍", label: "嗅探" },   // 新增
];
```

### 5.2 页面布局

```
┌──────────────────────────────────────────────────────────────────┐
│  🔍 资源嗅探                                                      │
│                                                                    │
│  ┌──────────────────────────────────────────────────────────────┐ │
│  │  🔍  搜索高质量资源...                    [时间▾] [排序▾] 🚀  │ │
│  └──────────────────────────────────────────────────────────────┘ │
│                                                                    │
│  渠道选择：                                                        │
│  [✅ 全部] [✅ 知乎] [✅ 小红书] [✅ GitHub] [✅ HN] [⬜ 抖音]    │
│  [✅ RSS] [✅ arXiv] [⬜ Reddit] [⬜ Twitter]                      │
│                                                                    │
│  ┌─ 嗅探包快捷入口 ──────────────────────────────────────────┐   │
│  │  [📦 AI前沿追踪] [📦 技术博客精选] [📦 中文热点] [+ 新建]  │   │
│  └──────────────────────────────────────────────────────────────┘ │
│                                                                    │
│  ── 搜索结果 (共 47 条，来自 5 个渠道) ─────────────────────────  │
│                                                                    │
│  ┌─ 搜索摘要 ────────────────────────────────────────────────┐   │
│  │  关键词聚类: [LLM] [Agent] [RAG] [Fine-tuning]            │   │
│  │  渠道分布: 知乎 12 | GitHub 15 | HN 8 | arXiv 7 | RSS 5  │   │
│  │  时间分布: ████████░░ 近7天集中                             │   │
│  └──────────────────────────────────────────────────────────────┘ │
│                                                                    │
│  [全部] [知乎 12] [GitHub 15] [HN 8] [arXiv 7] [RSS 5]  ← 渠道Tab│
│                                                                    │
│  ┌──────────────────────────────────────────────────────────────┐ │
│  │ ☐ 📄 Building LLM Agents with Tool Use              知乎    │ │
│  │   作者: xxx · 2天前 · 👍 2.3k · 💬 156                      │ │
│  │   "本文介绍了如何构建具有工具调用能力的 LLM Agent..."        │ │
│  │   [🔍 深度分析] [📚 收藏到KB] [📡 转为订阅源]               │ │
│  ├──────────────────────────────────────────────────────────────┤ │
│  │ ☐ ⭐ awesome-llm-agents                              GitHub  │ │
│  │   作者: xxx · 5天前 · ⭐ 3.2k · 🍴 420                      │ │
│  │   "A curated list of LLM agent frameworks and tools..."      │ │
│  │   [🔍 深度分析] [📚 收藏到KB] [📡 转为订阅源]               │ │
│  └──────────────────────────────────────────────────────────────┘ │
│                                                                    │
│  [已选 2 条] → [📊 对比分析] [📦 保存为嗅探包]                    │
│                                                                    │
└──────────────────────────────────────────────────────────────────┘
```

### 5.3 交互流程

```mermaid
flowchart TD
    A[用户输入关键词 / 选择嗅探包] --> B[选择渠道 + 过滤条件]
    B --> C[点击搜索]
    C --> D[Channel Probe 并行搜索各渠道]
    D --> E[返回 SniffResult[] + SearchSummary]
    E --> F{用户操作}

    F -->|浏览结果| G[按渠道 Tab 切换查看]
    F -->|深度分析| H[选中单条 → Deep Summary]
    F -->|对比分析| I[勾选多条 → Compare Summary]
    F -->|收藏| J[选中 → 加入知识库]
    F -->|转订阅| K[选中 → 创建为 Source]
    F -->|保存搜索| L[当前配置 → 保存为 Sniffer Pack]

    H --> M[全文抓取 → Resource → analyzeResource]
    I --> N[LLM 对比分析 → CompareSummary]
    K --> O[写入 sources 表 → FeedPage 可见]
```

<!-- CONTINUE_MARKER_2 -->

---

## 6. 后端 API 设计

### 6.1 嗅探搜索

```
POST /sniffer/search
Body: SniffQuery
Response: {
  results: SniffResult[];
  summary: SearchSummary;
  channel_status: Record<string, { status, count, elapsed_ms }>;
}
```

### 6.2 渠道管理

```
GET  /sniffer/channels                    # 获取所有渠道及状态
GET  /sniffer/channels/health             # 健康检查（类似 Agent Reach doctor）
POST /sniffer/channels/:id/check          # 单渠道健康检查
```

### 6.3 深度分析

```
POST /sniffer/results/:id/deep-analyze    # 单条深度分析
Body: { result: SniffResult }
Response: ResourceAnalysis                 # 复用现有类型
```

### 6.4 对比分析

```
POST /sniffer/compare
Body: { result_ids: string[], results: SniffResult[] }
Response: CompareSummary
```

### 6.5 嗅探包管理

```
GET    /sniffer/packs                     # 列出所有嗅探包
POST   /sniffer/packs                     # 创建嗅探包
PUT    /sniffer/packs/:id                 # 更新嗅探包
DELETE /sniffer/packs/:id                 # 删除嗅探包
POST   /sniffer/packs/:id/run            # 执行嗅探包
POST   /sniffer/packs/import             # 导入嗅探包 JSON
GET    /sniffer/packs/:id/export          # 导出嗅探包 JSON
```

### 6.6 结果操作

```
POST /sniffer/results/:id/save-to-kb      # 收藏到知识库
Body: { kb_id: string }

POST /sniffer/results/:id/convert-source   # 转为订阅源
Body: { source_type?: string }
Response: SourceRecord                      # 复用现有类型
```

<!-- CONTINUE_MARKER_3 -->

---

## 7. 数据库表设计

### 7.1 新增表

```sql
-- 嗅探结果缓存
CREATE TABLE sniff_results (
    result_id    TEXT PRIMARY KEY,
    query        TEXT NOT NULL,
    channel      TEXT NOT NULL,
    title        TEXT NOT NULL,
    url          TEXT NOT NULL,
    url_hash     TEXT NOT NULL,              -- 用于去重
    snippet      TEXT,
    author       TEXT,
    published_at TEXT,
    media_type   TEXT,
    metrics      TEXT,                        -- JSON
    raw_data     TEXT,                        -- JSON
    created_at   TEXT DEFAULT (datetime('now'))
);

CREATE INDEX idx_sniff_results_query ON sniff_results(query);
CREATE INDEX idx_sniff_results_url_hash ON sniff_results(url_hash);

-- 嗅探包
CREATE TABLE sniffer_packs (
    pack_id         TEXT PRIMARY KEY,
    name            TEXT NOT NULL,
    description     TEXT,
    icon            TEXT DEFAULT '📦',
    version         INTEGER DEFAULT 1,
    queries         TEXT NOT NULL,            -- JSON: SnifferPackQuery[]
    channels        TEXT NOT NULL,            -- JSON: channel config[]
    post_processing TEXT,                     -- JSON
    schedule        TEXT,                     -- JSON
    created_at      TEXT DEFAULT (datetime('now')),
    updated_at      TEXT DEFAULT (datetime('now')),
    run_count       INTEGER DEFAULT 0,
    last_result_count INTEGER DEFAULT 0
);

-- 摘要缓存
CREATE TABLE summary_cache (
    url_hash      TEXT NOT NULL,
    summary_type  TEXT NOT NULL,              -- "search" | "deep" | "compare"
    result        TEXT NOT NULL,              -- JSON
    created_at    TEXT DEFAULT (datetime('now')),
    ttl_hours     INTEGER DEFAULT 24,
    PRIMARY KEY (url_hash, summary_type)
);
```

### 7.2 现有表复用

- `resources` — 深度分析时写入，复用现有 Resource pipeline
- `sources` — 转订阅源时写入，复用现有 Source 管理
- `kb_items` — 收藏到知识库时写入，复用现有 KB 系统

<!-- CONTINUE_MARKER_4 -->

---

## 8. 三模块解耦关系总览

```
┌─────────────────────────────────────────────────────────────────┐
│                        Sailor 系统                               │
│                                                                   │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │  资源嗅探页面 (SnifferPage.tsx)                              │ │
│  │  ┌───────────┐   ┌───────────┐   ┌───────────────────────┐ │ │
│  │  │ Channel   │   │ Summary   │   │ Sniffer Pack          │ │ │
│  │  │ Probe     │   │ Engine    │   │ Config                │ │ │
│  │  │           │   │           │   │                       │ │ │
│  │  │ 可独立用于│   │ 可独立用于│   │ 可独立用于            │ │ │
│  │  │ 任何需要  │   │ 任何需要  │   │ 任何需要搜索          │ │ │
│  │  │ 多源搜索  │   │ 内容分析  │   │ 配置持久化的          │ │ │
│  │  │ 的场景    │   │ 的场景    │   │ 场景                  │ │ │
│  │  └─────┬─────┘   └─────┬─────┘   └──────────┬────────────┘ │ │
│  │        │               │                     │              │ │
│  └────────┼───────────────┼─────────────────────┼──────────────┘ │
│           │               │                     │                │
│  ─────────┼───────────────┼─────────────────────┼──── 复用边界 ─ │
│           ↓               ↓                     ↓                │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────────────────┐ │
│  │ FeedPage     │ │ TrendingPage │ │ KBPage                   │ │
│  │ (订阅源管理) │ │ (趋势报告)   │ │ (知识库)                 │ │
│  │              │ │              │ │                          │ │
│  │ 嗅探结果可   │ │ 嗅探报告可   │ │ 嗅探结果可               │ │
│  │ 转为订阅源   │ │ 合并到趋势   │ │ 直接收藏                 │ │
│  └──────────────┘ └──────────────┘ └──────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

解耦原则：
- **Channel Probe** 只负责"搜"，不关心结果怎么用 → 可被 FeedPage 复用做源发现
- **Summary Engine** 只负责"分析"，不关心数据从哪来 → 可被 TrendingPage 复用做报告增强
- **Sniffer Pack** 只负责"配置持久化"，不关心执行细节 → 可被定时任务系统复用

---

## 9. 文件结构规划

```
sailor/
├── frontend/src/
│   ├── pages/
│   │   └── SnifferPage.tsx              # 嗅探页面主组件
│   ├── components/
│   │   ├── SnifferSearchBar.tsx          # 搜索框 + 过滤条件
│   │   ├── SnifferChannelPicker.tsx      # 渠道选择器
│   │   ├── SnifferResultList.tsx         # 搜索结果列表
│   │   ├── SnifferResultCard.tsx         # 单条结果卡片
│   │   ├── SnifferSummaryPanel.tsx       # 搜索摘要面板
│   │   ├── SnifferCompareModal.tsx       # 对比分析弹窗
│   │   └── SnifferPackManager.tsx        # 嗅探包管理
│   └── types.ts                          # 新增 Sniffer 相关类型
│
├── backend/app/routers/
│   └── sniffer.py                        # 嗅探 API 路由
│
├── core/
│   ├── sniffer/
│   │   ├── channel_registry.py           # 渠道注册表
│   │   ├── adapters/                     # 各渠道适配器
│   │   │   ├── zhihu_adapter.py
│   │   │   ├── xiaohongshu_adapter.py
│   │   │   ├── github_adapter.py
│   │   │   ├── hackernews_adapter.py
│   │   │   ├── rss_adapter.py
│   │   │   ├── arxiv_adapter.py
│   │   │   └── web_adapter.py
│   │   ├── summary_engine.py             # 智能摘要引擎
│   │   └── pack_manager.py               # 嗅探包管理
│   ├── prompts/
│   │   ├── sniffer-deep-summary.md
│   │   ├── sniffer-compare-summary.md
│   │   └── sniffer-quality-score.md
│   └── storage/
│       └── sniffer_repository.py         # 嗅探数据存储
│
└── docs/
    └── resource-sniffer-design.md        # 本文档
```

---

## 10. 实施路线

### P0（1-2 周）— 核心搜索能力

- 搭建 SnifferPage 页面骨架 + 搜索框 UI
- 实现 ChannelRegistry + 3 个 P0 适配器（RSS、GitHub、HN）
- 实现搜索 API + 结果列表展示
- 搜索摘要（层级 1，纯规则）

### P1（2-3 周）— 分析 + 嗅探包

- 接入知乎、小红书适配器
- 实现深度分析（层级 2，复用现有 analyzeResource）
- 实现对比分析（层级 3）
- 嗅探包 CRUD + 导入导出
- 结果一键转订阅源 / 收藏到 KB

### P2（3-4 周）— 自动化 + 扩展

- 嗅探包定时执行（cron 调度）
- 接入抖音、Twitter、Reddit 等 P1 渠道
- 渠道健康检查面板（参考 Agent Reach doctor）
- 预置嗅探包
- 摘要缓存与去重优化




