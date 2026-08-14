from locuslab.ingest import make_span_id
from locuslab.models import Span, SpanLocation, SpanLocationKind


def test_span_id_is_stable_for_same_document_location_and_text() -> None:
    location = SpanLocation(kind=SpanLocationKind.PARAGRAPH, index=3, label="Clinical data")

    first = make_span_id("doc_example", location, "The endpoint rate was 95%.")
    second = make_span_id("doc_example", location, "The endpoint rate was 95%.")

    assert first == second
    assert first.startswith("span_")


def test_span_preserves_structured_location() -> None:
    location = SpanLocation(kind=SpanLocationKind.TABLE_CELL, index=7, label="B12")
    span = Span(
        span_id=make_span_id("doc_example", location, "42/50"),
        document_id="doc_example",
        location=location,
        text="42/50",
        section="Performance table",
    )

    assert span.location.kind == SpanLocationKind.TABLE_CELL
    assert span.location.label == "B12"
    assert span.section == "Performance table"
