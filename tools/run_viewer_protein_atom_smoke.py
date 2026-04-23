#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path

from selenium import webdriver
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from selenium.webdriver.firefox.service import Service as FirefoxService
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.select import Select
from selenium.webdriver.support.ui import WebDriverWait

from viewer_smoke_geometry_probe import summarize_geometry_probe

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PORT = 8765
DEFAULT_HOST = "127.0.0.1"
PROTEIN_SMOKE_BUNDLE = ROOT / "runs" / "viewer_protein_atom_smoke" / "protein_atom_frames_smoke_bundle_current.json"
DEFAULT_OUT_JSON = ROOT / "runs" / "viewer_protein_atom_smoke" / "protein_atom_frames_browser_smoke_current.json"
DEFAULT_SCREENSHOT = ROOT / "runs" / "viewer_protein_atom_smoke" / "protein_atom_frames_browser_smoke_current.png"
DEFAULT_FIREFOX_BIN = "/usr/bin/firefox"
DEFAULT_GECKODRIVER = "/snap/bin/geckodriver"


def _is_port_open(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.5)
        return sock.connect_ex((host, port)) == 0


def _start_server(host: str, port: int) -> subprocess.Popen[str]:
    return subprocess.Popen(
        [sys.executable, "-m", "http.server", str(port), "--bind", host],
        cwd=str(ROOT),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        text=True,
        start_new_session=True,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a headless browser smoke for the Protein Motion Smoke viewer preset.")
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--out-json", default=str(DEFAULT_OUT_JSON))
    parser.add_argument("--screenshot", default=str(DEFAULT_SCREENSHOT))
    parser.add_argument("--firefox-bin", default=DEFAULT_FIREFOX_BIN)
    parser.add_argument("--geckodriver", default=DEFAULT_GECKODRIVER)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    out_json = Path(args.out_json).resolve()
    screenshot = Path(args.screenshot).resolve()
    out_json.parent.mkdir(parents=True, exist_ok=True)

    subprocess.run([sys.executable, str(ROOT / "tools" / "build_viewer_protein_atom_smoke_fixture.py")], check=True, cwd=str(ROOT))

    server_proc: subprocess.Popen[str] | None = None
    if not _is_port_open(args.host, args.port):
        server_proc = _start_server(args.host, args.port)
        for _ in range(30):
            if _is_port_open(args.host, args.port):
                break
            time.sleep(0.25)
        else:
            raise RuntimeError(f"viewer smoke server failed to start on {args.host}:{args.port}")

    url = f"http://{args.host}:{args.port}/viewer/index.html?smoke=protein-motion"
    options = FirefoxOptions()
    options.add_argument("-headless")
    service = FirefoxService(executable_path=args.geckodriver if Path(args.geckodriver).exists() else None)
    driver = None

    try:
        driver = webdriver.Firefox(service=service, options=options)
        wait = WebDriverWait(driver, 30)
        driver.set_window_size(1500, 1100)
        driver.get(url)
        driver.execute_script("window.localStorage.clear(); window.sessionStorage.clear();")
        driver.get(url)

        wait.until(EC.presence_of_element_located((By.ID, "bundleInput")))
        bundle_ingest = driver.execute_async_script(
            """
            const done = arguments[arguments.length - 1];
            (async () => {
              try {
                if (typeof loadSurfaceBundlePreset !== 'function') throw new Error('loadSurfaceBundlePreset unavailable');
                const ok = await loadSurfaceBundlePreset('protein_atom_frames_smoke', { showSuccessToast: false });
                const debug = window.__viewerDebugApi?.getState?.() || window.__viewerDebugState || null;
                done({ ok, debug });
              } catch (error) {
                done({ ok: false, error: String(error && error.message ? error.message : error) });
              }
            })();
            """
        )
        if not bundle_ingest or not bundle_ingest.get("ok"):
            raise RuntimeError(f"protein smoke bundle ingest failed: {bundle_ingest}")
        debug_state = driver.execute_script("return window.__viewerDebugApi?.getState?.() || window.__viewerDebugState || null;")
        candidate_count = (debug_state or {}).get("candidateCount", -1)
        if not isinstance(candidate_count, int) or candidate_count < 1:
            bundle_status = driver.find_element(By.ID, "bundleStatus").text.strip()
            raise RuntimeError(
                f"protein smoke bundle ingest produced no candidates: count={candidate_count} status={bundle_status} debug={debug_state}"
            )
        wait.until(lambda d: len(d.find_elements(By.CSS_SELECTOR, "#fileList li.file-item-card")) >= 1)
        driver.find_elements(By.CSS_SELECTOR, "#fileList li")[0].click()
        smoke_js = driver.execute_async_script(
            """
            const done = arguments[arguments.length - 1];
            (async () => {
              try {
                let trajectorySummary = null;
                if (typeof selectCandidate === 'function') {
                  await selectCandidate(0, { forceReload: true });
                }
                if (typeof getSelectedCandidate === 'function' && typeof ensureTrajectoryData === 'function') {
                  const candidate = getSelectedCandidate();
                  if (candidate) {
                    await ensureTrajectoryData(candidate);
                    const collectStateCellProbeForViewer = (viewerLike) => {
                      if (typeof collectViewerStateRepresentationProbe === 'function') {
                        return collectViewerStateRepresentationProbe();
                      }
                      return {
                        stateRepCount: 0,
                        stateSurfaceRepCount: 0,
                        stateGaussianRepCount: 0,
                        stateMolecularSurfaceRepCount: 0,
                        state3DRepCount: 0,
                      };
                    };
                    const geometryProbe = typeof collectCanvas3dGeometryProbe === 'function'
                      ? collectCanvas3dGeometryProbe()
                      : null;
                    const geometryProbeDetail = {
                      canvas3d: geometryProbe,
                      stateCells: collectStateCellProbeForViewer(),
                      pocket: typeof collectPocketGeometryProbe === 'function'
                        ? collectPocketGeometryProbe(candidate)
                        : null,
                    };
                    trajectorySummary = {
                      frameCount: Number(candidate?.trajectoryData?.frameCount || 0),
                      proteinAtomSchemaReady: Boolean(candidate?.trajectoryData?.proteinAtomSchemaReady),
                      proteinAtomSchemaVersion: String(candidate?.trajectoryData?.proteinAtomSchemaVersion || ''),
                      proteinResidueSchemaReady: Boolean(candidate?.trajectoryData?.proteinResidueSchemaReady),
                      proteinResidueSchemaVersion: String(candidate?.trajectoryData?.proteinResidueSchemaVersion || ''),
                      geometryProbe,
                      geometryProbeDetail,
                    };
                    if (typeof queueTrajectoryFrameRender === 'function') {
                      await queueTrajectoryFrameRender(candidate, 0);
                    }
                  }
                }
                done({ ok: true, trajectorySummary });
              } catch (error) {
                done({ ok: false, error: String(error && error.message ? error.message : error) });
              }
            })();
            """
        )
        time.sleep(1.5)

        bundle_status = driver.find_element(By.ID, "bundleStatus").text.strip()
        struct_info = driver.find_element(By.ID, "structInfo").text.strip()
        body_text = driver.find_element(By.TAG_NAME, "body").text
        file_list_count = len(driver.find_elements(By.CSS_SELECTOR, "#fileList li"))
        screenshot.parent.mkdir(parents=True, exist_ok=True)
        driver.save_screenshot(str(screenshot))
        geometry_probe_detail = ((smoke_js or {}).get("trajectorySummary", {}) or {}).get("geometryProbeDetail") or {}
        geometry_probe_compact = summarize_geometry_probe(geometry_probe_detail)

        payload = {
            "summary": {
                "url": url,
                "smoke_pass": bool(
                    ("Protein Motion Smoke" in bundle_status or "protein_atom_frames_smoke" in bundle_status)
                    and bool((smoke_js or {}).get("trajectorySummary", {}).get("proteinAtomSchemaReady"))
                    and "Protein Trajectory" in body_text
                    and file_list_count >= 1
                ),
                "bundle_status": bundle_status,
                "file_list_count": file_list_count,
                "body_includes_protein_atom_contract": "protein_atom_frames_contract_v1" in body_text,
                "body_includes_protein_trajectory": "Protein Trajectory" in body_text,
                "body_includes_smoke_target": "Protein Motion Smoke" in body_text,
                "geometry_probe_status_line": geometry_probe_compact.get("status_line", ""),
                "geometry_probe_state_cell_representation_present": bool(
                    geometry_probe_compact.get("state_cell_representation_present")
                ),
                "geometry_probe_renderable_count": int(geometry_probe_compact.get("renderable_count") or 0),
                "console_error_count": None,
                "screenshot_path": str(screenshot),
                "next_required_step": "If smoke_pass is true, the viewer Protein Motion Smoke preset is browser-loadable and protein_atom_frames schema is visible in the UI.",
            },
            "diagnostics": {
                "struct_info_excerpt": struct_info[:4000],
                "body_excerpt": body_text[:6000],
                "browser_runtime": smoke_js,
                "geometry_probe_compact": geometry_probe_compact,
            },
        }
        out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        if not payload["summary"]["smoke_pass"]:
            raise RuntimeError("Protein Motion Smoke browser smoke failed")
    except TimeoutException as error:
        raise RuntimeError(f"viewer smoke timeout: {error}") from error
    finally:
        if driver is not None:
            driver.quit()
        if server_proc is not None:
            try:
                os.killpg(os.getpgid(server_proc.pid), signal.SIGTERM)
            except ProcessLookupError:
                pass

    payload = json.loads(out_json.read_text(encoding="utf-8"))
    print(json.dumps(payload.get("summary", {}), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
