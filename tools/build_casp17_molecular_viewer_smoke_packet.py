#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
from html.parser import HTMLParser
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]

DEFAULT_VIEWER_JSON = "runs/casp17_molecular_viewer_packet_current.json"
DEFAULT_VIEWER_HTML = "runs/casp17_molecular_viewer_current.html"
DEFAULT_OUT_JSON = "runs/casp17_molecular_viewer_smoke_packet_current.json"
DEFAULT_OUT_CSV = "runs/casp17_molecular_viewer_smoke_packet_current.csv"
DEFAULT_OUT_MD = "runs/casp17_molecular_viewer_smoke_packet_current.md"

REQUIRED_INTERNAL_SYMBOLS = [
    'id="internalCanvas"',
    "parsePdbAtoms",
    "setupInternalScene",
    "bindInternalCanvasEvents",
    "drawInternalScene",
    "renderInternalCanvas",
    "showFallbackPreview",
    "artifactUrl",
]

HOSTED_MOLECULAR_URL_MARKERS = [
    "https://3Dmol.org",
    "http://3Dmol.org",
    "https://3dmol.org",
    "http://3dmol.org",
    "https://molstar.org/viewer/",
    "http://molstar.org/viewer/",
    "https://unpkg.com",
    "https://cdn.jsdelivr.net",
]


class _ViewerDataParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._capture = False
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "script":
            return
        attr_map = {name: value for name, value in attrs}
        if attr_map.get("id") == "viewerData":
            self._capture = True

    def handle_data(self, data: str) -> None:
        if self._capture:
            self.parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "script" and self._capture:
            self._capture = False


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else ROOT / path


def _artifact(path_like: str | Path) -> str:
    path = _resolve(path_like).resolve()
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def _read_json(path_like: str | Path) -> dict[str, Any]:
    path = _resolve(path_like)
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _summary(payload: dict[str, Any]) -> dict[str, Any]:
    summary = payload.get("summary")
    return summary if isinstance(summary, dict) else {}


def _text(value: Any) -> str:
    return str(value or "").strip()


def _int(value: Any) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return 0


def _write_json(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _write_csv(path_like: str | Path, rows: list[dict[str, Any]]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames: list[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    if not fieldnames:
        fieldnames = ["target_id", "viewer_smoke_status", "blockers"]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _extract_viewer_data(html_text: str) -> dict[str, Any]:
    parser = _ViewerDataParser()
    parser.feed(html_text)
    if not parser.parts:
        return {}
    try:
        payload = json.loads("".join(parser.parts))
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _hosted_url_violations(html_text: str) -> list[str]:
    return [marker for marker in HOSTED_MOLECULAR_URL_MARKERS if marker in html_text]


def _missing_internal_symbols(html_text: str) -> list[str]:
    return [symbol for symbol in REQUIRED_INTERNAL_SYMBOLS if symbol not in html_text]


def _pdb_line_count(pdb_text: str, prefix: str) -> int:
    return sum(1 for line in pdb_text.splitlines() if line.startswith(prefix))


def _pdb_author_redacted(pdb_text: str) -> bool:
    author_lines = [line for line in pdb_text.splitlines() if line.startswith("AUTHOR")]
    return bool(author_lines) and all("REDACTED_FOR_LOCAL_VIEWER" in line for line in author_lines)


def _pdb_header_ok(target: dict[str, Any], pdb_text: str) -> bool:
    target_id = _text(target.get("target_id")).upper()
    lines = set(line.strip() for line in pdb_text.splitlines())
    return (
        "PFRMAT TS" in lines
        and f"TARGET {target_id}" in lines
        and "MODEL 1" in lines
        and any(line.startswith("END") for line in lines)
    )


def _target_row(target: dict[str, Any]) -> dict[str, Any]:
    target_id = _text(target.get("target_id")).upper()
    pdb_text = str(target.get("pdb_text") or "")
    fallback_path = _text(target.get("fallback_preview_png_path"))
    fallback_exists = bool(fallback_path and _resolve(fallback_path).exists())
    atom_count = _int(target.get("atom_count"))
    ca_count = _int(target.get("ca_count"))
    pdb_atom_count = _pdb_line_count(pdb_text, "ATOM")
    pdb_ca_count = sum(1 for line in pdb_text.splitlines() if line.startswith("ATOM") and line[12:16].strip() == "CA")
    blockers: list[str] = []
    if not target_id:
        blockers.append("target_id_missing")
    if atom_count <= 0 or ca_count <= 0:
        blockers.append("target_atom_or_ca_count_missing")
    if not pdb_text:
        blockers.append("embedded_pdb_missing")
    if pdb_atom_count != atom_count:
        blockers.append("embedded_pdb_atom_count_mismatch")
    if pdb_ca_count != ca_count:
        blockers.append("embedded_pdb_ca_count_mismatch")
    if not _pdb_author_redacted(pdb_text):
        blockers.append("author_not_redacted")
    if not _pdb_header_ok(target, pdb_text):
        blockers.append("pdb_header_missing_or_mismatch")
    if not fallback_exists:
        blockers.append("fallback_preview_missing")
    if fallback_path and not fallback_path.endswith("_structure_presentation_plate.png"):
        blockers.append("fallback_not_presentation_plate")
    return {
        "target_id": target_id,
        "viewer_smoke_status": "pass" if not blockers else "blocked",
        "chain_count": _int(target.get("chain_count")),
        "residue_count": _int(target.get("residue_count")),
        "atom_count": atom_count,
        "ca_count": ca_count,
        "embedded_pdb_atom_count": pdb_atom_count,
        "embedded_pdb_ca_count": pdb_ca_count,
        "author_redacted": _pdb_author_redacted(pdb_text),
        "pdb_header_ok": _pdb_header_ok(target, pdb_text),
        "fallback_preview_png_path": fallback_path,
        "fallback_preview_exists": fallback_exists,
        "fallback_is_presentation_plate": fallback_path.endswith("_structure_presentation_plate.png"),
        "blockers": ",".join(blockers),
    }


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    viewer_payload = _read_json(args.viewer_json)
    viewer_summary = _summary(viewer_payload)
    html_path = _resolve(args.viewer_html)
    html_exists = html_path.exists() and html_path.is_file()
    html_text = html_path.read_text(encoding="utf-8", errors="replace") if html_exists else ""
    viewer_data = _extract_viewer_data(html_text)
    targets = viewer_data.get("targets")
    target_items = [target for target in targets if isinstance(target, dict)] if isinstance(targets, list) else []
    rows = [_target_row(target) for target in target_items]

    missing_symbols = _missing_internal_symbols(html_text)
    hosted_violations = _hosted_url_violations(html_text)
    blocked_target_count = sum(1 for row in rows if row["viewer_smoke_status"] != "pass")
    expected_ready = _int(viewer_summary.get("ready_count"))
    target_count_match = bool(target_items and len(target_items) == expected_ready == _int(viewer_summary.get("target_count")))
    runtime_ok = (
        viewer_summary.get("webgl_runtime") == "internal_canvas_runtime"
        and viewer_summary.get("internal_canvas_runtime_enabled") is True
        and viewer_summary.get("static_preview_fallback_enabled") is True
        and viewer_summary.get("external_network_default") == "disabled"
    )
    html_ok = html_exists and not missing_symbols and not hosted_violations and bool(target_items)
    smoke_status = "pass" if runtime_ok and html_ok and target_count_match and blocked_target_count == 0 else "blocked"
    summary = {
        "packet_type": "casp17_molecular_viewer_smoke_packet",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "viewer_json": _artifact(args.viewer_json),
        "viewer_html": _artifact(args.viewer_html),
        "viewer_smoke_status": smoke_status,
        "webgl_runtime": _text(viewer_summary.get("webgl_runtime")),
        "internal_canvas_runtime_enabled": bool(viewer_summary.get("internal_canvas_runtime_enabled")),
        "static_preview_fallback_enabled": bool(viewer_summary.get("static_preview_fallback_enabled")),
        "external_network_default": _text(viewer_summary.get("external_network_default")),
        "html_exists": html_exists,
        "html_size_bytes": html_path.stat().st_size if html_exists else 0,
        "target_count": len(rows),
        "expected_ready_count": expected_ready,
        "target_count_match": target_count_match,
        "pass_count": sum(1 for row in rows if row["viewer_smoke_status"] == "pass"),
        "blocked_count": blocked_target_count,
        "fallback_preview_pass_count": sum(1 for row in rows if row["fallback_preview_exists"]),
        "presentation_fallback_count": sum(1 for row in rows if row["fallback_is_presentation_plate"]),
        "author_redaction_pass_count": sum(1 for row in rows if row["author_redacted"]),
        "pdb_header_pass_count": sum(1 for row in rows if row["pdb_header_ok"]),
        "internal_symbol_count": len(REQUIRED_INTERNAL_SYMBOLS) - len(missing_symbols),
        "missing_internal_symbols": ",".join(missing_symbols),
        "hosted_molecular_url_violation_count": len(hosted_violations),
        "hosted_molecular_url_violations": ",".join(hosted_violations),
        "blockers": ",".join(
            blocker
            for blocker, condition in [
                ("runtime_not_internal_canvas", not runtime_ok),
                ("viewer_html_missing_or_invalid", not html_ok),
                ("target_count_mismatch", not target_count_match),
                ("target_rows_blocked", blocked_target_count > 0),
            ]
            if condition
        ),
        "claim_boundary": "Static local viewer smoke only. It validates embedded internal-canvas viewer artifacts and local prediction display readiness; it does not render in a browser, prove native accuracy, fetch structures, or submit to CASP.",
    }
    return {"summary": summary, "rows": rows}


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# CASP17 Molecular Viewer Smoke Packet",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- viewer_smoke_status: `{summary['viewer_smoke_status']}`",
        f"- runtime: `{summary['webgl_runtime']}`",
        f"- target_count: `{summary['target_count']}`",
        f"- pass/blocked: `{summary['pass_count']}/{summary['blocked_count']}`",
        f"- fallback previews: `{summary['fallback_preview_pass_count']}/{summary['target_count']}`",
        f"- presentation fallbacks: `{summary['presentation_fallback_count']}/{summary['target_count']}`",
        f"- author redaction: `{summary['author_redaction_pass_count']}/{summary['target_count']}`",
        f"- pdb headers: `{summary['pdb_header_pass_count']}/{summary['target_count']}`",
        f"- internal symbols: `{summary['internal_symbol_count']}/{len(REQUIRED_INTERNAL_SYMBOLS)}`",
        f"- hosted molecular URL violations: `{summary['hosted_molecular_url_violation_count']}`",
        f"- blockers: `{summary['blockers'] or '-'}`",
        "",
        "## Targets",
        "",
        "| target | status | chains | residues | atoms | CA | embedded atoms | embedded CA | fallback | blockers |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['target_id']}` | `{row['viewer_smoke_status']}` | {row['chain_count']} | "
            f"{row['residue_count']} | {row['atom_count']} | {row['ca_count']} | "
            f"{row['embedded_pdb_atom_count']} | {row['embedded_pdb_ca_count']} | "
            f"`{row['fallback_preview_png_path'] or '-'}` | `{row['blockers'] or '-'}` |"
        )
    if not payload["rows"]:
        lines.append("| - | `blocked` | 0 | 0 | 0 | 0 | 0 | 0 | - | no embedded targets |")
    lines.extend(["", "## Claim Boundary", "", str(summary["claim_boundary"]), ""])
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a local static smoke packet for the CASP17 molecular viewer HTML.")
    parser.add_argument("--viewer-json", default=DEFAULT_VIEWER_JSON)
    parser.add_argument("--viewer-html", default=DEFAULT_VIEWER_HTML)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_payload(args)
    _write_json(args.out_json, payload)
    _write_csv(args.out_csv, payload["rows"])
    _write_md(args.out_md, payload)
    if payload["summary"]["viewer_smoke_status"] != "pass":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
