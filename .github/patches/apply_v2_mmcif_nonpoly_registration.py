from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def replace_exact(
    relative_path: str,
    old: str,
    new: str,
    *,
    expected_count: int = 1,
) -> None:
    path = ROOT / relative_path
    source = path.read_text(encoding="utf-8")
    observed = source.count(old)
    if observed != expected_count:
        raise SystemExit(
            f"unexpected replacement count in {relative_path}: "
            f"observed={observed} expected={expected_count} token={old!r}"
        )
    path.write_text(
        source.replace(old, new, expected_count),
        encoding="utf-8",
    )


def apply_molecular_exports() -> None:
    import_block = '''from .mmcif_nonpoly_identity import (
    MMCIF_NONPOLY_IDENTITY_DOCUMENT_SCHEMA_ID,
    MMCIF_NONPOLY_IDENTITY_PARSER_VERSION,
    MMCIF_NONPOLY_IDENTITY_PROFILE_ID,
    MmcifNonpolyComponentIdentity,
    MmcifNonpolyEntityIdentity,
    MmcifNonpolyIdentityError,
    MmcifNonpolyIdentitySnapshot,
    MmcifNonpolyInstanceIdentity,
    mmcif_nonpoly_identity_document,
    mmcif_nonpoly_identity_json_bytes,
    mmcif_nonpoly_identity_projection,
    mmcif_nonpoly_identity_source_binding,
    parse_mmcif_nonpoly_identity,
    require_mmcif_nonpoly_identity_document,
    write_mmcif_nonpoly_identity_json,
)
'''
    replace_exact(
        "betelgeuze_engine_v2/molecular/__init__.py",
        "from .mmcif_semantics import (\n",
        import_block + "from .mmcif_semantics import (\n",
    )
    replace_exact(
        "betelgeuze_engine_v2/molecular/__init__.py",
        '    "MMCIF_SEMANTIC_DOCUMENT_SCHEMA_ID",\n',
        '    "MMCIF_NONPOLY_IDENTITY_DOCUMENT_SCHEMA_ID",\n'
        '    "MMCIF_NONPOLY_IDENTITY_PARSER_VERSION",\n'
        '    "MMCIF_NONPOLY_IDENTITY_PROFILE_ID",\n'
        '    "MMCIF_SEMANTIC_DOCUMENT_SCHEMA_ID",\n',
    )
    replace_exact(
        "betelgeuze_engine_v2/molecular/__init__.py",
        '    "MmcifAsymIdentity",\n',
        '    "MmcifAsymIdentity",\n'
        '    "MmcifNonpolyComponentIdentity",\n'
        '    "MmcifNonpolyEntityIdentity",\n'
        '    "MmcifNonpolyIdentityError",\n'
        '    "MmcifNonpolyIdentitySnapshot",\n'
        '    "MmcifNonpolyInstanceIdentity",\n',
    )
    replace_exact(
        "betelgeuze_engine_v2/molecular/__init__.py",
        '    "mmcif_semantic_document",\n',
        '    "mmcif_nonpoly_identity_document",\n'
        '    "mmcif_nonpoly_identity_json_bytes",\n'
        '    "mmcif_nonpoly_identity_projection",\n'
        '    "mmcif_nonpoly_identity_source_binding",\n'
        '    "mmcif_semantic_document",\n',
    )
    replace_exact(
        "betelgeuze_engine_v2/molecular/__init__.py",
        '    "parse_mmcif_semantics",\n',
        '    "parse_mmcif_nonpoly_identity",\n'
        '    "parse_mmcif_semantics",\n',
    )
    replace_exact(
        "betelgeuze_engine_v2/molecular/__init__.py",
        '    "require_mmcif_semantic_document",\n',
        '    "require_mmcif_nonpoly_identity_document",\n'
        '    "require_mmcif_semantic_document",\n',
    )
    replace_exact(
        "betelgeuze_engine_v2/molecular/__init__.py",
        '    "write_mmcif_semantic_json",\n',
        '    "write_mmcif_nonpoly_identity_json",\n'
        '    "write_mmcif_semantic_json",\n',
    )


def apply_capability_registration() -> None:
    replace_exact(
        "betelgeuze_engine_v2/capabilities.py",
        'MMCIF_ALTLOC_DECLARATIONS_CAPABILITY_ID = "v2_bounded_mmcif_altloc_declarations"\n',
        'MMCIF_ALTLOC_DECLARATIONS_CAPABILITY_ID = "v2_bounded_mmcif_altloc_declarations"\n'
        'MMCIF_NONPOLY_IDENTITY_CAPABILITY_ID = "v2_bounded_mmcif_nonpoly_identity"\n',
    )
    blockers = '''    MMCIF_NONPOLY_IDENTITY_CAPABILITY_ID: (
        "source_authentication_missing",
        "atom_site_identity_and_coordinates_not_joined",
        "component_chemistry_and_roles_not_interpreted",
        "bond_topology_and_preparation_not_interpreted",
        "product_integration_not_qualified",
    ),
'''
    replace_exact(
        "betelgeuze_engine_v2/capabilities.py",
        '    PHYSICS_REGISTRY_CAPABILITY_ID: (\n',
        blockers + '    PHYSICS_REGISTRY_CAPABILITY_ID: (\n',
    )
    row = '''            MMCIF_NONPOLY_IDENTITY_CAPABILITY_ID: _row(
                MMCIF_NONPOLY_IDENTITY_CAPABILITY_ID,
                current_state="bounded_nonpoly_component_instance_identity",
                internal_execution_enabled=True,
                blocker_source="betelgeuze_engine_v2.capabilities.CAPABILITY_BLOCKERS",
            ),
'''
    replace_exact(
        "betelgeuze_engine_v2/capabilities.py",
        '            PHYSICS_REGISTRY_CAPABILITY_ID: _row(\n',
        row + '            PHYSICS_REGISTRY_CAPABILITY_ID: _row(\n',
    )
    replace_exact(
        "betelgeuze_engine_v2/capabilities.py",
        '    "MMCIF_SEMANTICS_CAPABILITY_ID",\n',
        '    "MMCIF_NONPOLY_IDENTITY_CAPABILITY_ID",\n'
        '    "MMCIF_SEMANTICS_CAPABILITY_ID",\n',
    )

    yaml_row = '''  v2_bounded_mmcif_nonpoly_identity:
    current_state: bounded_nonpoly_component_instance_identity
    implemented: true
    reference_contract_ready: true
    internal_reference_execution_enabled: true
    calibrated: false
    scientifically_validated: false
    public_evidence_ready: false
    benchmark_validated: false
    product_qualified: false
    customer_execution_enabled: false
    claim_safe: false
    blocker_source: betelgeuze_engine_v2.capabilities.CAPABILITY_BLOCKERS
    blockers:
      - source_authentication_missing
      - atom_site_identity_and_coordinates_not_joined
      - component_chemistry_and_roles_not_interpreted
      - bond_topology_and_preparation_not_interpreted
      - product_integration_not_qualified

'''
    replace_exact(
        "config/independent_engine_v2_capabilities.yaml",
        "  v2_independent_physics_registry:\n",
        yaml_row + "  v2_independent_physics_registry:\n",
    )


def apply_registration_tests() -> None:
    path = "tests/unit/test_engine_v2_post_merge_state.py"
    replace_exact(
        path,
        "    MMCIF_SEMANTICS_CAPABILITY_ID,\n",
        "    MMCIF_NONPOLY_IDENTITY_CAPABILITY_ID,\n"
        "    MMCIF_SEMANTICS_CAPABILITY_ID,\n",
    )
    replace_exact(
        path,
        '    assert len(loaded["capabilities"]) == 12\n',
        '    assert len(loaded["capabilities"]) == 13\n',
    )
    replace_exact(
        path,
        "    assert MMCIF_SEMANTICS_CAPABILITY_ID in rows\n",
        "    assert MMCIF_NONPOLY_IDENTITY_CAPABILITY_ID in rows\n"
        "    assert MMCIF_SEMANTICS_CAPABILITY_ID in rows\n",
    )
    assertions = '''    nonpoly = rows[MMCIF_NONPOLY_IDENTITY_CAPABILITY_ID]
    assert nonpoly["current_state"] == "bounded_nonpoly_component_instance_identity"
    assert nonpoly["internal_reference_execution_enabled"] is True
    assert "source_authentication_missing" in nonpoly["blockers"]
    assert "atom_site_identity_and_coordinates_not_joined" in nonpoly["blockers"]
    assert "component_chemistry_and_roles_not_interpreted" in nonpoly["blockers"]
    assert "bond_topology_and_preparation_not_interpreted" in nonpoly["blockers"]

'''
    replace_exact(
        path,
        '    physics_blockers = rows[PHYSICS_REGISTRY_CAPABILITY_ID]["blockers"]\n',
        assertions
        + '    physics_blockers = rows[PHYSICS_REGISTRY_CAPABILITY_ID]["blockers"]\n',
    )
    replace_exact(
        path,
        '        "test_engine_v2_mmcif_altloc_declarations.py",\n',
        '        "test_engine_v2_mmcif_altloc_declarations.py",\n'
        '        "test_engine_v2_mmcif_nonpoly_identity.py",\n',
    )


def apply_canonical_workflow() -> None:
    path = ".github/workflows/ci-engine-v2-main.yml"
    replace_exact(
        path,
        "            tests/unit/test_engine_v2_mmcif_altloc_declarations.py\n",
        "            tests/unit/test_engine_v2_mmcif_altloc_declarations.py\n"
        "            tests/unit/test_engine_v2_mmcif_nonpoly_identity.py\n",
    )
    replace_exact(
        path,
        "            tests/unit/test_engine_v2_mmcif_altloc_declarations.py \\\n",
        "            tests/unit/test_engine_v2_mmcif_altloc_declarations.py \\\n"
        "            tests/unit/test_engine_v2_mmcif_nonpoly_identity.py \\\n",
    )
    replace_exact(
        path,
        "          from betelgeuze_engine_v2.molecular.mmcif_syntax import parse_cif_block\n",
        "          from betelgeuze_engine_v2.molecular.mmcif_nonpoly_identity import (\n"
        "              MMCIF_NONPOLY_IDENTITY_DOCUMENT_SCHEMA_ID,\n"
        "          )\n"
        "          from betelgeuze_engine_v2.molecular.mmcif_syntax import parse_cif_block\n",
    )
    replace_exact(
        path,
        '          assert MMCIF_ALTLOC_DECLARATION_DOCUMENT_SCHEMA_ID.endswith("/1.0.0")\n',
        '          assert MMCIF_ALTLOC_DECLARATION_DOCUMENT_SCHEMA_ID.endswith("/1.0.0")\n'
        '          assert MMCIF_NONPOLY_IDENTITY_DOCUMENT_SCHEMA_ID.endswith("/1.0.0")\n',
    )


def apply_focused_workflow() -> None:
    path = ".github/workflows/ci-engine-v2-mmcif-nonpoly-identity.yml"
    replace_exact(
        path,
        '      - "betelgeuze_engine_v2/molecular/__init__.py"\n',
        '      - "betelgeuze_engine_v2/molecular/__init__.py"\n'
        '      - "betelgeuze_engine_v2/capabilities.py"\n'
        '      - "config/independent_engine_v2_capabilities.yaml"\n',
        expected_count=2,
    )
    replace_exact(
        path,
        '      - "tests/unit/test_engine_v2_mmcif_nonpoly_identity.py"\n',
        '      - "tests/unit/test_engine_v2_mmcif_nonpoly_identity.py"\n'
        '      - "tests/unit/test_engine_v2_post_merge_state.py"\n'
        '      - ".github/workflows/ci-engine-v2-main.yml"\n',
        expected_count=2,
    )
    replace_exact(
        path,
        "            betelgeuze_engine_v2\n",
        "            betelgeuze_engine_v2\n"
        "            config/independent_engine_v2_capabilities.yaml\n",
    )
    replace_exact(
        path,
        "            tests/unit/test_engine_v2_mmcif_nonpoly_identity.py\n",
        "            tests/unit/test_engine_v2_mmcif_nonpoly_identity.py\n"
        "            tests/unit/test_engine_v2_post_merge_state.py\n"
        "            docs/engine_v2_status.md\n"
        "            docs/engine_v2_public_api.md\n"
        "            docs/entrypoints.md\n"
        "            README.md\n"
        "            README.ko.md\n"
        "            .github/workflows/ci-engine-v2-main.yml\n",
    )
    replace_exact(
        path,
        "          python -m pip install pytest==8.3.5 numpy==1.26.4\n",
        "          python -m pip install pytest==8.3.5 PyYAML==6.0.3 numpy==1.26.4\n",
    )
    replace_exact(
        path,
        "            tests/unit/test_engine_v2_mmcif_nonpoly_identity.py \\\n",
        "            tests/unit/test_engine_v2_mmcif_nonpoly_identity.py \\\n"
        "            tests/unit/test_engine_v2_post_merge_state.py \\\n",
    )


def main() -> None:
    apply_molecular_exports()
    apply_capability_registration()
    apply_registration_tests()
    apply_canonical_workflow()
    apply_focused_workflow()
    (ROOT / ".github/workflows/apply-v2-mmcif-nonpoly-registration-final.yml").unlink()
    Path(__file__).unlink()


if __name__ == "__main__":
    main()
