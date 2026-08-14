"""End-to-end verify pipeline smoke tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

DEMO_DOSSIER = Path(__file__).parent.parent / "fixtures" / "demo_dossier"
EXPECTED_JSONL_FILES = [
    "claims.jsonl",
    "citations.jsonl",
    "sources.jsonl",
    "evidence_links.jsonl",
]


@pytest.fixture()
def run_dir(tmp_path: Path) -> Path:
    return tmp_path / "phase2_smoke_run"


@pytest.fixture()
def verify_result(run_dir: Path):  # type: ignore[return]
    from locuslab.pipeline import verify_dossier

    return verify_dossier(DEMO_DOSSIER, run_dir)


class TestProducesFourJsonlFiles:
    def test_verify_produces_four_jsonl_files(self, verify_result, run_dir):
        """Pipeline must produce all four JSONL output files."""
        for fname in EXPECTED_JSONL_FILES:
            fpath = run_dir / fname
            assert fpath.exists(), f"Missing output file: {fpath}"

    def test_output_dir_is_created(self, verify_result, run_dir):
        """Output directory must be created if it does not exist."""
        assert run_dir.is_dir(), "Output directory was not created"


class TestJsonlFilesWellFormed:
    def test_jsonl_files_are_well_formed(self, verify_result, run_dir):
        """Each line in every JSONL file must parse as valid JSON."""
        for fname in EXPECTED_JSONL_FILES:
            fpath = run_dir / fname
            text = fpath.read_text(encoding="utf-8")
            if not text.strip():
                continue
            for i, line in enumerate(text.splitlines(), start=1):
                if not line.strip():
                    continue
                try:
                    json.loads(line)
                except json.JSONDecodeError as exc:
                    pytest.fail(f"{fname} line {i} is not valid JSON: {exc!r}")

    def test_claims_jsonl_has_required_keys(self, verify_result, run_dir):
        """claims.jsonl records must have the expected top-level keys."""
        fpath = run_dir / "claims.jsonl"
        required = {"claim_id", "document_id", "span_id", "text", "claim_type",
                    "extraction_method", "confidence_label"}
        for line in fpath.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            obj = json.loads(line)
            missing = required - obj.keys()
            assert not missing, f"claims.jsonl record missing keys: {missing}"

    def test_citations_jsonl_has_required_keys(self, verify_result, run_dir):
        """citations.jsonl records must have the expected top-level keys."""
        fpath = run_dir / "citations.jsonl"
        required = {"mention_id", "document_id", "span_id", "marker_text",
                    "marker_form", "normalized_key", "occurrence_index",
                    "span_offset_start", "span_offset_end"}
        for line in fpath.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            obj = json.loads(line)
            missing = required - obj.keys()
            assert not missing, f"citations.jsonl record missing keys: {missing}"

    def test_sources_jsonl_has_required_keys(self, verify_result, run_dir):
        """sources.jsonl records must have the expected top-level keys."""
        fpath = run_dir / "sources.jsonl"
        required = {"source_id", "path", "citation_key", "availability_status"}
        for line in fpath.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            obj = json.loads(line)
            missing = required - obj.keys()
            assert not missing, f"sources.jsonl record missing keys: {missing}"

    def test_evidence_links_jsonl_has_required_keys(self, verify_result, run_dir):
        """evidence_links.jsonl records must have the expected top-level keys."""
        fpath = run_dir / "evidence_links.jsonl"
        required = {"evidence_link_id", "claim_id", "source_id", "status", "linking_method"}
        for line in fpath.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            obj = json.loads(line)
            missing = required - obj.keys()
            assert not missing, f"evidence_links.jsonl record missing keys: {missing}"


class TestJsonlDeterminism:
    def test_jsonl_files_are_deterministically_sorted(self, verify_result, run_dir):
        """Records must be sorted by their primary ID field."""
        id_fields = {
            "claims.jsonl": "claim_id",
            "citations.jsonl": "mention_id",
            "sources.jsonl": "source_id",
            "evidence_links.jsonl": "evidence_link_id",
        }
        for fname, id_field in id_fields.items():
            fpath = run_dir / fname
            ids = []
            for line in fpath.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                ids.append(json.loads(line)[id_field])
            assert ids == sorted(ids), f"{fname} not sorted by {id_field}: {ids}"

    def test_output_is_identical_across_two_runs(self, run_dir):
        """Two sequential runs must produce byte-identical JSONL files."""
        from locuslab.pipeline import verify_dossier

        run_dir.mkdir(parents=True, exist_ok=True)
        verify_dossier(DEMO_DOSSIER, run_dir)
        contents_first = {
            fname: (run_dir / fname).read_bytes() for fname in EXPECTED_JSONL_FILES
        }
        verify_dossier(DEMO_DOSSIER, run_dir)
        for fname in EXPECTED_JSONL_FILES:
            assert (run_dir / fname).read_bytes() == contents_first[fname], (
                f"{fname} differs between runs"
            )


class TestCliSummary:
    def test_cli_prints_summary_line(self, capsys, run_dir):
        """CLI stdout must contain a summary line with claim/citation/source/link counts."""
        from locuslab.cli import main

        code = main([
            "verify",
            str(DEMO_DOSSIER),
            "--out", str(run_dir),
        ])
        assert code == 0, f"CLI exited with code {code}"
        captured = capsys.readouterr()
        assert "claims" in captured.out, f"'claims' not in stdout: {captured.out!r}"
        assert "citations" in captured.out, f"'citations' not in stdout: {captured.out!r}"
        assert "sources" in captured.out, f"'sources' not in stdout: {captured.out!r}"
