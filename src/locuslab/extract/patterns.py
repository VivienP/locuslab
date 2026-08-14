"""Compiled regex patterns and normalization helpers for claim and citation extractors."""

from __future__ import annotations

import re

# --- Citation patterns ---

# Matches: (Smith et al., 2023), (Smith et al. 2023), (Smith, 2023), (Smith and Jones, 2021)
# Does NOT match: (n=412), (95% CI: 82.1-91.6), (2023)
AUTHOR_YEAR_PAREN = re.compile(
    r"\("
    r"(?P<authors>[A-Z][a-z]+(?:\s+(?:et\s+al\.?|and\s+[A-Z][a-z]+))?)"
    r"(?:,?\s*)"
    r"(?P<year>(?:19|20)\d{2})"
    r"\)",
)

# Anchored at start/end of stripped cell text.
# Matches: "Smith 2023", "Smith et al. 2023", "Smith et al.\n2022\nn=200"
# Applied only to TABLE_CELL spans.
# Trailing group allows optional n= suffix (e.g. from pypdf table extraction)
# but does NOT allow arbitrary trailing content — it is restricted to whitespace
# followed by n=\d+ only.
AUTHOR_YEAR_TABLE = re.compile(
    r"^(?P<authors>[A-Z][a-z]+(?:\s+(?:et\s+al\.?|and\s+[A-Z][a-z]+))?)"
    r"\s+"
    r"(?P<year>(?:19|20)\d{2})"
    r"(?:\s+n=\d+)?"
    r"\s*$",
)

# Matches: [1], [12], [123]. Does NOT match: [1234].
BRACKETED_NUMERIC = re.compile(
    r"\[(?P<number>\d{1,3})\]",
)

# Proprietary REF-NNN reference marker, up to 4 digits.
# Matches: REF-001, REF-012, REF-1234. Does NOT match: REF-12345 or REFERENCE 1.
# Bibliography ENTRIES ("REF-001. Author...") are filtered upstream by
# is_bibliography_span; this pattern emits a citation mention only on
# non-bibliography spans.
REF_ID_NUMERIC = re.compile(r"REF-(?P<number>\d{1,4})\b")

# Numeric parenthetical footnote marker: (1) through (99).
# Must NOT match:
#   - year-only parens (2008) — 4 digits excluded by {1,2} limit
#   - (n=412) — letter prefix before digits excluded by negative lookbehind
#   - (95% CI: ...) — % or : inside parens excluded
#   - (8-zig stents), (53 kPa) — any letter inside parens excluded
#   - (NCT01278303) — NCT prefix (letters) before digits excluded
# Negative lookbehind: no letter or % immediately before the opening paren.
# Positive requirement: 1-2 digits with no other characters inside the parens.
CITATION_NUMERIC_PARENTHETICAL = re.compile(
    r"(?<![A-Za-z%])"
    r"\((?P<number>\d{1,2})\)"
    r"(?![A-Za-z%\d])",
)

# NCT clinical trial identifier: NCT followed by exactly 8 digits.
# Optional surrounding parentheses: both "(NCT01824160)" and "NCT01824160" match.
# The full NCT\d{8} string (not the digit suffix alone) is the marker_text.
CITATION_NCT_ID = re.compile(
    r"\(?(?P<nct_id>NCT\d{8})\)?",
)

# Named guideline reference: SOCIETY YEAR Guidelines
# Matches: "ACC/AHA 2008 Guidelines", "ESC 2021 Guidelines", etc.
# Requires the word "Guidelines" to gate against bare society/year pairs.
# Society abbreviation: 2-10 uppercase letters, optionally separated by "/" for composites.
# Year: standard 4-digit year (19xx or 20xx).
CITATION_NAMED_GUIDELINE = re.compile(
    r"(?P<society>[A-Z]{2,10}(?:/[A-Z]{2,10})*)"
    r"\s+"
    r"(?P<year>(?:19|20)\d{2})"
    r"\s+"
    r"[Gg]uidelines?\b",
)

# Composite bracketed citation: [2, 3] or [2, 3, 6].
# Requires at least one comma between digits.
# Each component is emitted as a separate numeric_bracketed mention.
CITATION_BRACKETED_COMPOSITE = re.compile(
    r"\[(?P<numbers>(?:\d{1,3}\s*,\s*)+\d{1,3})\]",
)

# --- Numeric claim patterns ---

# Percentage followed immediately by a parenthetical CI range:
# "87.4% (95% CI: 82.1-91.6)"
# Captured as a single compound numeric claim.
PERCENTAGE_WITH_CI = re.compile(
    r"(?<!\d)"
    r"(?P<pct>\d{1,3}\.\d+\s*%)"
    r"\s*"
    r"(?P<ci_paren>\((?:95|90|99)\s*%?\s*CI\s*[:\-]\s*[\d.,\s\-]+\))",
)

# Bare percentage using the % symbol (not "percent" word): 87.4%, 3.2%
# Used when PERCENTAGE_WITH_CI does not match the position.
# Does NOT match the "percent" spelled-out form; that is handled by _PERCENT_WORD.
PERCENTAGE_DECIMAL = re.compile(
    r"(?<!\d)"
    r"(?P<value>\d{1,3}\.\d+)"
    r"\s*%",
)

# "percent" spelled out, with optional surrounding context
PERCENTAGE_WORD = re.compile(
    r"(?<!\d)"
    r"(?P<value>\d{1,3}\.\d+)"
    r"\s+"
    r"percent",
)

# Count expressions: n=412
COUNT_N = re.compile(
    r"n\s*=\s*(?P<value>\d+)",
)

# 95% CI ranges (standalone): "95% CI: 82.1-91.6"
CI_RANGE = re.compile(
    r"(?P<ci>(?:95|90|99)\s*%?\s*CI\s*[:\-]\s*[\d.,\s\-]+)",
)

# Classification patterns -- MDR/IVDR-specific.
# Per docs/architecture.md "Engine Domain Discipline", these belong in an MDR
# rule pack and should move out of the shared patterns module when pharma
# classification claims (e.g. biomarker class, safety narrative grading) need
# their own patterns.
# Adjective slot tolerates 0-4 word-or-hyphen tokens between the class label
# and "medical device" (e.g. "Class IIb non-invasive active medical device").
# [ab]? rejects IIc which is not a valid MDR class.
CLASS_IIA = re.compile(
    r"Class\s+II[ab]?\s+(?:[\w-]+\s+){0,4}medical\s+device",
    re.IGNORECASE,
)
CLASS_III = re.compile(
    r"Class\s+III\s+(?:[\w-]+\s+){0,4}medical\s+device",
    re.IGNORECASE,
)
CLASS_I = re.compile(r"Class\s+I\b.*?\bmedical\s+device", re.IGNORECASE)

# --- P3 entity/classification patterns ---

# MR Conditional — two-word phrase, case-insensitive via alternation.
# Low collision risk; "MR conditional" is highly specific in MDR context.
MR_CONDITIONAL = re.compile(r"\bMR\s+[Cc]onditional\b")

# NB number — "NB" or "Notified Body" prefix within ≤25 chars of a 4-digit number.
# Inline pattern: prefix group is mandatory, handles \s+ (including newlines) and
# optional colon separator (e.g. "Notified Body: 0123").
NB_NUMBER_INLINE = re.compile(
    r"\b(?:NB|Notified\s+Body)"
    r"(?:[:\s]+(?:ID\s+)?(?:number\s+)?)?"
    r"(?P<nb_id>\d{4})\b",
    re.IGNORECASE,
)

# Basic UDI-DI — anchor: "Basic UDI-DI" or "EUDAMED" label must appear in span.
UDI_DI_LABEL = re.compile(r"\bBasic\s+UDI[-\s]DI\b|\bEUDAMED\b", re.IGNORECASE)

# Code: 10-14 digit numeric prefix immediately followed by alphanumeric suffix.
# Lookbehind prevents matching within longer digit runs or slash-separated codes.
BASIC_UDI_DI = re.compile(
    r"(?<![A-Za-z\d/])"
    r"(?P<code>\d{10,14}[A-Za-z][A-Za-z0-9]*)"
    r"\b",
)

# EMDN code — anchor: "EMDN" keyword must appear in span text.
EMDN_LABEL = re.compile(r"\bEMDN\b", re.IGNORECASE)

# Code: 1 uppercase letter immediately followed by 8-12 digits, no space.
# Lookbehind prevents matching within longer alpha-digit runs.
EMDN_CODE = re.compile(
    r"(?<![A-Za-z\d])"
    r"(?P<code>[A-Z]\d{8,12})"
    r"(?![A-Za-z\d])",
)

# Harmonized standards — standard-body prefix + numeric code.
# Prefix alternation ordered longest-first to avoid partial matches (EN ISO before EN).
#
# Code structure: one primary token (no spaces inside, allows /, :, -, .) optionally
# followed by a single space and a secondary token that MUST start with a digit or '<'.
# This two-token limit stops the match before prose title words (e.g. "Sterilization")
# which start with uppercase letters, not digits.
#
# Examples matched:
#   EN ISO 11135:2014         → body="EN ISO", code="11135:2014"
#   ISO 10993-1:2018/Amd 1:2021 → body="ISO", code="10993-1:2018/Amd 1:2021"
#   ASTM F 136-13             → body="ASTM", code="F 136-13"
#   USP-NF 2023 <71>          → body="USP-NF", code="2023 <71>"
#   IEC 60601-1:2005/AMD1:2012/AMD2:2020 → body="IEC", code="60601-1:2005/AMD1:2012/AMD2:2020"
#
# Code is validated in extractor: must contain at least one digit.
HARMONIZED_STANDARD = re.compile(
    r"\b"
    r"(?P<body>EN\s+ISO|USP-NF|ISO|IEC|ASTM|EN)"
    r"[ \t]+"
    r"(?P<code>"
    r"[A-Za-z0-9<][A-Za-z0-9\-.:/<>]*"  # primary token (no spaces)
    r"(?:[ \t]+[0-9<][A-Za-z0-9\-.:/<>]*)?"  # optional secondary token (digit or < start)
    r")",
    re.IGNORECASE,
)

# Clinical performance keywords.
CLINICAL_PERFORMANCE_KEYWORDS = re.compile(
    r"\b(?:primary\s+endpoint|response\s+rate|sensitivity|specificity|"
    r"clinical\s+performance|intended\s+use|intended\s+purpose|"
    r"primary\s+outcome|efficacy|effectiveness)\b",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Value-Unit patterns — Phase 2D
# ---------------------------------------------------------------------------

# Numeric literal allowing optional sign, integer or decimal, dot or comma decimal
# separator (handles FR locale: 2,0 W/kg).
_NUM = r"[+-]?\d+(?:[.,]\d+)?"

# Tier-1 unit vocabulary.  Tesla (T) is handled separately via VALUE_UNIT_TESLA
# with a tighter context guard (R-1).  Tier-2 units (mm, kPa, h) are deferred.
_UNITS_TIER1_STRICT = r"(?:mmHg|atm|gauss/cm|W/kg|°C|days?|years?)"

# Single value + unit: "400 mmHg", "2.0 W/kg", "2,0 W/kg", "25 °C"
# Lookbehind prevents matching when a letter/digit/slash immediately precedes the
# number (e.g. avoids matching "ISO10993" or "ASTM").
VALUE_UNIT_SINGLE = re.compile(
    rf"(?<![A-Za-z\d/])({_NUM})\s*({_UNITS_TIER1_STRICT})\b",
    re.IGNORECASE,
)

# Range: "-40 to +400 mmHg", "15°C to 25°C" (unit at end only).
VALUE_UNIT_RANGE = re.compile(
    rf"({_NUM})\s+to\s+({_NUM})\s*({_UNITS_TIER1_STRICT})\b",
    re.IGNORECASE,
)

# Mean ± SD: "24 ± 26 mmHg", "-1 ± 15 mmHg".
VALUE_UNIT_MEAN_SD = re.compile(
    rf"({_NUM})\s*[±]\s*({_NUM})\s*({_UNITS_TIER1_STRICT})\b",
    re.IGNORECASE,
)

# Threshold operator (Unicode or ASCII): "≥ 12 years", "< 2 °C".
_THRESHOLD_OP = r"(?:≥|≤|>=|<=|>|<)"
VALUE_UNIT_THRESHOLD = re.compile(
    rf"({_THRESHOLD_OP})\s*({_NUM})\s*({_UNITS_TIER1_STRICT})\b",
    re.IGNORECASE,
)

# Spelled-out threshold: "up to 29 days", "maximum of 10 days", "less than 2 °C".
_THRESHOLD_WORDS = (
    r"(?:up\s+to|maximum\s+of|at\s+least|no\s+more\s+than|less\s+than)"
)
VALUE_UNIT_THRESHOLD_WORDS = re.compile(
    rf"(?:{_THRESHOLD_WORDS})\s+({_NUM})\s*({_UNITS_TIER1_STRICT})\b",
    re.IGNORECASE,
)

# Zero-point drift: "3.0 mmHg drift in 100 h".
VALUE_UNIT_DRIFT = re.compile(
    rf"({_NUM})\s*(mmHg)\s+(?:drift\s+)?in\s+({_NUM})\s*(?:h|hours?|days?)\b",
    re.IGNORECASE,
)

# Tesla — matches "<number> T" only when T is followed by whitespace, comma, dot,
# newline, closing paren/bracket, or end of string.  This prevents matching
# "25 T/m" (slash follows T) and "T cells" (no numeric prefix).
# The MRI context guard (R-1) is enforced in the extractor, not the pattern.
VALUE_UNIT_TESLA = re.compile(
    rf"({_NUM})\s+(T)\b(?=[,.\s\n\)\]]|$)",
)

# RBP label match — used with the (atm) context gate (D-1 Option A).
# Matches "RBP = 7.0" style entries in balloon sizing charts.
_VALUE_UNIT_RBP = re.compile(
    r"RBP\s*=\s*(\d+\.\d+)",
)

# MRI context indicator — presence required within ±200 chars of a Tesla match.
# `static` is intentionally broad for V1; FP surface (non-MRI spans containing
# both `static` and `<digit> T`) is negligible in the current dogfood set.
_MRI_CONTEXT = re.compile(
    r"(?:magnetic\s+field|static|tesla|mri|MR\s+system|MR\s+conditional)",
    re.IGNORECASE,
)


def normalize_author_year_key(authors_text: str, year_text: str) -> str:
    """Derive a normalized citation_key from raw author text and year.

    Rules:
    1. Take first token matching [A-Z][a-z]+.
    2. Lowercase it.
    3. Append underscore and 4-digit year.
    """
    first_author_match = re.search(r"[A-Z][a-z]+", authors_text)
    if not first_author_match:
        return f"unknown_{year_text}"
    return f"{first_author_match.group(0).lower()}_{year_text}"
