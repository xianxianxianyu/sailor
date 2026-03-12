# Sailor

Sailor 是一个本地优先的信息采集与研究工作台，当前代码主干为 `FastAPI + React + SQLite + 独立 Worker`。

## 快速启动

```bash
npm install
npm --prefix frontend install
pip install -r backend/requirements.txt
npm run dev
```

默认会同时启动：

- Backend：`http://127.0.0.1:8000`
- Frontend：`http://localhost:5173`
- Worker：`python -m backend.worker`

桌面开发模式：

```bash
npm run desktop:dev
```

## 文档入口

- 框架总览：`docs/framework.md`
- Runtime：`docs/modules/runtime.md`
- Sources：`docs/modules/sources.md`
- Sniffer：`docs/modules/sniffer.md`
- Intelligence：`docs/modules/intelligence.md`
- Knowledge Base：`docs/modules/knowledge-base.md`
- KG：`docs/modules/kg.md`
- Board：`docs/modules/board.md`
- Research：`docs/modules/research.md`
- Follow：`docs/modules/follow.md`
- LLM Config：`docs/modules/llm-config.md`

## 当前 UI 模块

- Discover：Sniffer 搜索与搜索包
- Feeds：统一 Sources 管理与运行
- KB：知识库与报告
- Follow：Board / Research / Follow 工作流
- 全局面板：日志、LLM 设置
