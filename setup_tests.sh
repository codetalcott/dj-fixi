#!/bin/bash
set -e

echo "=== Setting up dj-fixi test environment with uv ==="

# Navigate to project directory
cd "$(dirname "$0")"

# Create venv with uv
echo "Creating virtual environment..."
uv venv --python 3.12

# Install dependencies
echo "Installing dependencies..."
uv pip install -e ".[dev]"

echo "✓ Setup complete"
echo ""
echo "To run tests:"
echo "  source .venv/bin/activate"
echo "  pytest tests/ -v"
