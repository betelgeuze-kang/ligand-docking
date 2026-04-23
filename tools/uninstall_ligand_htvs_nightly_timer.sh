#!/usr/bin/env bash
set -euo pipefail

UNIT_DST_DIR="${HOME}/.config/systemd/user"

systemctl --user disable --now md-ligand-htvs-nightly.timer || true
rm -f "${UNIT_DST_DIR}/md-ligand-htvs-nightly.timer" "${UNIT_DST_DIR}/md-ligand-htvs-nightly.service"

systemctl --user daemon-reload
echo "Removed user timer/service: md-ligand-htvs-nightly.timer, md-ligand-htvs-nightly.service"
