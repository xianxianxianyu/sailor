#!/usr/bin/env python3
"""诊断脚本 - 识别后端 500 错误的具体原因"""

import sys
import os

# Add parent directory to path
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

import requests
import json

# Import from local helpers
from helpers.api_client import NewsAPIClient
from helpers.kb_api_client import KBAPIClient
from helpers.test_data import generate_test_source, generate_test_tag

BASE_URL = "http://localhost:8000"

def test_health():
    """测试健康检查"""
    print("\n=== 1. 健康检查 ===")
    try:
        response = requests.get(f"{BASE_URL}/healthz")
        print(f"✅ 健康检查: {response.status_code} - {response.json()}")
        return True
    except Exception as e:
        print(f"❌ 健康检查失败: {e}")
        return False

def test_source_run():
    """测试源运行"""
    print("\n=== 2. 测试源运行 ===")
    api = NewsAPIClient(BASE_URL)

    try:
        # 创建测试源
        source_data = generate_test_source()
        source = api.create_source(source_data)
        source_id = source["source_id"]
        print(f"✅ 创建源成功: {source_id}")

        # 尝试运行源
        print(f"尝试运行源 {source_id}...")
        try:
            result = api.run_source(source_id)
            print(f"✅ 运行源成功: {result}")

            # 清理
            api.delete_source(source_id)
            return True
        except requests.exceptions.HTTPError as e:
            print(f"❌ 运行源失败: {e.response.status_code}")
            print(f"响应内容: {e.response.text}")

            # 尝试清理
            try:
                api.delete_source(source_id)
            except:
                pass
            return False

    except Exception as e:
        print(f"❌ 测试源运行失败: {e}")
        return False

def test_kb_deletion():
    """测试 KB 删除"""
    print("\n=== 3. 测试 KB 删除 ===")
    kb_client = KBAPIClient(BASE_URL)

    try:
        # 创建测试 KB
        kb = kb_client.create_kb("test-diagnose-kb", "Test KB for diagnosis")
        kb_id = kb["kb_id"]
        print(f"✅ 创建 KB 成功: {kb_id}")

        # 尝试删除 KB
        print(f"尝试删除 KB {kb_id}...")
        try:
            kb_client.delete_kb(kb_id)
            print(f"✅ 删除 KB 成功")
            return True
        except requests.exceptions.HTTPError as e:
            print(f"❌ 删除 KB 失败: {e.response.status_code}")
            print(f"响应内容: {e.response.text}")
            return False

    except Exception as e:
        print(f"❌ 测试 KB 删除失败: {e}")
        return False

def test_kb_with_items_deletion():
    """测试删除包含项目的 KB"""
    print("\n=== 4. 测试删除包含项目的 KB ===")
    api = NewsAPIClient(BASE_URL)
    kb_client = KBAPIClient(BASE_URL)

    try:
        # 获取一个资源
        resources = api.list_resources(limit=1)
        if not resources:
            print("⚠️ 没有可用资源，跳过此测试")
            return None

        resource_id = resources[0]["resource_id"]
        print(f"使用资源: {resource_id}")

        # 创建 KB 并添加资源
        kb = kb_client.create_kb("test-diagnose-kb-with-items", "Test KB with items")
        kb_id = kb["kb_id"]
        print(f"✅ 创建 KB 成功: {kb_id}")

        kb_client.add_item_to_kb(kb_id, resource_id)
        print(f"✅ 添加资源到 KB 成功")

        # 尝试删除包含项目的 KB
        print(f"尝试删除包含项目的 KB {kb_id}...")
        try:
            kb_client.delete_kb(kb_id)
            print(f"✅ 删除包含项目的 KB 成功")
            return True
        except requests.exceptions.HTTPError as e:
            print(f"❌ 删除包含项目的 KB 失败: {e.response.status_code}")
            print(f"响应内容: {e.response.text}")
            return False

    except Exception as e:
        print(f"❌ 测试删除包含项目的 KB 失败: {e}")
        return False

def test_tag_deletion():
    """测试标签删除"""
    print("\n=== 5. 测试标签删除 ===")
    api = NewsAPIClient(BASE_URL)

    try:
        # 创建测试标签
        tag_data = generate_test_tag()
        tag = api.create_tag(tag_data["name"], tag_data["color"], tag_data["weight"])
        tag_id = tag["tag_id"]
        print(f"✅ 创建标签成功: {tag_id}")

        # 尝试删除标签
        print(f"尝试删除标签 {tag_id}...")
        try:
            api.delete_tag(tag_id)
            print(f"✅ 删除标签成功")
            return True
        except requests.exceptions.HTTPError as e:
            print(f"❌ 删除标签失败: {e.response.status_code}")
            print(f"响应内容: {e.response.text}")
            return False

    except Exception as e:
        print(f"❌ 测试标签删除失败: {e}")
        return False

def test_tag_with_resources_deletion():
    """测试删除已关联资源的标签"""
    print("\n=== 6. 测试删除已关联资源的标签 ===")
    api = NewsAPIClient(BASE_URL)

    try:
        # 获取一个资源
        resources = api.list_resources(limit=1)
        if not resources:
            print("⚠️ 没有可用资源，跳过此测试")
            return None

        resource_id = resources[0]["resource_id"]
        print(f"使用资源: {resource_id}")

        # 创建标签并关联资源
        tag_data = generate_test_tag()
        tag = api.create_tag(tag_data["name"], tag_data["color"], tag_data["weight"])
        tag_id = tag["tag_id"]
        print(f"✅ 创建标签成功: {tag_id}")

        api.tag_resource(resource_id, tag_id)
        print(f"✅ 关联资源到标签成功")

        # 尝试删除已关联资源的标签
        print(f"尝试删除已关联资源的标签 {tag_id}...")
        try:
            api.delete_tag(tag_id)
            print(f"✅ 删除已关联资源的标签成功")
            return True
        except requests.exceptions.HTTPError as e:
            print(f"❌ 删除已关联资源的标签失败: {e.response.status_code}")
            print(f"响应内容: {e.response.text}")
            return False

    except Exception as e:
        print(f"❌ 测试删除已关联资源的标签失败: {e}")
        return False

def main():
    """运行所有诊断测试"""
    print("=" * 60)
    print("Sailor 后端问题诊断脚本")
    print("=" * 60)

    results = {}

    # 运行所有测试
    results["health"] = test_health()
    results["source_run"] = test_source_run()
    results["kb_deletion"] = test_kb_deletion()
    results["kb_with_items_deletion"] = test_kb_with_items_deletion()
    results["tag_deletion"] = test_tag_deletion()
    results["tag_with_resources_deletion"] = test_tag_with_resources_deletion()

    # 总结
    print("\n" + "=" * 60)
    print("诊断结果总结")
    print("=" * 60)

    for test_name, result in results.items():
        if result is True:
            status = "✅ 通过"
        elif result is False:
            status = "❌ 失败"
        else:
            status = "⚠️ 跳过"
        print(f"{test_name:30s}: {status}")

    # 问题分析
    print("\n" + "=" * 60)
    print("问题分析")
    print("=" * 60)

    if not results["source_run"]:
        print("\n❌ 问题 1: 源运行失败")
        print("   位置: sailor/backend/app/routers/sources.py")
        print("   建议: 检查源运行逻辑，添加异常处理和日志")

    if not results["kb_deletion"]:
        print("\n❌ 问题 2: KB 删除失败")
        print("   位置: sailor/backend/app/routers/knowledge_bases.py")
        print("   建议: 检查删除逻辑，可能是外键约束或级联删除问题")

    if results["kb_deletion"] and not results["kb_with_items_deletion"]:
        print("\n❌ 问题 3: 删除包含项目的 KB 失败")
        print("   位置: sailor/backend/app/routers/knowledge_bases.py")
        print("   建议: 需要先删除 KB 项目或使用级联删除")

    if not results["tag_deletion"]:
        print("\n❌ 问题 4: 标签删除失败")
        print("   位置: sailor/backend/app/routers/tags.py")
        print("   建议: 检查删除逻辑，添加异常处理")

    if results["tag_deletion"] and not results["tag_with_resources_deletion"]:
        print("\n❌ 问题 5: 删除已关联资源的标签失败")
        print("   位置: sailor/backend/app/routers/tags.py")
        print("   建议: 需要先解除标签-资源关联或使用级联删除")

    print("\n" + "=" * 60)

if __name__ == "__main__":
    main()
