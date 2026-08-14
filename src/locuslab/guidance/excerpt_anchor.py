"""Phase 6E - Locate a rule pack `exact_excerpt` inside a derived .md source.

The rule pack stores excerpts produced by the Phase 6C pypdf extractor with
aggressive normalization (line breaks removed, footnote refs stripped). The
derived .md is produced by the Phase 6E-prep-A pdfplumber renderer which
preserves PDF line breaks and footnote markers. The two diverge on
whitespace and footnote positioning even though the substantive text is
identical.

`locate_excerpt` performs a whitespace-and-footnote-tolerant search and
returns a `SourceAnchor` with the matching position in the .md, the nearest
preceding `<!-- page=N -->` HTML comment, and a short preview.

No LLM, no network, no embedding. Pure Python regex + substring.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_PAGE_MARKER_RE = re.compile(r"<!--\s*page\s*=\s*(\d+)\s*-->")
# Drop footnote markers like "single\n52identification" (newline + digits
# adjacent to letters). Standalone digit-only lines are not touched.
_FOOTNOTE_RE = re.compile(r"\n\d+(?=[A-Za-z])")
_WS_RE = re.compile(r"\s+")
_PREVIEW_CHARS = 240


@dataclass(frozen=True)
class SourceAnchor:
    """Where a rule's exact_excerpt was located within a derived .md."""

    md_path: str
    """Repo-relative or absolute path of the .md the excerpt was found in."""

    char_offset: int
    """Byte/character offset of the match start in the original .md text."""

    line_number: int
    """1-indexed line number in the original .md."""

    page_anchor: int | None
    """Page number from the nearest preceding `<!-- page=N -->` marker, or None."""

    preview: str
    """Up to 240 chars of the original .md content starting at the match."""

    matched_via: str
    """How the match was achieved: `verbatim` or `whitespace_normalised`."""


def _normalise(text: str) -> str:
    """Collapse newlines/footnote refs/whitespace for tolerant matching.

    - Footnote markers `\\nNN<letter>` (e.g. `single\\n52identification`)
      become `\\n<letter>`.
    - Curly apostrophes/quotes are mapped to ASCII.
    - All whitespace runs collapse to a single space.

    USED FOR MATCHING ONLY. `_normalise_for_walk` is the length-preserving
    sibling used for back-mapping from a normalised position to the
    original text's char offset.
    """
    cleaned = text.replace("’", "'").replace("‘", "'")
    cleaned = cleaned.replace("“", '"').replace("”", '"')
    cleaned = _FOOTNOTE_RE.sub("\n", cleaned)
    cleaned = _WS_RE.sub(" ", cleaned).strip()
    return cleaned


def _normalise_for_walk(text: str) -> str:
    """Length-preserving normalisation. Each output char at index i comes
    from the original at index i, OR replaces a stripped footnote-digit
    with a space at the same index.

    Invariant: the K-th non-whitespace character in `_normalise(text)` is
    the same physical character as the K-th non-whitespace character in
    `_normalise_for_walk(text)`. The latter has the same length as the
    original `text`, so the position of that K-th non-ws char in
    `_normalise_for_walk(text)` IS the position in the original.

    This is the back-mapping fix for the Phase 6E reviewer BLOCKING:
    walking the ORIGINAL text by non-ws count was wrong because the
    original contains footnote digit chars that the aggressively
    normalised text does not.
    """
    cleaned = text.replace("’", "'").replace("‘", "'")
    cleaned = cleaned.replace("“", '"').replace("”", '"')
    # Replace footnote markers with the SAME number of space chars so
    # output length equals original length and position correspondence
    # is preserved 1-to-1.
    cleaned = _FOOTNOTE_RE.sub(lambda m: " " * len(m.group(0)), cleaned)
    return cleaned


def _nearest_preceding_page(md_text: str, char_offset: int) -> int | None:
    """Walk back from char_offset in md_text and return the most recent
    `<!-- page=N -->` page number, or None when no marker precedes."""
    prefix = md_text[:char_offset]
    matches = list(_PAGE_MARKER_RE.finditer(prefix))
    if not matches:
        return None
    return int(matches[-1].group(1))


def locate_excerpt(
    excerpt: str, md_text: str, md_path: str
) -> SourceAnchor | None:
    """Return an anchor for `excerpt` inside `md_text`, or None on miss.

    Two-pass strategy:

    1. Verbatim substring match — fast path when the rule pack excerpt
       matches the .md content character-for-character.
    2. Whitespace + footnote-tolerant match — collapse both texts, then
       walk back to the original offset where the matched prefix starts.

    Pass 2 protects against pypdf excerpt vs pdfplumber Markdown renderer
    drift (whitespace and footnote markers).
    """
    if not excerpt or not md_text:
        return None

    # Pass 1: verbatim
    direct_pos = md_text.find(excerpt)
    if direct_pos >= 0:
        return SourceAnchor(
            md_path=md_path,
            char_offset=direct_pos,
            line_number=md_text.count("\n", 0, direct_pos) + 1,
            page_anchor=_nearest_preceding_page(md_text, direct_pos),
            preview=md_text[direct_pos : direct_pos + _PREVIEW_CHARS],
            matched_via="verbatim",
        )

    # Pass 2: whitespace-normalised. Try the FULL normalised excerpt first
    # — finds the substantive body occurrence over a TOC echo when the
    # excerpt is long enough to disambiguate (the rule pack ships clauses,
    # not headings, so this lands on §body not §TOC). Fall back to the
    # first 4 words when the full excerpt cannot be located (typically a
    # multi-paragraph excerpt with structural line breaks the renderer
    # could not heal).
    excerpt_normalised = _normalise(excerpt)
    excerpt_words = excerpt_normalised.split(" ")
    if len(excerpt_words) < 2:
        return None
    md_normalised = _normalise(md_text)
    norm_pos = md_normalised.find(excerpt_normalised)
    if norm_pos < 0:
        head_query_normalised = " ".join(excerpt_words[:4])
        norm_pos = md_normalised.find(head_query_normalised)
    if norm_pos < 0:
        return None

    # Map back from normalised position to the original text by counting
    # non-whitespace characters. The K-th non-ws char in `md_normalised`
    # is the same K-th non-ws char in `md_walk` (length-preserving),
    # whose char positions are 1-to-1 with the original `md_text`.
    head_non_ws_count = sum(1 for c in md_normalised[:norm_pos] if not c.isspace())
    md_walk = _normalise_for_walk(md_text)
    counter = 0
    original_pos: int | None = None
    for i, char in enumerate(md_walk):
        if not char.isspace():
            if counter == head_non_ws_count:
                original_pos = i
                break
            counter += 1
    if original_pos is None:
        # Invariant violated: matched substring exists in md_normalised
        # but the K-th non-ws char cannot be located in the length-
        # preserving walk. Surface as a miss rather than a misleading
        # anchor at len(md_text). Phase 6E reviewer W-2.
        return None

    return SourceAnchor(
        md_path=md_path,
        char_offset=original_pos,
        line_number=md_text.count("\n", 0, original_pos) + 1,
        page_anchor=_nearest_preceding_page(md_text, original_pos),
        preview=md_text[original_pos : original_pos + _PREVIEW_CHARS],
        matched_via="whitespace_normalised",
    )
