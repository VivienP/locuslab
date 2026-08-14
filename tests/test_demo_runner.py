"""Demo runner script tests (offline)."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest
from docx import Document as DocxRead

# Make src/ importable so the canonical forbidden-language list stays the
# single source of truth (fixes reviewer drift between this test, Phase 6A,
# and src/locuslab/report/language.py).
_SRC = Path(__file__).resolve().parent.parent / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from locuslab.report.language import REPORT_FORBIDDEN_LANGUAGE  # noqa: E402

REPO_ROOT = Path(__file__).parent.parent
SCRIPT_PATH = REPO_ROOT / "scripts" / "run_demo.py"
DEMO_DOSSIER = REPO_ROOT / "fixtures" / "demo_dossier"
EXPECTED_ARTIFACTS = (
    "claims.jsonl",
    "citations.jsonl",
    "sources.jsonl",
    "evidence_links.jsonl",
    "findings.jsonl",
    "findings.csv",
    "graph.jsonl",
    "audit_manifest.json",
    "report.docx",
    "findings.xlsx",
    "report.json",
)


def _run_script(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT_PATH), *args],
        capture_output=True,
        text=True,
        check=False,
        cwd=cwd or REPO_ROOT,
    )


class TestRunDemoScriptOnFixture:
    @pytest.fixture()
    def run_dir(self, tmp_path: Path) -> Path:
        out = tmp_path / "demo_run"
        result = _run_script(
            "--dossier", str(DEMO_DOSSIER),
            "--out", str(out),
        )
        # Surface stderr in test output if the script failed.
        assert result.returncode == 0, (
            f"run_demo.py exited {result.returncode}.\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )
        return out

    @pytest.fixture()
    def stdout(self, tmp_path: Path) -> str:
        out = tmp_path / "demo_run_stdout"
        result = _run_script(
            "--dossier", str(DEMO_DOSSIER),
            "--out", str(out),
        )
        assert result.returncode == 0
        return result.stdout

    def test_script_exits_zero_on_fixture_demo(self, run_dir: Path) -> None:
        # Side effect of the fixture is the assertion; this test exists to
        # document the intent explicitly in the test report.
        assert run_dir.is_dir()

    def test_all_eleven_artifacts_exist(self, run_dir: Path) -> None:
        for fname in EXPECTED_ARTIFACTS:
            path = run_dir / fname
            assert path.exists(), f"Missing artifact: {fname}"
            # Reject 0-byte files: a silent pipeline drop must not look like
            # a successful demo. Pairs with the size check in run_demo.py.
            assert path.stat().st_size > 0, f"Hollow artifact (0 bytes): {fname}"

    def test_stdout_marks_artifacts_present(self, stdout: str) -> None:
        assert "OK " in stdout
        for fname in EXPECTED_ARTIFACTS:
            assert fname in stdout

    def test_stdout_lists_review_order(self, stdout: str) -> None:
        lower = stdout.lower()
        assert "report.docx" in lower
        assert "findings.xlsx" in lower
        assert "audit_manifest.json" in lower
        report_pos = lower.index("report.docx")
        xlsx_pos = lower.index("findings.xlsx")
        manifest_pos = lower.index("audit_manifest.json")
        assert report_pos < xlsx_pos < manifest_pos

    def test_stdout_omits_sales_script_language(self, stdout: str) -> None:
        lower = stdout.lower()
        banned = (
            "screen-share",
            "cheat sheet",
            "buyer artifact",
            "before the call",
            "prospect-call",
            "dogfood",
        )
        hits = [term for term in banned if term in lower]
        assert not hits, f"Sales-script language in stdout: {hits}"

    def test_stdout_points_at_limitations(self, stdout: str) -> None:
        assert "docs/LIMITATIONS.md" in stdout

    def test_stdout_contains_no_forbidden_verdict_language(self, stdout: str) -> None:
        lower = stdout.lower()
        offenders = [term for term in REPORT_FORBIDDEN_LANGUAGE if term in lower]
        assert not offenders, f"Forbidden verdict language in stdout: {offenders}"

    def test_stdout_carries_cli_summary_line_with_demo_counts(self, stdout: str) -> None:
        assert "Verified:" in stdout
        assert "report package written" in stdout
        assert "18 claims" in stdout
        assert "5 citations" in stdout
        assert "3 sources" in stdout
        assert "18 evidence links" in stdout
        assert "8 findings" in stdout
        assert "105 graph records" in stdout

    def test_no_sources_warning_absent_on_fixture(self, stdout: str) -> None:
        # The demo dossier resolves 3 sources, so the "0 sources" warning
        # block must not appear.
        assert "0 sources resolved" not in stdout


class TestRunDemoScriptOnNoBibliographyInput:
    """Run the script on a dossier with no bibliography to verify the
    sources=0 warning fires. Uses a tmp dossier containing just the demo
    CER, so the bibliography resolver finds nothing."""

    @pytest.fixture()
    def empty_bib_dossier(self, tmp_path: Path) -> Path:
        d = tmp_path / "no_bib_dossier"
        d.mkdir()
        # Copy only the CER (no bibliography/ subdir).
        cer_src = DEMO_DOSSIER / "CER.docx"
        (d / "CER.docx").write_bytes(cer_src.read_bytes())
        return d

    def test_warning_fires_when_sources_count_is_zero(
        self, tmp_path: Path, empty_bib_dossier: Path
    ) -> None:
        out = tmp_path / "no_bib_run"
        result = _run_script(
            "--dossier", str(empty_bib_dossier),
            "--out", str(out),
        )
        assert result.returncode == 0, (
            f"run_demo.py exited {result.returncode}.\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )
        assert "0 sources" in result.stdout, (
            "Expected 0-sources warning; stdout was:\n" + result.stdout
        )


class TestRunDemoScriptArgParsing:
    def test_missing_dossier_directory_exits_nonzero(self, tmp_path: Path) -> None:
        ghost = tmp_path / "does_not_exist"
        result = _run_script("--dossier", str(ghost), "--out", str(tmp_path / "out"))
        assert result.returncode != 0
        assert "not found" in result.stderr.lower()

    def test_default_dossier_when_no_args(self, tmp_path: Path) -> None:
        # Pass only --out so we don't pollute the system temp dir.
        result = _run_script("--out", str(tmp_path / "default_dossier_run"))
        assert result.returncode == 0, (
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )
        # Default dossier is fixtures/demo_dossier; 3 sources resolved.
        assert "3 sources" in result.stdout

    def test_help_does_not_mention_dogfood_or_prospect_paths(self) -> None:
        result = _run_script("--help")
        assert result.returncode == 0
        lower = (result.stdout + result.stderr).lower()
        assert "dogfood" not in lower
        assert "reports/dogfood" not in lower
        assert "screen-share" not in lower
        assert "cheat sheet" not in lower


class TestRunDemoReportDocxOpens:
    def test_report_docx_is_readable(self, tmp_path: Path) -> None:
        out = tmp_path / "docx_open"
        result = _run_script("--dossier", str(DEMO_DOSSIER), "--out", str(out))
        assert result.returncode == 0, result.stderr
        path = out / "report.docx"
        assert path.is_file() and path.stat().st_size > 0
        doc = DocxRead(str(path))
        texts = [p.text for p in doc.paragraphs]
        assert any("LocusLab Evidence Trace Audit Report" in t for t in texts)


class TestLocusVerifyDemoCounts:
    def test_cli_verify_matches_demo_summary(self, tmp_path: Path) -> None:
        out = tmp_path / "cli_demo"
        env = os.environ.copy()
        env["PYTHONPATH"] = str(REPO_ROOT / "src")
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "locuslab.cli",
                "verify",
                str(DEMO_DOSSIER),
                "--out",
                str(out),
            ],
            capture_output=True,
            text=True,
            check=False,
            cwd=REPO_ROOT,
            env=env,
        )
        assert result.returncode == 0, result.stderr
        stdout = result.stdout
        assert "18 claims" in stdout
        assert "5 citations" in stdout
        assert "3 sources" in stdout
        assert "18 evidence links" in stdout
        assert "8 findings" in stdout
        assert "105 graph records" in stdout
        docx = out / "report.docx"
        assert docx.is_file() and docx.stat().st_size > 0
        DocxRead(str(docx))
