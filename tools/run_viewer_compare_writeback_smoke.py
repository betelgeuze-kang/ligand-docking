#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import socket
import threading
import time
from contextlib import contextmanager
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from selenium.webdriver.firefox.service import Service as FirefoxService
from selenium.webdriver.support.ui import WebDriverWait

from viewer_smoke_geometry_probe import summarize_geometry_probe_slots


REPO_ROOT = Path("/home/betelgeuze/분자동역학")
OUT_DIR = REPO_ROOT / "runs" / "viewer_compare_writeback_smoke"
FIXTURE_JSON = OUT_DIR / "writeback_before_smoke_current.json"
CURRENT_BUNDLE_JSON = REPO_ROOT / "runs" / "selected_allatom_visual_bundle_current.json"
OUT_JSON = OUT_DIR / "compare_writeback_browser_smoke_current.json"
OUT_PNG = OUT_DIR / "compare_writeback_browser_smoke_current.png"
GECKODRIVER = Path("/snap/bin/geckodriver")


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, format: str, *args) -> None:  # noqa: A003
        return


def find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


@contextmanager
def local_http_server(root: Path):
    port = find_free_port()
    previous_cwd = Path.cwd()
    os.chdir(root)
    server = ThreadingHTTPServer(("127.0.0.1", port), QuietHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield port
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2.0)
        os.chdir(previous_cwd)


def wait_for_smoke_state(driver: webdriver.Firefox) -> dict:
    def _probe(_driver):
        return _driver.execute_script("return window.__viewerSmokeState || null;")

    state = WebDriverWait(driver, 60).until(_probe)
    deadline = time.time() + 60
    while time.time() < deadline:
        if state and state.get("status") in {"pass", "fail"}:
            return state
        time.sleep(0.25)
        state = driver.execute_script("return window.__viewerSmokeState || null;")
    return state or {"status": "timeout", "checks": {}, "message": "compare writeback smoke state did not settle"}


def read_smoke_state(driver: webdriver.Firefox) -> dict:
    return driver.execute_script("return window.__viewerSmokeState || null;") or {}


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    if not FIXTURE_JSON.exists():
        raise FileNotFoundError(f"missing fixture json: {FIXTURE_JSON}")

    with local_http_server(REPO_ROOT) as port:
        url = f"http://127.0.0.1:{port}/viewer/index.html?smoke=compare-writeback"
        options = FirefoxOptions()
        options.add_argument("-headless")
        service = FirefoxService(executable_path=str(GECKODRIVER))
        driver = webdriver.Firefox(service=service, options=options)
        try:
            driver.set_window_size(1800, 1400)
            driver.set_page_load_timeout(60)
            driver.get(url)
            wait = WebDriverWait(driver, 90)
            wait.until(lambda d: d.find_element("id", "bundleInput"))
            try:
                WebDriverWait(driver, 12).until(
                    lambda d: d.execute_script(
                        "return Array.isArray(window.state?.candidates) && window.state.candidates.length >= 1;"
                    )
                )
            except Exception:
                bundle_ingest = driver.execute_async_script(
                    """
                    const done = arguments[arguments.length - 1];
                    (async () => {
                      try {
                        const res = await fetch('/runs/selected_allatom_visual_bundle_current.json', { cache: 'no-store' });
                        if (!res.ok) throw new Error(`bundle fetch failed: ${res.status}`);
                        const payload = await res.json();
                        if (typeof ingestBundle !== 'function') throw new Error('ingestBundle unavailable');
                        ingestBundle(payload, 'compare writeback current bundle');
                        done({ ok: true, rows: Array.isArray(payload?.rows) ? payload.rows.length : 0 });
                      } catch (error) {
                        done({ ok: false, error: String(error && error.message ? error.message : error) });
                      }
                    })();
                    """
                )
                if not bundle_ingest or not bundle_ingest.get("ok"):
                    raise RuntimeError(f"compare writeback bundle ingest failed: {bundle_ingest}")
                debug_state = driver.execute_script("return window.__viewerDebugApi?.getState?.() || window.__viewerDebugState || null;")
                candidate_count = (debug_state or {}).get("candidateCount", -1)
                if not isinstance(candidate_count, int) or candidate_count < 1:
                    bundle_status = driver.find_element("id", "bundleStatus").text
                    raise RuntimeError(
                        f"compare writeback current bundle ingest produced no candidates: count={candidate_count} status={bundle_status} debug={debug_state}"
                    )
            wait.until(lambda d: d.find_elements("css selector", "#fileList li.file-item-card"))
            driver.find_element("id", "writebackBeforeInput").send_keys(str(FIXTURE_JSON))
            smoke_state = wait_for_smoke_state(driver)
            wait.until(lambda d: "Diff Row Matrix" in d.find_element("id", "compareDiffMatrix").text)
            side_button = driver.find_elements("css selector", "#compareDecisionBoard [data-action='writeback-side']")[0]
            driver.execute_script("arguments[0].click();", side_button)
            wait.until(lambda d: d.execute_script("return window.getComputedStyle(document.getElementById('compareSplitLayout')).display;") != "none")
            time.sleep(0.5)
            smoke_state = driver.execute_script(
                """
                if (typeof updateCompareWritebackSmokeState === 'function') {
                  updateCompareWritebackSmokeState();
                }
                return window.__viewerSmokeState || null;
                """
            ) or read_smoke_state(driver)
            viewer_debug_state = driver.execute_script("return window.__viewerDebugState || null;")
            geometry_probe_detail = driver.execute_script(
                """
                const getCandidateForSlot = (slot) => {
                  return window.__viewerDebugApi?.getCompareCandidate?.(slot) || null;
                };
                const selectedCandidate = window.__viewerDebugApi?.getSelectedCandidate?.() || null;
                return {
                  single: {
                    canvas3d: (typeof collectCanvas3dGeometryProbe === 'function') ? collectCanvas3dGeometryProbe() : null,
                    stateCells: (typeof collectViewerStateRepresentationProbe === 'function') ? collectViewerStateRepresentationProbe() : null,
                    pocket: (typeof collectPocketGeometryProbe === 'function' && selectedCandidate) ? collectPocketGeometryProbe(selectedCandidate) : null,
                  },
                  compareA: {
                    canvas3d: (typeof collectCompareCanvas3dGeometryProbe === 'function') ? collectCompareCanvas3dGeometryProbe('A') : null,
                    stateCells: (typeof collectCompareViewerStateRepresentationProbe === 'function') ? collectCompareViewerStateRepresentationProbe('A') : null,
                    candidateIndex: getCandidateForSlot('A')?.index ?? null,
                    candidateLabel: getCandidateForSlot('A')?.ligandId || '',
                  },
                  compareB: {
                    canvas3d: (typeof collectCompareCanvas3dGeometryProbe === 'function') ? collectCompareCanvas3dGeometryProbe('B') : null,
                    stateCells: (typeof collectCompareViewerStateRepresentationProbe === 'function') ? collectCompareViewerStateRepresentationProbe('B') : null,
                    candidateIndex: getCandidateForSlot('B')?.index ?? null,
                    candidateLabel: getCandidateForSlot('B')?.ligandId || '',
                  },
                };
                """
            )
            geometry_probe = {
                slot: (detail.get("canvas3d") if isinstance(detail, dict) else None)
                for slot, detail in geometry_probe_detail.items()
            }
            geometry_probe_compact = summarize_geometry_probe_slots(geometry_probe_detail)
            geometry_access = {
                "single_viewer_ready": bool((viewer_debug_state or {}).get("singleViewerReady")),
                "compareA_viewer_ready": bool((viewer_debug_state or {}).get("compareViewerAReady")),
                "compareB_viewer_ready": bool((viewer_debug_state or {}).get("compareViewerBReady")),
                "single_canvas_probe_ready": bool((geometry_probe.get("single") or {}).get("canvasReady")),
                "compareA_canvas_probe_ready": bool((geometry_probe.get("compareA") or {}).get("canvasReady")),
                "compareB_canvas_probe_ready": bool((geometry_probe.get("compareB") or {}).get("canvasReady")),
            }
            geometry_access["single_wrapper_gap"] = (
                geometry_access["single_viewer_ready"] and not geometry_access["single_canvas_probe_ready"]
            )
            geometry_access["compareA_wrapper_gap"] = (
                geometry_access["compareA_viewer_ready"] and not geometry_access["compareA_canvas_probe_ready"]
            )
            geometry_access["compareB_wrapper_gap"] = (
                geometry_access["compareB_viewer_ready"] and not geometry_access["compareB_canvas_probe_ready"]
            )
            compare_viewer_a_title = driver.find_element("id", "compareViewerATitle").text
            compare_viewer_b_title = driver.find_element("id", "compareViewerBTitle").text
            compare_debug_readiness = {
                "single": {
                    "viewer_present": bool((viewer_debug_state or {}).get("singleViewerReady")),
                    "ready": bool((viewer_debug_state or {}).get("singleViewerReady")),
                },
                "compareA": {
                    "viewer_present": bool((viewer_debug_state or {}).get("compareViewerAReady")),
                    "title": compare_viewer_a_title,
                    "ready": bool((viewer_debug_state or {}).get("compareViewerAReady")) and bool(compare_viewer_a_title.strip()),
                },
                "compareB": {
                    "viewer_present": bool((viewer_debug_state or {}).get("compareViewerBReady")),
                    "title": compare_viewer_b_title,
                    "ready": bool((viewer_debug_state or {}).get("compareViewerBReady")) and bool(compare_viewer_b_title.strip()),
                },
            }
            driver.save_screenshot(str(OUT_PNG))
            result = {
                "generated_at_local": time.strftime("%Y-%m-%dT%H:%M:%S"),
                "url": url,
                "fixture_json": str(FIXTURE_JSON),
                "smoke_state": smoke_state,
                "viewer_debug_state": viewer_debug_state,
                "smoke_badge": driver.find_element("id", "smokeStateBadge").text,
                "compare_console_status": driver.find_element("id", "compareConsoleStatus").text,
                "writeback_source": driver.find_element("id", "compareWritebackSource").text,
                "diff_matrix_excerpt": driver.find_element("id", "compareDiffMatrix").text[:1200],
                "decision_board_excerpt": driver.find_element("id", "compareDecisionBoard").text[:1200],
                "compare_split_visible": driver.execute_script(
                    "return window.getComputedStyle(document.getElementById('compareSplitLayout')).display !== 'none';"
                ),
                "compare_viewer_a_title": compare_viewer_a_title,
                "compare_viewer_b_title": compare_viewer_b_title,
                "compare_debug_readiness": compare_debug_readiness,
                "compare_debug_readiness_line": " | ".join(
                    [
                        f"single={'ready' if compare_debug_readiness.get('single', {}).get('ready') else 'pending'}",
                        f"A={'ready' if compare_debug_readiness.get('compareA', {}).get('ready') else 'pending'}",
                        f"B={'ready' if compare_debug_readiness.get('compareB', {}).get('ready') else 'pending'}",
                    ]
                ),
                "geometry_probe": geometry_probe,
                "geometry_probe_detail": geometry_probe_detail,
                "geometry_probe_compact": geometry_probe_compact,
                "geometry_access": geometry_access,
                "geometry_probe_compact_summary": {
                    slot: compact.get("status_line", "")
                    for slot, compact in geometry_probe_compact.items()
                },
                "screenshot_png": str(OUT_PNG),
                "pass": smoke_state.get("status") == "pass",
            }
        finally:
            driver.quit()

    OUT_JSON.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
