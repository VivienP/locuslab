"""Shared result type returned by every Phase 1b content reader."""

from __future__ import annotations

from dataclasses import dataclass

from locuslab.models import ParserWarning, Span


@dataclass(frozen=True)
class ReaderResult:
    """Spans, warnings, and parser identifier produced by a single-file reader."""

    spans: tuple[Span, ...]
    warnings: tuple[ParserWarning, ...]
    parser: str
