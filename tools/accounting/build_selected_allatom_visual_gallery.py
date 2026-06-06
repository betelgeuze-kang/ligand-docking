#!/usr/bin/env python3
from __future__ import annotations

import html
import json
import os
from dataclasses import dataclass
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
RUNS_DIR = REPO_ROOT / "runs"
DEFAULT_BUNDLE_FILES = [
    RUNS_DIR / "selected_allatom_visual_bundle_tcruzi_pde_current.json",
    RUNS_DIR / "selected_allatom_visual_bundle_cathepsin_k_current.json",
    RUNS_DIR / "selected_allatom_visual_bundle_sarscov2_mpro_current.json",
]
DEFAULT_OUTPUT = RUNS_DIR / "selected_allatom_visual_gallery_current.html"


@dataclass
class GalleryCard:
    target_id: str
    surface_label: str
    topk_count: int
    figure_url: str
    scatter_url: str
    dashboard_url: str
    bundle_url: str
    viewer_url: str
    render_structure_kind: str
    viewer_mode: str
    alignment_mode: str
    turntable_status: str
    turntable_recommendation: str


def _relative_url(path_like: str | Path | None, base_dir: Path) -> str:
    raw_text = str(path_like or "").strip()
    if not raw_text:
        return ""
    raw = Path(raw_text).expanduser()
    try:
        resolved = raw.resolve()
    except FileNotFoundError:
        resolved = raw
    try:
        return Path(os.path.relpath(resolved, start=base_dir)).as_posix()
    except ValueError:
        return raw_text


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text())


def _build_card(bundle_path: Path, output_path: Path) -> GalleryCard:
    payload = _read_json(bundle_path)
    summary = payload.get("summary", {})
    target_id = str(summary.get("target_id") or bundle_path.stem)
    return GalleryCard(
        target_id=target_id,
        surface_label=str(summary.get("selected_surface_label") or "-"),
        topk_count=int(summary.get("topk_count") or 0),
        figure_url=_relative_url(summary.get("metric_panel_png") or summary.get("primary_figure_path"), output_path.parent),
        scatter_url=_relative_url(summary.get("scatter_png"), output_path.parent),
        dashboard_url=_relative_url(summary.get("dashboard_html"), output_path.parent),
        bundle_url=_relative_url(bundle_path, output_path.parent),
        viewer_url="../viewer/index.html",
        render_structure_kind=str(summary.get("primary_render_structure_kind") or "-"),
        viewer_mode=str(summary.get("primary_protein_reference_viewer_mode") or "-"),
        alignment_mode=str(summary.get("primary_protein_reference_alignment_mode") or "-"),
        turntable_status=str(summary.get("primary_turntable_asset_status") or "-"),
        turntable_recommendation=str(summary.get("primary_turntable_asset_recommendation") or "-"),
    )


def build_gallery_html(cards: list[GalleryCard]) -> str:
    card_html = []
    for card in cards:
        card_html.append(
            f"""
            <article class="card">
              <div class="card-head">
                <div>
                  <p class="eyebrow">{html.escape(card.surface_label)}</p>
                  <h2>{html.escape(card.target_id)}</h2>
                </div>
                <div class="badge">top-k {card.topk_count}</div>
              </div>
              <div class="hero">
                <img class="zoomable" src="{html.escape(card.figure_url)}" alt="{html.escape(card.target_id)} metric panel" data-full-src="{html.escape(card.figure_url)}" data-caption="{html.escape(card.target_id)} metric panel"/>
              </div>
              <div class="secondary">
                <img class="zoomable" src="{html.escape(card.scatter_url)}" alt="{html.escape(card.target_id)} distance energy plot" data-full-src="{html.escape(card.scatter_url)}" data-caption="{html.escape(card.target_id)} distance vs energy"/>
              </div>
              <dl class="meta">
                <div><dt>Render</dt><dd>{html.escape(card.render_structure_kind)}</dd></div>
                <div><dt>Viewer</dt><dd>{html.escape(card.viewer_mode)}</dd></div>
                <div><dt>Align</dt><dd>{html.escape(card.alignment_mode)}</dd></div>
                <div><dt>Turntable</dt><dd>{html.escape(card.turntable_status)}</dd></div>
              </dl>
              <p class="note">Turntable recommendation: {html.escape(card.turntable_recommendation)}</p>
              <div class="actions">
                <a href="{html.escape(card.viewer_url)}">Viewer</a>
                <a href="{html.escape(card.dashboard_url)}">Dashboard</a>
                <a href="{html.escape(card.bundle_url)}">Bundle JSON</a>
                <a href="{html.escape(card.figure_url)}">PNG 원본</a>
              </div>
            </article>
            """.strip()
        )

    return f"""<!DOCTYPE html>
<html lang="ko">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>Selected All-Atom Visual Gallery</title>
  <style>
    :root {{
      color-scheme: dark;
      --bg: #0b1120;
      --panel: #111827;
      --panel-2: #1f2937;
      --text: #e5e7eb;
      --muted: #9ca3af;
      --accent: #60a5fa;
      --border: rgba(148,163,184,0.2);
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: Inter, system-ui, sans-serif;
      background:
        radial-gradient(circle at top right, rgba(37,99,235,0.18), transparent 28%),
        linear-gradient(180deg, #0b1120, #111827 55%, #0f172a);
      color: var(--text);
    }}
    header {{
      padding: 2rem 2rem 1rem;
    }}
    h1 {{
      margin: 0;
      font-size: clamp(1.8rem, 3vw, 2.6rem);
    }}
    .sub {{
      margin: 0.65rem 0 0;
      color: var(--muted);
      max-width: 70rem;
      line-height: 1.6;
    }}
    .top-actions {{
      margin-top: 1rem;
      display: flex;
      flex-wrap: wrap;
      gap: 0.75rem;
    }}
    .top-actions a, .actions a {{
      text-decoration: none;
      color: white;
      background: rgba(96,165,250,0.18);
      border: 1px solid rgba(96,165,250,0.28);
      padding: 0.65rem 0.95rem;
      border-radius: 999px;
      font-size: 0.88rem;
    }}
    main {{
      padding: 0 2rem 2rem;
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(360px, 1fr));
      gap: 1.25rem;
    }}
    .card {{
      background: rgba(17,24,39,0.82);
      border: 1px solid var(--border);
      border-radius: 1.25rem;
      padding: 1rem;
      box-shadow: 0 20px 40px rgba(2,6,23,0.28);
      backdrop-filter: blur(16px);
    }}
    .card-head {{
      display: flex;
      align-items: flex-start;
      justify-content: space-between;
      gap: 1rem;
      margin-bottom: 1rem;
    }}
    .eyebrow {{
      margin: 0 0 0.35rem;
      color: var(--accent);
      font-size: 0.78rem;
      text-transform: uppercase;
      letter-spacing: 0.08em;
    }}
    h2 {{
      margin: 0;
      font-size: 1.2rem;
    }}
    .badge {{
      white-space: nowrap;
      background: rgba(96,165,250,0.12);
      border: 1px solid rgba(96,165,250,0.22);
      color: #bfdbfe;
      padding: 0.4rem 0.7rem;
      border-radius: 999px;
      font-size: 0.82rem;
    }}
    .hero img, .secondary img {{
      width: 100%;
      display: block;
      border-radius: 0.9rem;
      border: 1px solid var(--border);
      background: #020617;
      cursor: zoom-in;
    }}
    .secondary {{
      margin-top: 0.85rem;
    }}
    .meta {{
      margin: 0.95rem 0 0;
      display: grid;
      grid-template-columns: repeat(2, minmax(0,1fr));
      gap: 0.7rem;
    }}
    .meta div {{
      padding: 0.75rem 0.8rem;
      border-radius: 0.85rem;
      background: rgba(31,41,55,0.78);
      border: 1px solid var(--border);
    }}
    dt {{
      font-size: 0.72rem;
      color: var(--muted);
      margin-bottom: 0.22rem;
      text-transform: uppercase;
      letter-spacing: 0.08em;
    }}
    dd {{
      margin: 0;
      font-size: 0.92rem;
      word-break: break-word;
    }}
    .note {{
      color: var(--muted);
      line-height: 1.6;
      font-size: 0.84rem;
      margin: 0.95rem 0 0;
    }}
    .actions {{
      margin-top: 0.95rem;
      display: flex;
      flex-wrap: wrap;
      gap: 0.65rem;
    }}
    .modal {{
      display: none;
      position: fixed;
      inset: 0;
      background: rgba(2, 6, 23, 0.82);
      z-index: 40;
      align-items: center;
      justify-content: center;
      padding: 1.25rem;
    }}
    .modal.active {{
      display: flex;
    }}
    .modal-content {{
      width: min(1400px, 96vw);
      max-height: 92vh;
      background: rgba(17,24,39,0.96);
      border: 1px solid var(--border);
      border-radius: 1rem;
      overflow: hidden;
      box-shadow: 0 30px 60px rgba(2,6,23,0.4);
    }}
    .modal-header {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 1rem;
      padding: 1rem 1.25rem;
      border-bottom: 1px solid var(--border);
    }}
    .modal-header h3 {{
      margin: 0;
      font-size: 1rem;
    }}
    .modal-close {{
      border: 0;
      background: transparent;
      color: var(--text);
      font-size: 1.25rem;
      cursor: pointer;
    }}
    .modal-body {{
      padding: 1rem;
      text-align: center;
    }}
    .modal-body img {{
      max-width: 100%;
      max-height: 78vh;
      border-radius: 0.75rem;
      border: 1px solid var(--border);
      background: #020617;
    }}
    .modal-caption {{
      margin-top: 0.75rem;
      color: var(--muted);
      font-size: 0.84rem;
    }}
    @media (max-width: 700px) {{
      header, main {{ padding-left: 1rem; padding-right: 1rem; }}
      .meta {{ grid-template-columns: 1fr; }}
    }}
  </style>
</head>
<body>
  <header>
    <h1>Selected All-Atom Visual Gallery</h1>
    <p class="sub">현재 selected-allatom 3타깃의 대표 PNG와 보조 distance-energy figure를 한 화면에 모아둔 gallery입니다. 각 카드에서 interactive viewer, per-target dashboard, bundle JSON, 원본 PNG로 바로 이동할 수 있습니다.</p>
    <div class="top-actions">
      <a href="../viewer/index.html">Interactive Viewer</a>
      <a href="./selected_allatom_visual_bundle_catalog_current.json">Bundle Catalog</a>
    </div>
  </header>
  <main>
    {''.join(card_html)}
  </main>
  <div id="galleryModal" class="modal">
    <div class="modal-content">
      <div class="modal-header">
        <h3 id="galleryModalTitle">Figure Preview</h3>
        <button id="galleryModalClose" class="modal-close">✕</button>
      </div>
      <div class="modal-body">
        <img id="galleryModalImage" alt="Gallery figure preview"/>
        <div id="galleryModalCaption" class="modal-caption"></div>
      </div>
    </div>
  </div>
  <script>
    (() => {{
      const modal = document.getElementById('galleryModal');
      const image = document.getElementById('galleryModalImage');
      const caption = document.getElementById('galleryModalCaption');
      const title = document.getElementById('galleryModalTitle');
      const closeBtn = document.getElementById('galleryModalClose');
      document.querySelectorAll('.zoomable').forEach((node) => {{
        node.addEventListener('click', () => {{
          image.src = node.dataset.fullSrc || node.src;
          caption.textContent = node.dataset.caption || node.alt || '';
          title.textContent = node.alt || 'Figure Preview';
          modal.classList.add('active');
        }});
      }});
      closeBtn.addEventListener('click', () => modal.classList.remove('active'));
      modal.addEventListener('click', (event) => {{
        if (event.target === modal) modal.classList.remove('active');
      }});
      window.addEventListener('keydown', (event) => {{
        if (event.key === 'Escape') modal.classList.remove('active');
      }});
    }})();
  </script>
</body>
</html>
"""


def main() -> None:
    cards = [_build_card(path, DEFAULT_OUTPUT) for path in DEFAULT_BUNDLE_FILES if path.exists()]
    DEFAULT_OUTPUT.write_text(build_gallery_html(cards))
    print(DEFAULT_OUTPUT)


if __name__ == "__main__":
    main()
