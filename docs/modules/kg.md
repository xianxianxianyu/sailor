# KG 模块

## 1. 作用

KG 模块负责知识图谱节点与链接的自动推断与重建。

核心代码位置：

- `backend/app/routers/kg_graph.py`
- `core/kg/link_engine.py`
- `core/kg/handlers.py`
- `core/storage/kg_graph_repository.py`

## 2. 核心对象

### 2.1 `KBGraphRepository`

- 图节点与边的持久化
- 提供图查询与节点更新能力

### 2.2 `KGLinkEngine`

- 使用 LLM 生成或修复节点间关系
- 负责“该怎么连”的推断，不负责 job 生命周期

### 2.3 KG Handlers

- `KGAddNodeHandler`
- `KGRelinkNodeHandler`

它们通过 Runtime 执行真实 job。

## 3. 主要 job

- `kg_add_node`
- `kg_relink_node`

## 4. 运行链路

1. 前端或后端入口创建 KG job
2. worker 调用 KG handler
3. handler 使用 `KGLinkEngine`
4. 结果写回 KG repository

## 5. 与其他模块的关系

- 输入通常来自 KB 内的结构化知识
- 可消费 Intelligence 产出的分析与主题信息
- Follow / Research 可把 KG 作为后续增强层，而不是主执行链路

## 6. 当前事实

- KG 当前是增强模块，不是系统主路径
- 它依赖 LLM 推断，适合在 job 中异步执行，不适合直接挂在同步接口里
