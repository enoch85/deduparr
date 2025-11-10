#!/bin/bash
# Test script - Format, lint, and test the entire codebase

set -e  # Exit on error

echo "🎨 Formatting backend code with black..."
cd /workspaces/deduparr
black .

echo ""
echo "🔍 Linting and fixing backend with ruff..."
ruff check --fix .

if ! ruff check .; then
    echo ""
    echo "❌ You need to fix the remaining backend issues before you can proceed."
    echo "   When fixed, please run the test again."
    exit 1
fi

echo ""
echo "🎨 Formatting frontend code with prettier..."
cd frontend
npm run format

echo ""
echo "🔍 Linting frontend code..."
npm run lint

echo ""
echo "🧹 Removing all cache files..."
cd /workspaces/deduparr
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
find . -type f -name "*.pyc" -delete 2>/dev/null || true

echo ""
echo "🧪 Running backend tests..."
cd backend
python -m pytest -v --tb=short 2>&1 | tail -50

echo ""
echo "✅ All done!"
