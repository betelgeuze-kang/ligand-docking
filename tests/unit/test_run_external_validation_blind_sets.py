from pathlib import Path

from tools import run_external_validation_blind_sets as mod


def test_validate_set_defs_accepts_comparison_candidate_claim_role(tmp_path: Path) -> None:
    profile_json = tmp_path / "profile.json"
    profile_json.write_text("{}", encoding="utf-8")

    mod._validate_set_defs(
        [
            {
                "set_id": "set1_core_blind",
                "title": "Core Blind Set",
                "purpose": "Comparison-only guarded candidate.",
                "claim_role": "comparison_candidate",
                "tasks": [
                    {
                        "task_id": "gpcr_core_full",
                        "domain": "gpcr",
                        "kind": "ligand_stress",
                        "profile_json": str(profile_json),
                        "ligand_sizes": "100000",
                        "date_tag_suffix": "gpcr-core-full-comparison",
                    }
                ],
            }
        ],
        "unit_spec",
    )
