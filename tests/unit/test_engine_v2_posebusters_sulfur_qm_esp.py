from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import stat

import numpy as np
import pytest

from betelgeuze_engine_v2.benchmark import public_posebusters_sulfur_qm_esp as qm


def _sdf() -> bytes:
    atoms = (
        (-1.2, 0.0, 0.0, "C"),
        (0.0, 0.0, 0.0, "S"),
        (1.2, 0.0, 0.0, "C"),
        (-1.6, 0.9, 0.0, "H"),
        (-1.6, -0.45, 0.78, "H"),
        (-1.6, -0.45, -0.78, "H"),
        (1.6, 0.9, 0.0, "H"),
        (1.6, -0.45, 0.78, "H"),
        (1.6, -0.45, -0.78, "H"),
    )
    bonds = (
        (1, 2),
        (2, 3),
        (1, 4),
        (1, 5),
        (1, 6),
        (3, 7),
        (3, 8),
        (3, 9),
    )
    lines = [
        "dimethyl sulfide",
        "  Betelgeuze",
        "",
        f"{len(atoms):>3}{len(bonds):>3}  0  0  0  0            999 V2000",
    ]
    lines.extend(
        f"{x:10.4f}{y:10.4f}{z:10.4f} {element:<3} 0  0  0  0  0  0  0  0  0  0  0  0"
        for x, y, z, element in atoms
    )
    lines.extend(
        f"{first:>3}{second:>3}  1  0  0  0  0"
        for first, second in bonds
    )
    lines.extend(("M  END", "$$$$", ""))
    return "\n".join(lines).encode("ascii")


def _pdbqt_atom(
    serial: int,
    name: str,
    x: float,
    y: float,
    z: float,
    charge: float,
    atom_type: str,
) -> str:
    prefix = (
        f"ATOM  {serial:5d} {name:<4} LIG A   1    "
        f"{x:8.3f}{y:8.3f}{z:8.3f}"
    )
    return f"{prefix:<70}{charge:6.3f} {atom_type}"


def _pdbqt() -> bytes:
    lines = [
        "REMARK SMILES CSC",
        "REMARK SMILES IDX 1 1 2 2 3 3",
        _pdbqt_atom(1, "C1", -1.2, 0.0, 0.0, -0.1, "C"),
        _pdbqt_atom(2, "S2", 0.0, 0.0, 0.0, 0.2, "SA"),
        _pdbqt_atom(3, "C3", 1.2, 0.0, 0.0, -0.1, "C"),
        "TORSDOF 0",
        "",
    ]
    return "\n".join(lines).encode("ascii")


def _angular_grid() -> np.ndarray:
    rows = []
    golden_angle = math.pi * (3.0 - math.sqrt(5.0))
    for index in range(qm.POSEBUSTERS_SULFUR_QM_ESP_ANGULAR_POINTS):
        z = 1.0 - 2.0 * (index + 0.5) / (
            qm.POSEBUSTERS_SULFUR_QM_ESP_ANGULAR_POINTS
        )
        radius = math.sqrt(max(0.0, 1.0 - z * z))
        angle = golden_angle * index
        rows.append(
            (
                radius * math.cos(angle),
                radius * math.sin(angle),
                z,
                1.0 / qm.POSEBUSTERS_SULFUR_QM_ESP_ANGULAR_POINTS,
            )
        )
    return np.asarray(rows, dtype=np.float64)


def _runtime_identity() -> qm.PoseBustersSulfurQMEspRuntimeIdentity:
    versions = {
        "h5py": "3.11.0",
        "numpy": "1.26.4",
        "pyscf": "2.14.0",
        "rdkit": "2025.9.6",
        "scipy": "1.12.0",
        "threadpoolctl": "3.6.0",
    }
    payloads = tuple(
        qm.PoseBustersSulfurQMEspRuntimePayload(
            distribution_name=name,
            distribution_version=version,
            payload_sha256=hashlib.sha256(f"{name}:payload".encode()).hexdigest(),
            content_sha256=hashlib.sha256(f"{name}:content".encode()).hexdigest(),
            payload_file_count=1,
            payload_size_bytes=1,
        )
        for name, version in sorted(versions.items())
    )
    pyscf_content = next(
        row.content_sha256
        for row in payloads
        if row.distribution_name == "pyscf"
    )
    digest = hashlib.sha256(b"test").hexdigest()
    return qm.PoseBustersSulfurQMEspRuntimeIdentity(
        python_implementation="CPython",
        python_version="3.10.12",
        python_cache_tag="cpython-310",
        python_executable_sha256=digest,
        python_executable_size_bytes=1,
        platform_system="Linux",
        platform_machine="x86_64",
        kernel_release="test",
        libc_name="glibc",
        libc_version="2.35",
        filesystem_encoding="utf-8",
        cpu_model="test CPU",
        cpu_identity_sha256=digest,
        affinity_cpu_count=1,
        pyscf_threads=1,
        native_thread_pool_count=1,
        native_thread_pool_identity_sha256=digest,
        numpy_configuration_sha256=digest,
        scipy_configuration_sha256=digest,
        wheel_filename=qm.POSEBUSTERS_SULFUR_QM_ESP_PYSCF_WHEEL_FILENAME,
        wheel_sha256=qm.POSEBUSTERS_SULFUR_QM_ESP_PYSCF_WHEEL_SHA256,
        wheel_size_bytes=1,
        wheel_content_sha256=pyscf_content,
        distribution_payloads=payloads,
    )


class _FakeRuntime:
    identity = _runtime_identity()

    def angular_grid(self) -> np.ndarray:
        return _angular_grid()

    def validate_sdf_smiles(
        self,
        sdf_payload: bytes,
        smiles: str,
    ) -> dict[str, object]:
        assert sdf_payload == _sdf()
        assert smiles == "CSC"
        return {
            "canonical_isomeric_smiles_sha256": hashlib.sha256(
                b"CSC"
            ).hexdigest(),
            "source_atom_count": 9,
            "source_explicit_hydrogen_count": 6,
            "formal_charge": 0,
            "graph_identity_match": True,
        }

    def run_qm(
        self,
        element_symbols: tuple[str, ...],
        coordinates_angstrom: np.ndarray,
        grid_points_angstrom: np.ndarray,
    ) -> qm._QMEspResult:
        assert element_symbols == ("C", "S", "C", "H", "H", "H", "H", "H", "H")
        assert coordinates_angstrom.shape == (9, 3)
        potential = (
            0.2
            + 0.01 * np.linalg.norm(grid_points_angstrom, axis=1)
            + 0.002 * grid_points_angstrom[:, 0]
        )
        return qm._QMEspResult(
            total_energy_hartree=-474.0,
            nuclear_repulsion_hartree=80.0,
            electron_count=34.0,
            cycle_count=12,
            density_matrix=np.asarray([[2.0]], dtype=np.float64),
            qm_esp_hartree_per_e=potential,
        )


def _comparison_row() -> dict[str, object]:
    charges = ((1, 6, -0.1, -0.05, "C", "C"), (2, 16, 0.2, 0.1, "SA", "S"), (3, 6, -0.1, -0.05, "C", "C"))
    return {
        "case_id": "7CIJ_G0C",
        "status": "evaluated",
        "atom_rows": [
            {
                "pdbqt_serial": serial,
                "role": "source_atom",
                "atomic_number": atomic_number,
                "meeko_ad4_atom_type": meeko_type,
                "openbabel_ad4_atom_type": openbabel_type,
                "meeko_charge_binary64_hex": float(meeko).hex(),
                "openbabel_charge_binary64_hex": float(openbabel).hex(),
            }
            for (
                serial,
                atomic_number,
                meeko,
                openbabel,
                meeko_type,
                openbabel_type,
            ) in charges
        ],
    }


def test_sulfur_qm_esp_case_reports_preregistered_metrics_without_promotion() -> None:
    sdf = _sdf()
    pdbqt = _pdbqt()
    protocol_row = {
        "schema_id": qm.POSEBUSTERS_SULFUR_QM_ESP_CASE_SCHEMA_ID,
        "case_id": "7CIJ_G0C",
        "status": "registered",
        "disposition_code": "neutral_thioether_charge_field",
        "source_sdf": {
            "member_path": "source.sdf",
            "sha256": hashlib.sha256(sdf).hexdigest(),
            "size_bytes": len(sdf),
        },
        "prepared_ligand": {
            "relative_path": "7CIJ_G0C/ligand.pdbqt",
            "sha256": hashlib.sha256(pdbqt).hexdigest(),
            "size_bytes": len(pdbqt),
        },
        "embedded_smiles_sha256": hashlib.sha256(b"CSC").hexdigest(),
        "comparison_binding": {
            "target_atom": {
                "pdbqt_serial": 2,
                "source_smiles_atom_index": 2,
                "meeko_ad4_atom_type": "SA",
                "openbabel_ad4_atom_type": "S",
            }
        },
    }
    row = qm._observed_case(
        protocol_row=protocol_row,
        source_sdf_payload=sdf,
        prepared_payload=pdbqt,
        comparison_row=_comparison_row(),
        runtime=_FakeRuntime(),
        angular_grid=_angular_grid(),
    )
    assert row["status"] == "evaluated"
    assert row["source_atom_count"] == 9
    assert row["charge_site_count"] == 3
    assert row["macrocycle_pseudoatom_excluded_count"] == 0
    assert row["surface_grid"]["point_count"] <= 100_000
    assert len(row["surface_grid"]["shell_point_counts"]) == 4
    assert row["scf"]["converged"] is True
    assert row["scf"]["cycle_count"] == 12
    assert row["target_sulfur"]["meeko_ad4_atom_type"] == "SA"
    assert row["target_sulfur"]["openbabel_ad4_atom_type"] == "S"
    assert row["charge_accuracy_pass"] is None
    assert row["lower_rmse_label_is_descriptive_only"] is True
    for model in ("meeko", "openbabel", "same_site_model_delta"):
        assert set(row["model_metrics"][model]) == {"global", "shells"}
        assert len(row["model_metrics"][model]["shells"]) == 4
        assert "weighted_rmse_hartree_per_e" in (
            row["model_metrics"][model]["global"]
        )


def test_sulfur_qm_esp_grid_has_equal_shell_weight_and_is_deterministic() -> None:
    coordinates = np.asarray(
        [[0.0, 0.0, 0.0], [1.8, 0.0, 0.0]],
        dtype=np.float64,
    )
    first = qm._surface_grid((16, 6), coordinates, _angular_grid())
    second = qm._surface_grid((16, 6), coordinates, _angular_grid())
    assert np.array_equal(first.points_angstrom, second.points_angstrom)
    assert np.array_equal(first.weights, second.weights)
    assert math.fsum(float(value) for value in first.weights) == pytest.approx(1.0)
    for shell_index in range(4):
        assert math.fsum(
            float(value)
            for value in first.weights[first.shell_indices == shell_index]
        ) == pytest.approx(0.25)


def test_sulfur_qm_esp_receipt_write_is_private_and_no_overwrite(
    tmp_path: Path,
) -> None:
    output = tmp_path / "receipt.json"
    payload = {"schema_id": "test", "receipt_sha256": "0" * 64}
    qm._write_private_no_overwrite(payload, output)
    assert stat.S_IMODE(output.stat().st_mode) == 0o600
    assert json.loads(output.read_text()) == payload
    with pytest.raises(qm.PoseBustersSulfurQMEspError, match="already exists"):
        qm._write_private_no_overwrite(payload, output)


def test_sulfur_qm_esp_cli_exposes_registration_and_observation() -> None:
    help_text = qm._parser().format_help()
    assert "fixed-geometry PoseBusters sulfur QM ESP diagnostic" in help_text
    assert "register" in help_text
    assert "verify-protocol" in help_text
    assert "observe" in help_text
    assert "verify-observation" in help_text
    assert qm.POSEBUSTERS_SULFUR_QM_ESP_CONFIGURATION[
        "decision_contract"
    ] == {
        "accuracy_pass_threshold": None,
        "lower_rmse_label": "descriptive_only",
        "product_promotion_allowed": False,
        "sa_vs_s_hydrogen_bond_type_adjudicated": False,
    }
