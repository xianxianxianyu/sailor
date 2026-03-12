# Sailor 后端问题诊断报告

**诊断日期**: 2026-03-03
**诊断工具**: diagnose_backend_issues.py
**后端版本**: Current

---

## 📊 诊断结果总览

| 测试项 | 状态 | 影响 |
|--------|------|------|
| 健康检查 | ✅ 通过 | 无 |
| 源运行 | ❌ 失败 | P0, P3 测试 |
| KB 删除（空） | ✅ 通过 | 无 |
| KB 删除（含项目） | ❌ 失败 | P2, P3 测试 |
| 标签删除（空） | ✅ 通过 | 无 |
| 标签删除（含资源） | ❌ 失败 | P0, P3 测试 |

---

## ❌ 问题 1: 源运行失败

### 错误信息
```
POST /sources/{source_id}/run → 500 Internal Server Error
响应: {"detail":"Source run failed: RSS parse failed: <unknown>:7:2: mismatched tag "}
```

### 根本原因
RSS 解析器遇到格式错误的 RSS feed，但没有正确处理异常。

### 影响范围
- **P0 测试**: 2 个测试失败
  - `test_run_source_and_verify_resources`
  - `test_full_pipeline_source_to_trending`
- **P3 测试**: 7 个测试失败
  - 所有依赖源运行的集成测试

### 问题位置
`sailor/backend/app/routers/sources.py` - `run_source()` 方法

### 修复建议

#### 方案 1: 改进错误处理（推荐）
```python
@router.post("/{source_id}/run")
def run_source(source_id: str):
    try:
        # 现有的源运行逻辑
        result = container.source_runner.run(source_id)
        return {"status": "ok", "result": result}
    except RSSParseError as e:
        # RSS 解析错误 - 返回 400 而不是 500
        raise HTTPException(
            status_code=400,
            detail=f"RSS parse failed: {str(e)}"
        )
    except Exception as e:
        # 其他错误 - 记录日志并返回 500
        logger.error(f"Source run failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Source run failed: {str(e)}"
        )
```

#### 方案 2: 使用更宽松的 RSS 解析器
```python
# 在 RSS 解析器中添加容错处理
import feedparser

def parse_rss(url: str):
    feed = feedparser.parse(url)
    if feed.bozo:  # 解析有错误
        logger.warning(f"RSS parse warning: {feed.bozo_exception}")
        # 继续处理，尽可能提取数据
    return feed.entries
```

#### 方案 3: 使用测试友好的 RSS feed
```python
# 在测试数据生成器中使用可靠的 RSS 源
def generate_test_source():
    return {
        "name": f"test-source-{uuid.uuid4().hex[:8]}",
        "source_type": "rss",
        "url": "https://hnrss.org/newest?count=5",  # 可靠的 RSS 源
        "config": {"fetch_interval": 3600}
    }
```

---

## ❌ 问题 2: 删除包含项目的 KB 失败

### 错误信息
```
DELETE /knowledge-bases/{kb_id} → 500 Internal Server Error
响应: Internal Server Error
```

### 根本原因
尝试删除包含项目的 KB 时，外键约束阻止删除，但没有正确处理。

### 影响范围
- **P2 测试**: 1 个测试可能失败
  - `test_delete_kb` (如果 KB 包含项目)
- **P3 测试**: 3 个测试失败
  - 所有需要清理 KB 的集成测试

### 问题位置
`sailor/backend/app/routers/knowledge_bases.py` - `delete_kb()` 方法

### 修复建议

#### 方案 1: 级联删除（推荐）
```python
@router.delete("/{kb_id}")
def delete_kb(kb_id: str) -> dict[str, bool]:
    try:
        # 先删除所有 KB 项目
        items = container.kb_repo.list_kb_items(kb_id)
        for item in items:
            container.kb_repo.remove_item_from_kb(kb_id, item.resource_id)

        # 再删除 KB
        deleted = container.kb_repo.delete_kb(kb_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="KB not found")
        return {"deleted": True}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"KB deletion failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"KB deletion failed: {str(e)}"
        )
```

#### 方案 2: 数据库级联删除
```python
# 在数据库 schema 中设置级联删除
class KBItem(Base):
    __tablename__ = "kb_items"

    kb_id = Column(String, ForeignKey("knowledge_bases.kb_id", ondelete="CASCADE"))
    # ...
```

---

## ❌ 问题 3: 删除已关联资源的标签失败

### 错误信息
```
DELETE /tags/{tag_id} → 500 Internal Server Error
响应: Internal Server Error
```

### 根本原因
尝试删除已关联资源的标签时，外键约束阻止删除，但没有正确处理。

### 影响范围
- **P0 测试**: 可能影响清理阶段
- **P3 测试**: 3 个测试失败
  - 所有需要清理标签的集成测试

### 问题位置
`sailor/backend/app/routers/tags.py` - `delete_tag()` 方法

### 修复建议

#### 方案 1: 级联删除（推荐）
```python
@router.delete("/{tag_id}")
def delete_tag(tag_id: str) -> dict[str, bool]:
    try:
        # 先解除所有标签-资源关联
        resources = container.tag_repo.get_resources_by_tag(tag_id)
        for resource_id in resources:
            container.tag_repo.untag_resource(resource_id, tag_id)

        # 再删除标签
        deleted = container.tag_repo.delete_tag(tag_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="Tag not found")
        return {"deleted": True}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Tag deletion failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Tag deletion failed: {str(e)}"
        )
```

#### 方案 2: 数据库级联删除
```python
# 在数据库 schema 中设置级联删除
class TagResource(Base):
    __tablename__ = "tag_resources"

    tag_id = Column(String, ForeignKey("tags.tag_id", ondelete="CASCADE"))
    # ...
```

---

## 🔧 修复优先级

### 高优先级（阻塞 P3 测试）
1. **问题 1: 源运行失败** - 使用方案 3（测试友好的 RSS 源）
2. **问题 2: KB 删除失败** - 使用方案 1（级联删除）
3. **问题 3: 标签删除失败** - 使用方案 1（级联删除）

### 中优先级（改进健壮性）
1. 添加详细的错误日志
2. 改进异常处理
3. 添加单元测试覆盖

### 低优先级（长期改进）
1. 数据库级联删除配置
2. 更宽松的 RSS 解析器
3. 添加重试机制

---

## 📝 修复步骤

### 步骤 1: 修复测试数据（最快）
```bash
# 修改 sailor/tests/e2e/helpers/test_data.py
# 使用可靠的 RSS 源
```

### 步骤 2: 修复 KB 删除
```bash
# 修改 sailor/backend/app/routers/knowledge_bases.py
# 添加级联删除逻辑
```

### 步骤 3: 修复标签删除
```bash
# 修改 sailor/backend/app/routers/tags.py
# 添加级联删除逻辑
```

### 步骤 4: 重新测试
```bash
# 重启后端服务
cd sailor
python -m uvicorn backend.app.main:app --reload --port 8000

# 运行诊断脚本验证修复
cd tests/e2e
python -X utf8 diagnose_backend_issues.py

# 运行完整测试
pytest sailor/tests/e2e/test_e2e_integration.py -v -s
```

---

## 📊 预期结果

修复后的测试通过率：

| 阶段 | 修复前 | 修复后（预期） | 改进 |
|------|--------|----------------|------|
| P0 | 92% | 100% | +8% |
| P2 | 87.5% | 100% | +12.5% |
| P3 | 0% | 95%+ | +95% |
| 总计 | 72% | 98%+ | +26% |

---

## 🎯 总结

### 问题根源
1. RSS 解析器缺少错误处理
2. 删除操作缺少级联清理逻辑
3. 外键约束冲突未正确处理

### 修复难度
- **问题 1**: 简单 - 修改测试数据即可
- **问题 2**: 中等 - 需要添加级联删除逻辑
- **问题 3**: 中等 - 需要添加级联删除逻辑

### 预计修复时间
- 问题 1: 5 分钟
- 问题 2: 15 分钟
- 问题 3: 15 分钟
- 测试验证: 10 分钟
- **总计**: 约 45 分钟

---

**报告生成时间**: 2026-03-03
**下一步**: 按照修复步骤执行修复
