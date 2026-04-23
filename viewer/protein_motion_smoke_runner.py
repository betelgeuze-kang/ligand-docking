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


REPO_ROOT = Path("/home/betelgeuze/분자동역학")
OUT_DIR = REPO_ROOT / "runs" / "viewer_protein_atom_smoke"
OUT_JSON = OUT_DIR / "protein_motion_browser_smoke_current.json"
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

    state = WebDriverWait(driver, 30).until(_probe)
    deadline = time.time() + 30
    while time.time() < deadline:
        if state and state.get("status") in {"pass", "fail"}:
            return state
        time.sleep(0.25)
        state = driver.execute_script("return window.__viewerSmokeState || null;")
    return state or {"status": "timeout", "checks": {}, "message": "viewer smoke state did not settle"}


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    with local_http_server(REPO_ROOT) as port:
        url = (
            f"http://127.0.0.1:{port}/viewer/index.html"
            "?surface-label=protein_atom_frames_smoke&smoke=protein-motion"
        )
        options = FirefoxOptions()
        options.add_argument("-headless")
        service = FirefoxService(executable_path=str(GECKODRIVER))
        driver = webdriver.Firefox(service=service, options=options)
        try:
            driver.set_page_load_timeout(30)
            driver.get(url)
            smoke_state = wait_for_smoke_state(driver)
            smoke_badge = driver.find_element("id", "smokeStateBadge").text
            schema_cells = driver.execute_script(
                """
                const cells = Array.from(document.querySelectorAll('#structInfo .info-cell'));
                return cells.map((cell) => cell.textContent.trim()).filter(Boolean);
                """
            )
            protein_schema_cells = [cell for cell in schema_cells if "Protein Trajectory" in cell or "RMSF Schema" in cell]
            result = {
                "generated_at_local": time.strftime("%Y-%m-%dT%H:%M:%S"),
                "url": url,
                "smoke_badge": smoke_badge,
                "smoke_state": smoke_state,
                "protein_schema_cells": protein_schema_cells,
                "pass": smoke_state.get("status") == "pass",
            }
        finally:
            driver.quit()

    OUT_JSON.write_text(json.dumps(result, ensure_ascii=False, indent=2))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
