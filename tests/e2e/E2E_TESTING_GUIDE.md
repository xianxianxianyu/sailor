# Sailor 端到端测试完整指南

## 测试概览

Sailor 系统的端到端测试分为三个优先级阶段，共 **44 个测试用例**：

```
📊 测试统计
├─ P0: News/Trending 系统 (13 测试) - test_e2e_news_system.py
├─ P2: KB 知识库系统 (16 测试) - test_e2e_kb_system.py
└─ P3: 跨系统集成 (15 测试) - test_e2e_integration.py
   总计: 44 个测试
```

---

## 🚀 前置准备

### 1. 启动后端服务

```bash
# 进入项目目录
cd E:\OS

# 启动后端服务（端口 8000）
python -m uvicorn backend.app.main:app --reload --port 8000
```

### 2. 验证服务运行

```bash
# 检查健康状态
curl http://localhost:8000/healthz

# 预期输出
{"status": "ok"}
```

### 3. 安装测试依赖

```bash
pip install pytest pytest-html requests
```

---

## 📋 P0: News/Trending 系统测试

### 测试范围
验证新闻源、论文源、标签、趋势报告和 Sniffer 搜索功能。

### 测试结构（13 个测试）

```
TestSourceManagement (3 测试)
├─ test_create_and_list_source          # 创建和列出 RSS 源
├─ test_run_source_and_verify_resources # 运行源并验证资源收集
└─ test_delete_source                   # 删除源

TestPaperSourceManagement (2 测试)
├─ test_create_and_list_paper_source    # 创建和列出论文源
└─ test_run_paper_source_and_verify_papers # 运行论文源并验证论文收集

TestTagging (3 测试)
├─ test_create_and_list_tags            # 创建和列出标签
├─ test_tag_resource                    # 给资源打标签
└─ test_list_resources_by_tag           # 按标签筛选资源

TestTrending (2 测试)
├─ test_get_trending_report             # 获取趋势报告（无 LLM）
└─ test_generate_trending_with_llm      # 生成趋势报告（带 LLM）⏭️

TestSniffer (2 测试)
├─ test_sniffer_search                  # 执行 Sniffer 搜索 ⏭️
└─ test_create_and_run_pack             # 创建并运行 Sniffer Pack ⏭️

TestE2EFlow (1 测试)
└─ test_complete_news_workflow          # 完整新闻工作流
```

### 执行步骤

#### 步骤 1: 运行所有 P0 测试

```bash
pytest tests/e2e/test_e2e_news_system.py -v -s
```

**预期输出：**
```
tests/e2e/test_e2e_news_system.py::TestSourceManagement::test_create_and_list_source PASSED
tests/e2e/test_e2e_news_system.py::TestSourceManagement::test_run_source_and_verify_resources PASSED
tests/e2e/test_e2e_news_system.py::TestSourceManagement::test_delete_source PASSED
tests/e2e/test_e2e_news_system.py::TestPaperSourceManagement::test_create_and_list_paper_source PASSED
tests/e2e/test_e2e_news_system.py::TestPaperSourceManagement::test_run_paper_source_and_verify_papers PASSED
tests/e2e/test_e2e_news_system.py::TestTagging::test_create_and_list_tags PASSED
tests/e2e/test_e2e_news_system.py::TestTagging::test_tag_resource PASSED
tests/e2e/test_e2e_news_system.py::TestTagging::test_list_resources_by_tag PASSED
tests/e2e/test_e2e_news_system.py::TestTrending::test_get_trending_report PASSED
tests/e2e/test_e2e_news_system.py::TestTrending::test_generate_trending_with_llm SKIPPED
tests/e2e/test_e2e_news_system.py::TestSniffer::test_sniffer_search SKIPPED
tests/e2e/test_e2e_news_system.py::TestSniffer::test_create_and_run_pack SKIPPED
tests/e2e/test_e2e_news_system.py::TestE2EFlow::test_complete_news_workflow PASSED

========== 10 passed, 3 skipped in 15-30s ==========
```

#### 步骤 2: 按测试类运行

```bash
# 源管理测试
pytest tests/e2e/test_e2e_news_system.py::TestSourceManagement -v -s

# 标签测试
pytest tests/e2e/test_e2e_news_system.py::TestTagging -v -s

# 趋势测试
pytest tests/e2e/test_e2e_news_system.py::TestTrending -v -s
```

#### 步骤 3: 运行单个测试

```bash
# 测试资源收集
pytest tests/e2e/test_e2e_news_system.py::TestSourceManagement::test_run_source_and_verify_resources -v -s

# 测试完整工作流
pytest tests/e2e/test_e2e_news_system.py::TestE2EFlow::test_complete_news_workflow -v -s
```

### 成功标准

- ✅ 至少 10 个测试通过（跳过 3 个需要外部服务的测试）
- ✅ 源创建和运行成功
- ✅ 资源被正确收集
- ✅ 标签系统正常工作
- ✅ 趋势报告生成成功

---

## 📋 P2: KB 知识库系统测试

### 测试范围
验证知识库 CRUD、资源管理、分析、报告生成和知识图谱功能。

### 测试结构（16 个测试）

```
TestKBManagement (2 测试)
├─ test_create_and_list_kb              # 创建和列出知识库
└─ test_delete_kb                       # 删除知识库

TestKBItems (4 测试)
├─ test_add_resource_to_kb              # 添加资源到知识库
├─ test_list_kb_items                   # 列出知识库项目
├─ test_remove_resource_from_kb         # 从知识库移除资源
└─ test_add_multiple_resources          # 添加多个资源

TestResourceAnalysis (3 测试)
├─ test_analyze_resource                # 分析单个资源 ⏭️
├─ test_batch_analyze_resources         # 批量分析资源 ⏭️
└─ test_get_resource_analysis           # 获取资源分析结果

TestKBReports (4 测试)
├─ test_generate_kb_report              # 生成知识库报告 ⏭️
├─ test_list_kb_reports                 # 列出知识库报告
├─ test_get_kb_report                   # 获取知识库报告详情
└─ test_delete_kb_report                # 删除知识库报告

TestKBGraph (2 测试)
├─ test_add_and_list_graph_edges        # 添加和列出图边
└─ test_delete_graph_edge               # 删除图边

TestE2EKBFlow (1 测试)
└─ test_complete_kb_workflow            # 完整知识库工作流
```

### 执行步骤

#### 步骤 1: 运行所有 P2 测试

```bash
pytest tests/e2e/test_e2e_kb_system.py -v -s
```

**预期输出：**
```
tests/e2e/test_e2e_kb_system.py::TestKBManagement::test_create_and_list_kb PASSED
tests/e2e/test_e2e_kb_system.py::TestKBManagement::test_delete_kb PASSED
tests/e2e/test_e2e_kb_system.py::TestKBItems::test_add_resource_to_kb PASSED
tests/e2e/test_e2e_kb_system.py::TestKBItems::test_list_kb_items PASSED
tests/e2e/test_e2e_kb_system.py::TestKBItems::test_remove_resource_from_kb PASSED
tests/e2e/test_e2e_kb_system.py::TestKBItems::test_add_multiple_resources PASSED
tests/e2e/test_e2e_kb_system.py::TestResourceAnalysis::test_analyze_resource SKIPPED
tests/e2e/test_e2e_kb_system.py::TestResourceAnalysis::test_batch_analyze_resources SKIPPED
tests/e2e/test_e2e_kb_system.py::TestResourceAnalysis::test_get_resource_analysis PASSED
tests/e2e/test_e2e_kb_system.py::TestKBReports::test_generate_kb_report SKIPPED
tests/e2e/test_e2e_kb_system.py::TestKBReports::test_list_kb_reports PASSED
tests/e2e/test_e2e_kb_system.py::TestKBReports::test_get_kb_report PASSED
tests/e2e/test_e2e_kb_system.py::TestKBReports::test_delete_kb_report PASSED
tests/e2e/test_e2e_kb_system.py::TestKBGraph::test_add_and_list_graph_edges PASSED
tests/e2e/test_e2e_kb_system.py::TestKBGraph::test_delete_graph_edge PASSED
tests/e2e/test_e2e_kb_system.py::TestE2EKBFlow::test_complete_kb_workflow PASSED

========== 13 passed, 3 skipped in 10-20s ==========
```

#### 步骤 2: 按测试类运行

```bash
# 知识库管理测试
pytest tests/e2e/test_e2e_kb_system.py::TestKBManagement -v -s

# 知识库项目测试
pytest tests/e2e/test_e2e_kb_system.py::TestKBItems -v -s

# 知识图谱测试
pytest tests/e2e/test_e2e_kb_system.py::TestKBGraph -v -s
```

#### 步骤 3: 运行单个测试

```bash
# 测试添加资源到知识库
pytest tests/e2e/test_e2e_kb_system.py::TestKBItems::test_add_resource_to_kb -v -s

# 测试完整工作流
pytest tests/e2e/test_e2e_kb_system.py::TestE2EKBFlow::test_complete_kb_workflow -v -s
```

### 成功标准

- ✅ 至少 13 个测试通过（跳过 3 个需要 LLM 的测试）
- ✅ 知识库 CRUD 操作正常
- ✅ 资源可以添加到知识库
- ✅ 知识图谱功能正常
- ✅ 报告列表和查询功能正常

---

## 📋 P3: 跨系统集成测试

### 测试范围
验证不同子系统之间的数据流、标签权重反馈循环和完整用户工作流。

### 测试结构（15 个测试）

```
TestTagWeightFeedback (3 测试)
├─ test_kb_addition_increments_tag_weights      # KB 添加增加标签权重
├─ test_multiple_kb_additions_accumulate_weight # 多次添加累积权重
└─ test_tag_weights_influence_trending_order    # 权重影响趋势排序

TestSnifferToKBFlow (3 测试) ⏭️ 全部跳过
├─ test_sniffer_result_to_kb_with_provenance    # Sniffer 结果保存到 KB
├─ test_sniffer_provenance_chain_maintained     # 溯源链维护
└─ test_multiple_sniffer_channels_to_kb         # 多渠道结果保存

TestTrendingIntegration (4 测试)
├─ test_trending_autotag_then_kb_weight_boost   # 自动打标后权重提升 ⏭️
├─ test_trending_respects_existing_tags         # 尊重现有标签
├─ test_kb_additions_affect_next_trending       # KB 添加影响趋势
└─ test_trending_groups_by_boosted_tags         # 按权重分组

TestCrossSystemDataFlow (3 测试)
├─ test_resource_lifecycle_across_systems       # 资源跨系统生命周期
├─ test_resource_shared_across_multiple_kbs     # 资源跨多个知识库共享
└─ test_tag_propagation_through_systems         # 标签在系统间传播

TestE2EIntegrationWorkflows (2 测试)
├─ test_complete_user_workflow_source_to_kb     # 完整工作流：源到知识库
└─ test_complete_user_workflow_sniffer_to_kb    # 完整工作流：Sniffer 到知识库 ⏭️
```

### 执行步骤

#### 步骤 1: 运行所有 P3 测试

```bash
pytest tests/e2e/test_e2e_integration.py -v -s
```

**预期输出：**
```
tests/e2e/test_e2e_integration.py::TestTagWeightFeedback::test_kb_addition_increments_tag_weights PASSED
tests/e2e/test_e2e_integration.py::TestTagWeightFeedback::test_multiple_kb_additions_accumulate_weight PASSED
tests/e2e/test_e2e_integration.py::TestTagWeightFeedback::test_tag_weights_influence_trending_order PASSED
tests/e2e/test_e2e_integration.py::TestSnifferToKBFlow::test_sniffer_result_to_kb_with_provenance SKIPPED
tests/e2e/test_e2e_integration.py::TestSnifferToKBFlow::test_sniffer_provenance_chain_maintained SKIPPED
tests/e2e/test_e2e_integration.py::TestSnifferToKBFlow::test_multiple_sniffer_channels_to_kb SKIPPED
tests/e2e/test_e2e_integration.py::TestTrendingIntegration::test_trending_autotag_then_kb_weight_boost SKIPPED
tests/e2e/test_e2e_integration.py::TestTrendingIntegration::test_trending_respects_existing_tags PASSED
tests/e2e/test_e2e_integration.py::TestTrendingIntegration::test_kb_additions_affect_next_trending PASSED
tests/e2e/test_e2e_integration.py::TestTrendingIntegration::test_trending_groups_by_boosted_tags PASSED
tests/e2e/test_e2e_integration.py::TestCrossSystemDataFlow::test_resource_lifecycle_across_systems PASSED
tests/e2e/test_e2e_integration.py::TestCrossSystemDataFlow::test_resource_shared_across_multiple_kbs PASSED
tests/e2e/test_e2e_integration.py::TestCrossSystemDataFlow::test_tag_propagation_through_systems PASSED
tests/e2e/test_e2e_integration.py::TestE2EIntegrationWorkflows::test_complete_user_workflow_source_to_kb PASSED
tests/e2e/test_e2e_integration.py::TestE2EIntegrationWorkflows::test_complete_user_workflow_sniffer_to_kb SKIPPED

========== 10 passed, 5 skipped in 20-40s ==========
```

#### 步骤 2: 按测试类运行

```bash
# 标签权重反馈测试
pytest tests/e2e/test_e2e_integration.py::TestTagWeightFeedback -v -s

# 跨系统数据流测试
pytest tests/e2e/test_e2e_integration.py::TestCrossSystemDataFlow -v -s

# 端到端工作流测试
pytest tests/e2e/test_e2e_integration.py::TestE2EIntegrationWorkflows -v -s
```

#### 步骤 3: 运行单个测试

```bash
# 测试标签权重增加
pytest tests/e2e/test_e2e_integration.py::TestTagWeightFeedback::test_kb_addition_increments_tag_weights -v -s

# 测试完整工作流
pytest tests/e2e/test_e2e_integration.py::TestE2EIntegrationWorkflows::test_complete_user_workflow_source_to_kb -v -s
```

### 成功标准

- ✅ 至少 10 个测试通过（跳过 5 个需要外部服务/LLM 的测试）
- ✅ 标签权重反馈循环正常工作
- ✅ 资源在多个系统间正确流转
- ✅ 跨系统数据一致性维护
- ✅ 完整用户工作流可用

---

## 🎯 完整测试流程

### 方案 1: 按优先级顺序运行

```bash
# 步骤 1: P0 - News/Trending 系统
pytest tests/e2e/test_e2e_news_system.py -v -s
# 预期: 10 passed, 3 skipped

# 步骤 2: P2 - KB 知识库系统
pytest tests/e2e/test_e2e_kb_system.py -v -s
# 预期: 13 passed, 3 skipped

# 步骤 3: P3 - 跨系统集成
pytest tests/e2e/test_e2e_integration.py -v -s
# 预期: 10 passed, 5 skipped

# 总计: 33 passed, 11 skipped
```

### 方案 2: 运行所有测试

```bash
# 运行所有端到端测试
pytest tests/e2e/ -v -s

# 预期输出
========== 33 passed, 11 skipped in 45-90s ==========
```

### 方案 3: 生成 HTML 报告

```bash
# 生成完整的 HTML 测试报告
pytest tests/e2e/ -v --html=e2e_test_report.html --self-contained-html

# 报告将保存在: e2e_test_report.html
# 用浏览器打开查看详细结果
```

---

## 📊 测试结果解读

### 成功的测试运行

```
========== 33 passed, 11 skipped in 60s ==========
```

**说明：**
- ✅ **33 passed**: 核心功能全部正常
- ⏭️ **11 skipped**: 需要外部服务或 LLM 配置的测试被跳过（正常）

### 跳过的测试说明

**需要 LLM 配置（4 个）：**
- `test_generate_trending_with_llm` - 需要 OpenAI/Anthropic API
- `test_analyze_resource` - 需要 LLM 分析
- `test_batch_analyze_resources` - 需要 LLM 批量分析
- `test_generate_kb_report` - 需要 LLM 生成报告
- `test_trending_autotag_then_kb_weight_boost` - 需要 LLM 自动打标

**需要外部服务（7 个）：**
- `test_sniffer_search` - 需要 GitHub/arXiv API
- `test_create_and_run_pack` - 需要 Sniffer 服务
- `test_sniffer_result_to_kb_with_provenance` - 需要 Sniffer 服务
- `test_sniffer_provenance_chain_maintained` - 需要 Sniffer 服务
- `test_multiple_sniffer_channels_to_kb` - 需要 Sniffer 服务
- `test_complete_user_workflow_sniffer_to_kb` - 需要 Sniffer 服务

### 失败处理

如果测试失败，检查：

1. **服务是否运行**
   ```bash
   curl http://localhost:8000/healthz
   ```

2. **端口是否被占用**
   ```bash
   netstat -ano | findstr :8000
   ```

3. **查看详细错误**
   ```bash
   pytest tests/e2e/test_e2e_news_system.py -v -s --tb=long
   ```

---

## 🔧 常见问题

### Q1: 测试运行很慢怎么办？

**A:** 可以并行运行测试（需要安装 pytest-xdist）：
```bash
pip install pytest-xdist
pytest tests/e2e/ -n 3  # 使用 3 个进程
```

### Q2: 如何只运行不跳过的测试？

**A:** 使用 `-k` 参数过滤：
```bash
pytest tests/e2e/ -v -s -k "not sniffer and not llm"
```

### Q3: 如何清理测试数据？

**A:** 测试会自动清理，但如果需要手动清理：
```bash
# 重启服务会清理内存数据
# 或者删除数据库文件（如果使用持久化存储）
```

### Q4: 如何启用 LLM 测试？

**A:** 通过 API 或前端配置 LLM：
```bash
# 通过 API 配置 DeepSeek
curl -X PUT http://localhost:8000/settings/llm \
  -H "Content-Type: application/json" \
  -d '{
    "provider": "deepseek",
    "base_url": "https://api.deepseek.com/v1",
    "model": "deepseek-chat",
    "api_key": "sk-your-key",
    "temperature": 0.3,
    "max_tokens": 1500
  }'

# 验证连接
curl -X POST http://localhost:8000/settings/llm/test

# 然后移除测试中的 @pytest.mark.skip 装饰器
```

---

## 📁 测试文件结构

```
tests/e2e/
├── test_e2e_news_system.py          # P0: News/Trending (13 测试)
├── test_e2e_kb_system.py            # P2: KB System (16 测试)
├── test_e2e_integration.py          # P3: Integration (15 测试)
├── conftest.py                       # Pytest 配置和 fixtures
├── helpers/
│   ├── api_client.py                # News/Trending API 客户端
│   ├── kb_api_client.py             # KB API 客户端
│   ├── integration_helpers.py       # 集成测试辅助函数
│   ├── test_data.py                 # 测试数据生成器
│   └── kb_test_data.py              # KB 测试数据生成器
├── P3_IMPLEMENTATION_SUMMARY.md     # P3 详细文档
└── RUN_P3_TESTS.md                  # P3 快速指南
```

---

## 🎓 总结

### 测试覆盖范围

| 优先级 | 系统 | 测试数 | 通过 | 跳过 | 文件 |
|--------|------|--------|------|------|------|
| P0 | News/Trending | 13 | 10 | 3 | test_e2e_news_system.py |
| P2 | KB System | 16 | 13 | 3 | test_e2e_kb_system.py |
| P3 | Integration | 15 | 10 | 5 | test_e2e_integration.py |
| **总计** | **全系统** | **44** | **33** | **11** | **3 个文件** |

### 核心验证点

✅ **P0 验证：**
- RSS/论文源管理
- 资源收集和存储
- 标签系统
- 趋势报告生成

✅ **P2 验证：**
- 知识库 CRUD
- 资源管理
- 知识图谱
- 报告系统

✅ **P3 验证：**
- 标签权重反馈循环
- 跨系统数据流
- 资源生命周期
- 端到端工作流

### 快速命令参考

```bash
# 运行所有测试
pytest tests/e2e/ -v -s

# 只运行 P0
pytest tests/e2e/test_e2e_news_system.py -v -s

# 只运行 P2
pytest tests/e2e/test_e2e_kb_system.py -v -s

# 只运行 P3
pytest tests/e2e/test_e2e_integration.py -v -s

# 生成 HTML 报告
pytest tests/e2e/ -v --html=report.html --self-contained-html
```

---

**文档版本**: 1.0
**最后更新**: 2026-03-03
**测试总数**: 44 个测试用例
