#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import socket
import subprocess
import threading
import time
from contextlib import contextmanager
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont


ROOT = Path(__file__).resolve().parents[2]
FIGURE_DIR = ROOT / "docs" / "figures"
WORK_DIR = ROOT / "tmp" / "render_inputs"

VIEWER_IMAGE = FIGURE_DIR / "webviewer_tcruzi_pde_actual_2026-05-15.png"
STRUCTURE_IMAGE = FIGURE_DIR / "tcruzi_pde_3v94_chainB_structure_actual_2026-05-15.png"
MANIFEST_JSON = FIGURE_DIR / "readme_molecular_figures_manifest_current.json"

SOURCE_PDB = ROOT / "data" / "public_structures" / "selected_allatom_native_v1" / "t_cruzi_pde_pdb_3V94.pdb"
OPENMM_CHAIN_PDB = ROOT / "runs" / "tcruzi_pde_strict_external_openmm" / "tcruzi_pde_3v94_chain_B.pdb"
OPENMM_CA_TRAJ_NPY = ROOT / "runs" / "tcruzi_pde_strict_external_openmm" / "tcruzi_pde_chain_B_openmm_ca_md.npy"
CA_TRAJ_PDB = WORK_DIR / "tcruzi_pde_chain_B_openmm_ca_md_multistate.pdb"
PYMOL_SCRIPT = WORK_DIR / "render_tcruzi_pde_readme_figures.pml"
DOMAIN_PANEL = WORK_DIR / "tcruzi_domain_panel_readme.png"
POCKET_PANEL = WORK_DIR / "tcruzi_pocket_panel_readme.png"
VIEWER_RAW_SCREENSHOT = WORK_DIR / "webviewer_tcruzi_pde_raw.png"

SURFACE_LABEL = "tcruzi_pde_allatom_review_packet"
VIEWER_PATH_QUERY = (
    f"/viewer/index.html?surface-label={SURFACE_LABEL}"
    "&rank=1&repr=cartoon&color=binding-focus&bg=%23ffffff"
    "&ao=analysis&pocket=true&fog=false"
)


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, format: str, *args: object) -> None:  # noqa: A003
        return


def repo_rel(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT))
    except ValueError:
        return str(path)


def ensure_inputs() -> None:
    missing = [path for path in (SOURCE_PDB, OPENMM_CHAIN_PDB, OPENMM_CA_TRAJ_NPY) if not path.exists()]
    if missing:
        raise FileNotFoundError("missing required figure input(s): " + ", ".join(map(str, missing)))


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


def build_viewer_url(port: int) -> str:
    return f"http://127.0.0.1:{port}{VIEWER_PATH_QUERY}"


def build_viewer_url_template() -> str:
    return f"http://127.0.0.1:<port>{VIEWER_PATH_QUERY}"


def extract_ca_records(pdb_path: Path) -> list[tuple[str, str, int, str]]:
    records: list[tuple[str, str, int, str]] = []
    for line in pdb_path.read_text(encoding="utf-8", errors="ignore").splitlines():
        if line.startswith("ATOM") and line[12:16].strip() == "CA":
            records.append(
                (
                    line[17:20].strip(),
                    line[21].strip() or "B",
                    int(line[22:26]),
                    line[26].strip() or "",
                )
            )
    return records


def write_ca_multistate_pdb(
    *,
    source_pdb: Path = OPENMM_CHAIN_PDB,
    trajectory_npy: Path = OPENMM_CA_TRAJ_NPY,
    out_pdb: Path = CA_TRAJ_PDB,
) -> dict[str, Any]:
    ca_records = extract_ca_records(source_pdb)
    frames = np.load(trajectory_npy)
    if frames.ndim != 3 or frames.shape[2] != 3:
        raise ValueError(f"expected CA trajectory shape [T, A, 3], got {frames.shape}")
    if frames.shape[1] != len(ca_records):
        raise ValueError(f"CA count mismatch: trajectory={frames.shape[1]} pdb={len(ca_records)}")

    out_pdb.parent.mkdir(parents=True, exist_ok=True)
    with out_pdb.open("w", encoding="utf-8") as fh:
        fh.write("REMARK CA trajectory derived from tcruzi_pde_chain_B_openmm_ca_md.npy\n")
        for model_index, frame in enumerate(frames, start=1):
            fh.write(f"MODEL {model_index:8d}\n")
            for atom_index, ((resn, chain, resi, icode), xyz) in enumerate(zip(ca_records, frame), start=1):
                x, y, z = map(float, xyz)
                fh.write(
                    f"ATOM  {atom_index:5d}  CA  {resn:>3s} {chain:1s}{resi:4d}{icode:1s}"
                    f"   {x:8.3f}{y:8.3f}{z:8.3f}  1.00 30.00           C\n"
                )
            fh.write("ENDMDL\n")
        fh.write("END\n")

    return {
        "out_pdb": repo_rel(out_pdb),
        "frame_count": int(frames.shape[0]),
        "ca_count": int(frames.shape[1]),
    }


def build_pymol_script() -> str:
    return f"""
load {repo_rel(SOURCE_PDB)}, full
load {repo_rel(CA_TRAJ_PDB)}, ca_motion
remove solvent
create protB, full and chain B and polymer.protein
create ligB, full and chain B and resn WYQ
create metalB, full and chain B and (resn ZN or resn MG)
create pocketB, protB within 5.0 of ligB
hide everything
set retain_order, 1
set orthoscopic, on
set bg_rgb, [1.0, 0.985, 0.955]
set ray_opaque_background, on
set antialias, 2
set ray_shadows, on
set ambient, 0.45
set direct, 0.70
set specular, 0.12
set shininess, 18
set reflect, 0.035
set depth_cue, 0
set ray_trace_mode, 1
set ray_trace_color, 0x2a3a40
set ray_trace_gain, 0.035
set cartoon_fancy_helices, on
set cartoon_smooth_loops, on
set cartoon_highlight_color, grey82
set cartoon_sampling, 16
show cartoon, protB
color 0x8fb7ff, protB
color 0xffc85a, pocketB
set cartoon_transparency, 0.02, protB
set cartoon_transparency, 0.0, pocketB
show surface, pocketB
set surface_color, 0x5fc4bc, pocketB
set transparency, 0.72, pocketB
show sticks, ligB
set stick_radius, 0.18, ligB
util.cbag ligB
show spheres, metalB
set sphere_scale, 0.36, metalB
color 0x7f6ae6, resn ZN
color 0x46c2ff, resn MG
show sticks, pocketB and sidechain and not elem H
set stick_radius, 0.085, pocketB
set stick_transparency, 0.42, pocketB
color 0xf2a23a, pocketB and elem C
color 0xe8463a, pocketB and elem O
color 0x3478f6, pocketB and elem N
show ribbon, ca_motion
set all_states, on
set ribbon_width, 3.1
set ribbon_transparency, 0.58, ca_motion
color 0xf49a2f, ca_motion
orient protB
rotate y, 22
rotate x, -9
zoom protB, 8
png {repo_rel(DOMAIN_PANEL)}, width=1280, height=960, dpi=240, ray=1

hide everything
show cartoon, protB
color 0xd8e6ff, protB
set cartoon_transparency, 0.12, protB
show surface, pocketB
set surface_color, 0x5fc4bc, pocketB
set transparency, 0.50, pocketB
show sticks, pocketB and sidechain and not elem H
set stick_radius, 0.105, pocketB
set stick_transparency, 0.24, pocketB
color 0xf2a23a, pocketB and elem C
color 0xe8463a, pocketB and elem O
color 0x3478f6, pocketB and elem N
show sticks, ligB
set stick_radius, 0.23, ligB
util.cbag ligB
show spheres, metalB
set sphere_scale, 0.46, metalB
color 0x7f6ae6, resn ZN
color 0x46c2ff, resn MG
orient ligB
zoom ligB or metalB or pocketB, 8.4
rotate y, 12
rotate x, -5
png {repo_rel(POCKET_PANEL)}, width=1280, height=960, dpi=240, ray=1
quit
""".strip() + "\n"


def run_pymol(pymol_bin: str) -> None:
    PYMOL_SCRIPT.parent.mkdir(parents=True, exist_ok=True)
    PYMOL_SCRIPT.write_text(build_pymol_script(), encoding="utf-8")
    subprocess.run([pymol_bin, "-cq", str(PYMOL_SCRIPT)], cwd=ROOT, check=True)


def font(name: str, size: int) -> ImageFont.FreeTypeFont:
    path = f"/usr/share/fonts/truetype/dejavu/{name}.ttf"
    return ImageFont.truetype(path, size)


def draw_structure_figure() -> None:
    domain = Image.open(DOMAIN_PANEL).convert("RGB")
    pocket = Image.open(POCKET_PANEL).convert("RGB")
    width, height = 1672, 941
    image = Image.new("RGB", (width, height), (255, 251, 244))
    draw = ImageDraw.Draw(image)
    bold = font("DejaVuSans-Bold", 34)
    head = font("DejaVuSans-Bold", 22)
    body = font("DejaVuSans", 17)
    small = font("DejaVuSans", 14)
    ink = (20, 47, 56)
    muted = (93, 111, 115)
    teal = (23, 126, 137)
    amber = (154, 90, 22)
    line = (215, 201, 181)

    draw.text((48, 36), "T. cruzi PDE Structural Evidence", font=bold, fill=ink)
    draw.text(
        (48, 80),
        "Actual PDB 3V94 chain B + OpenMM CA trajectory trace; inhibitor WYQ16 and catalytic metals preserved.",
        font=body,
        fill=muted,
    )

    panel_y = 118
    panel_h = 720
    gap = 28
    left_w = 790
    right_w = width - 96 - left_w - gap
    left_box = (48, panel_y, 48 + left_w, panel_y + panel_h)
    right_box = (48 + left_w + gap, panel_y, width - 48, panel_y + panel_h)
    for box in (left_box, right_box):
        shadow = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        shadow_draw = ImageDraw.Draw(shadow)
        shadow_draw.rounded_rectangle(
            (box[0] + 5, box[1] + 8, box[2] + 5, box[3] + 8),
            radius=26,
            fill=(40, 28, 14, 42),
        )
        image.paste(shadow.convert("RGB"), (0, 0), shadow)
        draw.rounded_rectangle(box, radius=26, fill=(255, 253, 248), outline=line, width=2)

    for panel, box, box_w in ((domain, left_box, left_w), (pocket, right_box, right_w)):
        panel = panel.copy()
        panel.thumbnail((box_w - 56, panel_h - 120), Image.Resampling.LANCZOS)
        x = box[0] + (box_w - panel.width) // 2
        y = box[1] + 84 + (panel_h - 120 - panel.height) // 2
        image.paste(panel, (x, y))

    labels = [
        ("A", "Full catalytic domain", "blue cartoon; amber CA motion trace", left_box, teal),
        ("B", "Active-site pocket", "WYQ16 ligand, Zn/Mg ions, translucent pocket surface", right_box, amber),
    ]
    for label, title, subtitle, box, color in labels:
        x, y, _, _ = box
        draw.rounded_rectangle((x + 24, y + 22, x + 64, y + 62), radius=12, fill=color)
        draw.text((x + 37, y + 29), label, font=head, fill=(255, 253, 248), anchor="la")
        draw.text((x + 78, y + 22), title, font=head, fill=ink)
        draw.text((x + 78, y + 50), subtitle, font=body, fill=muted)

    footer_y = 858
    items = [
        ((143, 183, 255), "protein cartoon"),
        ((95, 196, 188), "pocket surface"),
        ((80, 238, 82), "WYQ16 ligand"),
        ((244, 154, 47), "OpenMM CA trace"),
        ((127, 106, 230), "Zn"),
        ((70, 194, 255), "Mg"),
    ]
    x = 52
    for color, label in items:
        draw.rounded_rectangle((x, footer_y + 5, x + 18, footer_y + 23), radius=5, fill=color)
        draw.text((x + 28, footer_y + 3), label, font=small, fill=muted)
        x += draw.textbbox((0, 0), label, font=small)[2] + 68

    draw.text(
        (52, 902),
        "Source: data/public_structures/.../t_cruzi_pde_pdb_3V94.pdb; runs/tcruzi_pde_strict_external_openmm/*",
        font=small,
        fill=(120, 120, 112),
    )
    STRUCTURE_IMAGE.parent.mkdir(parents=True, exist_ok=True)
    image.save(STRUCTURE_IMAGE, optimize=True)


def capture_viewer_screenshot(geckodriver: str) -> str:
    from selenium import webdriver
    from selenium.webdriver.firefox.options import Options as FirefoxOptions
    from selenium.webdriver.firefox.service import Service as FirefoxService

    with local_http_server(ROOT) as port:
        url = build_viewer_url(port)
        options = FirefoxOptions()
        options.add_argument("-headless")
        options.set_preference("webgl.force-enabled", True)
        options.set_preference("webgl.disabled", False)
        driver = webdriver.Firefox(service=FirefoxService(executable_path=geckodriver), options=options)
        try:
            driver.set_window_size(1672, 941)
            driver.set_page_load_timeout(60)
            driver.get(url)
            deadline = time.time() + 75
            while time.time() < deadline:
                state = driver.execute_script("return window.__viewerDebugState || null;")
                if state and state.get("bundleLoaded") and state.get("candidateCount", 0) >= 1:
                    break
                time.sleep(0.25)
            time.sleep(8.0)
            VIEWER_RAW_SCREENSHOT.parent.mkdir(parents=True, exist_ok=True)
            driver.save_screenshot(str(VIEWER_RAW_SCREENSHOT))
        finally:
            driver.quit()
    return url


def frame_viewer_screenshot() -> None:
    shot = Image.open(VIEWER_RAW_SCREENSHOT).convert("RGB")
    width, height = 1672, 941
    canvas = Image.new("RGB", (width, height), (16, 37, 44))
    draw = ImageDraw.Draw(canvas)
    for y in range(height):
        r = int(16 + y / height * 8)
        g = int(37 + y / height * 10)
        b = int(44 + y / height * 8)
        draw.line((0, y, width, y), fill=(r, g, b))

    title = font("DejaVuSans-Bold", 32)
    body = font("DejaVuSans", 17)
    small = font("DejaVuSans", 14)
    draw.text((58, 34), "Actual MD Dynamics Viewer", font=title, fill=(255, 247, 234))
    draw.text(
        (58, 76),
        "Loaded surface bundle: tcruzi_pde_allatom_review_packet · selected candidate #1 · real Mol* viewport capture",
        font=body,
        fill=(215, 201, 181),
    )

    card = (54, 120, width - 54, height - 54)
    shadow = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    shadow_draw = ImageDraw.Draw(shadow)
    shadow_draw.rounded_rectangle((card[0] + 7, card[1] + 10, card[2] + 7, card[3] + 10), radius=28, fill=(0, 0, 0, 95))
    shadow = shadow.filter(ImageFilter.GaussianBlur(7))
    canvas.paste(shadow.convert("RGB"), (0, 0), shadow)
    draw.rounded_rectangle(card, radius=28, fill=(255, 252, 245), outline=(215, 201, 181), width=2)

    bar_h = 44
    draw.rounded_rectangle((card[0], card[1], card[2], card[1] + bar_h), radius=28, fill=(255, 247, 234), outline=(215, 201, 181), width=1)
    draw.rectangle((card[0], card[1] + 24, card[2], card[1] + bar_h), fill=(255, 247, 234))
    for index, color in enumerate(((166, 66, 58), (166, 101, 18), (47, 125, 89))):
        draw.ellipse((card[0] + 24 + index * 22, card[1] + 16, card[0] + 36 + index * 22, card[1] + 28), fill=color)
    draw.rounded_rectangle((card[0] + 112, card[1] + 12, card[2] - 24, card[1] + 32), radius=9, fill=(243, 235, 221), outline=(215, 201, 181))
    draw.text((card[0] + 128, card[1] + 13), "viewer/index.html?surface-label=tcruzi_pde_allatom_review_packet", font=small, fill=(93, 111, 115))

    max_w = card[2] - card[0] - 32
    max_h = card[3] - card[1] - bar_h - 24
    shot.thumbnail((max_w, max_h), Image.Resampling.LANCZOS)
    x = card[0] + (card[2] - card[0] - shot.width) // 2
    y = card[1] + bar_h + 12
    canvas.paste(shot, (x, y))
    draw.text((58, height - 34), "Actual browser screenshot; outer frame only added for README presentation.", font=small, fill=(184, 176, 162))
    VIEWER_IMAGE.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(VIEWER_IMAGE, optimize=True)


def verify_png(path: Path) -> dict[str, Any]:
    with Image.open(path) as image:
        size = image.size
        mode = image.mode
        image.verify()
    return {"path": repo_rel(path), "size": list(size), "mode": mode, "bytes": path.stat().st_size}


def write_manifest(*, viewer_url: str, ca_info: dict[str, Any], skipped: list[str]) -> dict[str, Any]:
    manifest = {
        "status": "readme_molecular_figures_ready",
        "generated_at_local": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "generator": {
            "script": repo_rel(Path(__file__)),
            "command": "python3 tools/render_readme_molecular_figures.py",
        },
        "target_id": "T. cruzi PDE",
        "surface_label": SURFACE_LABEL,
        "reproducibility_scope": {
            "committed_outputs": [
                repo_rel(VIEWER_IMAGE),
                repo_rel(STRUCTURE_IMAGE),
                repo_rel(MANIFEST_JSON),
            ],
            "requires_local_runtime_artifacts": [
                repo_rel(OPENMM_CHAIN_PDB),
                repo_rel(OPENMM_CA_TRAJ_NPY),
            ],
            "committed_public_structure_input": repo_rel(SOURCE_PDB),
        },
        "source_inputs": {
            "source_pdb": repo_rel(SOURCE_PDB),
            "openmm_chain_pdb": repo_rel(OPENMM_CHAIN_PDB),
            "openmm_ca_trajectory_npy": repo_rel(OPENMM_CA_TRAJ_NPY),
            "ca_multistate_pdb": ca_info,
        },
        "viewer": {
            "url_path_query": VIEWER_PATH_QUERY,
            "captured_url": build_viewer_url_template() if viewer_url else "",
            "output_png": verify_png(VIEWER_IMAGE) if VIEWER_IMAGE.exists() else {},
        },
        "structure_render": {
            "style": "alphafold_style_pymol_two_panel",
            "pymol_script": repo_rel(PYMOL_SCRIPT),
            "domain_panel": repo_rel(DOMAIN_PANEL),
            "pocket_panel": repo_rel(POCKET_PANEL),
            "output_png": verify_png(STRUCTURE_IMAGE) if STRUCTURE_IMAGE.exists() else {},
        },
        "skipped_steps": skipped,
    }
    MANIFEST_JSON.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return manifest


def render_figures(*, skip_browser: bool, skip_pymol: bool, geckodriver: str, pymol_bin: str) -> dict[str, Any]:
    ensure_inputs()
    FIGURE_DIR.mkdir(parents=True, exist_ok=True)
    WORK_DIR.mkdir(parents=True, exist_ok=True)
    skipped: list[str] = []
    ca_info = write_ca_multistate_pdb()

    if skip_pymol:
        skipped.append("pymol")
    else:
        run_pymol(pymol_bin)
        draw_structure_figure()

    viewer_url = ""
    if skip_browser:
        skipped.append("browser")
    else:
        viewer_url = capture_viewer_screenshot(geckodriver)
        frame_viewer_screenshot()

    return write_manifest(viewer_url=viewer_url, ca_info=ca_info, skipped=skipped)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Regenerate README molecular figures from actual viewer and structure data.")
    parser.add_argument("--skip-browser", action="store_true", help="Do not recapture the Selenium/Firefox viewer screenshot.")
    parser.add_argument("--skip-pymol", action="store_true", help="Do not rerun PyMOL; only refresh available outputs/manifest.")
    parser.add_argument("--geckodriver", default="/snap/bin/geckodriver")
    parser.add_argument("--pymol-bin", default="pymol")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    manifest = render_figures(
        skip_browser=bool(args.skip_browser),
        skip_pymol=bool(args.skip_pymol),
        geckodriver=str(args.geckodriver),
        pymol_bin=str(args.pymol_bin),
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
