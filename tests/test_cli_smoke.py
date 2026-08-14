"""CLI smoke tests - updated for Phase 2 pipeline (verify now exits 0 on success)."""

from pathlib import Path

import pytest

from locuslab.cli import main


def test_cli_help_returns_zero() -> None:
    assert main(["--help"]) == 0


def test_verify_empty_dossier_produces_zero_outputs(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """An empty dossier loads successfully and produces JSONL files with zero records."""
    dossier = tmp_path / "dossier"
    dossier.mkdir()
    run_dir = tmp_path / "run"

    result = main(["verify", str(dossier), "--out", str(run_dir)])

    captured = capsys.readouterr()
    assert result == 0, f"Expected exit 0, got {result}. stderr: {captured.err!r}"
    assert "claims" in captured.out
    assert "citations" in captured.out
    # All JSONL output files must exist (empty)
    for fname in ["claims.jsonl", "citations.jsonl", "sources.jsonl", "evidence_links.jsonl"]:
        assert (run_dir / fname).exists(), f"Missing: {fname}"


def test_verify_on_demo_dossier_completes_successfully(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Demo dossier verify exits 0 and prints summary with non-zero counts."""
    result = main(
        ["verify", "fixtures/demo_dossier", "--out", str(tmp_path / "run")]
    )

    captured = capsys.readouterr()
    assert result == 0, f"Expected exit 0, got {result}. stderr: {captured.err!r}"
    assert "claims" in captured.out
    assert "citations" in captured.out
    assert "sources" in captured.out


def test_verify_reports_dossier_load_error_when_path_is_a_file(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    bogus = tmp_path / "not_a_dir.txt"
    bogus.write_text("placeholder")

    result = main(["verify", str(bogus), "--out", str(tmp_path / "run")])

    captured = capsys.readouterr()
    assert result == 2
    assert "Dossier could not be loaded" in captured.err
