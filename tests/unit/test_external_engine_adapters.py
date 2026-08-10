from __future__ import annotations

from collections import deque
import hashlib
import inspect
from pathlib import Path
import subprocess

import pytest

from benchmarks.oracles import gnina, gromacs, vina
from benchmarks.oracles.contract import OracleRequest
from benchmarks.oracles.execution import sha256_regular_file


GROMACS_VERSION = """\
                         :-) GROMACS - gmx_d, 2024.2 (-:

GROMACS version:    2024.2
Precision:          double
Memory model:       64 bit
"""

GROMACS_ENERGY = """\
@    title "GROMACS Energies"
@    xaxis  label "Time (ps)"
@ s0 legend "Potential"
@ s1 legend "Coul-SR"
0.000000 -1.250000e+02 -2.500000e+01
0.002000 -1.249500e+02 -2.495000e+01
"""

GROMACS_FORCE = """\
@    title "GROMACS Forces"
@    xaxis  label "Time (ps)"
0.000000 1.0 2.0 3.0 -1.0 -2.0 -3.0
0.002000 1.5 2.5 3.5 -1.5 -2.5 -3.5
"""

VINA_STDOUT = """\
AutoDock Vina v1.2.5
mode |   affinity | dist from best mode
     | (kcal/mol) | rmsd l.b.| rmsd u.b.
-----+------------+----------+----------
   1       -7.500      0.000      0.000
   2       -7.000      1.250      2.500
"""

GNINA_STDOUT = """\
gnina v1.0.3
mode | affinity | intramol | CNN pose score | CNN affinity
-----+----------+----------+----------------+-------------
   1     -8.100     -0.400       0.8000       6.200
   2     -7.900     -0.300       0.7000       5.900
"""


def _pdbqt_atom(serial: int, x: float, y: float, z: float) -> str:
    return (
        f"HETATM{serial:5d}  C{serial:<2d} LIG A   1    "
        f"{x:8.3f}{y:8.3f}{z:8.3f}  1.00  0.00     0.000 C"
    )


def _vina_pose_text(scores: tuple[float, ...] = (-7.5, -7.0)) -> str:
    records: list[str] = []
    for rank, score in enumerate(scores, start=1):
        records.extend(
            (
                f"MODEL {rank}",
                f"REMARK VINA RESULT: {score:.3f} 0.000 0.000",
                "ROOT",
                _pdbqt_atom(1, float(rank), 2.0, 3.0),
                "ENDROOT",
                "TORSDOF 0",
                "ENDMDL",
            )
        )
    return "\n".join(records) + "\n"


def _gnina_record(
    *,
    title: str,
    affinity: float,
    cnn_score: float,
    cnn_affinity: float,
) -> str:
    return f"""\
{title}
  GNINA

  1  0  0  0  0  0            999 V2000
    1.0000    2.0000    3.0000 C   0  0  0  0  0  0  0  0  0  0  0  0
M  END
> <minimizedAffinity>
{affinity}

> <CNNscore>
{cnn_score}

> <CNNaffinity>
{cnn_affinity}

$$$$
"""


GNINA_SDF = _gnina_record(
    title="pose-1", affinity=-8.1, cnn_score=0.8, cnn_affinity=6.2
) + _gnina_record(title="pose-2", affinity=-7.9, cnn_score=0.7, cnn_affinity=5.9)


class FakeRunner:
    def __init__(self, *responses: object) -> None:
        self.responses = deque(responses)
        self.calls: list[tuple[tuple[str, ...], dict[str, object]]] = []

    def __call__(self, argv: list[str], **kwargs: object) -> object:
        self.calls.append((tuple(argv), dict(kwargs)))
        response = self.responses.popleft()
        if isinstance(response, BaseException):
            raise response
        return response


def _install_docking_executable(
    path: Path,
    *,
    version: str,
    stdout: str,
    pose_bytes: bytes,
    expected_inputs: dict[str, bytes],
    returncode: int = 0,
    stderr: str = "",
    symlink_output: bool = False,
    attempt_snapshot_write: bool = False,
) -> tuple[Path, str]:
    source = f"""#!/usr/bin/python3
import pathlib
import sys

VERSION = {version!r}
STDOUT = {stdout!r}
STDERR = {stderr!r}
POSE = {pose_bytes!r}
EXPECTED = {expected_inputs!r}
RETURN_CODE = {returncode!r}
SYMLINK_OUTPUT = {symlink_output!r}
ATTEMPT_SNAPSHOT_WRITE = {attempt_snapshot_write!r}

args = sys.argv[1:]
if args == ["--version"]:
    sys.stdout.write(VERSION)
    raise SystemExit(0)

def option(name):
    return args[args.index(name) + 1]

for flag, expected in EXPECTED.items():
    if pathlib.Path(option(flag)).read_bytes() != expected:
        sys.stderr.write("prepared input mismatch")
        raise SystemExit(91)

if ATTEMPT_SNAPSHOT_WRITE:
    snapshot = pathlib.Path(option("--ligand"))
    try:
        snapshot.chmod(0o600)
        snapshot.write_bytes(b"attacker-snapshot")
    except OSError:
        pass
    if snapshot.read_bytes() != EXPECTED["--ligand"]:
        sys.stderr.write("snapshot mutation succeeded")
        raise SystemExit(92)

output = pathlib.Path(option("--out"))
if SYMLINK_OUTPUT:
    target = output.with_name("solver-symlink-target")
    target.write_bytes(POSE)
    output.symlink_to(target.name)
else:
    output.write_bytes(POSE)
sys.stdout.write(STDOUT)
sys.stderr.write(STDERR)
raise SystemExit(RETURN_CODE)
"""
    path.write_text(source, encoding="utf-8")
    path.chmod(0o700)
    return path, sha256_regular_file(path)


def _install_gromacs_executable(
    path: Path, *, expected_tpr: bytes, expected_trajectory: bytes
) -> tuple[Path, str]:
    source = f"""#!/usr/bin/python3
import os
import pathlib
import sys

VERSION = {GROMACS_VERSION!r}
ENERGY = {GROMACS_ENERGY.encode("utf-8")!r}
FORCE = {GROMACS_FORCE.encode("utf-8")!r}
EXPECTED_TPR = {expected_tpr!r}
EXPECTED_TRAJECTORY = {expected_trajectory!r}

for name, value in {{
    "GMX_DISABLE_GPU_DETECTION": "1",
    "CUDA_VISIBLE_DEVICES": "",
    "HIP_VISIBLE_DEVICES": "",
    "ROCR_VISIBLE_DEVICES": "",
}}.items():
    if os.environ.get(name) != value:
        sys.stderr.write("backend environment mismatch")
        raise SystemExit(81)

args = sys.argv[1:]
if args == ["--version"]:
    sys.stdout.write(VERSION)
    raise SystemExit(0)

def option(name):
    return args[args.index(name) + 1]

command = args[0]
if command == "mdrun":
    if pathlib.Path(option("-s")).read_bytes() != EXPECTED_TPR:
        raise SystemExit(82)
    if pathlib.Path(option("-rerun")).read_bytes() != EXPECTED_TRAJECTORY:
        raise SystemExit(83)
    prefix = option("-deffnm")
    pathlib.Path(prefix + ".edr").write_bytes(b"fake-edr")
    pathlib.Path(prefix + ".trr").write_bytes(b"fake-trr")
elif command == "energy":
    pathlib.Path(option("-o")).write_bytes(ENERGY)
elif command == "traj":
    pathlib.Path(option("-of")).write_bytes(FORCE)
else:
    raise SystemExit(84)
sys.stdout.write(command + " complete")
"""
    path.write_text(source, encoding="utf-8")
    path.chmod(0o700)
    return path, sha256_regular_file(path)


def _completed(stdout: str = "", stderr: str = "", returncode: int = 0):
    return subprocess.CompletedProcess(
        args=["fake"], returncode=returncode, stdout=stdout, stderr=stderr
    )


def _write(path: Path, content: str) -> Path:
    path.write_text(content, encoding="utf-8")
    return path


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _vina_bound_case(
    tmp_path: Path, name: str
) -> tuple[Path, str, Path, Path, OracleRequest]:
    root = tmp_path / name
    root.mkdir()
    receptor = _write(root / "receptor.pdbqt", "trusted receptor\n")
    ligand = _write(root / "ligand.pdbqt", "trusted ligand\n")
    executable, executable_hash = _install_docking_executable(
        root / "vina",
        version="AutoDock Vina v1.2.5",
        stdout=VINA_STDOUT,
        pose_bytes=_vina_pose_text().encode("utf-8"),
        expected_inputs={
            "--receptor": receptor.read_bytes(),
            "--ligand": ligand.read_bytes(),
        },
    )
    request = OracleRequest(
        engine_id="vina",
        case_id=name,
        task=vina.ORACLE_TASK,
        input_sha256={"receptor": _sha256(receptor), "ligand": _sha256(ligand)},
        parameters={
            "center_angstrom": [0.0, 0.0, 0.0],
            "size_angstrom": [20.0, 20.0, 20.0],
            "exhaustiveness": 8,
            "num_modes": 9,
            "scoring": "vina",
            "cnn_scoring": "none",
        },
    )
    return executable, executable_hash, receptor, ligand, request


def _gnina_bound_case(
    tmp_path: Path, name: str
) -> tuple[Path, str, Path, Path, Path, OracleRequest]:
    root = tmp_path / name
    root.mkdir()
    receptor = _write(root / "receptor.pdb", "trusted receptor\n")
    ligand = _write(root / "ligand.sdf", "trusted ligand\n")
    autobox = _write(root / "autobox.sdf", "trusted autobox\n")
    executable, executable_hash = _install_docking_executable(
        root / "gnina",
        version="gnina v1.0.3",
        stdout=GNINA_STDOUT,
        pose_bytes=GNINA_SDF.encode("utf-8"),
        expected_inputs={
            "--receptor": receptor.read_bytes(),
            "--ligand": ligand.read_bytes(),
            "--autobox_ligand": autobox.read_bytes(),
        },
    )
    request = OracleRequest(
        engine_id="gnina",
        case_id=name,
        task=gnina.ORACLE_TASK,
        input_sha256={
            "receptor": _sha256(receptor),
            "ligand": _sha256(ligand),
            "autobox_ligand": _sha256(autobox),
        },
        parameters={
            "autobox_add_angstrom": 4.0,
            "exhaustiveness": 8,
            "num_modes": 9,
            "scoring": "vina",
            "cnn_scoring": "rescore",
            "cnn_model": "crossdock_default2018",
            "no_gpu": True,
        },
    )
    return executable, executable_hash, receptor, ligand, autobox, request


def test_gromacs_double_identity_and_canonical_rerun_commands() -> None:
    identity = gromacs.parse_identity(GROMACS_VERSION, executable="/oracle/gmx_d")
    assert identity.version == "2024.2"
    assert identity.precision == "double"

    mdrun = gromacs.build_mdrun_rerun_command(
        identity.executable,
        tpr="rerun.tpr",
        trajectory="frames.trr",
        deffnm="oracle",
    )
    assert mdrun[:6] == (
        "/oracle/gmx_d",
        "mdrun",
        "-s",
        "rerun.tpr",
        "-rerun",
        "frames.trr",
    )
    assert mdrun[-9:] == (
        "-nb",
        "cpu",
        "-pme",
        "cpu",
        "-bonded",
        "cpu",
        "-update",
        "cpu",
        "-reprod",
    )


def test_gromacs_rejects_non_double_binary_and_runs_pinned_script_rerun(
    tmp_path: Path,
) -> None:
    with pytest.raises(gromacs.OracleAdapterError) as caught:
        gromacs.parse_identity(
            GROMACS_VERSION.replace("double", "mixed"), executable="gmx"
        )
    assert caught.value.code == "malformed"

    inputs = {
        "tpr": _write(tmp_path / "prepared.tpr", "self-contained tpr\n"),
        "trajectory": _write(tmp_path / "frames.trr", "prepared frames\n"),
    }
    executable, executable_hash = _install_gromacs_executable(
        tmp_path / "gmx_d",
        expected_tpr=inputs["tpr"].read_bytes(),
        expected_trajectory=inputs["trajectory"].read_bytes(),
    )
    request = OracleRequest(
        engine_id="gromacs",
        case_id="rerun-1",
        task=gromacs.ORACLE_TASK,
        input_sha256={role: _sha256(path) for role, path in inputs.items()},
        parameters={
            "mode": "rerun",
            "precision": "double",
            "energy_terms": ["Potential"],
            "force_group": "System",
        },
    )
    execution = gromacs.run_rerun(
        executable,
        request=request,
        expected_executable_sha256=executable_hash,
        tpr=inputs["tpr"],
        trajectory=inputs["trajectory"],
    )
    assert execution.identity.precision == "double"
    assert execution.observations.energies.frames[1].time_fs == 2.0
    assert execution.mdrun.stdout == "mdrun complete"
    assert execution.energy_extract.stdout == "energy complete"
    assert execution.force_extract.stdout == "traj complete"
    assert "/proc/self/fd/" in execution.mdrun.argv[0]
    assert execution.provenance.request_sha256 == request.sha256
    assert execution.provenance.to_dict()["claim_safe"] is False
    assert set(execution.provenance.raw_output_sha256) >= {
        "energy_xvg",
        "force_xvg",
        "energy_edr",
        "force_trr",
    }
    assert execution.energy_xvg == GROMACS_ENERGY.encode("utf-8")
    assert execution.force_xvg == GROMACS_FORCE.encode("utf-8")
    assert (
        hashlib.sha256(execution.energy_xvg).hexdigest()
        == execution.provenance.raw_output_sha256["energy_xvg"]
    )
    assert (
        hashlib.sha256(execution.force_xvg).hexdigest()
        == execution.provenance.raw_output_sha256["force_xvg"]
    )


def test_gromacs_energy_force_parser_has_canonical_units_and_alignment() -> None:
    observations = gromacs.parse_rerun_text(GROMACS_ENERGY, GROMACS_FORCE)
    assert observations.energies.terms == ("Potential", "Coul-SR")
    assert observations.energies.frames[1].time_fs == 2.0
    assert observations.energies.values("Potential") == pytest.approx(
        (-125.0 / 4.184, -124.95 / 4.184)
    )
    assert observations.energies.frames[0].values_kj_mol == pytest.approx(
        (-125.0, -25.0)
    )
    assert observations.forces[0].forces_kcal_mol_angstrom[0] == pytest.approx(
        (1.0 / 41.84, 2.0 / 41.84, 3.0 / 41.84)
    )
    assert observations.forces[0].forces_kcal_mol_angstrom[1] == pytest.approx(
        (-1.0 / 41.84, -2.0 / 41.84, -3.0 / 41.84)
    )
    assert observations.forces[0].forces_kj_mol_nm[0] == pytest.approx((1.0, 2.0, 3.0))
    assert observations.forces[0].forces_kj_mol_nm[1] == pytest.approx(
        (-1.0, -2.0, -3.0)
    )

    with pytest.raises(gromacs.OracleAdapterError) as caught:
        gromacs.parse_force_text(GROMACS_FORCE.replace("3.5", "nan"))
    assert caught.value.code == "malformed"
    with pytest.raises(gromacs.OracleAdapterError) as caught:
        gromacs.parse_rerun_text(
            GROMACS_ENERGY, GROMACS_FORCE.replace("0.002000", "0.003000")
        )
    assert caught.value.code == "malformed"


def test_vina_prepared_only_command_freezes_scoring_and_box() -> None:
    command = vina.build_command(
        "vina",
        receptor_pdbqt="receptor.pdbqt",
        ligand_pdbqt="ligand.pdbqt",
        output_pdbqt="poses.pdbqt",
        center_angstrom=(1.0, -0.0, 3.5),
        size_angstrom=(20.0, 22.0, 24.0),
        seed=7,
        cpu=2,
    )
    assert command[:5] == (
        "vina",
        "--receptor",
        "receptor.pdbqt",
        "--ligand",
        "ligand.pdbqt",
    )
    assert command[command.index("--scoring") + 1] == "vina"
    assert "--cnn_scoring" not in command
    assert command[command.index("--center_y") + 1] == "0"
    assert command[command.index("--seed") + 1] == "7"

    for kwargs in (
        {"ligand_pdbqt": "raw.sdf"},
        {"scoring": "ad4"},
        {"cnn_scoring": "rescore"},
    ):
        base = {
            "binary": "vina",
            "receptor_pdbqt": "receptor.pdbqt",
            "ligand_pdbqt": "ligand.pdbqt",
            "output_pdbqt": "poses.pdbqt",
            "center_angstrom": (0.0, 0.0, 0.0),
            "size_angstrom": (20.0, 20.0, 20.0),
        }
        base.update(kwargs)
        with pytest.raises(vina.OracleAdapterError) as caught:
            vina.build_command(**base)
        assert caught.value.code == "malformed"


def test_vina_version_score_and_pose_outputs_cross_validate() -> None:
    identity = vina.parse_version("AutoDock Vina v1.2.5")
    assert (identity.version, identity.scoring, identity.cnn_scoring) == (
        "1.2.5",
        "vina",
        "none",
    )
    result = vina.parse_output(VINA_STDOUT, _vina_pose_text())
    assert tuple(score.affinity_kcal_mol for score in result.scores) == (-7.5, -7.0)
    assert tuple(pose.atom_count for pose in result.poses) == (1, 1)

    with pytest.raises(vina.OracleAdapterError) as caught:
        vina.parse_output(VINA_STDOUT, _vina_pose_text((-7.4, -7.0)))
    assert caught.value.code == "malformed"


def test_vina_run_executes_pinned_script_and_validates_written_pose(
    tmp_path: Path,
) -> None:
    receptor = _write(tmp_path / "prepared-receptor.pdbqt", "receptor\n")
    ligand = _write(tmp_path / "prepared-ligand.pdbqt", "ligand\n")
    executable, executable_hash = _install_docking_executable(
        tmp_path / "vina",
        version="AutoDock Vina v1.2.5",
        stdout=VINA_STDOUT,
        pose_bytes=_vina_pose_text().encode("utf-8"),
        expected_inputs={
            "--receptor": receptor.read_bytes(),
            "--ligand": ligand.read_bytes(),
        },
    )
    request = OracleRequest(
        engine_id="vina",
        case_id="vina-1",
        task=vina.ORACLE_TASK,
        input_sha256={"receptor": _sha256(receptor), "ligand": _sha256(ligand)},
        parameters={
            "center_angstrom": [0.0, 0.0, 0.0],
            "size_angstrom": [20.0, 20.0, 20.0],
            "exhaustiveness": 8,
            "num_modes": 9,
            "scoring": "vina",
            "cnn_scoring": "none",
        },
    )
    result = vina.run_vina(
        executable,
        request=request,
        expected_executable_sha256=executable_hash,
        receptor_pdbqt=receptor,
        ligand_pdbqt=ligand,
        center_angstrom=(0.0, 0.0, 0.0),
        size_angstrom=(20.0, 20.0, 20.0),
    )
    assert result.identity.version == "1.2.5"
    assert len(result.result.poses) == 2
    assert result.pose_pdbqt == _vina_pose_text().encode("utf-8")
    assert result.provenance.request_sha256 == request.sha256
    assert result.provenance.executable_sha256 == executable_hash
    assert "/proc/self/fd/" in result.command.argv[0]
    assert (
        result.provenance.raw_output_sha256["poses_pdbqt"]
        == hashlib.sha256(_vina_pose_text().encode("utf-8")).hexdigest()
    )
    assert result.provenance.to_dict()["scientifically_validated"] is False
    with pytest.raises(vina.OracleAdapterError) as caught:
        vina.parse_score_table(VINA_STDOUT.replace("-7.500", "nan"))
    assert caught.value.code == "malformed"


def test_vina_rejects_more_modes_than_requested(tmp_path: Path) -> None:
    executable, executable_hash, receptor, ligand, base_request = _vina_bound_case(
        tmp_path, "vina-mode-bound"
    )
    parameters = dict(base_request.parameters)
    parameters["num_modes"] = 1
    request = OracleRequest(
        engine_id="vina",
        case_id="vina-mode-bound",
        task=vina.ORACLE_TASK,
        input_sha256=base_request.input_sha256,
        parameters=parameters,
        seed=base_request.seed,
        thread_count=base_request.thread_count,
    )

    with pytest.raises(vina.OracleAdapterError) as caught:
        vina.run_vina(
            executable,
            request=request,
            expected_executable_sha256=executable_hash,
            receptor_pdbqt=receptor,
            ligand_pdbqt=ligand,
            center_angstrom=(0.0, 0.0, 0.0),
            size_angstrom=(20.0, 20.0, 20.0),
            num_modes=1,
        )

    assert caught.value.code == "malformed"
    assert caught.value.provenance is not None
    assert caught.value.provenance.error_code == "malformed"


def test_vina_high_assurance_real_binary_consumes_namespace_snapshot(
    tmp_path: Path,
) -> None:
    executable, executable_hash, receptor, ligand, request = _vina_bound_case(
        tmp_path, "vina-swap"
    )
    run = vina.run_vina(
        executable,
        request=request,
        expected_executable_sha256=executable_hash,
        receptor_pdbqt=receptor,
        ligand_pdbqt=ligand,
        center_angstrom=(0.0, 0.0, 0.0),
        size_angstrom=(20.0, 20.0, 20.0),
    )
    assert "/proc/self/fd/" in run.command.argv[0]
    assert "/proc/self/fd/" in run.command.argv[run.command.argv.index("--ligand") + 1]
    assert ligand.read_bytes() == b"trusted ligand\n"


def test_vina_high_assurance_sealed_snapshot_resists_binary_write(
    tmp_path: Path,
) -> None:
    executable, executable_hash, receptor, ligand, request = _vina_bound_case(
        tmp_path, "vina-private-swap"
    )

    executable, executable_hash = _install_docking_executable(
        executable,
        version="AutoDock Vina v1.2.5",
        stdout=VINA_STDOUT,
        pose_bytes=_vina_pose_text().encode("utf-8"),
        expected_inputs={
            "--receptor": receptor.read_bytes(),
            "--ligand": ligand.read_bytes(),
        },
        attempt_snapshot_write=True,
    )
    run = vina.run_vina(
        executable,
        request=request,
        expected_executable_sha256=executable_hash,
        receptor_pdbqt=receptor,
        ligand_pdbqt=ligand,
        center_angstrom=(0.0, 0.0, 0.0),
        size_angstrom=(20.0, 20.0, 20.0),
    )
    assert len(run.result.poses) == 2
    assert ligand.read_bytes() == b"trusted ligand\n"


def test_vina_high_assurance_rejects_drift_hash_and_path_inputs(
    tmp_path: Path,
) -> None:
    executable, executable_hash, receptor, ligand, request = _vina_bound_case(
        tmp_path, "vina-fail"
    )
    common = {
        "request": request,
        "expected_executable_sha256": executable_hash,
        "receptor_pdbqt": receptor,
        "ligand_pdbqt": ligand,
        "center_angstrom": (0.0, 0.0, 0.0),
        "size_angstrom": (20.0, 20.0, 20.0),
    }
    ligand.write_text("mutated ligand\n", encoding="utf-8")
    with pytest.raises(vina.OracleAdapterError) as caught:
        vina.run_vina(executable, **common)
    assert caught.value.code == "malformed"

    ligand.write_text("trusted ligand\n", encoding="utf-8")
    with pytest.raises(vina.OracleAdapterError) as caught:
        vina.run_vina(
            executable,
            **{**common, "expected_executable_sha256": "0" * 64},
        )
    assert caught.value.code == "malformed"
    with pytest.raises(vina.OracleAdapterError) as caught:
        vina.run_vina(
            "vina",
            **common,
        )
    assert caught.value.code == "binary_missing"


def test_vina_nonzero_retains_bounded_claim_false_failure_provenance(
    tmp_path: Path,
) -> None:
    executable, executable_hash, receptor, ligand, request = _vina_bound_case(
        tmp_path, "vina-nonzero"
    )
    executable, executable_hash = _install_docking_executable(
        executable,
        version="AutoDock Vina v1.2.5",
        stdout="partial solver stdout",
        stderr="bounded solver failure",
        pose_bytes=_vina_pose_text().encode("utf-8"),
        expected_inputs={
            "--receptor": receptor.read_bytes(),
            "--ligand": ligand.read_bytes(),
        },
        returncode=17,
    )
    with pytest.raises(vina.OracleAdapterError) as caught:
        vina.run_vina(
            executable,
            request=request,
            expected_executable_sha256=executable_hash,
            receptor_pdbqt=receptor,
            ligand_pdbqt=ligand,
            center_angstrom=(0.0, 0.0, 0.0),
            size_angstrom=(20.0, 20.0, 20.0),
        )
    assert caught.value.code == "nonzero"
    provenance = caught.value.provenance
    assert provenance is not None
    assert provenance.status == "failure"
    assert provenance.error_code == "nonzero_exit"
    assert provenance.request_sha256 == request.sha256
    assert provenance.executable_sha256 == executable_hash
    assert dict(provenance.values["input_sha256"]) == dict(request.input_sha256)
    assert (
        provenance.raw_output_sha256["failure_stderr"]
        == hashlib.sha256(b"bounded solver failure").hexdigest()
    )
    assert provenance.to_dict()["claim_safe"] is False


def test_vina_nonfinite_output_retains_all_captured_failure_hashes(
    tmp_path: Path,
) -> None:
    executable, executable_hash, receptor, ligand, request = _vina_bound_case(
        tmp_path, "vina-nonfinite"
    )
    malformed_stdout = VINA_STDOUT.replace("-7.500", "nan", 1)
    pose_text = _vina_pose_text()
    executable, executable_hash = _install_docking_executable(
        executable,
        version="AutoDock Vina v1.2.5",
        stdout=malformed_stdout,
        pose_bytes=pose_text.encode("utf-8"),
        expected_inputs={
            "--receptor": receptor.read_bytes(),
            "--ligand": ligand.read_bytes(),
        },
    )

    with pytest.raises(vina.OracleAdapterError) as caught:
        vina.run_vina(
            executable,
            request=request,
            expected_executable_sha256=executable_hash,
            receptor_pdbqt=receptor,
            ligand_pdbqt=ligand,
            center_angstrom=(0.0, 0.0, 0.0),
            size_angstrom=(20.0, 20.0, 20.0),
        )

    assert caught.value.code == "malformed"
    provenance = caught.value.provenance
    assert provenance is not None
    assert provenance.status == "failure"
    assert provenance.error_code == "malformed"
    assert (
        provenance.raw_output_sha256["docking_stdout"]
        == hashlib.sha256(malformed_stdout.encode("utf-8")).hexdigest()
    )
    assert (
        provenance.raw_output_sha256["poses_pdbqt"]
        == hashlib.sha256(pose_text.encode("utf-8")).hexdigest()
    )
    assert set(provenance.raw_output_sha256) >= {
        "version_stdout",
        "version_stderr",
        "docking_stdout",
        "docking_stderr",
        "poses_pdbqt",
    }
    assert provenance.to_dict()["claim_safe"] is False


def test_gnina_prepared_only_command_freezes_cnn_rescoring() -> None:
    command = gnina.build_command(
        "gnina",
        receptor="receptor.pdb",
        ligand="start.sdf",
        autobox_ligand="crystal.sdf",
        output_sdf="poses.sdf",
        seed=19,
    )
    assert command[command.index("--scoring") + 1] == "vina"
    assert command[command.index("--cnn_scoring") + 1] == "rescore"
    assert command[command.index("--cnn") + 1] == "crossdock_default2018"
    assert "--no_gpu" in command

    with pytest.raises(gnina.OracleAdapterError) as caught:
        gnina.build_command(
            "gnina",
            receptor="receptor.pdb",
            ligand="start.sdf",
            autobox_ligand="crystal.sdf",
            output_sdf="poses.sdf",
            cnn_scoring="all",
        )
    assert caught.value.code == "malformed"


def test_gnina_public_redocking_builder_preserves_both_frozen_modes() -> None:
    paths = {
        "receptor": Path("case/case_protein.pdb"),
        "seed": Path("case/case_ligand_start_conf.sdf"),
        "native": Path("case/case_ligand.sdf"),
    }
    vina_command = gnina.build_prepared_redocking_command(
        "case",
        "vina",
        paths,
        binary=Path("private/gnina"),
        output=Path("poses/vina.sdf"),
        seed=11,
    )
    gnina_command = gnina.build_prepared_redocking_command(
        "case",
        "gnina",
        paths,
        binary=Path("private/gnina"),
        output=Path("poses/gnina.sdf"),
        seed=11,
    )
    common = (
        "private/gnina",
        "--receptor",
        "case/case_protein.pdb",
        "--ligand",
        "case/case_ligand_start_conf.sdf",
        "--autobox_ligand",
        "case/case_ligand.sdf",
        "--autobox_add",
        "4",
        "--num_modes",
        "5",
        "--exhaustiveness",
        "1",
        "--cpu",
        "1",
        "--no_gpu",
        "--seed",
        "11",
    )
    assert vina_command[: len(common)] == common
    assert vina_command[-4:] == ("--scoring", "vina", "--cnn_scoring", "none")
    assert gnina_command[-6:] == (
        "--scoring",
        "vina",
        "--cnn_scoring",
        "rescore",
        "--cnn",
        "crossdock_default2018",
    )


def test_gnina_version_score_and_sdf_outputs_cross_validate() -> None:
    identity = gnina.parse_version("gnina v1.0.3 HEAD:deadbeef")
    assert (
        identity.version,
        identity.scoring,
        identity.cnn_scoring,
        identity.cnn_model,
    ) == ("1.0.3", "vina", "rescore", "crossdock_default2018")
    result = gnina.parse_output(GNINA_STDOUT, GNINA_SDF)
    assert tuple(score.cnn_pose_score for score in result.scores) == (0.8, 0.7)
    assert tuple(pose.atom_count for pose in result.poses) == (1, 1)

    with pytest.raises(gnina.OracleAdapterError) as caught:
        gnina.parse_output(GNINA_STDOUT, GNINA_SDF.replace("0.8\n", "inf\n", 1))
    assert caught.value.code == "malformed"


def test_gnina_run_executes_pinned_script_and_validates_written_pose(
    tmp_path: Path,
) -> None:
    receptor = _write(tmp_path / "prepared-receptor.pdb", "receptor\n")
    ligand = _write(tmp_path / "prepared-ligand.sdf", "ligand\n")
    autobox = _write(tmp_path / "prepared-crystal.sdf", "crystal\n")
    executable, executable_hash = _install_docking_executable(
        tmp_path / "gnina",
        version="gnina v1.0.3",
        stdout=GNINA_STDOUT,
        pose_bytes=GNINA_SDF.encode("utf-8"),
        expected_inputs={
            "--receptor": receptor.read_bytes(),
            "--ligand": ligand.read_bytes(),
            "--autobox_ligand": autobox.read_bytes(),
        },
    )
    request = OracleRequest(
        engine_id="gnina",
        case_id="gnina-1",
        task=gnina.ORACLE_TASK,
        input_sha256={
            "receptor": _sha256(receptor),
            "ligand": _sha256(ligand),
            "autobox_ligand": _sha256(autobox),
        },
        parameters={
            "autobox_add_angstrom": 4.0,
            "exhaustiveness": 8,
            "num_modes": 9,
            "scoring": "vina",
            "cnn_scoring": "rescore",
            "cnn_model": "crossdock_default2018",
            "no_gpu": True,
        },
    )
    result = gnina.run_gnina(
        executable,
        request=request,
        expected_executable_sha256=executable_hash,
        receptor=receptor,
        ligand=ligand,
        autobox_ligand=autobox,
    )
    assert result.identity.version == "1.0.3"
    assert len(result.result.poses) == 2
    assert result.pose_sdf == GNINA_SDF.encode("utf-8")
    assert result.provenance.request_sha256 == request.sha256
    assert result.provenance.executable_sha256 == executable_hash
    assert "/proc/self/fd/" in result.command.argv[0]
    assert (
        result.provenance.raw_output_sha256["poses_sdf"]
        == hashlib.sha256(GNINA_SDF.encode("utf-8")).hexdigest()
    )
    assert result.provenance.to_dict()["claim_safe"] is False
    with pytest.raises(gnina.OracleAdapterError) as caught:
        gnina.parse_output(GNINA_STDOUT, GNINA_SDF.replace("-8.1\n", "-8.0\n", 1))
    assert caught.value.code == "malformed"


def test_gnina_rejects_more_modes_than_requested(tmp_path: Path) -> None:
    (
        executable,
        executable_hash,
        receptor,
        ligand,
        autobox,
        base_request,
    ) = _gnina_bound_case(tmp_path, "gnina-mode-bound")
    parameters = dict(base_request.parameters)
    parameters["num_modes"] = 1
    request = OracleRequest(
        engine_id="gnina",
        case_id="gnina-mode-bound",
        task=gnina.ORACLE_TASK,
        input_sha256=base_request.input_sha256,
        parameters=parameters,
        seed=base_request.seed,
        thread_count=base_request.thread_count,
    )

    with pytest.raises(gnina.OracleAdapterError) as caught:
        gnina.run_gnina(
            executable,
            request=request,
            expected_executable_sha256=executable_hash,
            receptor=receptor,
            ligand=ligand,
            autobox_ligand=autobox,
            num_modes=1,
        )

    assert caught.value.code == "malformed"
    assert caught.value.provenance is not None
    assert caught.value.provenance.error_code == "malformed"


def test_gnina_high_assurance_rejects_symlink_solver_output(
    tmp_path: Path,
) -> None:
    executable, executable_hash, receptor, ligand, autobox, request = _gnina_bound_case(
        tmp_path, "gnina-fresh"
    )
    executable, executable_hash = _install_docking_executable(
        executable,
        version="gnina v1.0.3",
        stdout=GNINA_STDOUT,
        pose_bytes=GNINA_SDF.encode("utf-8"),
        expected_inputs={
            "--receptor": receptor.read_bytes(),
            "--ligand": ligand.read_bytes(),
            "--autobox_ligand": autobox.read_bytes(),
        },
        symlink_output=True,
    )
    common = {
        "request": request,
        "expected_executable_sha256": executable_hash,
        "receptor": receptor,
        "ligand": ligand,
        "autobox_ligand": autobox,
    }
    with pytest.raises(gnina.OracleAdapterError) as caught:
        gnina.run_gnina(executable, **common)
    assert caught.value.code == "malformed"


def test_gnina_high_assurance_rejects_exact_role_or_digest_mismatch(
    tmp_path: Path,
) -> None:
    executable, executable_hash, receptor, ligand, autobox, request = _gnina_bound_case(
        tmp_path, "gnina-binding"
    )
    parameters = dict(request.to_dict()["parameters"])
    missing_role = OracleRequest(
        engine_id="gnina",
        case_id="missing-role",
        task=gnina.ORACLE_TASK,
        input_sha256={"receptor": _sha256(receptor), "ligand": _sha256(ligand)},
        parameters=parameters,
    )
    with pytest.raises(gnina.OracleAdapterError) as caught:
        gnina.run_gnina(
            executable,
            request=missing_role,
            expected_executable_sha256=executable_hash,
            receptor=receptor,
            ligand=ligand,
            autobox_ligand=autobox,
        )
    assert caught.value.code == "malformed"

    bad_digest = OracleRequest(
        engine_id="gnina",
        case_id="bad-digest",
        task=gnina.ORACLE_TASK,
        input_sha256={
            "receptor": _sha256(receptor),
            "ligand": "0" * 64,
            "autobox_ligand": _sha256(autobox),
        },
        parameters=parameters,
    )
    with pytest.raises(gnina.OracleAdapterError) as caught:
        gnina.run_gnina(
            executable,
            request=bad_digest,
            expected_executable_sha256=executable_hash,
            receptor=receptor,
            ligand=ligand,
            autobox_ligand=autobox,
        )
    assert caught.value.code == "malformed"


@pytest.mark.parametrize(
    "entrypoint", (vina.run_vina, gnina.run_gnina, gromacs.run_rerun)
)
def test_provenance_entrypoints_do_not_expose_runner_injection(entrypoint) -> None:
    assert "runner" not in inspect.signature(entrypoint).parameters


@pytest.mark.parametrize(
    ("module", "valid_version"),
    (
        (gromacs, GROMACS_VERSION),
        (vina, "AutoDock Vina v1.2.5"),
        (gnina, "gnina v1.0.3"),
    ),
)
@pytest.mark.parametrize(
    ("response", "code"),
    (
        (FileNotFoundError(), "binary_missing"),
        (subprocess.TimeoutExpired(cmd=["fake"], timeout=1.0), "timeout"),
        (_completed(returncode=17), "nonzero"),
        (_completed(stdout="not an engine identity"), "malformed"),
        (_completed(stdout="x" * 1_048_577), "malformed"),
    ),
)
def test_all_adapters_use_stable_execution_error_codes(
    module: object,
    valid_version: str,
    response: object,
    code: str,
) -> None:
    del valid_version
    runner = FakeRunner(response)
    with pytest.raises(module.OracleAdapterError) as caught:  # type: ignore[attr-defined]
        module.probe_identity("missing-or-fake", runner=runner)  # type: ignore[attr-defined]
    assert caught.value.code == code
