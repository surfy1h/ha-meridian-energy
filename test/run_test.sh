#!/bin/bash

# Meridian API Test Runner
echo "🧪 Meridian Energy API Test Runner"
echo "=================================="

# Check if Python 3 is available
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is required but not installed"
    exit 1
fi

# Install requirements if needed
echo "📦 Installing requirements..."
pip3 install -r requirements.txt

echo ""
echo "🚀 Starting API tests..."
echo "You can provide credentials as arguments: ./run_test.sh username password"
echo "Or enter them when prompted."
echo ""

# Run the test
python3 test_meridian_api.py "$@"