#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
exec python -m uvicorn web_test:app --host 127.0.0.1 --port 8001 --no-access-log
