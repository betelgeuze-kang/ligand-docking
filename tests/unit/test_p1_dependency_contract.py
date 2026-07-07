from __future__ import annotations

from pathlib import Path


def test_api_constraints_document_optional_httpx2_intent() -> None:
    root = Path(__file__).resolve().parents[2]
    constraints = root / "requirements" / "constraints-api-py311-linux-x86_64.txt"
    matrix = root / "docs" / "dependency_matrix.md"

    assert constraints.exists()
    text = constraints.read_text(encoding="utf-8")
    assert "fastapi" in text
    assert "pydantic-settings" in text
    assert "httpx2<1" in text

    doc = matrix.read_text(encoding="utf-8")
    assert "httpx2" in doc
    assert "Optional API HTTP test helper" in doc
    assert "constraints-api-py311-linux-x86_64.txt" in doc


def test_science_limitations_document_names_blocked_claims() -> None:
    root = Path(__file__).resolve().parents[2]
    doc = (root / "docs" / "SCIENCE_LIMITATIONS.md").read_text(encoding="utf-8")

    assert "proxy_binding_energy_score" in doc
    assert "experimental ΔG" in doc
    assert "true MM/PBSA" in doc
    assert "general-purpose docking platform" in doc
    assert "pose_rmsd_A" in doc
