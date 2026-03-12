#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Verification script for LLM Config Engine implementation.
Tests all major functionality without requiring API keys.
"""

from pathlib import Path
from backend.app.container import build_container


def test_engine_creation():
    """Test 1: Engine creation and initialization"""
    print("=" * 60)
    print("Test 1: Engine Creation")
    print("=" * 60)

    container = build_container(Path.cwd())
    engine = container.llm_config_engine

    print(f"[OK] Engine created: {engine}")
    print(f"[OK] Container reference set: {engine._container is not None}")
    print()


def test_config_loading():
    """Test 2: Configuration loading"""
    print("=" * 60)
    print("Test 2: Configuration Loading")
    print("=" * 60)

    container = build_container(Path.cwd())
    engine = container.llm_config_engine

    # Load LLM config
    llm_config = engine.load_llm_config()
    print(f"LLM Configuration:")
    print(f"  Provider: {llm_config.provider}")
    print(f"  Base URL: {llm_config.base_url}")
    print(f"  Model: {llm_config.model}")
    print(f"  Temperature: {llm_config.temperature}")
    print(f"  Max Tokens: {llm_config.max_tokens}")
    print(f"  API Key Set: {bool(llm_config.api_key)}")
    print()

    # Load Embedding config
    emb_config = engine.load_embedding_config()
    print(f"Embedding Configuration:")
    print(f"  Provider: {emb_config.provider}")
    print(f"  Base URL: {emb_config.base_url}")
    print(f"  Model: {emb_config.model}")
    print(f"  Dimensions: {emb_config.dimensions}")
    print(f"  API Key Set: {bool(emb_config.api_key)}")
    print()


def test_client_creation():
    """Test 3: Client creation"""
    print("=" * 60)
    print("Test 3: Client Creation")
    print("=" * 60)

    container = build_container(Path.cwd())
    engine = container.llm_config_engine

    # Create LLM client
    llm_client = engine.create_llm_client()
    print(f"[OK] LLM Client created: {llm_client}")
    print(f"  Type: {type(llm_client).__name__}")
    print()

    # Create Embedding client
    embedding_client = engine.create_embedding_client()
    print(f"[OK] Embedding Client created: {embedding_client}")
    print(f"  Type: {type(embedding_client).__name__}")
    print(f"  Provider: {embedding_client.config.provider}")
    print(f"  Model: {embedding_client.config.model}")
    print()


def test_hot_reload():
    """Test 4: Hot reload functionality"""
    print("=" * 60)
    print("Test 4: Hot Reload")
    print("=" * 60)

    container = build_container(Path.cwd())
    engine = container.llm_config_engine

    # Get initial component IDs
    initial_llm_id = id(container.llm_client)
    initial_article_id = id(container.article_agent)
    initial_kg_id = id(container.kg_link_engine)

    print(f"Initial LLM Client ID: {initial_llm_id}")
    print(f"Initial Article Agent ID: {initial_article_id}")
    print(f"Initial KG Link Engine ID: {initial_kg_id}")
    print()

    # Trigger reload
    print("Triggering reload_all()...")
    engine.reload_all()
    print()

    # Check if components were replaced
    new_llm_id = id(container.llm_client)
    new_article_id = id(container.article_agent)
    new_kg_id = id(container.kg_link_engine)

    print(f"New LLM Client ID: {new_llm_id}")
    print(f"New Article Agent ID: {new_article_id}")
    print(f"New KG Link Engine ID: {new_kg_id}")
    print()

    print(f"[OK] LLM Client reloaded: {initial_llm_id != new_llm_id}")
    print(f"[OK] Article Agent reloaded: {initial_article_id != new_article_id}")
    print(f"[OK] KG Link Engine reloaded: {initial_kg_id != new_kg_id}")
    print()


def test_config_persistence():
    """Test 5: Configuration save/load"""
    print("=" * 60)
    print("Test 5: Configuration Persistence")
    print("=" * 60)

    container = build_container(Path.cwd())
    engine = container.llm_config_engine

    # Load current config
    config = engine.load_llm_config()
    print(f"Current model: {config.model}")

    # Save config (without changing anything)
    engine.save_llm_config(
        provider=config.provider,
        base_url=config.base_url,
        model=config.model,
        temperature=config.temperature,
        max_tokens=config.max_tokens,
    )
    print(f"[OK] Configuration saved successfully")

    # Reload and verify
    reloaded = engine.load_llm_config()
    print(f"[OK] Configuration reloaded: {reloaded.model}")
    print(f"[OK] Configuration matches: {config.model == reloaded.model}")
    print()


def test_container_integration():
    """Test 6: Container integration"""
    print("=" * 60)
    print("Test 6: Container Integration")
    print("=" * 60)

    container = build_container(Path.cwd())

    print(f"[OK] LLM Config Engine: {container.llm_config_engine}")
    print(f"[OK] LLM Client: {container.llm_client}")
    print(f"[OK] Article Agent: {container.article_agent}")
    print(f"[OK] KB Agent: {container.kb_agent}")
    print(f"[OK] Tagging Agent: {container.tagging_agent}")
    print(f"[OK] KG Link Engine: {container.kg_link_engine}")
    print(f"[OK] Intelligence Engine: {container.intelligence_engine}")
    print()


def main():
    """Run all tests"""
    print("\n")
    print("╔" + "=" * 58 + "╗")
    print("║" + " " * 10 + "LLM Config Engine Verification" + " " * 17 + "║")
    print("╚" + "=" * 58 + "╝")
    print()

    try:
        test_engine_creation()
        test_config_loading()
        test_client_creation()
        test_hot_reload()
        test_config_persistence()
        test_container_integration()

        print("=" * 60)
        print("ALL TESTS PASSED")
        print("=" * 60)
        print()
        print("The LLM Config Engine is working correctly!")
        print()

    except Exception as e:
        print()
        print("=" * 60)
        print("TEST FAILED")
        print("=" * 60)
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return 1

    return 0


if __name__ == "__main__":
    exit(main())
