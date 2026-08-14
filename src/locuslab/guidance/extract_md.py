"""Phase 6E-prep-A — PDF-to-Markdown extractor using pdfplumber (optional dep).

The ``pdfplumber`` import is deferred to the function body so that
``import locuslab.guidance.extract_md`` succeeds without ``pdfplumber``
installed. Only calling ``extract_md()`` will fail when the dependency is
absent.

DO NOT add a module-level ``import pdfplumber`` here.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# Renderer version; bump when the rendering algorithm changes.
# 0.1.0 — initial pdfplumber-based extractor.
# 0.2.0 — Phase 6E-prep-A1 cleanups: running-header strip, page-footer strip,
#         TOC-line skip, table-region exclusion from char extraction.
_RENDERER_VERSION = "locuslab-renderer:0.2.0"

# ---------------------------------------------------------------------------
# Font-size clustering thresholds for heading detection.
#
# Strategy: collect all font sizes from pdfplumber chars, sort descending,
# then map the top-3 distinct size bands to H1/H2/H3.
#
# Cutoff: only font sizes ≥ HEADING_MIN_FONTSIZE are considered heading
# candidates. Body text is typically ~10-11pt; headings in MDCG 2019-9
# start at ~12pt.
#
# AGPL-deny: do NOT add pymupdf, pymupdf4llm, marker, or docling imports.
# They are AGPL-licensed and would be incompatible with Apache-2.0 distribution of this project.
# ---------------------------------------------------------------------------
_HEADING_MIN_FONTSIZE: float = 11.5

# Fraction of pages on which a line must appear to be classified as a running
# header/footer and stripped. 0.8 = appears on ≥ 80% of pages.
_RUNNING_LINE_THRESHOLD: float = 0.8

# Number of top/bottom lines per page to consider as header/footer candidates.
_RUNNING_LINE_WINDOW: int = 3

# Page-number footer pattern: e.g. "1(24)", "12( 24 )". Matches the entire line
# (after strip). Used to discard footer lines that the running-line detector
# would miss (their text varies per page).
_PAGE_FOOTER_RE = re.compile(r"^\s*\d+\s*\(\s*\d+\s*\)\s*$")

# TOC line pattern: text followed by leader dots and a page number at end.
# Example: "Introduction............................ 4"
# Conservative: requires ≥ 5 consecutive dots to avoid false positives on
# decimal lists or ellipses.
_TOC_LINE_RE = re.compile(r"\.{5,}\s*\d+\s*$")


@dataclass(frozen=True)
class ExtractedMarkdown:
    """Result of PDF-to-Markdown extraction."""

    markdown_text: str
    page_anchors: list[int]
    normalization_applied: list[str]
    limitations: list[str]


def extract_md(
    pdf_path: Path,
    *,
    parser_version: str,
) -> ExtractedMarkdown:
    """Extract structured Markdown from a guidance PDF.

    Import of ``pdfplumber`` is deferred to this function body.
    Raises ``RuntimeError`` with install instructions if missing.
    Deterministic: same PDF produces byte-equal output across runs.

    Args:
        pdf_path: Path to the PDF file to extract.
        parser_version: Caller-supplied version string used in the frontmatter
            (e.g. ``"pdfplumber:0.11.x+locuslab-renderer:0.1.0"``).

    Returns:
        ``ExtractedMarkdown`` with ``markdown_text``, ``page_anchors``,
        ``normalization_applied``, and ``limitations``.
    """
    try:
        import pdfplumber  # noqa: PLC0415  # type: ignore[import-untyped]
    except ImportError as exc:
        raise RuntimeError(
            "pdfplumber is not installed. "
            'Install with: pip install -e ".[guidance-extract]"'
        ) from exc

    return _do_extract(pdf_path, pdfplumber=pdfplumber, parser_version=parser_version)


# ---------------------------------------------------------------------------
# Internal extraction logic (separated to keep the public API surface minimal)
# ---------------------------------------------------------------------------


def _normalise_text(text: str) -> tuple[str, list[str]]:
    """Apply deterministic text normalizations; return (normalised, applied)."""
    applied: list[str] = []
    original = text

    # Smart quotes → ASCII
    for smart, ascii_eq in [
        ("“", '"'),
        ("”", '"'),
        ("‘", "'"),
        ("’", "'"),
        ("‚", "'"),
        ("‛", "'"),
    ]:
        if smart in text:
            text = text.replace(smart, ascii_eq)
    if text != original:
        applied.append("smart_quotes_to_ascii")
        original = text

    # Ligatures
    lig_map = {"ﬁ": "fi", "ﬂ": "fl", "ﬀ": "ff"}
    for lig, repl in lig_map.items():
        if lig in text:
            text = text.replace(lig, repl)
    if text != original:
        applied.append("ligatures_expanded")
        original = text

    # Non-breaking hyphens and dashes → ASCII hyphen
    for dash in ["‐", "‑", "–"]:
        if dash in text:
            text = text.replace(dash, "-")
    if text != original:
        applied.append("nb_hyphens_to_ascii")
        original = text

    # Double-space runs collapsed
    no_dbl = re.sub(r" {2,}", " ", text)
    if no_dbl != text:
        text = no_dbl
        applied.append("double_spaces_collapsed")
        original = text

    # Space before punctuation removed
    sp_punct = re.sub(r" ([,;:!?.])", r"\1", text)
    if sp_punct != text:
        text = sp_punct
        applied.append("space_before_punctuation_removed")

    return text, list(dict.fromkeys(applied))  # preserve order, deduplicate


def _cluster_heading_sizes(all_sizes: list[float]) -> dict[float, int]:
    """Map font sizes to heading levels 1-3 using top-3 distinct bands.

    Returns a dict: size → heading_level (1, 2, or 3).
    Sizes below ``_HEADING_MIN_FONTSIZE`` are excluded from consideration.
    """
    candidates = [s for s in all_sizes if s >= _HEADING_MIN_FONTSIZE]
    # Deduplicate and round to 1 decimal to merge near-equal sizes
    rounded: set[float] = set()
    for s in candidates:
        rounded.add(round(s, 1))
    top3 = sorted(rounded, reverse=True)[:3]
    return {size: level + 1 for level, size in enumerate(top3)}


def _extract_page_chars(page: Any) -> list[dict[str, Any]]:
    """Return char dicts from a pdfplumber page, sorted top-to-bottom, left-to-right."""
    chars: list[dict[str, Any]] = getattr(page, "chars", []) or []
    return sorted(
        chars,
        key=lambda c: (round(float(c.get("top", 0)), 1), float(c.get("x0", 0))),
    )


def _chars_to_lines(chars: list[dict[str, Any]]) -> list[tuple[float, float, str]]:
    """Group chars by y-position into (y_top, avg_fontsize, line_text) tuples.

    Returns list sorted by y_top (top of page = smallest value).
    """
    if not chars:
        return []

    lines: list[tuple[float, float, str]] = []
    current_y: float = round(float(chars[0].get("top", 0)), 1)
    current_chars: list[dict[str, Any]] = []

    for ch in chars:
        y = round(float(ch.get("top", 0)), 1)
        if abs(y - current_y) <= 2.0:
            current_chars.append(ch)
        else:
            if current_chars:
                sizes = [
                    float(c.get("size", 0) or c.get("fontsize", 0))
                    for c in current_chars
                ]
                avg_size = sum(sizes) / len(sizes) if sizes else 0.0
                text = "".join(str(c.get("text", "")) for c in current_chars)
                lines.append((current_y, avg_size, text))
            current_y = y
            current_chars = [ch]

    if current_chars:
        sizes = [
            float(c.get("size", 0) or c.get("fontsize", 0)) for c in current_chars
        ]
        avg_size = sum(sizes) / len(sizes) if sizes else 0.0
        text = "".join(str(c.get("text", "")) for c in current_chars)
        lines.append((current_y, avg_size, text))

    return lines


def _table_to_gfm(table: list[Any]) -> str | None:
    """Convert a pdfplumber table to GFM pipe-table.

    Returns None (with a limitation comment) on empty or malformed tables.
    """
    if not table or not table[0]:
        return None
    # Normalize cells: convert each cell to a str, handling None
    rows: list[list[str]] = [
        [str(cell or "").strip() for cell in row] for row in table
    ]

    if not rows:
        return None

    header = rows[0]
    n_cols = len(header)
    output_lines: list[str] = []
    output_lines.append("| " + " | ".join(header) + " |")
    output_lines.append("| " + " | ".join(["---"] * n_cols) + " |")
    for row in rows[1:]:
        # Pad or truncate to n_cols
        padded: list[str] = (row + [""] * n_cols)[:n_cols]
        output_lines.append("| " + " | ".join(padded) + " |")
    return "\n".join(output_lines)


def _get_table_bboxes(page: Any) -> list[tuple[float, float, float, float]]:
    """Return list of table bboxes (x0, top, x1, bottom) on a pdfplumber page.

    Used to exclude chars within table regions from the flowed-text extraction,
    avoiding the "table content appears twice" artifact (once as text, once
    as a GFM pipe-table).
    """
    try:
        tables = page.find_tables() or []
    except Exception:
        return []
    bboxes: list[tuple[float, float, float, float]] = []
    for tbl in tables:
        bbox = getattr(tbl, "bbox", None)
        if bbox and len(bbox) >= 4:
            x0, top, x1, bottom = (float(v) for v in bbox[:4])
            bboxes.append((x0, top, x1, bottom))
    return bboxes


def _is_char_in_bbox(
    char: dict[str, Any], bboxes: list[tuple[float, float, float, float]]
) -> bool:
    """True if the char's center point falls inside any of the given bboxes."""
    if not bboxes:
        return False
    cx = (float(char.get("x0", 0)) + float(char.get("x1", 0))) / 2.0
    cy = (float(char.get("top", 0)) + float(char.get("bottom", 0))) / 2.0
    return any(
        x0 <= cx <= x1 and top <= cy <= bottom for x0, top, x1, bottom in bboxes
    )


@dataclass(frozen=False)
class _PageData:
    """Per-page accumulator used between pass-1 (collect) and pass-2 (render)."""

    page_num: int
    # (y_top, avg_size, text) tuples for non-table flowed text.
    lines: list[tuple[float, float, str]] = field(default_factory=list)
    # Top-N and bottom-N line texts for running-header/footer detection.
    top_lines: list[str] = field(default_factory=list)
    bot_lines: list[str] = field(default_factory=list)
    # Pre-rendered GFM table strings (or limitation comments).
    tables_md: list[str] = field(default_factory=list)
    # True if no chars were extracted at all (likely image-only page).
    is_empty: bool = False


def _detect_running_lines(
    pages: list[_PageData], threshold: float
) -> tuple[set[str], set[str]]:
    """Return (headers, footers): line texts that recur on ≥ threshold of pages.

    Each set holds the *stripped, normalized* text of lines that pdfplumber
    extracted at the top (resp. bottom) of ≥ threshold fraction of pages.
    """
    n_pages = len(pages)
    if n_pages < 3:
        # With <3 pages, repetition is not a reliable signal.
        return set(), set()

    top_counter: dict[str, int] = {}
    bot_counter: dict[str, int] = {}
    for pd in pages:
        for t in pd.top_lines:
            top_counter[t] = top_counter.get(t, 0) + 1
        for t in pd.bot_lines:
            bot_counter[t] = bot_counter.get(t, 0) + 1

    min_count = max(2, int(threshold * n_pages))
    headers = {t for t, c in top_counter.items() if c >= min_count}
    footers = {t for t, c in bot_counter.items() if c >= min_count}
    return headers, footers


def _do_extract(
    pdf_path: Path,
    *,
    pdfplumber: Any,
    parser_version: str,
) -> ExtractedMarkdown:
    """Core extraction logic (pdfplumber already imported by caller).

    Single pdfplumber.open pass that accumulates per-page data into
    ``_PageData`` records. After the pass, global heading clustering and
    running-header detection both operate on the accumulated data, so
    table-region exclusion, header/footer stripping, page-number footer
    stripping, and TOC-line skipping all apply during the markdown
    assembly step.
    """
    all_normalizations: list[str] = []
    all_limitations: list[str] = []
    page_anchors: list[int] = []
    page_data: list[_PageData] = []
    all_sizes: list[float] = []

    # ------------------------------------------------------------------
    # Pass 1: open PDF once, collect everything we need per page.
    # ------------------------------------------------------------------
    with pdfplumber.open(str(pdf_path)) as pdf:
        for page_num, page in enumerate(pdf.pages, start=1):
            pd = _PageData(page_num=page_num)
            page_anchors.append(page_num)

            # Tables: extract first, then use their bboxes to filter chars below.
            table_bboxes = _get_table_bboxes(page)
            try:
                raw_tables = page.extract_tables() or []
                for tbl in raw_tables:
                    gfm = _table_to_gfm(tbl)
                    if gfm:
                        pd.tables_md.append(gfm)
                    else:
                        pd.tables_md.append(
                            "<!-- table extraction limited: empty or malformed table -->"
                        )
            except Exception as exc:
                pd.tables_md.append(f"<!-- table extraction limited: {exc} -->")
                all_limitations.append(
                    f"page {page_num}: table extraction failed: {exc}"
                )

            # Chars: extract, filter out those inside table bboxes, group into lines.
            all_chars = _extract_page_chars(page)
            if not all_chars:
                pd.is_empty = True
                all_limitations.append(
                    f"page {page_num}: no text chars extracted (possible image-only page)"
                )
                page_data.append(pd)
                continue

            non_table_chars = [
                c for c in all_chars if not _is_char_in_bbox(c, table_bboxes)
            ]

            # Accumulate font sizes from non-table chars for global heading clustering.
            for ch in non_table_chars:
                sz = float(ch.get("size", 0) or ch.get("fontsize", 0))
                if sz > 0:
                    all_sizes.append(sz)

            pd.lines = _chars_to_lines(non_table_chars)

            # Top/bottom windows for running-line detection (stripped text only).
            stripped_lines = [(_l[2].strip()) for _l in pd.lines if _l[2].strip()]
            pd.top_lines = stripped_lines[:_RUNNING_LINE_WINDOW]
            pd.bot_lines = stripped_lines[-_RUNNING_LINE_WINDOW:]

            page_data.append(pd)

    # ------------------------------------------------------------------
    # Pass 2: compute globals from accumulated data.
    # ------------------------------------------------------------------
    heading_map = _cluster_heading_sizes(all_sizes)
    running_headers, running_footers = _detect_running_lines(
        page_data, _RUNNING_LINE_THRESHOLD
    )
    if running_headers:
        all_normalizations.append("running_headers_stripped")
    if running_footers:
        all_normalizations.append("running_footers_stripped")

    # ------------------------------------------------------------------
    # Pass 3: assemble markdown from accumulated data + globals.
    # No pdfplumber calls; pure transformation.
    # ------------------------------------------------------------------
    md_parts: list[str] = []
    saw_page_footer = False
    saw_toc_line = False

    for pd in page_data:
        md_parts.append(f"\n<!-- page={pd.page_num} -->\n")
        if pd.is_empty:
            continue

        prev_was_heading = False
        for _y, avg_size, raw_text in pd.lines:
            text = raw_text.strip()
            if not text:
                continue

            # Skip running headers/footers (recurring boilerplate).
            if text in running_headers or text in running_footers:
                continue

            # Skip page-number footers like "1(24)".
            if _PAGE_FOOTER_RE.match(text):
                saw_page_footer = True
                continue

            # Skip TOC lines with leader dots.
            if _TOC_LINE_RE.search(text):
                saw_toc_line = True
                continue

            normalised, norms = _normalise_text(text)
            for n in norms:
                if n not in all_normalizations:
                    all_normalizations.append(n)
            text = normalised

            rounded_size = round(avg_size, 1)
            heading_level = heading_map.get(rounded_size)

            if heading_level is not None:
                prefix = "#" * heading_level
                md_parts.append(f"\n{prefix} {text}\n")
                prev_was_heading = True
            else:
                if prev_was_heading:
                    md_parts.append("\n")
                md_parts.append(text + "\n")
                prev_was_heading = False

        for tbl_md in pd.tables_md:
            md_parts.append(f"\n{tbl_md}\n")

    if saw_page_footer:
        all_normalizations.append("page_number_footers_stripped")
    if saw_toc_line:
        all_normalizations.append("toc_lines_skipped")

    markdown_text = "".join(md_parts)
    # Collapse 3+ consecutive blank lines to 2.
    markdown_text = re.sub(r"\n{4,}", "\n\n\n", markdown_text)

    return ExtractedMarkdown(
        markdown_text=markdown_text,
        page_anchors=page_anchors,
        normalization_applied=sorted(set(all_normalizations)),
        limitations=all_limitations,
    )
