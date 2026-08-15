"""Deterministic serialization helpers for ingestion diagnostics."""

from __future__ import annotations

from collections.abc import Sequence

from locuslab.models import ParserWarning


def serialize_parser_warnings(
    warnings: Sequence[ParserWarning],
) -> list[dict[str, str | None]]:
    """Return complete parser warnings in a stable order."""
    ordered = sorted(
        warnings,
        key=lambda warning: (
            warning.code.value,
            warning.path,
            warning.location or "",
            warning.message,
        ),
    )
    return [
        {
            "code": warning.code.value,
            "message": warning.message,
            "path": warning.path,
            "location": warning.location,
        }
        for warning in ordered
    ]
