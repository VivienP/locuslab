"""Content-based SSCP router fallback (offline)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
_SRC = REPO_ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from locuslab.ingest.loader import (  # noqa: E402
    _refine_kind_from_content,
    load_dossier,
)
from locuslab.models import (  # noqa: E402
    Document,
    DocumentKind,
    Span,
    SpanLocation,
    SpanLocationKind,
)
from locuslab.pipeline import verify_dossier  # noqa: E402

DEMO_DOSSIER = REPO_ROOT / "fixtures" / "demo_dossier"
SYNTHETIC_SSCP_BY_FILENAME = (
    REPO_ROOT / "tests" / "fixtures" / "sscp_synthetic" / "by_filename"
)
SYNTHETIC_SSCP_BY_CONTENT = (
    REPO_ROOT / "tests" / "fixtures" / "sscp_synthetic" / "by_content"
)


def _make_doc(kind: DocumentKind, doc_id: str = "doc_test", path: str = "test.pdf") -> Document:
    return Document(
        document_id=doc_id,
        kind=kind,
        path=path,
        sha256="0" * 64,
        parser="test",
    )


def _make_span(text: str, doc_id: str = "doc_test", span_id: str = "span_0") -> Span:
    return Span(
        span_id=span_id,
        document_id=doc_id,
        location=SpanLocation(kind=SpanLocationKind.PARAGRAPH, index=0),
        text=text,
    )


class TestRefinementUnit:
    def test_other_with_sscp_title_reclassifies_to_sscp(self) -> None:
        doc = _make_doc(DocumentKind.OTHER, doc_id="doc_a")
        spans = [_make_span("Summary of Safety and Clinical Performance", doc_id="doc_a")]
        refined = _refine_kind_from_content(doc, spans)
        assert refined.kind == DocumentKind.SSCP

    def test_other_without_marker_stays_other(self) -> None:
        doc = _make_doc(DocumentKind.OTHER, doc_id="doc_b")
        spans = [_make_span("This is a Certificate of Acceptance.", doc_id="doc_b")]
        refined = _refine_kind_from_content(doc, spans)
        assert refined.kind == DocumentKind.OTHER

    def test_marker_is_case_insensitive(self) -> None:
        doc = _make_doc(DocumentKind.OTHER, doc_id="doc_c")
        spans = [_make_span("SUMMARY OF SAFETY AND CLINICAL PERFORMANCE", doc_id="doc_c")]
        refined = _refine_kind_from_content(doc, spans)
        assert refined.kind == DocumentKind.SSCP

    def test_existing_cer_kind_not_overridden_even_with_marker(self) -> None:
        """Refinement must not touch documents already classified by filename."""
        doc = _make_doc(DocumentKind.CER, doc_id="doc_cer")
        spans = [_make_span("Summary of Safety and Clinical Performance", doc_id="doc_cer")]
        refined = _refine_kind_from_content(doc, spans)
        assert refined.kind == DocumentKind.CER

    def test_marker_deep_in_body_not_reclassified(self) -> None:
        """The scan is bounded to the first 5 spans to avoid mis-classifying
        a CER body that references an SSCP in a later paragraph."""
        doc = _make_doc(DocumentKind.OTHER, doc_id="doc_deep")
        spans = [
            _make_span(f"Boilerplate paragraph {i}.", doc_id="doc_deep", span_id=f"span_{i}")
            for i in range(10)
        ]
        spans.append(_make_span(
            "Summary of Safety and Clinical Performance",
            doc_id="doc_deep",
            span_id="span_late",
        ))
        refined = _refine_kind_from_content(doc, spans)
        assert refined.kind == DocumentKind.OTHER, (
            "Marker appearing after the scan limit must not trigger reclassification"
        )

    def test_refinement_only_considers_spans_for_current_document(self) -> None:
        """Spans belonging to a different document_id must not influence
        the refinement of this document."""
        doc = _make_doc(DocumentKind.OTHER, doc_id="doc_target")
        # Marker exists, but on a span belonging to a different document.
        spans = [
            _make_span(
                "Summary of Safety and Clinical Performance",
                doc_id="doc_other",
                span_id="span_other",
            ),
            _make_span("Plain content for the target doc", doc_id="doc_target"),
        ]
        refined = _refine_kind_from_content(doc, spans)
        assert refined.kind == DocumentKind.OTHER


class TestContentBasedSscpFixture:
    def test_content_marker_file_classifies_as_sscp(self) -> None:
        result = load_dossier(SYNTHETIC_SSCP_BY_CONTENT)
        kinds = {doc.path: doc.kind for doc in result.documents}
        assert any(kind == DocumentKind.SSCP for kind in kinds.values()), (
            f"Filename without sscp token should classify as SSCP after "
            f"content-based refinement; got {kinds}"
        )

    def test_content_marker_verify_emits_guidance_review(self, tmp_path: Path) -> None:
        result = verify_dossier(
            dossier_dir=SYNTHETIC_SSCP_BY_CONTENT, output_dir=tmp_path
        )
        # 10 = rule count in the committed SSCP rule pack.
        assert result.n_guidance_review_items == 10, (
            "Content-routed synthetic SSCP should emit a 10-item guidance review"
        )
        assert (tmp_path / "guidance_review.json").is_file()
        assert (tmp_path / "guidance_review.md").is_file()
        manifest = json.loads(
            (tmp_path / "audit_manifest.json").read_text(encoding="utf-8")
        )
        assert "guidance_review.json" in manifest["artifact_hashes"]
        assert manifest["artifact_counts"]["guidance_review_items"] == 10


class TestFilenameSscpFixture:
    def test_filename_sscp_kind_is_sscp(self) -> None:
        result = load_dossier(SYNTHETIC_SSCP_BY_FILENAME)
        kinds = [doc.kind for doc in result.documents]
        assert DocumentKind.SSCP in kinds


class TestDemoDossierUnchanged:
    def test_demo_dossier_has_no_sscp_after_refinement(self) -> None:
        result = load_dossier(DEMO_DOSSIER)
        kinds = [doc.kind for doc in result.documents]
        assert DocumentKind.SSCP not in kinds, (
            "Demo dossier has no SSCP file and no SSCP-titled content; "
            "refinement must not introduce a false positive"
        )

    def test_demo_verify_still_no_guidance(self, tmp_path: Path) -> None:
        result = verify_dossier(dossier_dir=DEMO_DOSSIER, output_dir=tmp_path)
        assert result.n_guidance_review_items is None
        assert not (tmp_path / "guidance_review.json").exists()
