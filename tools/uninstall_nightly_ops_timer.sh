#!/usr/bin/env bash
set -euo pipefail

UNIT_DST_DIR="${HOME}/.config/systemd/user"

systemctl --user disable --now md-nightly-ops.timer || true
rm -f "${UNIT_DST_DIR}/md-nightly-ops.timer" "${UNIT_DST_DIR}/md-nightly-ops.service"
systemctl --user daemon-reload

echo "Removed user timer/service: md-nightly-ops.timer, md-nightly-ops.service"
