#!/usr/bin/env bash
# Run the a0 CLI from the repo root.
set -euo pipefail
cd "$(dirname "$0")"
python -m a0.a0 "$@"
