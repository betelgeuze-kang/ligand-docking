from __future__ import annotations

import json
from pathlib import Path


PROFILE_PATHS = [
    Path("config/ligand_htvs_blind_ca2_zn_v1.json"),
    Path("config/ligand_htvs_blind_ca2_zn_chembl50_v1.json"),
    Path("config/ligand_htvs_blind_pxr_nr1i2_v1.json"),
    Path("config/ligand_htvs_blind_pxr_nr1i2_chembl50_v1.json"),
]


def test_ca2_pxr_scaffold_profiles_are_explicitly_validate_only_and_non_claim() -> None:
    for path in PROFILE_PATHS:
        payload = json.loads(path.read_text(encoding="utf-8"))
        assert payload["dry_run"] is True, path
        assert payload["template_profile"] is True, path
        assert payload["template_execution_intent"] == "validate_only", path
        assert payload["claim_ready"] is False, path
        desc = str(payload["description"])
        assert "validate-only" in desc, path
        assert "non-claim" in desc, path
        assert "non-production" in desc, path
