# Follow 模块

## 1. 作用

Follow 是当前系统的最高层业务编排模块，用来把 Board、Research 等输入组织成最终的出刊结果。

当前 UI 对应：

- `frontend/src/pages/FollowPage.tsx`

核心代码位置：

- `backend/app/routers/follows.py`
- `core/follow/repository.py`
- `core/follow/orchestrator.py`
- `core/follow/run_handler.py`
- `core/follow/composer.py`
- `core/follow/handlers.py`

## 2. 核心对象

### 2.1 `FollowRepository`

- Follow 配置 CRUD
- Follow run 与 issue 相关记录

### 2.2 `FollowOrchestrator`

- Follow 的业务编排中心
- 协调 board、research、artifact、jobs

### 2.3 `IssueComposerEngine`

- 把 Board / Research 输入收敛成最终 `issue_snapshot`
- 关注产物结构，不负责外部采集

### 2.4 `FollowRunHandler`

- Runtime 侧的执行入口
- 把 orchestrator 包装成统一 job

## 3. 主要 job

- `follow_run`
- `issue_compose`

## 4. 运行链路

1. 定义 Follow 配置
2. 触发 `follow_run`
3. orchestrator 检查依赖输入
4. 需要时触发 board / research 相关 job
5. 调用 `IssueComposerEngine`
6. 输出 `issue_snapshot` artifact

## 5. 与其他模块的关系

- 输入来自 Board 与 Research
- 运行依赖 Runtime
- 产物依赖 ArtifactStore

## 6. 当前事实

- Follow 是当前最接近“业务工作流系统”的模块
- 如果要描述系统的完整业务闭环，应该从 Follow 往下追到 Board / Research / Runtime，而不是从单个采集器看
