# Sailor E2E 测试快速参考

## 📊 测试概览

```
总计: 44 个测试
├─ P0: News/Trending 系统 (13 测试) ✅ 10 通过, ⏭️ 3 跳过
├─ P2: KB 知识库系统 (16 测试)    ✅ 13 通过, ⏭️ 3 跳过
└─ P3: 跨系统集成 (15 测试)       ✅ 10 通过, ⏭️ 5 跳过
```

## 🚀 快速开始

### 1. 启动服务
```bash
python -m uvicorn backend.app.main:app --reload --port 8000
```

### 2. 运行测试
```bash
# 运行所有测试
pytest tests/e2e/ -v -s

# 按阶段运行
pytest tests/e2e/test_e2e_news_system.py -v -s    # P0
pytest tests/e2e/test_e2e_kb_system.py -v -s      # P2
pytest tests/e2e/test_e2e_integration.py -v -s    # P3

# 生成报告
pytest tests/e2e/ -v --html=report.html --self-contained-html
```

## 📋 P0: News/Trending 系统 (13 测试)

### 测试内容
- ✅ RSS 源管理 (创建、运行、删除)
- ✅ 论文源管理 (创建、运行)
- ✅ 标签系统 (创建、打标、筛选)
- ✅ 趋势报告 (生成、查询)
- ⏭️ Sniffer 搜索 (需要外部服务)

### 运行命令
```bash
pytest tests/e2e/test_e2e_news_system.py -v -s
```

### 预期结果
```
========== 10 passed, 3 skipped in 15-30s ==========
```

## 📋 P2: KB 知识库系统 (16 测试)

### 测试内容
- ✅ 知识库 CRUD (创建、列出、删除)
- ✅ 资源管理 (添加、移除、列出)
- ✅ 知识图谱 (添加边、删除边)
- ✅ 报告系统 (列出、查询、删除)
- ⏭️ LLM 分析 (需要 API 密钥)

### 运行命令
```bash
pytest tests/e2e/test_e2e_kb_system.py -v -s
```

### 预期结果
```
========== 13 passed, 3 skipped in 10-20s ==========
```

## 📋 P3: 跨系统集成 (15 测试)

### 测试内容
- ✅ 标签权重反馈循环 (KB 添加 → 权重增加)
- ✅ 跨系统数据流 (Source → Resource → KB → Trending)
- ✅ 资源生命周期 (多系统共享)
- ✅ 完整用户工作流 (端到端验证)
- ⏭️ Sniffer 集成 (需要外部服务)

### 运行命令
```bash
pytest tests/e2e/test_e2e_integration.py -v -s
```

### 预期结果
```
========== 10 passed, 5 skipped in 20-40s ==========
```

## 🎯 完整测试流程

### 方案 1: 顺序运行
```bash
# 步骤 1: P0
pytest tests/e2e/test_e2e_news_system.py -v -s
# ✅ 10 passed, ⏭️ 3 skipped

# 步骤 2: P2
pytest tests/e2e/test_e2e_kb_system.py -v -s
# ✅ 13 passed, ⏭️ 3 skipped

# 步骤 3: P3
pytest tests/e2e/test_e2e_integration.py -v -s
# ✅ 10 passed, ⏭️ 5 skipped

# 总计: ✅ 33 passed, ⏭️ 11 skipped
```

### 方案 2: 一次运行
```bash
pytest tests/e2e/ -v -s
# ✅ 33 passed, ⏭️ 11 skipped in 45-90s
```

## 📊 测试详情

### P0 测试类 (6 个类)
```
TestSourceManagement          # RSS 源管理 (3 测试)
TestPaperSourceManagement     # 论文源管理 (2 测试)
TestTagging                   # 标签系统 (3 测试)
TestTrending                  # 趋势报告 (2 测试)
TestSniffer                   # Sniffer 搜索 (2 测试) ⏭️
TestE2EFlow                   # 完整工作流 (1 测试)
```

### P2 测试类 (6 个类)
```
TestKBManagement              # 知识库管理 (2 测试)
TestKBItems                   # 资源管理 (4 测试)
TestResourceAnalysis          # 资源分析 (3 测试) ⏭️ 2 个
TestKBReports                 # 报告系统 (4 测试) ⏭️ 1 个
TestKBGraph                   # 知识图谱 (2 测试)
TestE2EKBFlow                 # 完整工作流 (1 测试)
```

### P3 测试类 (5 个类)
```
TestTagWeightFeedback         # 标签权重反馈 (3 测试)
TestSnifferToKBFlow           # Sniffer 集成 (3 测试) ⏭️
TestTrendingIntegration       # 趋势集成 (4 测试) ⏭️ 1 个
TestCrossSystemDataFlow       # 跨系统数据流 (3 测试)
TestE2EIntegrationWorkflows   # 端到端工作流 (2 测试) ⏭️ 1 个
```

## 🔍 按功能运行测试

### 源管理
```bash
pytest tests/e2e/test_e2e_news_system.py::TestSourceManagement -v -s
pytest tests/e2e/test_e2e_news_system.py::TestPaperSourceManagement -v -s
```

### 标签系统
```bash
pytest tests/e2e/test_e2e_news_system.py::TestTagging -v -s
pytest tests/e2e/test_e2e_integration.py::TestTagWeightFeedback -v -s
```

### 知识库
```bash
pytest tests/e2e/test_e2e_kb_system.py::TestKBManagement -v -s
pytest tests/e2e/test_e2e_kb_system.py::TestKBItems -v -s
```

### 趋势报告
```bash
pytest tests/e2e/test_e2e_news_system.py::TestTrending -v -s
pytest tests/e2e/test_e2e_integration.py::TestTrendingIntegration -v -s
```

### 完整工作流
```bash
pytest tests/e2e/test_e2e_news_system.py::TestE2EFlow -v -s
pytest tests/e2e/test_e2e_kb_system.py::TestE2EKBFlow -v -s
pytest tests/e2e/test_e2e_integration.py::TestE2EIntegrationWorkflows -v -s
```

## 🎯 关键测试用例

### 必须通过的核心测试
```bash
# 资源收集
pytest tests/e2e/test_e2e_news_system.py::TestSourceManagement::test_run_source_and_verify_resources -v -s

# 标签系统
pytest tests/e2e/test_e2e_news_system.py::TestTagging::test_tag_resource -v -s

# 知识库添加
pytest tests/e2e/test_e2e_kb_system.py::TestKBItems::test_add_resource_to_kb -v -s

# 标签权重反馈
pytest tests/e2e/test_e2e_integration.py::TestTagWeightFeedback::test_kb_addition_increments_tag_weights -v -s

# 跨系统数据流
pytest tests/e2e/test_e2e_integration.py::TestCrossSystemDataFlow::test_resource_lifecycle_across_systems -v -s

# 完整工作流
pytest tests/e2e/test_e2e_integration.py::TestE2EIntegrationWorkflows::test_complete_user_workflow_source_to_kb -v -s
```

## 🔧 故障排查

### 服务未启动
```bash
# 检查服务
curl http://localhost:8000/healthz

# 启动服务
python -m uvicorn backend.app.main:app --reload --port 8000
```

### 端口被占用
```bash
# 查找进程
netstat -ano | findstr :8000

# 结束进程
taskkill /PID <PID> /F
```

### 查看详细错误
```bash
pytest tests/e2e/test_e2e_news_system.py -v -s --tb=long
```

## 📈 成功标准

### 整体目标
- ✅ 至少 33 个测试通过
- ⏭️ 11 个测试跳过（正常）
- ❌ 0 个测试失败

### 各阶段目标
- **P0**: ✅ 10/13 通过 (77%)
- **P2**: ✅ 13/16 通过 (81%)
- **P3**: ✅ 10/15 通过 (67%)

### 核心功能验证
- ✅ 源管理和资源收集
- ✅ 标签系统和权重反馈
- ✅ 知识库 CRUD 和资源管理
- ✅ 知识图谱功能
- ✅ 跨系统数据流
- ✅ 端到端用户工作流

## 📚 相关文档

- **完整指南**: `tests/e2e/E2E_TESTING_GUIDE.md`
- **P3 详细文档**: `tests/e2e/P3_IMPLEMENTATION_SUMMARY.md`
- **P3 快速指南**: `tests/e2e/RUN_P3_TESTS.md`

---

**快速命令**
```bash
# 一键运行所有测试
pytest tests/e2e/ -v -s

# 生成 HTML 报告
pytest tests/e2e/ -v --html=report.html --self-contained-html
```
