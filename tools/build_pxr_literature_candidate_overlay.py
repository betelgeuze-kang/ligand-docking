#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import re
import time
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Callable
from urllib.parse import quote_plus, urlencode
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]

EUTILS_BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
DEFAULT_QUEUE_JSON = "runs/family_evidence_acquisition_queue_current.json"
DEFAULT_OUT_JSON = "runs/pxr_literature_candidate_overlay_current.json"
DEFAULT_OUT_CSV = "runs/pxr_literature_candidate_overlay_current.csv"
DEFAULT_OUT_MD = "runs/pxr_literature_candidate_overlay_current.md"
DEFAULT_TOP_N = 6

TARGET_TERMS = ("pregnane x receptor", "pxr", "nr1i2", "sxr")
NONHUMAN_TERMS = ("mouse", "mice", "murine", "rat", "rats", "zebrafish")
PRECLINICAL_TERMS = NONHUMAN_TERMS + ("preclinical", "in vivo", "ex vivo", "animal")
REVIEW_TERMS = ("review", "reviews")
LIGAND_QUERY_TERMS = {
    "acetaminophen": ("acetaminophen", "paracetamol"),
    "aspirin": ("aspirin", "acetylsalicylic acid"),
    "bexarotene": ("bexarotene",),
    "caffeine": ("caffeine",),
    "nicotinamide": ("nicotinamide", "niacinamide"),
}
HUMAN_TERMS = ("human", "humans", "homo sapiens")
DIRECT_SUPPORT_TERMS = (
    "weak activator",
    "weak activators",
    "activator",
    "activators",
    "antagonize",
    "antagonizes",
    "antagonist",
    "binding",
    "bind",
    "competition for binding",
    "compete",
    "competes",
)


def _resolve(path_like: str) -> Path:
    path = Path(path_like)
    if path.is_absolute():
        return path
    cwd_path = (Path.cwd() / path).resolve()
    if cwd_path.exists():
        return cwd_path
    return (ROOT / path).resolve()


def _load_json(path_like: str) -> dict[str, Any]:
    with _resolve(path_like).open("r", encoding="utf-8") as fh:
        return json.load(fh)


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def _normalize(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def _contains_any(text: str, terms: tuple[str, ...]) -> bool:
    normalized = f" {_normalize(text)} "
    return any(f" {_normalize(term)} " in normalized for term in terms)


def _sentence_chunks(title: str, abstract: str) -> list[str]:
    text = " ".join(part for part in [title, abstract] if part).strip()
    if not text:
        return []
    chunks = re.split(r"(?<=[.!?])\s+", text)
    return [chunk.strip() for chunk in chunks if chunk.strip()]


def _ligand_terms(ligand: str) -> tuple[str, ...]:
    return LIGAND_QUERY_TERMS.get(ligand.lower(), (ligand,))


def _title_abstract_query(ligand: str) -> str:
    ligand_clause = " OR ".join(f'"{term}"[Title/Abstract]' for term in _ligand_terms(ligand))
    target_clause = ' OR '.join(
        [
            '"pregnane X receptor"[Title/Abstract]',
            "PXR[Title/Abstract]",
            "NR1I2[Title/Abstract]",
            "SXR[Title/Abstract]",
        ]
    )
    return f"(({ligand_clause})) AND (({target_clause}))"


def _esearch_url(query: str, *, retmax: int = 5) -> str:
    return f"{EUTILS_BASE}/esearch.fcgi?{urlencode({'db': 'pubmed', 'term': query, 'retmode': 'json', 'retmax': retmax})}"


def _efetch_url(ids: list[str]) -> str:
    return f"{EUTILS_BASE}/efetch.fcgi?{urlencode({'db': 'pubmed', 'id': ','.join(ids), 'retmode': 'xml'})}"


def _fetch_text(url: str) -> str:
    req = Request(url, headers={"User-Agent": "md-family-expansion/1.0"})
    with urlopen(req, timeout=30) as resp:
        return resp.read().decode("utf-8")


def _esearch_ids(query: str, *, fetch_text: Callable[[str], str] | None = None) -> list[str]:
    payload = json.loads((fetch_text or _fetch_text)(_esearch_url(query)))
    return list(payload.get("esearchresult", {}).get("idlist", []) or [])


def _efetch_articles(ids: list[str], *, fetch_text: Callable[[str], str] | None = None) -> list[dict[str, str]]:
    if not ids:
        return []
    xml_text = (fetch_text or _fetch_text)(_efetch_url(ids))
    root = ET.fromstring(xml_text)
    articles: list[dict[str, str]] = []
    for article in root.findall(".//PubmedArticle"):
        pmid = "".join(article.findtext(".//PMID", default="")).strip()
        title = "".join(article.findtext(".//ArticleTitle", default="")).strip()
        abstract_parts = [
            "".join(node.itertext()).strip()
            for node in article.findall(".//Abstract/AbstractText")
            if "".join(node.itertext()).strip()
        ]
        abstract = " ".join(abstract_parts).strip()
        articles.append({"pmid": pmid, "title": title, "abstract": abstract})
    by_id = {row["pmid"]: row for row in articles if row["pmid"]}
    return [by_id[id_] for id_ in ids if id_ in by_id]


def _candidate_signal(ligand: str, title: str, abstract: str) -> tuple[str, bool, bool, bool, bool, bool]:
    combined = " ".join(part for part in [title, abstract] if part).strip()
    title_ligand_hit = _contains_any(title, _ligand_terms(ligand))
    title_target_hit = _contains_any(title, TARGET_TERMS)
    title_human_hit = _contains_any(title, HUMAN_TERMS)
    title_nonhuman_hit = _contains_any(title, NONHUMAN_TERMS)
    combined_ligand_hit = _contains_any(combined, _ligand_terms(ligand))
    combined_target_hit = _contains_any(combined, TARGET_TERMS)
    human_hit = _contains_any(combined, HUMAN_TERMS)
    nonhuman_hit = _contains_any(combined, NONHUMAN_TERMS)
    preclinical_hit = _contains_any(combined, PRECLINICAL_TERMS)
    review_hit = _contains_any(combined, REVIEW_TERMS)
    direct_support_hit = _contains_any(combined, DIRECT_SUPPORT_TERMS)
    sentence_chunks = _sentence_chunks(title, abstract)
    same_sentence_ligand_target = any(
        _contains_any(chunk, _ligand_terms(ligand)) and _contains_any(chunk, TARGET_TERMS)
        for chunk in sentence_chunks
    )
    same_sentence_human = any(
        _contains_any(chunk, _ligand_terms(ligand))
        and _contains_any(chunk, TARGET_TERMS)
        and _contains_any(chunk, HUMAN_TERMS)
        for chunk in sentence_chunks
    )
    if title_ligand_hit and title_target_hit and title_human_hit and not title_nonhuman_hit and not review_hit:
        return "high_signal_human_candidate", title_ligand_hit, title_target_hit, human_hit, nonhuman_hit, review_hit
    if title_ligand_hit and title_target_hit and (
        title_nonhuman_hit or (preclinical_hit and not title_human_hit) or (nonhuman_hit and not title_human_hit)
    ):
        return "title_direct_nonhuman_candidate", title_ligand_hit, title_target_hit, human_hit, nonhuman_hit, review_hit
    if title_ligand_hit and title_target_hit and review_hit:
        return "review_context_candidate", title_ligand_hit, title_target_hit, human_hit, nonhuman_hit, review_hit
    if title_ligand_hit and title_target_hit:
        return "high_signal_candidate", title_ligand_hit, title_target_hit, human_hit, nonhuman_hit, review_hit
    if combined_ligand_hit and combined_target_hit and human_hit and direct_support_hit and not review_hit and not nonhuman_hit:
        return "abstract_direct_human_candidate", combined_ligand_hit, combined_target_hit, human_hit, nonhuman_hit, review_hit
    if same_sentence_human:
        return "same_sentence_human_candidate", combined_ligand_hit, combined_target_hit, human_hit, nonhuman_hit, review_hit
    if same_sentence_ligand_target:
        return "same_sentence_candidate", combined_ligand_hit, combined_target_hit, human_hit, nonhuman_hit, review_hit
    if combined_ligand_hit and combined_target_hit and review_hit:
        return "review_context_candidate", combined_ligand_hit, combined_target_hit, human_hit, nonhuman_hit, review_hit
    if combined_ligand_hit and combined_target_hit:
        return "abstract_supported_candidate", combined_ligand_hit, combined_target_hit, human_hit, nonhuman_hit, review_hit
    if combined_target_hit:
        return "target_only_candidate", combined_ligand_hit, combined_target_hit, human_hit, nonhuman_hit, review_hit
    if combined_ligand_hit:
        return "ligand_only_candidate", combined_ligand_hit, combined_target_hit, human_hit, nonhuman_hit, review_hit
    return "weak_candidate", combined_ligand_hit, combined_target_hit, human_hit, nonhuman_hit, review_hit


def _row_from_queue(
    row: dict[str, Any],
    *,
    search_ids: Callable[[str], list[str]] | None = None,
    fetch_articles: Callable[[list[str]], list[dict[str, str]]] | None = None,
    throttle_sec: float = 0.34,
) -> dict[str, Any]:
    ligand = str(row.get("ligand", "")).strip()
    query = _title_abstract_query(ligand)
    result = {
        "queue_rank": int(row.get("queue_rank", 0) or 0),
        "family": str(row.get("family", "")).strip(),
        "packet_step": str(row.get("packet_step", "")).strip(),
        "ligand": ligand,
        "priority_tier": str(row.get("priority_tier", "")).strip(),
        "blocking_reason": str(row.get("blocking_reason", "")).strip(),
        "pubmed_query": query,
        "pubmed_query_url": f"https://pubmed.ncbi.nlm.nih.gov/?term={quote_plus(query)}",
        "candidate_status": "pending_query",
        "candidate_count": 0,
        "high_signal_candidate_count": 0,
        "best_candidate_pmid": "",
        "best_candidate_title": "",
        "best_candidate_url": "",
        "best_candidate_signal": "",
        "best_candidate_mentions_human": "",
        "best_candidate_mentions_nonhuman": "",
        "best_candidate_review_like": "",
        "best_candidate_note": "",
    }
    try:
        if throttle_sec > 0:
            time.sleep(throttle_sec)
        ids = (search_ids or _esearch_ids)(query)
        result["candidate_count"] = len(ids)
        if not ids:
            result["candidate_status"] = "no_candidates"
            result["best_candidate_note"] = "No PubMed title/abstract candidates matched the exact ligand + PXR query."
            return result
        if throttle_sec > 0:
            time.sleep(throttle_sec)
        articles = (fetch_articles or _efetch_articles)(ids[:5])
    except Exception as exc:
        result["candidate_status"] = "query_error"
        result["best_candidate_note"] = f"Live PubMed query failed: {exc}"
        return result

    best_signal_rank = {
        "high_signal_human_candidate": 4,
        "abstract_direct_human_candidate": 3,
        "same_sentence_human_candidate": 2,
        "high_signal_candidate": 1,
        "title_direct_nonhuman_candidate": 0,
        "same_sentence_candidate": -1,
        "review_context_candidate": -2,
        "abstract_supported_candidate": -3,
        "target_only_candidate": -4,
        "ligand_only_candidate": -5,
        "weak_candidate": -6,
    }
    best: dict[str, Any] | None = None
    high_signal_count = 0
    for article in articles:
        signal, ligand_hit, target_hit, human_hit, nonhuman_hit, review_hit = _candidate_signal(
            ligand,
            article["title"],
            article["abstract"],
        )
        if signal in {"high_signal_human_candidate", "abstract_direct_human_candidate", "high_signal_candidate"}:
            high_signal_count += 1
        scored = {
            **article,
            "signal": signal,
            "ligand_hit": ligand_hit,
            "target_hit": target_hit,
            "human_hit": human_hit,
            "nonhuman_hit": nonhuman_hit,
            "review_hit": review_hit,
        }
        if best is None or best_signal_rank[signal] > best_signal_rank[str(best["signal"])]:
            best = scored

    result["high_signal_candidate_count"] = high_signal_count
    if best is None:
        result["candidate_status"] = "no_candidates"
        result["best_candidate_note"] = "PubMed returned IDs, but none could be parsed into article metadata."
        return result

    result["best_candidate_pmid"] = str(best["pmid"])
    result["best_candidate_title"] = str(best["title"])
    result["best_candidate_url"] = f"https://pubmed.ncbi.nlm.nih.gov/{best['pmid']}/"
    result["best_candidate_signal"] = str(best["signal"])
    result["best_candidate_mentions_human"] = "yes" if bool(best["human_hit"]) else "no"
    result["best_candidate_mentions_nonhuman"] = "yes" if bool(best["nonhuman_hit"]) else "no"
    result["best_candidate_review_like"] = "yes" if bool(best["review_hit"]) else "no"
    if high_signal_count:
        result["candidate_status"] = "high_signal_candidates_present"
        result["best_candidate_note"] = (
            "PubMed returned a strong human-target support candidate for the exact ligand + PXR query."
            if str(best["signal"]) == "abstract_direct_human_candidate"
            else "At least one PubMed title mentions both the ligand and PXR/NR1I2 directly."
        )
    elif str(best["signal"]) == "same_sentence_human_candidate":
        result["candidate_status"] = "same_sentence_human_candidates_present"
        result["best_candidate_note"] = "PubMed returned a candidate where ligand and PXR/NR1I2 co-occur in the same sentence with human context."
    elif str(best["signal"]) == "title_direct_nonhuman_candidate":
        result["candidate_status"] = "title_direct_nonhuman_candidates_present"
        result["best_candidate_note"] = "PubMed returned a title-direct ligand + PXR candidate, but the strongest signal is still non-human or preclinical."
    elif str(best["signal"]) == "same_sentence_candidate":
        result["candidate_status"] = "same_sentence_candidates_present"
        result["best_candidate_note"] = "PubMed returned a candidate where ligand and PXR/NR1I2 co-occur in the same sentence, but human context is still weak."
    elif str(best["signal"]) == "review_context_candidate":
        result["candidate_status"] = "review_context_candidates_present"
        result["best_candidate_note"] = "PubMed returned review-like or summary context mentioning the ligand and PXR/NR1I2, but not a claim-safe source."
    elif str(best["signal"]) == "abstract_supported_candidate":
        result["candidate_status"] = "abstract_supported_candidates_present"
        result["best_candidate_note"] = "PubMed returned candidates where the ligand and PXR/NR1I2 co-occur in title/abstract text, but not as an exact title match."
    elif str(best["signal"]) == "target_only_candidate":
        result["candidate_status"] = "target_only_candidates_present"
        result["best_candidate_note"] = "PubMed returned PXR-targeted papers, but the ligand match was weak in title/abstract text."
    else:
        result["candidate_status"] = "weak_candidates_only"
        result["best_candidate_note"] = "PubMed candidates were weak or indirect for this exact ligand + PXR query."
    return result


def build_payload(
    queue_payload: dict[str, Any],
    *,
    top_n: int = DEFAULT_TOP_N,
    search_ids: Callable[[str], list[str]] | None = None,
    fetch_articles: Callable[[list[str]], list[dict[str, str]]] | None = None,
    throttle_sec: float = 0.34,
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for row in queue_payload.get("rows", []) or []:
        if len(rows) >= max(top_n, 0):
            break
        if str(row.get("family", "")).strip() != "pxr":
            continue
        rows.append(
            _row_from_queue(
                row,
                search_ids=search_ids,
                fetch_articles=fetch_articles,
                throttle_sec=throttle_sec,
            )
        )

    summary = {
        "row_count": len(rows),
        "top_n": top_n,
        "high_signal_row_count": sum(1 for row in rows if row["candidate_status"] == "high_signal_candidates_present"),
        "same_sentence_human_row_count": sum(
            1 for row in rows if row["candidate_status"] == "same_sentence_human_candidates_present"
        ),
        "title_direct_nonhuman_row_count": sum(
            1 for row in rows if row["candidate_status"] == "title_direct_nonhuman_candidates_present"
        ),
        "same_sentence_row_count": sum(
            1 for row in rows if row["candidate_status"] == "same_sentence_candidates_present"
        ),
        "review_context_row_count": sum(1 for row in rows if row["candidate_status"] == "review_context_candidates_present"),
        "target_only_row_count": sum(1 for row in rows if row["candidate_status"] == "target_only_candidates_present"),
        "no_candidate_row_count": sum(1 for row in rows if row["candidate_status"] == "no_candidates"),
        "query_error_row_count": sum(1 for row in rows if row["candidate_status"] == "query_error"),
        "primary_focus_ligand": str(rows[0].get("ligand", "")).strip() if rows else "",
        "next_required_step": (
            "Review exact human-support candidates first, treat title-direct non-human or review-like hits as manual confirmation only, and rerun the PXR capture refresh only after a claim-safe source is confirmed."
        ),
    }
    return {"summary": summary, "rows": rows}


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    s = payload["summary"]
    lines = [
        "# PXR Literature Candidate Overlay",
        "",
        f"- row_count: `{s['row_count']}`",
        f"- top_n: `{s['top_n']}`",
        f"- high_signal_row_count: `{s['high_signal_row_count']}`",
        f"- same_sentence_human_row_count: `{s['same_sentence_human_row_count']}`",
        f"- title_direct_nonhuman_row_count: `{s['title_direct_nonhuman_row_count']}`",
        f"- same_sentence_row_count: `{s['same_sentence_row_count']}`",
        f"- review_context_row_count: `{s['review_context_row_count']}`",
        f"- target_only_row_count: `{s['target_only_row_count']}`",
        f"- no_candidate_row_count: `{s['no_candidate_row_count']}`",
        f"- query_error_row_count: `{s['query_error_row_count']}`",
        f"- primary_focus_ligand: `{s['primary_focus_ligand']}`",
        "",
        "## Next Step",
        "",
        f"- {s['next_required_step']}",
        "",
        "## Rows",
        "",
        "| queue_rank | ligand | candidate_status | high_signal_candidate_count | best_candidate_pmid | best_candidate_signal |",
        "| ---: | --- | --- | ---: | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| {row['queue_rank']} | `{row['ligand']}` | `{row['candidate_status']}` | "
            f"{row['high_signal_candidate_count']} | `{row['best_candidate_pmid'] or '-'}` | "
            f"`{row['best_candidate_signal'] or '-'}` |"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a live PubMed title/abstract candidate overlay for top PXR evidence rows.")
    parser.add_argument("--queue-json", default=DEFAULT_QUEUE_JSON)
    parser.add_argument("--top-n", default=DEFAULT_TOP_N, type=int)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(_load_json(args.queue_json), top_n=args.top_n)
    out_json = _resolve(args.out_json)
    out_csv = _resolve(args.out_csv)
    out_md = _resolve(args.out_md)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    _write_csv(out_csv, payload["rows"])
    _write_markdown(out_md, payload)


if __name__ == "__main__":
    main()
