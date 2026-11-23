#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
export VOSK_MODEL_PATH="${VOSK_MODEL_PATH:-$HOME/robot-live-voice/models/vosk-model-small-en-us-0.15}"
exec .venv/bin/uvicorn app:app --host 127.0.0.1 --port 8001 --no-access-log --log-level warning
