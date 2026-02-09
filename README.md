# Sailor

Sailor 是一个最小可运行的闭环示例，包含以下能力：

- RSS / RSSHub + Miniflux 内容采集
- 预处理流水线（normalize -> extract -> clean -> enrich）
- 资源收件箱 + 手动归档到知识库
- 主流程任务自动化（scan -> review -> add to KB）
- React 前端 + FastAPI 后端

## 项目结构

```text
sailor/
  core/
    collector/      # 采集引擎抽象与数据源适配器
    pipeline/       # 预处理流水线基类与阶段实现
    services/       # 入库编排服务
    storage/        # SQLite 表结构与仓储
    tasks/          # 主流程任务抽象
  backend/
    app/            # FastAPI 接口
  frontend/
    src/            # React 应用
  data/
    seed_entries.json
```

## Start（使用 Conda）

### 1) 启动后端

```bash
cd sailor
conda create -n sailor python=3.11 -y
conda activate sailor
pip install -r backend/requirements.txt
uvicorn backend.app.main:app --reload
```

后端默认地址：`http://localhost:8000`

主要 API：

- `POST /tasks/run-ingestion`
- `GET /resources?status=inbox`
- `GET /resources/{resource_id}`
- `GET /knowledge-bases`
- `POST /knowledge-bases/{kb_id}/items`
- `GET /resources/{resource_id}/knowledge-bases`
- `GET /tasks/main-flow`

### 2) 启动前端

```bash
cd sailor/frontend
npm install
npm run dev
```

前端默认地址：`http://localhost:5173`

如果后端不在 `localhost:8000`，请先配置：

```bash
set VITE_API_BASE=http://localhost:8000
```

## 说明

- `RSSCollector` 默认从 `data/seed_entries.json` 加载本地数据，方便稳定地本地测试。
- 提供 `MINIFLUX_BASE_URL` 和 `MINIFLUX_TOKEN` 后，`MinifluxCollector` 会调用 Miniflux API。
- `CollectionEngine` 在进入流水线前，会按 `source + url` 做去重。
- 知识库写入是幂等的（`UNIQUE(kb_id, resource_id)`）。
