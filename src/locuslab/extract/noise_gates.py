"""Content-based noise gates for P1 failure modes.

Implements two gates confirmed across three dogfood runs on 2026-05-23:

  FM-PHASE2-2  SSCP repeated PDF header/chrome contamination.
               Strip the running page header from the working text before
               keyword matching.  span.text is never mutated.

  FM-IFU-2     IFU foreshortening table percentage suppression.
               Detect foreshortening table context and skip
               PERCENTAGE_DECIMAL matching for that span.

Design constraints (Option B — strip-then-extract):
- Do NOT mutate Span.text.
- Do NOT change span_id or document_id on emitted claims.
- No DocumentKind.IFU — gates operate on span text content only.
- No network calls.
"""

from __future__ import annotations

import re

# ---------------------------------------------------------------------------
# FM-PHASE2-2 helpers
# ---------------------------------------------------------------------------

# RAUMEDIC German running header:
#   "Titel: Summary of Safety and Clinical Performance \n \n \n
#    VA_RM_00124_FB_05  4.0 \n
#    Seite 7 von 41 \n"
_RAUMEDIC_PAGE_HEADER: re.Pattern[str] = re.compile(
    r"^Titel:[^\n]*\n"
    r"(?:[^\n]*\n){0,4}"
    r"Seite\s+\d+\s+von\s+\d+\s*\n",
    re.IGNORECASE,
)

# NuMED (and similar) English SSCP running header:
#   "NuMED \n
#    Summary of Safety and Clinical Performance \n
#    SSCP – Stents – CoA & RVOT \n
#    FCD-1137  Rev 02  Page 12 of 45 \n"
_SSCP_PAGE_HEADER: re.Pattern[str] = re.compile(
    r"^[^\n]{0,80}\n"               # optional manufacturer/brand line
    r"[^\n]*(?:Summary\s+of\s+Safety|SSCP)[^\n]*\n"  # SSCP title line
    r"[^\n]+\n"                     # doc-ref / subtitle line
    r"[^\n]*\bPage\s+\d+\s+of\s+\d+[^\n]*\n",  # page marker line
    re.IGNORECASE,
)

# SSCP standard boilerplate intro sentence that appears on the "About this SSCP"
# page.  Keyword matches whose context window contains this phrase are not
# evidence claims — they are the SSCP template description of itself.
_SSCP_BOILERPLATE_MARKERS: re.Pattern[str] = re.compile(
    r"intended\s+to\s+provide\s+public\s+access"
    r"|main\s+aspects\s+of\s+the\s+safety\s+and\s+clinical\s+performance",
    re.IGNORECASE,
)


# Supplementary CP keywords that apply ONLY when `strip_sscp_page_header` has
# actually removed a recognized header prefix from the span text.  These are NOT
# in the global `CLINICAL_PERFORMANCE_KEYWORDS` set on purpose — they expand
# recall only in the narrow case where an SSCP page contained "Performance" in
# the header (matched by the global set) and the same page's body contains an
# outcome/incidence row that should still emit a claim after the header is
# stripped.
POST_HEADER_STRIP_CP_KEYWORDS: re.Pattern[str] = re.compile(
    r"\b(?:outcome|incidence)\b",
    re.IGNORECASE,
)


def strip_sscp_page_header(text: str) -> str:
    """Return *text* with any SSCP/RAUMEDIC running page header prefix removed.

    The stripped prefix is the shortest match at the very start of the text.
    If no recognized header pattern is found, the original text is returned
    unchanged.  span.text is never mutated — callers must use the returned
    value for keyword matching only.
    """
    m = _RAUMEDIC_PAGE_HEADER.match(text)
    if m:
        return text[m.end():]
    m = _SSCP_PAGE_HEADER.match(text)
    if m:
        return text[m.end():]
    return text


def is_sscp_boilerplate_cp_context(context_text: str) -> bool:
    """Return True when *context_text* is the SSCP standard intro paragraph.

    A keyword match whose surrounding context window contains the SSCP
    self-describing boilerplate ("intended to provide public access", "main
    aspects of the safety and clinical performance") is definitional, not an
    evidence claim.
    """
    return bool(_SSCP_BOILERPLATE_MARKERS.search(context_text))


# ---------------------------------------------------------------------------
# FM-IFU-2 helpers
# ---------------------------------------------------------------------------

# Markers that identify a foreshortening chart section in an IFU page span.
_FORESHORTENING_CHART_MARKER: re.Pattern[str] = re.compile(
    r"(?:Foreshortening\s+(?:Chart|Table)|Percentage\s+Shortening)",
    re.IGNORECASE,
)

# CP-stent model code (e.g. CP8Z16, CP10Z39, CP10Z60).
_CP_STENT_MODEL_CODE: re.Pattern[str] = re.compile(r"\bCP\d{1,2}Z\d{2,3}\b")


_PERCENTAGE_VALUE: re.Pattern[str] = re.compile(r"\b\d+[.,]\d+\s*%")


def is_foreshortening_table_span(text: str) -> bool:
    """Return True when *text* belongs to an IFU foreshortening chart span.

    Detection uses span text content only — no span.location.kind check and
    no DocumentKind.IFU dependency (neither exists in V1 or is added by P1).

    Detection paths (any one sufficient):
    1. "Foreshortening Chart" or "Foreshortening Table" appears in the text.
    2. "Percentage Shortening" appears AND at least one CP-stent model code is present.
    3. Two or more CP-stent model codes appear AND non_empty_lines >= 4 AND
       percentage_count >= 2. Both structural co-signals must be satisfied
       together (AND, not OR). Branch 3 is required to suppress translated
       foreshortening tables (e.g., FR "Tableau des raccourcissements", IT
       "Tabella accorciamento", DE "Verkürzungstabelle") which lack the English
       markers, while NOT suppressing clinical narrative sentences that
       incidentally mention two CP product codes.

    Branch 3 co-signal rationale: translated foreshortening tables have many rows
    (typically 10+ non-blank lines) and many percentage cells (typically 20+
    values). A clinical narrative sentence mentioning two CP codes is typically
    1-3 lines with at most one dot-decimal percentage. Requiring BOTH co-signals
    (AND semantics) prevents false suppression of a narrative that satisfies only
    one signal (e.g., a 4-line paragraph with one percentage, or a 1-line sentence
    with two percentages). The co-signal uses language-neutral structural features
    only — no locale-specific phrases.
    """
    if re.search(r"Foreshortening\s+(?:Chart|Table)", text, re.IGNORECASE):
        return True
    cp_codes = _CP_STENT_MODEL_CODE.findall(text)
    if re.search(r"Percentage\s+Shortening", text, re.IGNORECASE) and len(cp_codes) >= 1:
        return True
    if len(cp_codes) >= 2:
        non_empty_lines = sum(1 for ln in text.splitlines() if ln.strip())
        percentage_count = len(_PERCENTAGE_VALUE.findall(text))
        if non_empty_lines >= 4 and percentage_count >= 2:
            return True
    return False
