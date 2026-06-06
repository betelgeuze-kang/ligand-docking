from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from deploy.model_registry import (
    download_model_artifact,
    load_index,
    publish_model_artifact,
    rollback_model_version,
)


def test_publish_download_and_tamper_detection(tmp_path: Path) -> None:
    registry = tmp_path / "registry"
    download = tmp_path / "download"
    artifact = tmp_path / "model.pt"
    artifact.write_bytes(b"weights-v1")

    manifest = publish_model_artifact(
        model_path=artifact,
        model_name="residual_score",
        version="v1",
        registry_dir=registry,
        signing_key="secret",
        key_id="unit-test",
        metadata={"approved_by": "operator"},
    )

    assert manifest["manifest_version"] == "product_model_artifact_manifest_v1"
    assert manifest["artifact_sha256"]
    assert manifest["signature"]
    assert load_index(registry_dir=registry, model_name="residual_score")["current_version"] == "v1"

    result = download_model_artifact(
        model_name="residual_score",
        version_or_stage="current",
        registry_dir=registry,
        download_path=download,
        signing_key="secret",
    )
    assert result["verified"] is True
    assert Path(result["artifact_path"]).read_bytes() == b"weights-v1"
    assert Path(result["manifest_path"]).is_file()

    registered_artifact = registry / "models" / "residual_score" / "versions" / "v1" / "artifacts" / "model.pt"
    registered_artifact.write_bytes(b"tampered")
    with pytest.raises(ValueError, match="sha256 mismatch"):
        download_model_artifact(
            model_name="residual_score",
            version_or_stage="current",
            registry_dir=registry,
            download_path=download,
            signing_key="secret",
        )


def test_rollback_restores_previous_signed_version(tmp_path: Path) -> None:
    registry = tmp_path / "registry"
    v1 = tmp_path / "model-v1.bin"
    v2 = tmp_path / "model-v2.bin"
    v1.write_bytes(b"one")
    v2.write_bytes(b"two")

    publish_model_artifact(
        model_path=v1,
        model_name="pose_ranker",
        version="v1",
        registry_dir=registry,
        signing_key="secret",
        key_id="unit-test",
    )
    publish_model_artifact(
        model_path=v2,
        model_name="pose_ranker",
        version="v2",
        registry_dir=registry,
        signing_key="secret",
        key_id="unit-test",
    )

    assert load_index(registry_dir=registry, model_name="pose_ranker")["current_version"] == "v2"
    index = rollback_model_version(
        model_name="pose_ranker",
        target_version="previous",
        registry_dir=registry,
        signing_key="secret",
        key_id="unit-test",
    )
    assert index["current_version"] == "v1"
    assert index["activation_reason"] == "rollback"


def test_current_pointer_tamper_is_rejected(tmp_path: Path) -> None:
    registry = tmp_path / "registry"
    download = tmp_path / "download"
    artifact = tmp_path / "model.bin"
    artifact.write_bytes(b"payload")

    publish_model_artifact(
        model_path=artifact,
        model_name="tamper_model",
        version="v1",
        registry_dir=registry,
        signing_key="secret",
        key_id="unit-test",
    )

    index_path = registry / "models" / "tamper_model" / "index.json"
    index = json.loads(index_path.read_text(encoding="utf-8"))
    index["current_version"] = "v2"
    index_path.write_text(json.dumps(index, sort_keys=True), encoding="utf-8")

    with pytest.raises(ValueError, match="index signature verification failed"):
        download_model_artifact(
            model_name="tamper_model",
            version_or_stage="current",
            registry_dir=registry,
            download_path=download,
            signing_key="secret",
        )
    next_artifact = tmp_path / "model-v2.bin"
    next_artifact.write_bytes(b"next")
    with pytest.raises(ValueError, match="index signature verification failed"):
        publish_model_artifact(
            model_path=next_artifact,
            model_name="tamper_model",
            version="v2",
            registry_dir=registry,
            signing_key="secret",
            key_id="unit-test",
        )


def test_upload_download_rollback_clis_round_trip(tmp_path: Path) -> None:
    registry = tmp_path / "registry"
    download = tmp_path / "download"
    model_v1 = tmp_path / "model-v1.bin"
    model_v2 = tmp_path / "model-v2.bin"
    model_v1.write_bytes(b"cli-one")
    model_v2.write_bytes(b"cli-two")
    env = {**os.environ, "MODEL_REGISTRY_SIGNING_KEY": "secret", "MODEL_REGISTRY_KEY_ID": "unit-test"}

    for path, version in [(model_v1, "v1"), (model_v2, "v2")]:
        subprocess.run(
            [
                sys.executable,
                "deploy/upload_model.py",
                "--model_path",
                str(path),
                "--model_name",
                "cli_model",
                "--version",
                version,
                "--registry-dir",
                str(registry),
            ],
            cwd=Path.cwd(),
            env=env,
            check=True,
            capture_output=True,
            text=True,
        )

    rollback = subprocess.run(
        [
            sys.executable,
            "deploy/rollback_model.py",
            "--model_name",
            "cli_model",
            "--registry-dir",
            str(registry),
        ],
        cwd=Path.cwd(),
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )
    assert json.loads(rollback.stdout)["current_version"] == "v1"

    downloaded = subprocess.run(
        [
            sys.executable,
            "deploy/download_model.py",
            "--model_name",
            "cli_model",
            "--version_or_stage",
            "current",
            "--registry-dir",
            str(registry),
            "--download_path",
            str(download),
        ],
        cwd=Path.cwd(),
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )
    assert json.loads(downloaded.stdout)["verified"] is True
    assert (download / "model-v1.bin").read_bytes() == b"cli-one"
