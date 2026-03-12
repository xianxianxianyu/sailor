# LLM Config 模块

## 1. 作用

LLM Config 模块负责统一管理模型配置、密钥存储、调用统计和热重载。

核心代码位置：

- `core/llm_config/engine.py`
- `core/llm_config/repository.py`
- `core/llm_config/adapters.py`
- `core/agent/base.py`
- `backend/app/routers/settings.py`
- `frontend/src/components/LLMSettingsModal.tsx`

## 2. 核心对象

### 2.1 `LLMConfigEngine`

- 读取与保存 LLM / Embedding 配置
- 创建统一 `LLMClient`
- 记录调用次数与 token 统计
- 提供 hot reload

### 2.2 `ConfigRepository`

- 管理 `data/llm_config.json`
- API Key 写系统 keyring

### 2.3 Provider Adapters

- 把不同 provider 适配为统一调用接口
- 当前支持 OpenAI compatible 路径

## 3. 对外接口

主要 API：

- `GET /settings/llm`
- `PUT /settings/llm`
- `POST /settings/llm/test`
- `GET /settings/embedding`
- `PUT /settings/embedding`

## 4. 运行链路

1. 用户通过设置页保存模型配置
2. 非密钥配置写 `data/llm_config.json`
3. 密钥写 keyring
4. `LLMConfigEngine.reload_all()` 热更新 container 内客户端
5. 各 Agent / Engine 共享新的客户端配置

## 5. 与其他模块的关系

- Intelligence、KG、KB Reports 等所有 LLM 能力都依赖它
- Runtime 的日志里看到的 `LLM call` / `LLM response` 也是从这里发出的

## 6. 当前事实

- 当前全局共享同一套 LLM Client
- 各业务模块通常只覆盖单次调用参数，例如 `max_tokens`，底层 provider、模型、温度由这里统一控制
