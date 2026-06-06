from __future__ import annotations

import json
from pathlib import Path

from tools.cleanup import build_cleanup_operations_surface_contract as mod


def _write_api_surface(root: Path, *, include_router: bool = True) -> None:
    (root / "api").mkdir()
    (root / "betelgeuze_cleanup").mkdir()
    (root / "api" / "cleanup.py").write_text(
        '@router.get("/operations")\n'
        '@router.get("/approval-gate")\n'
        '@router.get("/completion")\n'
        '@router.get("/postcheck")\n'
        '@router.get("/payloads")\n'
        '@router.get("/protected-ligand-heavy-review")\n'
        '@router.get("/protected-policy")\n'
        'delete_enabled = False\n'
        'delete_executed = False\n'
        'external_state_mutated = False\n',
        encoding="utf-8",
    )
    (root / "api" / "main.py").write_text(
        "from api.cleanup import router as cleanup_router\napp.include_router(cleanup_router)\n" if include_router else "",
        encoding="utf-8",
    )
    (root / "betelgeuze_cleanup" / "cli.py").write_text("# cli\n", encoding="utf-8")


def test_cleanup_operations_surface_contract_ready(tmp_path: Path) -> None:
    _write_api_surface(tmp_path)

    payload = mod.build_cleanup_operations_surface_contract(root=tmp_path)

    summary = payload["summary"]
    assert summary["status"] == "cleanup_operations_surface_contract_ready"
    assert summary["surface_ready"] is True
    assert summary["cleanup_local_status_cli_present"] is True
    assert summary["cleanup_operations_endpoint_present"] is True
    assert summary["cleanup_approval_gate_endpoint_present"] is True
    assert summary["cleanup_completion_endpoint_present"] is True
    assert summary["cleanup_postcheck_endpoint_present"] is True
    assert summary["cleanup_payloads_endpoint_present"] is True
    assert summary["cleanup_protected_ligand_heavy_review_endpoint_present"] is True
    assert summary["cleanup_protected_policy_endpoint_present"] is True
    assert summary["delete_executed"] is False
    assert summary["external_state_mutated"] is False
    assert payload["blockers"] == []


def test_cleanup_operations_surface_contract_blocks_unmounted_router(tmp_path: Path) -> None:
    _write_api_surface(tmp_path, include_router=False)

    payload = mod.build_cleanup_operations_surface_contract(root=tmp_path)

    assert payload["summary"]["status"] == "blocked_cleanup_operations_surface_contract"
    assert payload["summary"]["cleanup_router_registered"] is False
    assert any(blocker["code"] == "cleanup_router_registered_not_ready" for blocker in payload["blockers"])


def test_cleanup_operations_surface_contract_tool_writes_outputs(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    _write_api_surface(root)
    out_json = tmp_path / "surface.json"
    out_csv = tmp_path / "surface.csv"
    out_md = tmp_path / "surface.md"

    mod.main(["--root", str(root), "--out-json", str(out_json), "--out-csv", str(out_csv), "--out-md", str(out_md)])

    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["summary"]["status"] == "cleanup_operations_surface_contract_ready"
    assert out_csv.read_text(encoding="utf-8").startswith("check,status,")
    assert "Cleanup Operations Surface Contract" in out_md.read_text(encoding="utf-8")
