#!/usr/bin/env bash
set -euo pipefail

# Static wrapper-command guard.
# This is not a sandbox and cannot inspect commands run inside an agent.

cmd="${*:-}"
for pat in \
  "git push" \
  "git merge" \
  "git reset --hard" \
  "git checkout --" \
  "npm publish" \
  "pnpm publish" \
  "yarn publish" \
  "docker push" \
  "kubectl apply" \
  "terraform apply" \
  "vercel deploy --prod" \
  "railway up" \
  "fly deploy" \
  "stripe refunds create" \
  "prisma migrate deploy" \
  "supabase db push" \
  "rm -rf /" \
  "predictioncenter.org" \
  "casp submit"; do
  if printf '%s' "$cmd" | grep -qi -- "$pat"; then
    echo "Blocked dangerous command pattern in wrapper/config command: $pat" >&2
    exit 2
  fi
done
