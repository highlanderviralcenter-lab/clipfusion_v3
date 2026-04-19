#!/bin/bash
# Executa a aplicação ClipFusion V3 via CLI.
set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_ROOT"
python3 -m app.main "$@"
