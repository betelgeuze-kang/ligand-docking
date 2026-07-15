from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path

import pytest

from api.job_store import SQLiteJobStore


def _precreate_external_link(
    *,
    link_kind: str,
    victim: Path,
    destination: Path,
) -> None:
    if destination.exists() or destination.is_symlink():
        destination.unlink()
    if link_kind == "symlink":
        destination.symlink_to(victim)
    else:
        os.link(victim, destination)


@pytest.mark.parametrize("link_kind", ["symlink", "hardlink"])
def test_runner_linked_status_is_rejected_without_victim_write_or_completion(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    link_kind: str,
) -> None:
    import api.worker as worker

    job_id = f"job-linked-status-{link_kind}"
    store = SQLiteJobStore(tmp_path / "jobs.sqlite3")
    store.create_job(job_id, {"target_name": "ADRB2"})
    acquired = store.acquire_next_job("worker-attacker", lease_seconds=60)
    assert acquired is not None
    monkeypatch.setattr(
        worker.settings, "results_storage_path", str(tmp_path / "results")
    )
    worker.write_status_file(
        worker.job_status_path(job_id),
        {"job_id": job_id, "status": "submitted"},
    )
    victim = tmp_path / f"status-{link_kind}-victim.json"

    async def _malicious_runner(current_job_id: str, request_data: dict) -> None:
        attempt_dir = Path(worker.job_results_dir(current_job_id))
        result_path = attempt_dir / "result.json"
        result_path.write_text('{"owner":"ATTACKER"}\n', encoding="utf-8")
        victim.write_text(
            json.dumps(
                {
                    "job_id": current_job_id,
                    "status": "completed",
                    "result_file": str(result_path),
                }
            ),
            encoding="utf-8",
        )
        _precreate_external_link(
            link_kind=link_kind,
            victim=victim,
            destination=attempt_dir / "status.json",
        )

    failed = asyncio.run(
        worker.run_job_once(
            store,
            job_id=job_id,
            request_data=dict(acquired["request"]),
            runner=_malicious_runner,
            worker_id="worker-attacker",
            attempt_token=str(acquired["attempt_token"]),
            lease_seconds=60,
        )
    )

    expected_victim = json.dumps(
        {
            "job_id": job_id,
            "status": "completed",
            "result_file": str(
                Path(failed["published_status_path"]).parent / "result.json"
            ),
        }
    )
    assert victim.read_text(encoding="utf-8") == expected_victim
    assert failed["status"] == "failed"
    assert store.get_job(job_id)["status"] == "failed"
    assert not any(
        event["payload"].get("status") == "completed"
        for event in store.list_pending_outbox_events()
    )


@pytest.mark.parametrize("link_kind", ["symlink", "hardlink"])
def test_parent_reserved_artifacts_replace_links_without_touching_victims_and_serve_winner(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    link_kind: str,
) -> None:
    import api.main as main
    import api.worker as worker
    from fastapi.testclient import TestClient

    job_id = f"job-parent-reserved-{link_kind}"
    store = SQLiteJobStore(tmp_path / "jobs.sqlite3")
    store.create_job(job_id, {"target_name": "ADRB2"})
    results_root = tmp_path / "results"
    monkeypatch.setattr(worker.settings, "results_storage_path", str(results_root))
    monkeypatch.setattr(main.settings, "results_storage_path", str(results_root))
    monkeypatch.setattr(main.settings, "api_job_store_path", str(store.path))
    monkeypatch.setattr(main, "job_store", store)
    worker.write_status_file(
        worker.job_status_path(job_id),
        {"job_id": job_id, "status": "submitted"},
    )
    victims: dict[str, tuple[Path, bytes]] = {}

    async def _winner_with_precreated_links(
        current_job_id: str,
        request_data: dict,
    ) -> None:
        attempt_dir = Path(worker.job_results_dir(current_job_id))
        result_path = attempt_dir / "winner.json"
        result_path.write_text('{"owner":"WINNER"}\n', encoding="utf-8")
        for reserved_name in (
            "result_manifest.json",
            "evidence_bundle.json",
            "published_status.json",
        ):
            victim = tmp_path / f"{link_kind}-{reserved_name}"
            content = f"external victim for {reserved_name}\n".encode()
            victim.write_bytes(content)
            victims[reserved_name] = (victim, content)
            _precreate_external_link(
                link_kind=link_kind,
                victim=victim,
                destination=attempt_dir / reserved_name,
            )
        worker.write_status_file(
            worker.job_status_path(current_job_id),
            {
                "job_id": current_job_id,
                "status": "completed",
                "result_file": str(result_path),
            },
        )

    completed = asyncio.run(
        worker.process_next_job_once(
            store,
            worker_id="worker-winner",
            runner=_winner_with_precreated_links,
            lease_seconds=60,
        )
    )

    assert completed is not None
    assert completed["status"] == "completed"
    for reserved_name, (victim, original_content) in victims.items():
        assert victim.read_bytes() == original_content
        published_path = (
            Path(completed["published_status_path"])
            if reserved_name == "published_status.json"
            else Path(completed[f"{reserved_name.removesuffix('.json')}_path"])
        )
        assert not os.path.samefile(victim, published_path)

    response = TestClient(main.app).get(f"/results/{job_id}")
    assert response.status_code == 200
    assert response.json() == {"owner": "WINNER"}
    completed_events = [
        event
        for event in store.list_pending_outbox_events()
        if event["payload"].get("status") == "completed"
    ]
    assert len(completed_events) == 1
