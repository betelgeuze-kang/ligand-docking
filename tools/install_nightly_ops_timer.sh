#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
UNIT_SRC_DIR="${ROOT_DIR}/ops/systemd"
UNIT_DST_DIR="${HOME}/.config/systemd/user"

mkdir -p "${UNIT_DST_DIR}"
cp -f "${UNIT_SRC_DIR}/md-nightly-ops.service" "${UNIT_DST_DIR}/"
cp -f "${UNIT_SRC_DIR}/md-nightly-ops.timer" "${UNIT_DST_DIR}/"

systemctl --user daemon-reload
systemctl --user enable --now md-nightly-ops.timer
systemctl --user status md-nightly-ops.timer --no-pager || true

echo "Installed user timer: md-nightly-ops.timer"
