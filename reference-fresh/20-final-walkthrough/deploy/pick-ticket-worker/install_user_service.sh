#!/usr/bin/env bash
set -euo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
repo_root=$(cd -- "${script_dir}/../.." && pwd)
service_template="${script_dir}/tinywms-pick-ticket-worker.service.in"
output_dir="${HOME}/.config/systemd/user"
output_service="${output_dir}/tinywms-pick-ticket-worker.service"

mkdir -p "${output_dir}"
python3 - "$repo_root" "$service_template" "$output_service" <<'PY'
from __future__ import annotations

import sys
from pathlib import Path

repo_root = Path(sys.argv[1])
template = Path(sys.argv[2])
output = Path(sys.argv[3])
content = template.read_text(encoding='utf-8').replace('@REPO_ROOT@', str(repo_root))
output.write_text(content, encoding='utf-8')
print(output)
PY

systemctl --user daemon-reload
systemctl --user enable --now tinywms-pick-ticket-worker.service
printf 'Rendered and started user service for %s\n' "${repo_root}"
