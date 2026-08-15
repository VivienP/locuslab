"""Deterministic findings regression tests.

Covers four checker families:
- broken_citation_anchor
- unresolved_evidence_link
- source_availability_gap
- manual_review_required

Plus the run_checkers orchestrator and findings.csv output. All fixtures
are constructed inline or sourced from the synthetic demo_dossier fixture
to keep tests offline and deterministic.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

from locuslab.checkers import (
    CHECKER_BROKEN_CITATION,
    CHECKER_MANUAL_REVIEW,
    CHECKER_SOURCE_AVAILABILITY,
    CHECKER_UNRESOLVED_EVIDENCE,
    check_broken_citation_anchor,
    check_manual_review_required,
    check_source_availability_gap,
    check_unresolved_evidence_link,
    make_eco_id,
)
from locuslab.extract.citation_parser import CitationMention
from locuslab.models import (
    AdjudicationState,
    Claim,
    ClaimType,
    ConfidenceLabel,
    EvidenceLink,
    Finding,
    FindingSeverity,
    Source,
)
from locuslab.output import write_findings_csv

DEMO_DOSSIER = Path(__file__).parent.parent / "fixtures" / "demo_dossier"

# Conservative-language forbidden words per spec section 5 and the
# no-confident-verdict-without-evidence skill. Every checker family's
# positive test asserts these words are absent from `evidence`.
_FORBIDDEN_LANGUAGE = frozenset(
    {
        "non-compliant",
        "noncompliant",
        "false claim",
        "nb will reject",
        "regulatory failure",
        "must ",
        "shall ",
        "unsupported",
    }
)


def _assert_conservative_language(evidence: str) -> None:
    """Fail if forbidden compliance/verdict language appears in *evidence*."""
    lower = evidence.lower()
    for word in _FORBIDDEN_LANGUAGE:
        assert word not in lower, f"Forbidden word {word!r} in finding evidence: {evidence!r}"


def _make_citation(
    mention_id: str,
    document_id: str,
    span_id: str,
    marker_form: str,
    marker_text: str,
    normalized_key: str | None,
) -> CitationMention:
    return CitationMention(
        mention_id=mention_id,
        document_id=document_id,
        span_id=span_id,
        marker_text=marker_text,
        marker_form=marker_form,
        normalized_key=normalized_key,
        section=None,
        span_offset_start=0,
        span_offset_end=len(marker_text),
        occurrence_index=1,
        confidence_label="high",
        parser_id="citation_parser:v1",
    )


def _make_claim(
    claim_id: str,
    document_id: str = "doc_0a1b2c3d4e5f6789",
    span_id: str = "span_test",
    claim_type: ClaimType = ClaimType.CLINICAL_PERFORMANCE,
) -> Claim:
    return Claim(
        claim_id=claim_id,
        document_id=document_id,
        span_id=span_id,
        text="test claim",
        claim_type=claim_type,
        extraction_method="extract.test:v1",
        confidence_label=ConfidenceLabel.HIGH,
    )


def _make_link(
    link_id: str,
    claim_id: str,
    status: str,
    source_id: str | None = None,
    linking_method: str = "no_link_found",
    candidate_source_ids: tuple[str, ...] = (),
) -> EvidenceLink:
    return EvidenceLink(
        evidence_link_id=link_id,
        claim_id=claim_id,
        source_id=source_id,
        status=status,
        linking_method=linking_method,
        candidate_source_ids=candidate_source_ids,
    )


def _make_source(
    source_id: str,
    availability_status: str,
    citation_key: str | None = None,
    path: str | None = None,
    origin_span_ids: tuple[str, ...] = (),
) -> Source:
    return Source(
        source_id=source_id,
        path=path,
        citation_key=citation_key,
        availability_status=availability_status,
        origin_span_ids=origin_span_ids,
    )


# ===========================================================================
# Family 1 — broken_citation_anchor
# ===========================================================================


class TestBrokenCitationAnchor:
    def test_bracketed_numeric_without_resolution_emits_finding(self):
        cite = _make_citation(
            "cite_bracket_1",
            "doc_1dd5a3cd674157b5",
            "span_05f0a0e4c6224e9f",
            marker_form="numeric_bracketed",
            marker_text="[1]",
            normalized_key=None,
        )
        findings = check_broken_citation_anchor([cite], sources=[])
        assert len(findings) == 1
        assert findings[0].severity == FindingSeverity.MAJOR
        assert findings[0].finding_type == "unresolved_citation_marker"
        assert findings[0].checker_id == CHECKER_BROKEN_CITATION
        assert "[1]" in findings[0].evidence
        assert "doc_1dd5a3cd674157b5" in findings[0].affected_object_ids
        assert "span_05f0a0e4c6224e9f" in findings[0].affected_object_ids
        assert findings[0].adjudication_state == AdjudicationState.PENDING
        _assert_conservative_language(findings[0].evidence)
        _assert_conservative_language(findings[0].remediation_hint)

    def test_author_year_with_resolved_source_emits_nothing(self):
        cite = _make_citation(
            "cite_smith",
            "doc_test",
            "span_test",
            marker_form="author_year_parenthetical",
            marker_text="(Smith et al., 2023)",
            normalized_key="smith_2023",
        )
        smith_source = _make_source(
            "src_smith", availability_status="local_fulltext", citation_key="smith_2023"
        )
        findings = check_broken_citation_anchor([cite], sources=[smith_source])
        assert findings == []

    def test_author_year_with_unresolved_key_emits_finding(self):
        cite = _make_citation(
            "cite_kerry",
            "doc_test",
            "span_test",
            marker_form="author_year_table_cell",
            marker_text="Kerry et al. 2022",
            normalized_key="kerry_2022",
        )
        # Only Smith is available; Kerry is not.
        smith_source = _make_source(
            "src_smith", availability_status="local_fulltext", citation_key="smith_2023"
        )
        findings = check_broken_citation_anchor([cite], sources=[smith_source])
        assert len(findings) == 1
        assert findings[0].finding_type == "unresolved_citation_marker"
        assert "kerry_2022" in findings[0].evidence

    def test_numeric_parenthetical_footnote_emits_nothing(self):
        # In-document footnotes like `(3)` have document-scoped keys
        # (footnote_<doc_short>_<n>) that intentionally do not resolve to a
        # global Source. The checker must skip this form.
        cite = _make_citation(
            "cite_footnote",
            "doc_test",
            "span_test",
            marker_form="numeric_parenthetical",
            marker_text="(3)",
            normalized_key="footnote_test_3",
        )
        findings = check_broken_citation_anchor([cite], sources=[])
        assert findings == []


# ===========================================================================
# Family 2 — unresolved_evidence_link
# ===========================================================================


class TestUnresolvedEvidenceLink:
    def test_source_unresolved_link_emits_major_finding(self):
        claim = _make_claim("claim_benefit_risk", claim_type=ClaimType.BENEFIT_RISK)
        link = _make_link(
            "link_1",
            claim.claim_id,
            status="source_unresolved",
            linking_method="no_link_found",
        )
        findings = check_unresolved_evidence_link([link], [claim])
        assert len(findings) == 1
        assert findings[0].severity == FindingSeverity.MAJOR
        assert findings[0].finding_type == "claim_without_resolved_source"
        assert findings[0].checker_id == CHECKER_UNRESOLVED_EVIDENCE
        # Source-traceability language convention (not a verdict).
        assert "no resolved local source" in findings[0].evidence.lower()
        # "unsupported" must NOT appear in buyer-facing finding evidence —
        # absence of an evidence link is not equivalent to evidence of falsity.
        assert "unsupported" not in findings[0].evidence.lower()
        assert "unsupported" not in findings[0].remediation_hint.lower()
        _assert_conservative_language(findings[0].evidence)
        _assert_conservative_language(findings[0].remediation_hint)

    def test_resolved_link_emits_nothing(self):
        claim = _make_claim("claim_resolved")
        link = _make_link("link_ok", claim.claim_id, status="resolved", source_id="src_ok")
        findings = check_unresolved_evidence_link([link], [claim])
        assert findings == []

    def test_link_without_matching_claim_emits_nothing(self):
        # Defensive: orphan link references no claim in the input set.
        link = _make_link("link_orphan", "claim_does_not_exist", status="source_unresolved")
        findings = check_unresolved_evidence_link([link], claims=[])
        assert findings == []

    def test_ambiguous_link_names_all_candidate_sources(self):
        claim = _make_claim("claim_ambiguous")
        link = _make_link(
            "link_ambiguous",
            claim.claim_id,
            status="source_ambiguous",
            linking_method="explicit_citation_ambiguous",
            candidate_source_ids=("src_b", "src_a"),
        )

        findings = check_unresolved_evidence_link([link], [claim])

        assert len(findings) == 1
        assert findings[0].finding_type == "claim_with_ambiguous_sources"
        assert "multiple local sources" in findings[0].evidence
        assert "src_a" in findings[0].affected_object_ids
        assert "src_b" in findings[0].affected_object_ids


# ===========================================================================
# Family 3 — source_availability_gap
# ===========================================================================


class TestSourceAvailabilityGap:
    def test_missing_file_source_emits_major_finding(self):
        source = _make_source(
            "src_pms",
            availability_status="missing_file",
            citation_key=None,
            path="bibliography/PMS.docx",
            origin_span_ids=("span_gspr_pms",),
        )
        claim = _make_claim("claim_pms", claim_type=ClaimType.COMPLETENESS)
        link = _make_link(
            "link_pms",
            claim.claim_id,
            status="source_missing",
            source_id=source.source_id,
            linking_method="filename_reference",
        )
        findings = check_source_availability_gap([source], [link], [claim])
        assert len(findings) == 1
        assert findings[0].severity == FindingSeverity.MAJOR
        assert findings[0].finding_type == "evidence_document_referenced_but_missing"
        assert findings[0].checker_id == CHECKER_SOURCE_AVAILABILITY
        assert "PMS.docx" in findings[0].evidence
        assert "not located" in findings[0].evidence
        assert "span_gspr_pms" in findings[0].affected_object_ids
        _assert_conservative_language(findings[0].evidence)
        _assert_conservative_language(findings[0].remediation_hint)

    def test_local_fulltext_source_emits_nothing(self):
        source = _make_source(
            "src_smith", availability_status="local_fulltext", citation_key="smith_2023"
        )
        findings = check_source_availability_gap([source], [], [])
        assert findings == []

    def test_completeness_gap_without_source_record(self):
        # GSPR row with Applicable=Yes but no Evidence_Document at all.
        # Linker emits `source_missing` link with `source_id=None`.
        claim = _make_claim("claim_gspr", claim_type=ClaimType.COMPLETENESS)
        link = _make_link(
            "link_gspr_no_doc",
            claim.claim_id,
            status="source_missing",
            source_id=None,
            linking_method="no_link_found",
        )
        findings = check_source_availability_gap([], [link], [claim])
        assert len(findings) == 1
        assert findings[0].finding_type == "completeness_gap_applicable_but_no_evidence"
        assert findings[0].severity == FindingSeverity.MAJOR
        assert "has no evidence document reference" in findings[0].evidence.lower()
        assert "is referenced" not in findings[0].evidence.lower()

    def test_missing_file_source_no_critical_severity(self):
        # MVP severity discipline: zero Critical on synthetic dossiers.
        source = _make_source(
            "src_any", availability_status="missing_file", path="bibliography/Any.pdf"
        )
        findings = check_source_availability_gap([source], [], [])
        assert all(f.severity != FindingSeverity.CRITICAL for f in findings)


# ===========================================================================
# Family 4 — manual_review_required
# ===========================================================================


class TestManualReviewRequired:
    def test_classification_claim_with_manual_review_emits_informational(self):
        claim = _make_claim("claim_class", claim_type=ClaimType.CLASSIFICATION)
        link = _make_link(
            "link_class", claim.claim_id, status="manual_review_required"
        )
        findings = check_manual_review_required([link], [claim])
        assert len(findings) == 1
        assert findings[0].severity == FindingSeverity.INFORMATIONAL
        assert findings[0].finding_type == "classification_rationale_requires_manual_review"
        assert findings[0].checker_id == CHECKER_MANUAL_REVIEW
        assert "manual review" in findings[0].evidence.lower()
        _assert_conservative_language(findings[0].evidence)
        _assert_conservative_language(findings[0].remediation_hint)

    def test_numeric_claim_with_manual_review_is_filtered_out(self):
        # NUMERIC claims are extraction primitives; manual_review on them is
        # structural noise and must be filtered.
        claim = _make_claim("claim_num", claim_type=ClaimType.NUMERIC)
        link = _make_link("link_num", claim.claim_id, status="manual_review_required")
        findings = check_manual_review_required([link], [claim])
        assert findings == []


# ===========================================================================
# ECO ID stability
# ===========================================================================


class TestEcoIdStability:
    def test_eco_id_is_deterministic_across_calls(self):
        ids_a = make_eco_id("CITE", ["doc_x", "span_y", "cite_z"])
        ids_b = make_eco_id("CITE", ["doc_x", "span_y", "cite_z"])
        assert ids_a == ids_b
        # Format check.
        assert ids_a.startswith("ECO-CITE-")
        assert len(ids_a) == len("ECO-CITE-") + 8

    def test_eco_id_order_independent_on_affected_ids(self):
        # The hash is over sorted affected IDs, so order should not matter.
        ids_a = make_eco_id("SRC", ["a", "b", "c"])
        ids_b = make_eco_id("SRC", ["c", "a", "b"])
        assert ids_a == ids_b


# ===========================================================================
# Orchestrator + end-to-end
# ===========================================================================


class TestRunCheckersOrchestrator:
    def test_demo_dossier_emits_gold_pattern_findings(self, tmp_path):
        """End-to-end: run pipeline on demo_dossier, confirm gold expected pattern."""
        from locuslab.pipeline import verify_dossier

        run_dir = tmp_path / "p3_orchestrator_run"
        result = verify_dossier(DEMO_DOSSIER, run_dir)
        assert result.n_findings >= 5, (
            f"Expected at least 5 findings on demo dossier; got {result.n_findings}"
        )
        findings_path = run_dir / "findings.jsonl"
        assert findings_path.exists()
        findings = [
            json.loads(line) for line in findings_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        # Zero Critical on synthetic fixture (severity discipline).
        criticals = [f for f in findings if f["severity"] == "Critical"]
        assert criticals == [], f"Unexpected Critical findings: {criticals}"
        # At least one of each priority family must fire.
        types = {f["finding_type"] for f in findings}
        assert "unresolved_citation_marker" in types
        assert "claim_without_resolved_source" in types
        assert any(t.startswith("evidence_document_referenced_but_missing") for t in types) or \
               "completeness_gap_applicable_but_no_evidence" in types
        assert "classification_rationale_requires_manual_review" in types


# ===========================================================================
# CSV output
# ===========================================================================


class TestFindingsCsvOutput:
    def test_csv_header_and_row_round_trip(self, tmp_path):
        finding = Finding(
            eco_id="ECO-CITE-deadbeef",
            severity=FindingSeverity.MAJOR,
            checker_id="checker.test:v1",
            finding_type="unresolved_citation_marker",
            affected_object_ids=("doc_a", "span_b", "cite_c"),
            evidence="Citation marker '[1]' not located in provided package.",
            remediation_hint="Add the source file.",
            adjudication_state=AdjudicationState.PENDING,
        )
        path = tmp_path / "findings.csv"
        write_findings_csv([finding], path)
        rows = list(csv.reader(path.open(encoding="utf-8")))
        assert rows[0] == [
            "eco_id",
            "severity",
            "checker_id",
            "finding_type",
            "affected_object_ids",
            "evidence",
            "remediation_hint",
            "adjudication_state",
        ]
        assert len(rows) == 2
        assert rows[1][0] == "ECO-CITE-deadbeef"
        assert rows[1][4] == "doc_a;span_b;cite_c"
        assert rows[1][7] == "pending"

    def test_csv_with_no_findings_writes_header_only(self, tmp_path):
        path = tmp_path / "empty_findings.csv"
        write_findings_csv([], path)
        rows = list(csv.reader(path.open(encoding="utf-8")))
        assert len(rows) == 1
        assert rows[0][0] == "eco_id"


# ===========================================================================
# Pipeline integration
# ===========================================================================


class TestFindingsArtifactWritten:
    def test_pipeline_writes_both_findings_artifacts(self, tmp_path):
        from locuslab.pipeline import verify_dossier

        run_dir = tmp_path / "p3_artifact_run"
        verify_dossier(DEMO_DOSSIER, run_dir)
        assert (run_dir / "findings.jsonl").exists()
        assert (run_dir / "findings.csv").exists()
        # CSV must have at least the header.
        csv_text = (run_dir / "findings.csv").read_text(encoding="utf-8")
        assert csv_text.startswith("eco_id,severity,checker_id")
