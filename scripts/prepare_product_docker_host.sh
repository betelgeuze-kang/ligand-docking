#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "Preparing Docker host for ROCm product image smoke" >&2

if [[ ! -r /etc/os-release ]]; then
  echo "Missing /etc/os-release; this helper currently targets Ubuntu hosts." >&2
  exit 2
fi

. /etc/os-release
if [[ "${ID:-}" != "ubuntu" ]]; then
  echo "Unsupported host OS: ${ID:-unknown}. Install Docker manually, then run the rocm-runtime smoke." >&2
  exit 2
fi

if ! command -v docker >/dev/null 2>&1; then
  echo "Docker CLI missing; installing docker.io via apt." >&2
  sudo apt-get update
  sudo apt-get install -y docker.io
fi

if command -v systemctl >/dev/null 2>&1 && [[ -d /run/systemd/system ]]; then
  sudo systemctl enable --now docker
elif command -v service >/dev/null 2>&1; then
  sudo service docker start
else
  echo "Could not find systemctl or service to start Docker." >&2
  exit 3
fi

if ! docker info >/dev/null 2>&1; then
  echo "Docker is installed but not accessible as the current user." >&2
  echo "Either run: DOCKER_CMD='sudo docker' PRODUCT_IMAGE_VERIFY_MODE=rocm-runtime bash deploy/verify_product_image.sh" >&2
  echo "Or add this user to the docker group and start a fresh login shell:" >&2
  echo "  sudo usermod -aG docker ${USER}" >&2
  exit 4
fi

if [[ ! -e /dev/kfd || ! -e /dev/dri ]]; then
  echo "ROCm device nodes are missing; expected /dev/kfd and /dev/dri for rocm-runtime smoke." >&2
  exit 5
fi

if command -v rocminfo >/dev/null 2>&1; then
  rocminfo >/dev/null
fi

echo "Docker host is ready." >&2
echo "Next:" >&2
echo "  PRODUCT_IMAGE_VERIFY_MODE=rocm-runtime bash ${ROOT}/deploy/verify_product_image.sh" >&2
