#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from api.validated_runner import _runner_script, validate_profile_readiness


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"profile must be JSON object: {path}")
    return payload


def validate_profiles(profiles_dir: Path) -> dict[str, Any]:
    profiles = sorted(profiles_dir.glob("*.json"))
    rows: list[dict[str, Any]] = []
    enabled_count = 0
    failed_count = 0
    for path in profiles:
        row: dict[str, Any] = {
            "profile_path": str(path),
            "profile_id": path.stem,
            "enabled": False,
            "status": "unknown",
            "error": "",
        }
        try:
            profile = _load_json(path)
            row["profile_id"] = str(profile.get("profile_id", path.stem) or path.stem)
            row["enabled"] = bool(profile.get("enabled") is True)
            if not row["enabled"]:
                row["status"] = "disabled_skip"
            else:
                enabled_count += 1
                script = _runner_script(profile)
                readiness = validate_profile_readiness(profile, runner_script_path=script)
                row["status"] = "ready"
                row["runner_script"] = str(profile.get("runner_script", "") or "")
                row["claim_scope"] = readiness["claim_scope"]
                row["evidence_artifact"] = readiness["evidence_artifact"]
        except Exception as exc:
            failed_count += 1
            row["status"] = "failed"
            row["error"] = str(exc)
        rows.append(row)
    return {
        "status": "pass" if failed_count == 0 else "failed",
        "profiles_dir": str(profiles_dir),
        "profile_count": len(profiles),
        "enabled_profile_count": enabled_count,
        "failed_profile_count": failed_count,
        "rows": rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate API runner profile readiness gates.")
    parser.add_argument("--profiles-dir", default="config/api_validated_runner_profiles")
    parser.add_argument("--out-json", default="")
    args = parser.parse_args()

    payload = validate_profiles(Path(args.profiles_dir))
    text = json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    if args.out_json:
        out = Path(args.out_json)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text, encoding="utf-8")
    else:
        print(text, end="")
    return 0 if payload["status"] == "pass" else 2


if __name__ == "__main__":
    raise SystemExit(main())
