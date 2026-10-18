#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../.."
: "${TINYWMS_PORT:=8000}"
: "${TINYWMS_INVENTORY_FILE:=data/inventory.json}"
export TINYWMS_PORT TINYWMS_INVENTORY_FILE
exec python3 src/http_server.py
