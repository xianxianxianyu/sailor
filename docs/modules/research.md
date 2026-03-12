# Research 模块

## 1. 作用

Research 模块负责论文源同步、研究主题定义、快照生成与研究运行。

当前 UI 对应：

- `frontend/src/pages/ResearchPage.tsx`

核心代码位置：

- `backend/app/routers/paper_sources.py`
- `backend/app/routers/research_programs.py`
- `core/paper/repository.py`
- `core/paper/handlers.py`
- `core/paper/engine.py`
- `core/paper_logic/*`

## 2. 子层次

### 2.1 Paper Sources

- 管理论文数据源
- 同步 canonical papers
- 记录 `paper_runs`

### 2.2 Research Program

- 定义研究主题、过滤条件、启停状态
- 是 Research 业务侧的配置对象

### 2.3 Research Snapshot

- 在某一时刻冻结某个 program 命中的 papers
- 用于后续 run 和差异计算

### 2.4 `ResearchRunEngine`

- 基于 snapshot 与 baseline 计算研究增量
- 输出 `research_bundle`

## 3. 主要 job

- `paper_source_run`
- `research_snapshot`
- `research_run`

## 4. 对外接口

主要 API 包括：

- paper source CRUD / run
- research program CRUD
- research snapshot / run 相关接口

具体以 `paper_sources.py` 与 `research_programs.py` 为准。

## 5. 运行链路

1. 配置 paper source
2. 同步 papers
3. 创建 research program
4. 触发 `research_snapshot`
5. 触发 `research_run`
6. 产出 `research_bundle`

## 6. 与其他模块的关系

- Follow 会消费 research bundle
- ArtifactStore 保存 research run 产物
- Research 与 Sources 并列，都是长期供给模块，但输入对象是论文而不是通用资源

## 7. 当前事实

- Research 是 Follow 的另一条核心输入链路
- Paper 数据同步、Research Program、Research Run 已经是拆分良好的多阶段模块，而不是单个大接口
