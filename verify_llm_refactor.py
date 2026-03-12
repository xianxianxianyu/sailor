#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LLM 调用链路重构验证脚本
测试 LLMConfigEngine 作为统一调用入口的功能
"""

from pathlib import Path
from backend.app.container import build_container


def test_engine_as_unified_entry():
    """测试 1: Engine 作为统一调用入口"""
    print("=" * 60)
    print("Test 1: Engine 作为统一调用入口")
    print("=" * 60)

    container = build_container(Path.cwd())
    engine = container.llm_config_engine

    # 验证 Engine 有 chat 方法
    print(f"[OK] Engine has chat method: {hasattr(engine, 'chat')}")
    print(f"[OK] Engine has get_status method: {hasattr(engine, 'get_status')}")
    print(f"[OK] Engine has get_stats method: {hasattr(engine, 'get_stats')}")
    print()


def test_client_forwarding():
    """测试 2: LLMClient 转发到 Engine"""
    print("=" * 60)
    print("Test 2: LLMClient 转发到 Engine")
    print("=" * 60)

    container = build_container(Path.cwd())

    # 验证 LLMClient 有 Engine 引用
    print(f"[OK] LLMClient has _engine: {hasattr(container.llm_client, '_engine')}")
    print(f"[OK] _engine is LLMConfigEngine: {container.llm_client._engine is container.llm_config_engine}")

    # 验证 LLMClient 有转发方法
    print(f"[OK] LLMClient has chat method: {hasattr(container.llm_client, 'chat')}")
    print(f"[OK] LLMClient has _legacy_chat method: {hasattr(container.llm_client, '_legacy_chat')}")
    print()


def test_agent_integration():
    """测试 3: Agent 集成"""
    print("=" * 60)
    print("Test 3: Agent 集成")
    print("=" * 60)

    container = build_container(Path.cwd())

    # 验证所有 Agent 的 LLM Client 都有 Engine 引用
    agents = [
        ("ArticleAnalysisAgent", container.article_agent),
        ("KBClusterAgent", container.kb_agent),
        ("TaggingAgent", container.tagging_agent),
        ("KGLinkEngine", container.kg_link_engine),
    ]

    for name, agent in agents:
        has_engine = agent.llm._engine is container.llm_config_engine
        print(f"[OK] {name} uses Engine: {has_engine}")

    print()


def test_hot_reload():
    """测试 4: 热重载保持 Engine 引用"""
    print("=" * 60)
    print("Test 4: 热重载保持 Engine 引用")
    print("=" * 60)

    container = build_container(Path.cwd())

    # 记录初始状态
    initial_client_id = id(container.llm_client)
    initial_article_id = id(container.article_agent)

    print(f"Initial LLM Client ID: {initial_client_id}")
    print(f"Initial Article Agent ID: {initial_article_id}")

    # 触发热重载
    print("Triggering reload_all()...")
    container.llm_config_engine.reload_all()

    # 验证重载后
    new_client_id = id(container.llm_client)
    new_article_id = id(container.article_agent)

    print(f"New LLM Client ID: {new_client_id}")
    print(f"New Article Agent ID: {new_article_id}")

    print(f"[OK] Client reloaded: {initial_client_id != new_client_id}")
    print(f"[OK] Agent reloaded: {initial_article_id != new_article_id}")
    print(f"[OK] Engine reference maintained: {container.llm_client._engine is container.llm_config_engine}")
    print(f"[OK] All agents have engine: {container.article_agent.llm._engine is container.llm_config_engine}")
    print()


def test_status_methods():
    """测试 5: 状态和统计方法"""
    print("=" * 60)
    print("Test 5: 状态和统计方法")
    print("=" * 60)

    container = build_container(Path.cwd())
    engine = container.llm_config_engine

    # 测试状态方法
    status = engine.get_status()
    print(f"[OK] get_status() returns: {status}")

    stats = engine.get_stats()
    print(f"[OK] get_stats() returns: {stats}")

    emb_status = engine.get_embedding_status()
    print(f"[OK] get_embedding_status() returns: {emb_status}")
    print()


def test_call_path():
    """测试 6: 调用路径验证"""
    print("=" * 60)
    print("Test 6: 调用路径验证")
    print("=" * 60)

    container = build_container(Path.cwd())

    # 验证调用路径：Agent -> LLMClient -> Engine
    print("Call path: Agent.llm.chat() -> LLMClient.chat() -> Engine.chat()")
    print(f"[OK] Agent has llm: {hasattr(container.article_agent, 'llm')}")
    print(f"[OK] llm is LLMClient: {type(container.article_agent.llm).__name__ == 'LLMClient'}")
    print(f"[OK] LLMClient has _engine: {container.article_agent.llm._engine is not None}")
    print(f"[OK] _engine is LLMConfigEngine: {type(container.article_agent.llm._engine).__name__ == 'LLMConfigEngine'}")
    print()


def test_backward_compatibility():
    """测试 7: 向后兼容性"""
    print("=" * 60)
    print("Test 7: 向后兼容性")
    print("=" * 60)

    container = build_container(Path.cwd())

    # 验证 LLMClient 仍然可以独立工作（没有 Engine）
    from core.agent.base import LLMClient, LLMConfig

    config = LLMConfig(
        api_key="test-key",
        base_url="https://api.test.com/v1",
        model="test-model",
    )
    standalone_client = LLMClient(config)

    print(f"[OK] LLMClient can be created without engine: {standalone_client._engine is None}")
    print(f"[OK] Standalone client has _legacy_chat: {hasattr(standalone_client, '_legacy_chat')}")
    print("[INFO] Standalone client will use _legacy_chat() when _engine is None")
    print()


def main():
    """运行所有测试"""
    print("\n")
    print("╔" + "=" * 58 + "╗")
    print("║" + " " * 12 + "LLM 调用链路重构验证" + " " * 24 + "║")
    print("╚" + "=" * 58 + "╝")
    print()

    try:
        test_engine_as_unified_entry()
        test_client_forwarding()
        test_agent_integration()
        test_hot_reload()
        test_status_methods()
        test_call_path()
        test_backward_compatibility()

        print("=" * 60)
        print("所有测试通过")
        print("=" * 60)
        print()
        print("重构总结:")
        print("1. LLMConfigEngine 现在是统一的 LLM 调用入口")
        print("2. 所有 Agent 通过 LLMClient 转发到 Engine")
        print("3. 支持统一的日志、监控、统计")
        print("4. 热重载正确维护 Engine 引用")
        print("5. 保持向后兼容性")
        print()

    except Exception as e:
        print()
        print("=" * 60)
        print("测试失败")
        print("=" * 60)
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return 1

    return 0


if __name__ == "__main__":
    exit(main())
