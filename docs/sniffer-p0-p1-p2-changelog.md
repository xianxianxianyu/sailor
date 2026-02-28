# Sailor 资源嗅探 — P0/P1/P2 实施记录

## 1. 各阶段目标

### P0 — 核心搜索能力（已完成）

建立资源嗅探的基础架构：跨渠道搜索 + 结果展示 + 嗅探包管理。

- 3 个渠道适配器：HackerNews、GitHub、RSS
- `ChannelRegistry` 并行搜索分发
- `SummaryEngine` 纯规则搜索摘要（渠道分布、关键词聚类、时间分布、热门排行）
- 嗅探包（SnifferPack）基础 CRUD
- 前端：SnifferPage 搜索 UI + 结果卡片 + 摘要侧栏

### P1 — 分析 + 操作（已完成）

在搜索结果上叠加 LLM 分析能力和资源操作。

- **P1-1 深度分析**：单条结果 → 转 Resource → 调用 `article_agent.analyze()` 获取 LLM 分析
- **P1-2 对比分析**：多选结果 → LLM 横向对比，输出多维度评分 + 综合结论
- **P1-3 结果操作**：收藏到知识库（复用 `kb_repo.add_item()`）、转订阅源（复用 `source_repo.upsert_source()`）
- **P1-4 嗅探包导入导出**：JSON 格式往返

### P2 — 自动化 + 扩展（已完成）

让嗅探包自动运行，增加系统可观测性和开箱即用体验。

- **P2-1 定时执行**：`threading.Timer` 调度器，支持 `every_1h/6h/12h/24h` 四档
- **P2-2 健康检查**：并行检测所有渠道状态 + 延迟
- **P2-3 预置包**：首次启动自动创建"AI 前沿"、"开源热门"、"技术博客"三个嗅探包
- **P2-4 缓存去重**：搜索摘要写入 `summary_cache` 表；搜索结果按 URL 去重

---

## 2. 修改后的架构

```
sailor/
├── core/
│   ├── models.py                          # SnifferPack(+schedule), CompareSummary
│   ├── prompts/
│   │   └── sniffer-compare-summary.md     # [新建] 对比分析 prompt
│   ├── sniffer/
│   │   ├── __init__.py
│   │   ├── channel_registry.py            # ChannelRegistry (+URL 去重)
│   │   ├── pack_manager.py               # PackManager (+import/export/presets)
│   │   ├── summary_engine.py             # SummaryEngine (+compare/cache)
│   │   ├── scheduler.py                  # [新建] SnifferScheduler
│   │   └── adapters/
│   │       ├── hackernews_adapter.py
│   │       ├── github_adapter.py
│   │       └── rss_adapter.py
│   └── storage/
│       ├── db.py                          # sniffer_packs 表 (+schedule 列)
│       ├── sniffer_repository.py          # (+get_result, schedule 方法)
│       └── repositories.py               # ResourceRepo, KBRepo (复用)
│
├── backend/app/
│   ├── schemas.py                         # (+P1/P2 新增 schemas)
│   ├── container.py                       # (+scheduler, presets 初始化)
│   └── routers/
│       └── sniffer.py                     # (+7 个新端点)
│
└── frontend/src/
    ├── types.ts                           # (+CompareSummary, ChannelHealth)
    ├── api.ts                             # (+8 个新 API 函数)
    ├── pages/
    │   └── SnifferPage.tsx                # (重写: 多选/浮动栏/侧栏 tabs)
    └── components/
        ├── SnifferResultCard.tsx           # (+checkbox/操作按钮)
        ├── SnifferCompareModal.tsx         # [新建] 对比分析弹窗
        ├── SnifferPackPanel.tsx            # [新建] 嗅探包管理面板
        └── SnifferHealthPanel.tsx          # [新建] 渠道健康面板
```

---

## 3. API 端点清单

### P0 已有端点

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/sniffer/search` | 跨渠道搜索 |
| GET | `/sniffer/channels` | 列出所有渠道 |
| GET | `/sniffer/packs` | 列出嗅探包 |
| POST | `/sniffer/packs` | 创建嗅探包 |
| DELETE | `/sniffer/packs/{pack_id}` | 删除嗅探包 |
| POST | `/sniffer/packs/{pack_id}/run` | 运行嗅探包 |

### P1 新增端点

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/sniffer/results/{id}/deep-analyze` | 深度分析（LLM） |
| POST | `/sniffer/results/{id}/save-to-kb` | 收藏到知识库 |
| POST | `/sniffer/results/{id}/convert-source` | 转为订阅源 |
| POST | `/sniffer/compare` | 多条结果对比分析（LLM） |
| POST | `/sniffer/packs/import` | 导入嗅探包 |
| GET | `/sniffer/packs/{id}/export` | 导出嗅探包 |

### P2 新增端点

| 方法 | 路径 | 说明 |
|------|------|------|
| PATCH | `/sniffer/packs/{id}/schedule` | 设置定时调度 |
| GET | `/sniffer/channels/health` | 渠道健康检查（含延迟） |

---

## 4. 数据模型变更

### SnifferPack（扩展）

```python
@dataclass
class SnifferPack:
    pack_id: str
    name: str
    query_json: str = "{}"
    description: str | None = None
    schedule_cron: str | None = None      # P2 新增: "every_1h" | "every_6h" | ...
    last_run_at: datetime | None = None   # P2 新增
    next_run_at: datetime | None = None   # P2 新增
    created_at: datetime | None = None
```

### CompareSummary（新增）

```python
@dataclass
class CompareSummary:
    dimensions: list[dict[str, Any]]  # [{name, items: [{title, score, comment}]}]
    verdict: str                       # 综合结论
    model: str                         # 使用的 LLM 模型
```

### sniffer_packs 表（DDL 变更）

```sql
CREATE TABLE IF NOT EXISTS sniffer_packs (
    pack_id         TEXT PRIMARY KEY,
    name            TEXT NOT NULL,
    query_json      TEXT NOT NULL DEFAULT '{}',
    description     TEXT,
    schedule_cron   TEXT,          -- P2 新增
    last_run_at     TEXT,          -- P2 新增
    next_run_at     TEXT,          -- P2 新增
    created_at      TEXT DEFAULT CURRENT_TIMESTAMP
);
```

---

## 5. 修改文件明细

### 后端新建（2 个文件）

| 文件 | 说明 |
|------|------|
| `core/prompts/sniffer-compare-summary.md` | 对比分析 LLM prompt 模板 |
| `core/sniffer/scheduler.py` | `SnifferScheduler`：基于 `threading.Timer` 的定时调度器 |

### 后端修改（8 个文件）

| 文件 | 变更内容 |
|------|----------|
| `core/models.py` | `SnifferPack` 加 3 个 schedule 字段；新增 `CompareSummary` |
| `core/storage/db.py` | `sniffer_packs` 表加 `schedule_cron`、`last_run_at`、`next_run_at` 列 |
| `core/storage/sniffer_repository.py` | 新增 `get_result()`、`get_results_by_ids()`、`update_pack_schedule()`、`update_pack_last_run()`、`list_scheduled_packs()`；更新 `_row_to_pack` |
| `core/sniffer/summary_engine.py` | 新增 `compare()` 方法（LLM 对比）；`summarize()` 加缓存读写；接受 `sniffer_repo` 参数 |
| `core/sniffer/pack_manager.py` | 新增 `import_pack()`、`export_pack()`、`ensure_presets()` |
| `core/sniffer/channel_registry.py` | `search()` 结果按 URL 去重 |
| `backend/app/schemas.py` | 新增 `SaveToKBIn`、`ConvertSourceIn`、`CompareIn`、`CompareSummaryOut`、`ImportPackIn`、`SnifferPackFullOut`、`UpdatePackScheduleIn`、`ChannelHealthOut` |
| `backend/app/routers/sniffer.py` | 新增 8 个端点；提取 `_result_to_out()` 辅助函数 |
| `backend/app/container.py` | 引入 `SnifferScheduler`；`SummaryEngine` 传入 `sniffer_repo`；调用 `ensure_presets()`；启动 scheduler |

### 前端新建（3 个文件）

| 文件 | 说明 |
|------|------|
| `components/SnifferCompareModal.tsx` | 对比分析结果弹窗（维度表格 + 综合结论） |
| `components/SnifferPackPanel.tsx` | 嗅探包管理面板（列表/运行/导入/导出/定时配置） |
| `components/SnifferHealthPanel.tsx` | 渠道健康检查面板（状态点 + 延迟显示） |

### 前端修改（4 个文件）

| 文件 | 变更内容 |
|------|----------|
| `types.ts` | `SnifferPack` 扩展 schedule 字段；新增 `CompareSummary`、`ChannelHealth` |
| `api.ts` | 新增 `deepAnalyze`、`compareResults`、`saveToKB`、`convertToSource`、`importSnifferPack`、`exportSnifferPack`、`updatePackSchedule`、`getChannelHealth` |
| `components/SnifferResultCard.tsx` | 加 checkbox 多选 + 深度分析/收藏/转订阅按钮 |
| `pages/SnifferPage.tsx` | 重写：多选状态管理、浮动操作栏、侧栏 tabs（摘要/嗅探包/状态）、对比弹窗、KB 选择弹窗、深度分析弹窗、落地页面板 |
| `styles.css` | 新增选中态、操作按钮、浮动栏、侧栏 tabs、对比弹窗、嗅探包面板、健康面板、落地页布局等样式 |

---

## 6. 关键复用关系

| 功能 | 复用的已有模块 |
|------|---------------|
| 深度分析 | `resource_repo.upsert()` → `article_agent.analyze()` |
| 收藏到 KB | `resource_repo.upsert()` → `kb_repo.add_item()` |
| 转订阅源 | `source_repo.upsert_source()` |
| LLM 调用 | `container.llm_client.chat()` |
| 摘要缓存 | `sniffer_repo.get_cached_summary()` / `set_cached_summary()` (已有 `summary_cache` 表) |
| KB 选择弹窗 | 复用 `KBPickerModal` 组件 |
