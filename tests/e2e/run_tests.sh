#!/bin/bash
# Quick test execution script for News/Trending E2E tests

set -e

echo "=================================================="
echo "News/Trending System E2E Tests - Quick Runner"
echo "=================================================="
echo ""

# Check if service is running
echo "Step 1: Checking service availability..."
python tests/e2e/verify_service.py
if [ $? -ne 0 ]; then
    echo ""
    echo "❌ Service check failed. Please start the service first:"
    echo "   python -m uvicorn backend.app.main:app --reload --port 8000"
    exit 1
fi

echo ""
echo "Step 2: Running E2E tests..."
echo ""

# Run tests with verbose output
pytest tests/e2e/test_e2e_news_system.py -v -s --tb=short

echo ""
echo "=================================================="
echo "Test execution complete!"
echo "=================================================="
