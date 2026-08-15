"""CLI smoke tests for successful and rejected verification requests."""

from pathlib import Path

import pytest

from locuslab.cli import main


def test_cli_help_returns_zero() -> None:
    assert main(["--help"]) == 0


def test_verify_empty_dossier_fails_without_outputs(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """An empty dossier cannot masquerade as a successful zero-content audit."""
    dossier = tmp_path / "dossier"
    dossier.mkdir()
    run_dir = tmp_path / "run"

    result = main(["verify", str(dossier), "--out", str(run_dir)])

    captured = capsys.readouterr()
    assert result == 2
    assert "no usable content" in captured.err.lower()
    assert captured.out == ""
    assert not run_dir.exists()


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


def test_verify_reports_output_error_when_output_path_is_a_file(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    dossier = tmp_path / "dossier"
    dossier.mkdir()
    output_file = tmp_path / "run"
    output_file.write_text("user data", encoding="utf-8")

    result = main(["verify", str(dossier), "--out", str(output_file)])

    captured = capsys.readouterr()
    assert result == 2
    assert "Output directory could not be prepared" in captured.err
    assert output_file.read_text(encoding="utf-8") == "user data"
