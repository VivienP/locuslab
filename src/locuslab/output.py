"""JSONL / CSV serialization helpers for pipeline output."""

from __future__ import annotations

import csv
import dataclasses
import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from locuslab.models import Finding

_FINDINGS_CSV_COLUMNS = (
    "eco_id",
    "severity",
    "checker_id",
    "finding_type",
    "affected_object_ids",
    "evidence",
    "remediation_hint",
    "adjudication_state",
)


def _to_dict(record: Any) -> dict[str, Any]:
    """Convert a dataclass or TypedDict record to a plain dict."""
    if dataclasses.is_dataclass(record) and not isinstance(record, type):
        return dataclasses.asdict(record)
    if isinstance(record, dict):
        return record
    raise TypeError(f"Cannot serialize record of type {type(record)!r}")


def write_jsonl(records: Sequence[Any], path: Path) -> None:
    """Write dataclass or TypedDict records as sorted JSONL.

    Records must already be sorted by the caller. Each record is written as
    one JSON object per line with no trailing whitespace. The file is always
    written (empty if records is empty) to guarantee the file exists after a
    pipeline run.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as fh:
        for record in records:
            fh.write(json.dumps(_to_dict(record), ensure_ascii=False))
            fh.write("\n")


def write_findings_csv(findings: Sequence[Finding], path: Path) -> None:
    """Write Findings as a buyer-facing CSV with stable column ordering.

    Multi-valued `affected_object_ids` is joined with ";" so each row stays
    single-line. Embedded newlines or quotes in `evidence` / `remediation_hint`
    are handled by csv.QUOTE_MINIMAL. The file is always written (header-only
    if findings is empty) to guarantee the file exists after a pipeline run.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh, quoting=csv.QUOTE_MINIMAL)
        writer.writerow(_FINDINGS_CSV_COLUMNS)
        for finding in findings:
            writer.writerow(
                (
                    finding.eco_id,
                    finding.severity.value,
                    finding.checker_id,
                    finding.finding_type,
                    ";".join(finding.affected_object_ids),
                    finding.evidence,
                    finding.remediation_hint,
                    finding.adjudication_state.value,
                )
            )
