#!/bin/bash
set -euo pipefail
export PATH=/opt/homebrew/bin:/usr/bin:/bin
export PYTHONDONTWRITEBYTECODE=1
exec python3.13 "$(dirname "$0")/links_daily.py" "$@"
