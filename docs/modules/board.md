# Board 模块

## 1. 作用

Board 模块负责“榜单型数据源”的采集、快照和增量运行。

当前 UI 对应：

- `frontend/src/pages/BoardPage.tsx`

核心代码位置：

- `backend/app/routers/boards.py`
- `core/board/repository.py`
- `core/board/tools.py`
- `core/board/handlers.py`
- `core/board/engine.py`

## 2. 核心对象

### 2.1 `BoardRepository`

- Board CRUD
- Board snapshot / snapshot items 持久化

### 2.2 Board Tools

当前主要采集能力：

- GitHub Trending
- Hugging Face 相关榜单

### 2.3 `BoardSnapshotHandler`

- 负责执行一次 snapshot capture
- 输出不可变快照

### 2.4 `BoardRunEngine`

- 基于当前 snapshot 与 baseline snapshot 计算 delta
- 产出 `board_bundle`

### 2.5 `BoardRunHandler`

- 把 `BoardRunEngine` 包装成可执行 job

## 3. 主要 job

- `board_snapshot`
- `board_run`

## 4. 对外接口

Board 路由负责：

- Board CRUD
- 触发 snapshot
- 触发 run
- 读取 board 结果与 artifact

具体 API 以 `backend/app/routers/boards.py` 为准。

## 5. 运行链路

1. 创建 board
2. 触发 `board_snapshot`
3. 得到当前榜单快照
4. 再触发 `board_run`
5. 计算与 baseline 的差异，形成可复用产物

## 6. 与其他模块的关系

- Follow 会消费 board bundle
- ArtifactStore 保存 board run 结果
- Runtime 为 board 提供统一 job / event / tool call 语义

## 7. 当前事实

- Board 是 Follow 系统的重要输入模块
- 它和 Sources 的区别是：Board 采集的是“榜单快照”，不是通用文章流
