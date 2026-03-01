# 资源嗅探（Sniffer）页面 IA/UX 梳理与改版方案

> 范围：分析与方案（不修改代码）
>
> 主要实现参考：`frontend/src/pages/SnifferPage.tsx`、`frontend/src/components/Sniffer*.tsx`、`backend/app/routers/sniffer.py`

你反馈资源嗅探页面“很多模块凑在一起、排版和使用很 dirty”。从产品与用户的角度，这类问题往往不是“功能太多”，而是缺少明确的主任务、层级与收纳策略，导致注意力被分散、意图混杂、反馈不闭环。

下面按“功能清单 -> 模块归属 -> 优先级 -> 信息架构与交互改版方案”的顺序，把现状拆清并给出可落地的页面方案。

---

## 1. 功能清单与模块归属（按“用户能做什么”拆）

页面编排在 `frontend/src/pages/SnifferPage.tsx`，组件主要在 `frontend/src/components/*Sniffer*.tsx`，后端入口在 `backend/app/routers/sniffer.py`。

| 用户功能 | 前端模块 | API/后端/核心模块 |
|---|---|---|
| 跨渠道搜索（关键词 + 时间 + 排序 + 渠道） | `frontend/src/components/SnifferSearchBar.tsx` + `frontend/src/pages/SnifferPage.tsx` | `POST /sniffer/search` -> `core/sniffer/channel_registry.py`（并发分发到 adapters）+ `core/sniffer/summary_engine.py`（生成摘要）+ `core/storage/sniffer_repository.py`（落库/缓存） |
| 渠道列表/可用性提示（用于勾选） | `frontend/src/components/SnifferSearchBar.tsx` | `GET /sniffer/channels` -> `ChannelRegistry.list_channels()`（adapter.check） |
| 结果浏览（列表/指标/按渠道查看） | `frontend/src/pages/SnifferPage.tsx` + `frontend/src/components/SnifferResultCard.tsx` | 结果来自 search 响应；页面内还有“渠道 tab”做二次过滤（当前是客户端过滤） |
| 搜索摘要（分布、关键词簇、top） | `frontend/src/components/SnifferSummaryPanel.tsx` | search 响应里自带 summary（后端 `SummaryEngine.summarize()`，并做 summary_cache） |
| 单条深度分析 | `frontend/src/components/SnifferResultCard.tsx`（触发）+ 页面内“深度分析结果”面板 | `POST /sniffer/results/{id}/deep-analyze` -> 复用资源分析链路（落到 Resource 再分析） |
| 多条对比分析（多选） | `frontend/src/components/SnifferCompareModal.tsx` + `SnifferPage` 选择态/浮条 | `POST /sniffer/compare` -> `SummaryEngine.compare()`（LLM）+ prompt `core/prompts/sniffer-compare-summary.md` |
| 收藏到知识库 | `frontend/src/components/KBPickerModal.tsx` + `SnifferResultCard` 入口 | `POST /sniffer/results/{id}/save-to-kb` -> 复用 KB/Resource repo |
| 转为订阅源 | `SnifferResultCard` 入口 | `POST /sniffer/results/{id}/convert-source` -> 复用 Source repo |
| 嗅探包（运行/导入/导出/删除/定时） | `frontend/src/components/SnifferPackPanel.tsx` | `/sniffer/packs*` + `core/sniffer/pack_manager.py` + `core/sniffer/scheduler.py` |
| 渠道健康状态（状态/延迟） | `frontend/src/components/SnifferHealthPanel.tsx` | `GET /sniffer/channels/health`（后端并发 check，返回 status + latency） |

从概念上，这些功能天然分成 3+2 组：

- 主链路：Channel Probe（跨渠道搜索）+ Results Browsing（浏览/筛选）
- 洞察/分析：Summary（搜索摘要）+ Deep Analyze（单条）+ Compare（多条）
- 自动化/资产化：Sniffer Pack（保存搜索、运行、导入导出、定时）
- 运维/可信度：Health（渠道状态）
- 运营动作：Save to KB / Convert to Source（把好结果沉淀/进入订阅体系）

---

## 2. 模块优先级（产品视角：首屏必须突出什么）

- P0（默认必须显眼、顺滑）：关键词搜索 + 渠道范围（一个入口）+ 时间/排序 + 结果浏览（快速判断）+ 轻量洞察（摘要）+ “沉淀动作”（收藏到 KB / 转订阅源，至少有一个明确主动作）
- P1（可达但不抢注意力）：深度分析、对比分析、多选批量动作、“保存当前搜索为嗅探包”
- P2（收纳到工具区/管理区）：嗅探包管理（导入/导出/删除/定时）、渠道健康详情（诊断用）

补充：对“高频研究/情报”用户，嗅探包的“运行/复跑”可能是 P0；但它也应该是“快捷入口”，而不是把“开始搜索”挤到次要位置。

---

## 3. 为什么现在会显得 dirty（根因，不是“功能太多”）

- 目标任务不够突出：落地页把 `嗅探包/状态`放得很像主舞台，反而弱化“输入关键词 -> 搜”的第一动机（首屏心智被管理工具劫持）。
- 同一概念双控制：渠道既在搜索区勾选，又在结果区用 tab 过滤，用户会困惑“我到底在哪定义范围？tab 是过滤还是重新搜索？”。
- 意图混杂：右侧 tab 把“洞察（摘要）/自动化（嗅探包）/运维（状态）”放成同级入口，导致信息层级扁平、互相抢注意力。
- 面板碎片化：多选浮条 + 对比 modal + 深度分析 modal + KB modal + 侧边 tab，频繁切上下文，用户很难形成稳定“工作台”感。
- 反馈/可信度不足：前端存在静默吞错的路径（操作失败用户无感），会直接放大“脏/不靠谱”的体验。
- 视觉一致性问题：`frontend/src/styles.css` 里 Sniffer 的“主骨架（search+results+sidebar）”有样式，但像选择浮条/侧边 tab/panel/landing 等若缺少对应样式，会让局部看起来像临时拼装（这会非常符合 dirty 观感）。

---

## 4. 推荐改版：Search Workspace + Inspector + Tools Drawer

目标：页面只保留一个“探索工作台”，把“工具/管理”从主工作流里抽离。

### 4.1 页面结构（桌面端）

- 顶部 Query Bar（P0）：关键词输入框（最大、占视觉中心）+ `Sources/渠道`胶囊（显示选中数量 + 健康小点）+ 时间 + 排序 + 主按钮“搜索/更新”。
- 应用条件 Chips 行（P0）：把当前范围显式化（渠道/时间/排序），可一键删除某个条件；高级条件收进“更多筛选…”。
- 主区 Results（P0）：结果列表是唯一主舞台；支持“按来源分组/全部混排”视图切换（替代现在“渠道 tab = 第二套范围控制”）。
- 右侧 Inspector（P0/P1，取代多重 modal + 侧边 tab 混放）：
  - 未选中：展示“搜索洞察”（摘要，最多 3 个核心块，剩余折叠）。
  - 选中 1 条：展示条目详情 + 深度分析（在 inspector 内联进度/结果）。
  - 多选：展示选择集合摘要 + 进入对比分析。
- 底部 Sticky 选择动作条（P1）：不要“漂浮到处挡内容”，而是稳定贴底；根据选择数量动态推荐主动作（1 条：深度分析；2-5 条：对比；更多：提示缩减）。

### 4.2 一致性原则（减少“拼装感”）

- 查询范围只有一个真相：只保留 Query Bar 的渠道选择；结果区的“按渠道”只能是视图/分组，不再像“第二个范围控制器”。
- 交互尽量留在同一个工作台上下文：Deep Analyze/Compare 优先在 inspector 内联，modal 只用于破坏性确认或必须聚焦的报告。

---

## 5. 收纳策略（P2 不消失，但不和主链路同台）

- Tools Drawer（右上角“工具”按钮打开）：
  - Packs：默认只提供“运行/最近运行”，管理项（导入/导出/删除/定时）折叠到“管理”分组。
  - Health：默认只显示异常渠道（优先级排序），展开才看全表；与结果区的“部分渠道失败”提示联动（点提示直接打开 Health）。

- Packs 的正确入口：在 Query Bar 提供“保存当前搜索为嗅探包”，让 packs 成为“沉淀搜索意图”的自然下一步，而不是一个并列 tab。

---

## 6. 关键交互细则（让页面从“拼装”变成“工作台”）

- 查询修改变成“dirty”状态：用户改了条件但不自动刷新，直到按回车/点搜索；加载时保留旧结果并标注“正在更新…”，避免空白闪烁。
- 部分失败要可见：如果某些渠道超时/失败，结果仍显示成功渠道，同时在顶部给一个可点击提示（打开 Health drawer）。
- “沉淀动作”要有闭环反馈：收藏/转订阅必须有 toast + 卡片上的已保存状态；失败要可重试，不要静默。
- 深度分析/对比尽量不弹新 modal：优先在 inspector 内联；对比建议做成“专用全屏视图”，减少叠层。

---

## 7. 推荐落地顺序（风险最小、收益最大）

如果认可这个方向，改造可以按下面顺序推进：

1) 先重排信息架构（Query + Results + Inspector）
2) 再把 Packs/Health 收到 Tools drawer
3) 最后统一反馈/错误与“保存为嗅探包”入口
