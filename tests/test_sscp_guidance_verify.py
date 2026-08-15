"""SSCP guidance review wired into locus verify (offline)."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent
_SRC = REPO_ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from locuslab.guidance.evaluate_sscp import (  # noqa: E402
    DETERMINISTIC_RULE_IDS,
    EVALUATION_METHOD_DETERMINISTIC,
    EVALUATION_METHOD_HUMAN,
    EVALUATION_STATUS_MISSING,
    EVALUATION_STATUS_NOT_EVALUATED,
    EVALUATION_STATUS_OBSERVED,
    evaluate_sscp_rules,
    is_sscp_run,
)
from locuslab.models import (  # noqa: E402
    Document,
    DocumentKind,
    Span,
    SpanLocation,
    SpanLocationKind,
)
from locuslab.pipeline import verify_dossier  # noqa: E402
from locuslab.report.language import REPORT_FORBIDDEN_LANGUAGE  # noqa: E402

DEMO_DOSSIER = REPO_ROOT / "fixtures" / "demo_dossier"
SYNTHETIC_SSCP_DOSSIER = (
    REPO_ROOT / "tests" / "fixtures" / "sscp_synthetic" / "by_filename"
)
RULE_PACK_PATH = REPO_ROOT / "docs" / "rules" / "guidance" / "sscp" / "rule_pack.json"

_MODAL_EXCEPTIONS = frozenset({"must ", "shall "})
_FORBIDDEN_FOR_GUIDANCE_OUTPUT = (
    REPORT_FORBIDDEN_LANGUAGE - _MODAL_EXCEPTIONS
) | frozenset({"violation", "fail", "passed", "nb rejection", "defect"})


def _make_doc(doc_id: str = "doc_test_sscp", path: str = "SSCP_test.docx") -> Document:
    return Document(
        document_id=doc_id,
        kind=DocumentKind.SSCP,
        path=path,
        sha256="0" * 64,
        parser="test",
    )


def _make_span(text: str, span_id: str = "span_test", doc_id: str = "doc_test_sscp") -> Span:
    return Span(
        span_id=span_id,
        document_id=doc_id,
        location=SpanLocation(kind=SpanLocationKind.PARAGRAPH, index=0),
        text=text,
    )


@pytest.fixture()
def rule_pack() -> dict[str, object]:
    return json.loads(RULE_PACK_PATH.read_text(encoding="utf-8"))


class TestSscpTrigger:
    def test_is_sscp_run_true_for_sscp_kind(self) -> None:
        assert is_sscp_run([_make_doc()]) is True

    def test_is_sscp_run_false_for_only_cer(self) -> None:
        cer = Document(
            document_id="doc_cer",
            kind=DocumentKind.CER,
            path="CER.docx",
            sha256="0" * 64,
            parser="test",
        )
        assert is_sscp_run([cer]) is False

    def test_is_sscp_run_true_when_any_doc_is_sscp(self) -> None:
        cer = Document(
            document_id="doc_cer",
            kind=DocumentKind.CER,
            path="CER.docx",
            sha256="0" * 64,
            parser="test",
        )
        assert is_sscp_run([cer, _make_doc()]) is True

    def test_is_sscp_run_false_for_empty(self) -> None:
        assert is_sscp_run([]) is False


class TestEvaluatorPatterns:
    def test_intended_purpose_observed_on_matching_span(
        self, rule_pack: dict[str, object]
    ) -> None:
        spans = [_make_span("Section 2. Intended purpose of the device: treatment of X.")]
        evals = evaluate_sscp_rules(rule_pack=rule_pack, spans=spans)
        e = evals["guidance.sscp.required_section.intended_purpose"]
        assert e["evaluation_status"] == EVALUATION_STATUS_OBSERVED
        assert e["evaluation_method"] == EVALUATION_METHOD_DETERMINISTIC
        assert e["evidence_matches"]
        assert e["evidence_matches"][0]["matched_pattern"] == "intended purpose"

    def test_device_description_observed_via_operating_principles(
        self, rule_pack: dict[str, object]
    ) -> None:
        spans = [_make_span("The device operating principles are as follows: ...")]
        evals = evaluate_sscp_rules(rule_pack=rule_pack, spans=spans)
        e = evals["guidance.sscp.required_section.device_description"]
        assert e["evaluation_status"] == EVALUATION_STATUS_OBSERVED
        assert any(
            m["matched_pattern"] == "operating principles" for m in e["evidence_matches"]
        )

    def test_basic_udi_di_observed(self, rule_pack: dict[str, object]) -> None:
        spans = [_make_span("Basic UDI-DI: 12345BUDI-DI")]
        evals = evaluate_sscp_rules(rule_pack=rule_pack, spans=spans)
        e = evals["guidance.sscp.metadata.basic_udi_di_present"]
        assert e["evaluation_status"] == EVALUATION_STATUS_OBSERVED

    def test_notified_body_observed(self, rule_pack: dict[str, object]) -> None:
        spans = [_make_span("Notified Body number: 0123. Validation completed.")]
        evals = evaluate_sscp_rules(rule_pack=rule_pack, spans=spans)
        e = evals["guidance.sscp.metadata.notified_body_identifier"]
        assert e["evaluation_status"] == EVALUATION_STATUS_OBSERVED

    def test_all_four_missing_on_empty_spans(self, rule_pack: dict[str, object]) -> None:
        evals = evaluate_sscp_rules(rule_pack=rule_pack, spans=[])
        for rid in DETERMINISTIC_RULE_IDS:
            e = evals[rid]
            assert e["evaluation_status"] == EVALUATION_STATUS_MISSING
            assert e["evidence_matches"] == []
            assert e["evaluation_method"] == EVALUATION_METHOD_DETERMINISTIC

    def test_six_pending_rules_are_not_evaluated(self, rule_pack: dict[str, object]) -> None:
        evals = evaluate_sscp_rules(rule_pack=rule_pack, spans=[])
        not_evaluated_ids = {
            rid for rid, e in evals.items()
            if e["evaluation_status"] == EVALUATION_STATUS_NOT_EVALUATED
        }
        assert len(not_evaluated_ids) == 6
        for rid in not_evaluated_ids:
            e = evals[rid]
            assert e["evaluation_method"] == EVALUATION_METHOD_HUMAN
            assert e["evidence_matches"] is None

    def test_evidence_matches_capped(self, rule_pack: dict[str, object]) -> None:
        """Evaluator must cap evidence_matches at 5 to avoid noise."""
        many_spans = [
            _make_span(f"Intended purpose mention #{i}", span_id=f"span_{i}")
            for i in range(12)
        ]
        evals = evaluate_sscp_rules(rule_pack=rule_pack, spans=many_spans)
        e = evals["guidance.sscp.required_section.intended_purpose"]
        assert len(e["evidence_matches"]) <= 5

    def test_match_is_case_insensitive(self, rule_pack: dict[str, object]) -> None:
        spans = [_make_span("INTENDED PURPOSE: clinical")]
        evals = evaluate_sscp_rules(rule_pack=rule_pack, spans=spans)
        e = evals["guidance.sscp.required_section.intended_purpose"]
        assert e["evaluation_status"] == EVALUATION_STATUS_OBSERVED

    def test_non_sscp_spans_cannot_satisfy_sscp_rule(
        self, rule_pack: dict[str, object]
    ) -> None:
        spans = [
            _make_span("No matching heading.", doc_id="doc_sscp"),
            _make_span(
                "Intended purpose appears only in the CER.",
                span_id="span_cer",
                doc_id="doc_cer",
            ),
        ]
        evals = evaluate_sscp_rules(
            rule_pack=rule_pack,
            spans=spans,
            allowed_document_ids=frozenset({"doc_sscp"}),
        )
        e = evals["guidance.sscp.required_section.intended_purpose"]
        assert e["evaluation_status"] == EVALUATION_STATUS_MISSING
        assert e["evidence_matches"] == []


class TestPipelineSkipsGuidanceForNonSscpDossier:
    def test_demo_dossier_emits_no_guidance(self, tmp_path: Path) -> None:
        result = verify_dossier(dossier_dir=DEMO_DOSSIER, output_dir=tmp_path)
        assert result.n_guidance_review_items is None, (
            "Non-SSCP dossier must skip guidance review"
        )
        assert not (tmp_path / "guidance_review.json").exists()
        assert not (tmp_path / "guidance_review.md").exists()

    def test_demo_dossier_manifest_has_no_guidance_keys(self, tmp_path: Path) -> None:
        verify_dossier(dossier_dir=DEMO_DOSSIER, output_dir=tmp_path)
        manifest = json.loads(
            (tmp_path / "audit_manifest.json").read_text(encoding="utf-8")
        )
        assert "guidance_review_items" not in manifest["artifact_counts"]
        for key in manifest["artifact_hashes"]:
            assert not key.startswith("guidance_review"), (
                f"non-SSCP manifest should not carry {key}"
            )

    def test_reused_output_removes_stale_guidance_artifacts(
        self, tmp_path: Path
    ) -> None:
        verify_dossier(
            dossier_dir=SYNTHETIC_SSCP_DOSSIER,
            output_dir=tmp_path,
        )
        assert (tmp_path / "guidance_review.json").is_file()
        assert (tmp_path / "guidance_review.md").is_file()

        verify_dossier(dossier_dir=DEMO_DOSSIER, output_dir=tmp_path)

        assert not (tmp_path / "guidance_review.json").exists()
        assert not (tmp_path / "guidance_review.md").exists()


class TestPipelineEmitsGuidanceForSscpDossier:
    @pytest.fixture()
    def sscp_run(self, tmp_path: Path) -> Path:
        verify_dossier(dossier_dir=SYNTHETIC_SSCP_DOSSIER, output_dir=tmp_path)
        return tmp_path

    def test_guidance_artifacts_written(self, sscp_run: Path) -> None:
        assert (sscp_run / "guidance_review.json").is_file()
        assert (sscp_run / "guidance_review.md").is_file()

    def test_guidance_json_has_ten_items(self, sscp_run: Path) -> None:
        data = json.loads((sscp_run / "guidance_review.json").read_text(encoding="utf-8"))
        assert data["n_review_items"] == 10
        assert len(data["review_items"]) == 10

    def test_approved_rules_carry_excerpt_and_evaluation(self, sscp_run: Path) -> None:
        data = json.loads((sscp_run / "guidance_review.json").read_text(encoding="utf-8"))
        items_by_id = {it["rule_id"]: it for it in data["review_items"]}
        for rid in DETERMINISTIC_RULE_IDS:
            it = items_by_id[rid]
            assert isinstance(it["exact_excerpt"], str) and it["exact_excerpt"]
            assert isinstance(it["source_hash"], str) and it["source_hash"]
            assert it["evaluation_method"] == EVALUATION_METHOD_DETERMINISTIC
            assert it["evaluation_status"] in (
                EVALUATION_STATUS_OBSERVED, EVALUATION_STATUS_MISSING
            )

    def test_pending_rules_remain_not_evaluated(self, sscp_run: Path) -> None:
        data = json.loads((sscp_run / "guidance_review.json").read_text(encoding="utf-8"))
        for it in data["review_items"]:
            if it["rule_id"] not in DETERMINISTIC_RULE_IDS:
                assert it["evaluation_status"] == EVALUATION_STATUS_NOT_EVALUATED
                assert it["evaluation_method"] == EVALUATION_METHOD_HUMAN
                assert it["evidence_matches"] is None

    def test_every_item_remains_review_aid(self, sscp_run: Path) -> None:
        data = json.loads((sscp_run / "guidance_review.json").read_text(encoding="utf-8"))
        for it in data["review_items"]:
            assert it["review_status"] == "needs_human_confirmation"
            assert it["output_boundary"] == "not_an_ECO_finding"

    def test_findings_jsonl_unchanged_by_guidance(
        self, sscp_run: Path, tmp_path: Path
    ) -> None:
        """The guidance layer must not alter findings.jsonl, AND
        guidance_review.json + .md must be byte-equal across two runs on
        the same SSCP dossier (Phase 6D W-2: closes the spec §8
        determinism property with a concrete byte-equality assertion)."""
        # Already produced sscp_run; produce a fresh control run.
        control = tmp_path / "control_run"
        verify_dossier(dossier_dir=SYNTHETIC_SSCP_DOSSIER, output_dir=control)

        sscp_findings = (sscp_run / "findings.jsonl").read_bytes()
        control_findings = (control / "findings.jsonl").read_bytes()
        assert sscp_findings == control_findings, (
            "findings.jsonl must be byte-equal across two runs on the same dossier"
        )

        # Phase 6D W-2: guidance JSON is byte-deterministic (sort_keys=True,
        # no wall-clock, deterministic patterns).
        sscp_guidance_json = (sscp_run / "guidance_review.json").read_bytes()
        control_guidance_json = (control / "guidance_review.json").read_bytes()
        assert sscp_guidance_json == control_guidance_json, (
            "guidance_review.json must be byte-equal across two runs"
        )

        # Markdown is also deterministic (Py3.7+ dict iteration is
        # insertion-order, the renderer builds each item with literal field
        # order). If this ever drifts a future packet must fix it before
        # promoting guidance to a buyer-shipped artifact pair.
        sscp_guidance_md = (sscp_run / "guidance_review.md").read_bytes()
        control_guidance_md = (control / "guidance_review.md").read_bytes()
        assert sscp_guidance_md == control_guidance_md, (
            "guidance_review.md must be byte-equal across two runs"
        )

    def test_audit_manifest_includes_guidance_hashes(self, sscp_run: Path) -> None:
        m = json.loads((sscp_run / "audit_manifest.json").read_text(encoding="utf-8"))
        assert "guidance_review.json" in m["artifact_hashes"]
        assert "guidance_review.md" in m["artifact_hashes"]
        assert m["artifact_counts"]["guidance_review_items"] == 10

    def test_guidance_json_no_forbidden_language(self, sscp_run: Path) -> None:
        js = (sscp_run / "guidance_review.json").read_text(encoding="utf-8").lower()
        offenders = [term for term in _FORBIDDEN_FOR_GUIDANCE_OUTPUT if term in js]
        assert not offenders, f"forbidden language in guidance JSON: {offenders}"

    def test_guidance_md_no_forbidden_language(self, sscp_run: Path) -> None:
        md = (sscp_run / "guidance_review.md").read_text(encoding="utf-8").lower()
        offenders = [term for term in _FORBIDDEN_FOR_GUIDANCE_OUTPUT if term in md]
        assert not offenders, f"forbidden language in guidance MD: {offenders}"


class TestCliSummaryIntegration:
    def test_cli_emits_guidance_suffix_on_sscp(self, tmp_path: Path) -> None:
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "locuslab.cli",
                "verify",
                str(SYNTHETIC_SSCP_DOSSIER),
                "--out",
                str(tmp_path),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0, result.stderr
        assert "guidance review written" in result.stdout

    def test_cli_omits_guidance_suffix_on_non_sscp(self, tmp_path: Path) -> None:
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "locuslab.cli",
                "verify",
                str(DEMO_DOSSIER),
                "--out",
                str(tmp_path),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0, result.stderr
        assert "guidance review written" not in result.stdout


class TestVerifyResultShape:
    def test_n_guidance_review_items_none_for_non_sscp(self, tmp_path: Path) -> None:
        result = verify_dossier(dossier_dir=DEMO_DOSSIER, output_dir=tmp_path)
        assert result.n_guidance_review_items is None

    def test_n_guidance_review_items_is_ten_for_sscp(self, tmp_path: Path) -> None:
        result = verify_dossier(
            dossier_dir=SYNTHETIC_SSCP_DOSSIER, output_dir=tmp_path
        )
        # 10 = rule count in the committed SSCP rule pack.
        assert result.n_guidance_review_items == 10
