"""Forbidden-language helper for buyer-facing report content (Phase 5).

The bans apply ONLY to generated report text (report.json, findings.xlsx,
report.docx). Historical workflow records, code comments, and spec rationale
are out of scope; this helper is not a repo-wide grep gate.

Per the no-confident-verdict-without-evidence skill and the Phase 3
demo-hardening pass, V1 must not assign compliance/support/severity verdicts
in buyer-facing text. The forbidden list extends the Phase 3 checker-language
ban with terms unique to report-package prose ("must", "shall", "MDR
violation", etc.).
"""

from __future__ import annotations

REPORT_FORBIDDEN_LANGUAGE: frozenset[str] = frozenset(
    {
        "non-compliant",
        "noncompliant",
        "regulatory failure",
        "false claim",
        "nb will reject",
        "notified body will reject",
        "mdr violation",
        "unsupported",
        "must ",
        "shall ",
    }
)


def assert_no_forbidden_language(text: str, where: str) -> None:
    """Raise ValueError if any forbidden term appears in text (case-insensitive).

    `where` is a human-readable origin label included in the error message so
    test failures point at the offending artifact.

    "must " and "shall " carry a trailing space deliberately to avoid matching
    substrings inside benign words (e.g. "Mustang", "shallot"). Future
    quoted-excerpt support from official sources can revisit this convention.
    """
    lower = text.lower()
    offenders = sorted(term for term in REPORT_FORBIDDEN_LANGUAGE if term in lower)
    if offenders:
        raise ValueError(
            f"Forbidden report language detected in {where}: {offenders}"
        )
