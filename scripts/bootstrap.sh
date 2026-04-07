#!/bin/bash
# Bootstrap script (Unix)
# Usage: ./scripts/bootstrap.sh [--skip-npm]
set -e
cd "$(dirname "$0")/.."
python3 scripts/bootstrap.py "$@"
