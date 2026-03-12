#!/usr/bin/env python3
"""Verify that the Sailor service is ready for E2E testing."""
import sys
import requests


def check_service(base_url: str = "http://localhost:8000") -> bool:
    """Check if service is running and accessible."""
    try:
        response = requests.get(f"{base_url}/healthz", timeout=5)
        if response.status_code == 200:
            print(f"✅ Service is running at {base_url}")
            return True
        else:
            print(f"❌ Service returned status {response.status_code}")
            return False
    except requests.exceptions.ConnectionError:
        print(f"❌ Cannot connect to service at {base_url}")
        print("   Please start the service with:")
        print("   python -m uvicorn backend.app.main:app --reload --port 8000")
        return False
    except Exception as e:
        print(f"❌ Error checking service: {e}")
        return False


def check_endpoints(base_url: str = "http://localhost:8000") -> dict:
    """Check if key endpoints are accessible."""
    endpoints = {
        "/sources": "Sources API",
        "/tags": "Tags API",
        "/sniffer/packs": "Sniffer API",
    }

    results = {}
    for endpoint, name in endpoints.items():
        try:
            response = requests.get(f"{base_url}{endpoint}", timeout=5)
            if response.status_code in [200, 404]:  # 404 is ok for empty lists
                print(f"✅ {name} accessible")
                results[endpoint] = True
            else:
                print(f"⚠️  {name} returned status {response.status_code}")
                results[endpoint] = False
        except Exception as e:
            print(f"❌ {name} error: {e}")
            results[endpoint] = False

    return results


if __name__ == "__main__":
    print("Checking Sailor service readiness for E2E tests...\n")

    # Check service health
    if not check_service():
        sys.exit(1)

    print("\nChecking API endpoints...")
    results = check_endpoints()

    # Summary
    print("\n" + "=" * 50)
    total = len(results)
    passed = sum(results.values())
    print(f"Endpoint checks: {passed}/{total} passed")

    if passed == total:
        print("\n✅ Service is ready for E2E testing!")
        print("\nRun tests with:")
        print("  pytest tests/e2e/test_e2e_news_system.py -v -s")
        sys.exit(0)
    else:
        print("\n⚠️  Some endpoints are not accessible")
        print("   Tests may fail or skip")
        sys.exit(1)
