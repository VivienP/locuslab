"""Gold diff helper: recall/precision against gold fixtures.

This test always passes. It measures but does not assert numeric thresholds.
"""

from __future__ import annotations

import json
from pathlib import Path

DEMO_DOSSIER = Path(__file__).parent.parent / "fixtures" / "demo_dossier"
GOLD_DIR = Path(__file__).parent.parent / "fixtures" / "gold"


def _load_gold(name: str) -> dict:  # type: ignore[type-arg]
    return json.loads((GOLD_DIR / name).read_text(encoding="utf-8"))


def _run_pipeline(tmp_path: Path) -> dict[str, list[dict]]:  # type: ignore[type-arg]
    from locuslab.pipeline import verify_dossier

    run_dir = tmp_path / "gold_diff_run"
    verify_dossier(DEMO_DOSSIER, run_dir)

    result: dict[str, list[dict]] = {}  # type: ignore[type-arg]
    for fname in ["claims.jsonl", "citations.jsonl", "sources.jsonl", "evidence_links.jsonl"]:
        records = []
        text = (run_dir / fname).read_text(encoding="utf-8")
        for line in text.splitlines():
            if line.strip():
                records.append(json.loads(line))
        result[fname] = records
    return result


def test_gold_diff_reports_per_category_counts(tmp_path: Path, capsys) -> None:
    """Run pipeline and report recall/precision per category. No thresholds asserted."""
    pipeline_out = _run_pipeline(tmp_path)
    gold_claims = _load_gold("demo_claims.json")
    gold_citations = _load_gold("demo_citations.json")
    gold_bib = _load_gold("demo_bibliography.json")
    gold_links = _load_gold("demo_evidence_links.json")

    print("\nGold Diff - Demo Dossier")
    print("========================")

    # --- Claims ---
    expected_by_type: dict[str, list[dict]] = {}  # type: ignore[type-arg]
    for ec in gold_claims["expected_claims"]:
        t = ec["claim_type"]
        expected_by_type.setdefault(t, []).append(ec)

    extracted_claims = pipeline_out["claims.jsonl"]
    extracted_by_type: dict[str, list[dict]] = {}  # type: ignore[type-arg]
    for c in extracted_claims:
        t = c["claim_type"]
        extracted_by_type.setdefault(t, []).append(c)

    print("Claims:")
    for claim_type, expected_list in sorted(expected_by_type.items()):
        extracted_list = extracted_by_type.get(claim_type, [])
        # Match by text_fragment substring
        matched = 0
        for ec in expected_list:
            frag = ec["text_fragment"]
            target_span = ec["span_id"]
            # Check if any extracted claim for this span type contains the fragment
            for xc in extracted_list:
                if xc["span_id"] == target_span and frag.lower() in xc["text"].lower():
                    matched += 1
                    break
        n_expected = len(expected_list)
        n_extracted = len(extracted_list)
        print(
            f"  {claim_type:<24}: {matched}/{n_expected} expected matched, "
            f"{n_extracted} extracted"
        )

    # --- Citations ---
    expected_cites = gold_citations["expected_citations"]
    expected_cites_by_form: dict[str, list[dict]] = {}  # type: ignore[type-arg]
    for ec in expected_cites:
        form = ec["marker_form"]
        expected_cites_by_form.setdefault(form, []).append(ec)

    extracted_cites = pipeline_out["citations.jsonl"]
    extracted_cites_by_form: dict[str, list[dict]] = {}  # type: ignore[type-arg]
    for c in extracted_cites:
        form = c["marker_form"]
        extracted_cites_by_form.setdefault(form, []).append(c)

    print("Citations:")
    for form, expected_list in sorted(expected_cites_by_form.items()):
        matched = 0
        for ec in expected_list:
            target_span = ec["source_span_id"]
            marker = ec["marker_text"]
            for xc in extracted_cites_by_form.get(form, []):
                if xc["span_id"] == target_span and marker in xc["marker_text"]:
                    matched += 1
                    break
        n_expected = len(expected_list)
        n_extracted = len(extracted_cites_by_form.get(form, []))
        print(f"  {form:<30}: {matched}/{n_expected} expected matched, {n_extracted} extracted")

    # --- Sources ---
    expected_local = gold_bib["expected_bibliography_entries"]
    expected_external = gold_bib["expected_external_references"]
    extracted_sources = pipeline_out["sources.jsonl"]

    local_matched = sum(
        1 for e in expected_local
        if any(s["path"] == e["relative_path"] and s["availability_status"] == "local_fulltext"
               for s in extracted_sources)
    )
    missing_matched = sum(
        1 for e in expected_external
        if any(s["path"] == e["referenced_value"] and s["availability_status"] == "missing_file"
               for s in extracted_sources)
    )
    print("Sources:")
    print(f"  {'local_fulltext':<20}: {local_matched}/{len(expected_local)} resolved")
    print(f"  {'missing_file':<20}: {missing_matched}/{len(expected_external)} flagged")

    # --- Evidence Links ---
    expected_links = gold_links["expected_evidence_links"]
    expected_links_by_status: dict[str, list[dict]] = {}  # type: ignore[type-arg]
    for el in expected_links:
        st = el["expected_status"]
        expected_links_by_status.setdefault(st, []).append(el)

    extracted_links = pipeline_out["evidence_links.jsonl"]
    extracted_links_by_status: dict[str, list[dict]] = {}  # type: ignore[type-arg]
    for lk in extracted_links:
        st = lk["status"]
        extracted_links_by_status.setdefault(st, []).append(lk)

    print("Evidence Links:")
    for status, expected_list in sorted(expected_links_by_status.items()):
        n_expected = len(expected_list)
        n_extracted = len(extracted_links_by_status.get(status, []))
        print(f"  {status:<30}: {n_extracted} extracted / {n_expected} expected")

    # No numeric threshold assertions - always passes
    assert True
