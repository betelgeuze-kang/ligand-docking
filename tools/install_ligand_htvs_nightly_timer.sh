#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
UNIT_SRC_DIR="${ROOT_DIR}/ops/systemd"
UNIT_DST_DIR="${HOME}/.config/systemd/user"

mkdir -p "${UNIT_DST_DIR}"
cp -f "${UNIT_SRC_DIR}/md-ligand-htvs-nightly.service" "${UNIT_DST_DIR}/"
cp -f "${UNIT_SRC_DIR}/md-ligand-htvs-nightly.timer" "${UNIT_DST_DIR}/"

systemctl --user daemon-reload
systemctl --user enable --now md-ligand-htvs-nightly.timer
systemctl --user status md-ligand-htvs-nightly.timer --no-pager || true

echo "Installed user timer: md-ligand-htvs-nightly.timer"
