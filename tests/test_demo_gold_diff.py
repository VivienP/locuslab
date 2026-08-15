"""Executable gold contract for the synthetic demo dossier."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

DEMO_DOSSIER = Path(__file__).parent.parent / "fixtures" / "demo_dossier"
GOLD_DIR = Path(__file__).parent.parent / "fixtures" / "gold"


def _load_gold(name: str) -> dict[str, Any]:
    return json.loads((GOLD_DIR / name).read_text(encoding="utf-8"))


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _run_pipeline(tmp_path: Path) -> dict[str, list[dict[str, Any]]]:
    from locuslab.pipeline import verify_dossier

    run_dir = tmp_path / "gold_diff_run"
    verify_dossier(DEMO_DOSSIER, run_dir)
    return {
        name: _read_jsonl(run_dir / name)
        for name in (
            "claims.jsonl",
            "citations.jsonl",
            "sources.jsonl",
            "evidence_links.jsonl",
            "findings.jsonl",
        )
    }


def _matching_claims(
    expected: dict[str, Any], claims: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    fragment = expected["text_fragment"].lower()
    return [
        claim
        for claim in claims
        if claim["document_id"] == expected["document_id"]
        and claim["span_id"] == expected["span_id"]
        and claim["claim_type"] == expected["claim_type"]
        and claim["confidence_label"] == expected["expected_confidence_label"]
        and fragment in claim["text"].lower()
    ]


def test_demo_gold_annotations_match_live_artifacts(tmp_path: Path) -> None:
    actual = _run_pipeline(tmp_path)
    claim_gold = _load_gold("demo_claims.json")["expected_claims"]
    citation_gold = _load_gold("demo_citations.json")["expected_citations"]
    bibliography_gold = _load_gold("demo_bibliography.json")
    link_gold = _load_gold("demo_evidence_links.json")["expected_evidence_links"]
    finding_gold = _load_gold("demo_expected_findings.json")["expected_findings"]

    actual_claim_by_gold_id: dict[str, dict[str, Any]] = {}
    for expected in claim_gold:
        matches = _matching_claims(expected, actual["claims.jsonl"])
        assert len(matches) == 1, (
            f"{expected['gold_id']} matched {len(matches)} live claims; expected one"
        )
        actual_claim_by_gold_id[expected["gold_id"]] = matches[0]

    for expected in citation_gold:
        matches = [
            citation
            for citation in actual["citations.jsonl"]
            if citation["span_id"] == expected["source_span_id"]
            and citation["marker_form"] == expected["marker_form"]
            and expected["marker_text"] in citation["marker_text"]
        ]
        assert len(matches) == 1, (
            f"{expected['gold_id']} matched {len(matches)} live citations; expected one"
        )

    source_gold = {
        entry["gold_id"]: entry
        for entry in (
            bibliography_gold["expected_bibliography_entries"]
            + bibliography_gold["expected_external_references"]
        )
    }
    actual_source_by_gold_id: dict[str, dict[str, Any]] = {}
    for gold_id, expected in source_gold.items():
        expected_path = expected.get("relative_path", expected.get("referenced_value"))
        expected_status = (
            "local_fulltext" if "relative_path" in expected else "missing_file"
        )
        matches = [
            source
            for source in actual["sources.jsonl"]
            if source["path"] == expected_path
            and source["availability_status"] == expected_status
        ]
        assert len(matches) == 1, (
            f"{gold_id} matched {len(matches)} live sources; expected one"
        )
        actual_source_by_gold_id[gold_id] = matches[0]

    for expected in link_gold:
        claim = actual_claim_by_gold_id[expected["claim_gold_id"]]
        source_gold_id = expected["source_gold_id"]
        expected_source_id = (
            actual_source_by_gold_id[source_gold_id]["source_id"]
            if source_gold_id is not None
            else None
        )
        matches = [
            link
            for link in actual["evidence_links.jsonl"]
            if link["claim_id"] == claim["claim_id"]
            and link["source_id"] == expected_source_id
            and link["status"] == expected["expected_status"]
            and link["linking_method"] == expected["expected_linking_method"]
        ]
        assert len(matches) == 1, (
            f"{expected['gold_id']} matched {len(matches)} live links; expected one"
        )

    assert len(actual["findings.jsonl"]) == len(finding_gold)
    for expected in finding_gold:
        matches = [
            finding
            for finding in actual["findings.jsonl"]
            if finding["severity"] == expected["severity"]
            and finding["finding_type"] == expected["finding_type"]
            and expected["affected_span_id"] in finding["affected_object_ids"]
            and expected["evidence_fragment"].lower() in finding["evidence"].lower()
        ]
        assert len(matches) == 1, (
            f"{expected['gold_id']} matched {len(matches)} live findings; expected one"
        )
