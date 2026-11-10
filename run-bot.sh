#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
mkdir -p logs
exec ./venv/bin/python -m app.admin_bot 2>&1 | tee -a logs/bot.log