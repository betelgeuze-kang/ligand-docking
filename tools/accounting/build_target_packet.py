from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

TARGET_PRESETS: dict[str, dict[str, str]] = {
    "alk2": {
        "launch": "build_alk2_launch_packet",
        "live_progress": "build_alk2_live_progress",
        "render_suite": "build_alk2_render_suite",
        "result_review": "build_alk2_result_review",
        "result_summary": "build_alk2_result_summary",
    },
}


def build_target_packet(*, target_id: str, packet_kind: str, root: Path) -> dict[str, Any]:
    preset = TARGET_PRESETS.get(target_id, {})
    builder = preset.get(packet_kind, "")
    if not builder:
        raise ValueError(f"unknown target packet: target_id={target_id} packet_kind={packet_kind}")
    builder_path = root / "tools" / "accounting" / f"{builder}.py"
    if not builder_path.exists():
        raise FileNotFoundError(f"builder missing: {builder_path}")
    return {
        "target_id": target_id,
        "packet_kind": packet_kind,
        "builder_module": f"tools.accounting.{builder}",
        "builder_path": str(builder_path),
        "status": "target_packet_builder_resolved",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Resolve parameterized target packet builders.")
    parser.add_argument("--target-id", required=True)
    parser.add_argument("--packet-kind", required=True)
    parser.add_argument("--root", default=".")
    parser.add_argument("--out-json", required=True)
    args = parser.parse_args(argv)
    payload = build_target_packet(
        target_id=args.target_id,
        packet_kind=args.packet_kind,
        root=Path(args.root).resolve(),
    )
    out = Path(args.out_json)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
