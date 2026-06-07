from __future__ import annotations

import importlib.metadata
import importlib.util
import re
from pathlib import Path
from typing import Any

CLAIM_BOUNDARY = (
    "CAMEO API dependency readiness only; it audits the optional API server dependency profile needed for local "
    "receiver runtime smoke. It does not install packages, start a server, register CAMEO, submit predictions, send email, "
    "or mutate external state."
)

EXTRA_RUNTIME_IMPORTS = ("fastapi.testclient",)
IMPORT_NAME_OVERRIDES = {
    "pydantic-settings": "pydantic_settings",
}


def _text(value: Any) -> str:
    return str(value or "").strip()


def _normalize_name(value: str) -> str:
    return re.sub(r"[-_.]+", "-", value.strip().lower())


def _display_from_requirement(requirement: str) -> str:
    text = requirement.strip()
    if ";" in text:
        text = text.split(";", 1)[0].strip()
    if " @ " in text:
        text = text.split(" @ ", 1)[0].strip()
    return re.split(r"\s*(?:===|~=|==|!=|<=|>=|<|>)\s*|\s+", text, maxsplit=1)[0].strip()


def _base_package_name(display_name: str) -> str:
    return display_name.split("[", 1)[0].strip()


def _import_name(display_name: str) -> str:
    base = _normalize_name(_base_package_name(display_name))
    return IMPORT_NAME_OVERRIDES.get(base, base.replace("-", "_"))


def _installed_version(display_name: str) -> str:
    base = _base_package_name(display_name)
    try:
        return importlib.metadata.version(base)
    except importlib.metadata.PackageNotFoundError:
        return ""


def _importable(import_name: str) -> bool:
    try:
        return importlib.util.find_spec(import_name) is not None
    except (ImportError, ModuleNotFoundError, ValueError):
        return False


def _parse_requirements(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if " #" in stripped:
            stripped = stripped.split(" #", 1)[0].strip()
        display_name = _display_from_requirement(stripped)
        if not display_name:
            continue
        import_name = _import_name(display_name)
        version = _installed_version(display_name)
        can_import = _importable(import_name)
        rows.append(
            {
                "source_line": line_number,
                "requirement": stripped,
                "display_name": display_name,
                "package_name": _base_package_name(display_name),
                "import_name": import_name,
                "installed_version": version,
                "importable": can_import,
                "status": "pass" if can_import else "fail",
                "install_or_activate_hint": f"install/activate API profile package: {display_name}",
                "external_state_mutated": False,
            }
        )
    return rows


def _blocker(code: str, reason: str, *, package: str = "") -> dict[str, str]:
    payload = {"code": code, "severity": "hard", "reason": reason}
    if package:
        payload["package"] = package
    return payload


def build_cameo_api_dependency_readiness(
    *,
    requirements_path: str | Path = "requirements-api.txt",
    root: str | Path = ".",
) -> dict[str, Any]:
    root_path = Path(root).resolve()
    req_path = Path(requirements_path)
    if not req_path.is_absolute():
        req_path = root_path / req_path

    blockers: list[dict[str, str]] = []
    rows: list[dict[str, Any]] = []
    if not req_path.exists():
        blockers.append(_blocker("requirements_api_missing", f"API requirements file is missing: {req_path}"))
    else:
        rows.extend(_parse_requirements(req_path))

    for row in rows:
        if row["status"] != "pass":
            blockers.append(
                _blocker(
                    "api_dependency_not_importable",
                    f"{row['display_name']} must be importable as {row['import_name']} for CAMEO receiver runtime smoke.",
                    package=_text(row["display_name"]),
                )
            )

    extra_rows: list[dict[str, Any]] = []
    for import_name in EXTRA_RUNTIME_IMPORTS:
        can_import = _importable(import_name)
        extra_rows.append(
            {
                "source_line": 0,
                "requirement": import_name,
                "display_name": import_name,
                "package_name": import_name,
                "import_name": import_name,
                "installed_version": "",
                "importable": can_import,
                "status": "pass" if can_import else "fail",
                "install_or_activate_hint": "install/activate API profile so FastAPI TestClient is importable",
                "external_state_mutated": False,
            }
        )
        if not can_import:
            blockers.append(
                _blocker(
                    "api_runtime_extra_not_importable",
                    f"{import_name} must be importable for local CAMEO POST smoke.",
                    package=import_name,
                )
            )
    rows.extend(extra_rows)

    status = "cameo_api_dependency_ready" if not blockers else "blocked_cameo_api_dependency_readiness"
    missing = [row["display_name"] for row in rows if row["status"] != "pass"]
    summary = {
        "packet_type": "cameo_api_dependency_readiness",
        "status": status,
        "requirements_path": str(req_path),
        "declared_dependency_count": len([row for row in rows if row["source_line"] > 0]),
        "runtime_extra_count": len(extra_rows),
        "pass_count": sum(1 for row in rows if row["status"] == "pass"),
        "missing_or_unimportable_count": len(missing),
        "missing_or_unimportable": missing,
        "blocker_count": len(blockers),
        "execution_enabled": False,
        "server_started": False,
        "package_install_executed": False,
        "outbound_email_enabled": False,
        "external_state_mutated": False,
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": (
            "Install or activate the API dependency profile from requirements-api.txt, then rerun CAMEO API dependency readiness and receiver smoke."
            if blockers
            else "API dependency profile is importable; rerun CAMEO receiver smoke to verify POST /cameo/targets and fail-closed ledger evidence."
        ),
    }
    return {"summary": summary, "blockers": blockers, "rows": rows}
