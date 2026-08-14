"""Phase 5 — Report package generation (report.json / findings.xlsx / report.docx)."""

from locuslab.report.json_report import (
    REPORT_SCHEMA_VERSION,
    build_report_dict,
    write_report_json,
)
from locuslab.report.language import (
    REPORT_FORBIDDEN_LANGUAGE,
    assert_no_forbidden_language,
)
from locuslab.report.package import ReportPackagePaths, write_report_package

__all__ = [
    "REPORT_FORBIDDEN_LANGUAGE",
    "REPORT_SCHEMA_VERSION",
    "ReportPackagePaths",
    "assert_no_forbidden_language",
    "build_report_dict",
    "write_report_json",
    "write_report_package",
]
