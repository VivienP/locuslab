from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

SCRIPT = Path("scripts/check_project_state_docs.py")
STALE_LABEL = "Phase 0 - Repo Bootstrap"


def run_checker(cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT.resolve()), "--check"],
        cwd=cwd,
        text=True,
        capture_output=True,
        check=False,
    )


def _canonical_phase() -> str:
    text = Path("docs/roadmap.md").read_text(encoding="utf-8")
    match = re.search(r"^## Current Phase:\s*(?P<phase>.+)$", text, flags=re.MULTILINE)
    assert match is not None, "docs/roadmap.md is missing its '## Current Phase' header"
    return match.group("phase").strip()


def test_project_state_docs_are_in_sync() -> None:
    result = run_checker(Path.cwd())

    assert result.returncode == 0, result.stdout + result.stderr


def test_dependency_install_contract_uses_pyproject_only() -> None:
    readme = Path("README.md").read_text(encoding="utf-8")
    workflow = Path(".github/workflows/ci.yml").read_text(encoding="utf-8")

    assert not Path("requirements.lock").exists()
    assert "requirements.lock" not in readme
    assert 'pip install -e ".[dev]"' in workflow


def test_public_scope_descriptions_match_the_shipped_mdr_ivdr_surface() -> None:
    scoped_paths = (
        Path("pyproject.toml"),
        Path("docs/architecture.md"),
        Path("src/locuslab/__init__.py"),
        Path("src/locuslab/models.py"),
        Path("src/locuslab/extract/claim_extractor.py"),
    )

    for path in scoped_paths:
        text = path.read_text(encoding="utf-8").lower()
        assert "scaffolding" not in text, path
        assert "domain-agnostic" not in text, path

    architecture = Path("docs/architecture.md").read_text(encoding="utf-8")
    assert "LocusLab V1 is MDR/IVDR-specific" in architecture
    assert "no cross-domain compatibility is claimed" in architecture


def test_regression_corpus_contains_data_not_work_session_notes() -> None:
    regression_root = Path("eval/regressions")
    stale_names = {"doc_updates.md", "notes.md", "test_plan.md"}

    assert not [
        path for path in regression_root.rglob("*") if path.name in stale_names
    ]

    regression_files = sorted(regression_root.rglob("regression.jsonl"))
    assert regression_files
    for path in regression_files:
        records = [
            json.loads(line)
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        assert records, path


def test_unimplemented_evaluation_fixture_is_not_published_as_ground_truth() -> None:
    assert not Path("eval/synthetic_dossier/ground_truth.json").exists()
    gold_readme = Path("fixtures/gold/README.md").read_text(encoding="utf-8")
    assert "eval/synthetic_dossier" not in gold_readme


def test_third_party_inventory_has_no_work_session_labels() -> None:
    source = Path("docs/THIRD_PARTY.md").read_text(encoding="utf-8")
    packaged = Path("src/locuslab/resources/docs/THIRD_PARTY.md").read_text(
        encoding="utf-8"
    )

    assert source == packaged
    assert "WS6" not in source
    assert "workstream" not in source.lower()


def test_project_state_doc_checker_detects_stale_phase_text(tmp_path: Path) -> None:
    for path in (
        "docs/roadmap.md",
        "README.md",
        "AGENTS.md",
        "CLAUDE.md",
        "docs/development_workflow.md",
        "AI_CONTRACT.md",
    ):
        source = Path(path)
        if not source.is_file():
            continue
        target = tmp_path / path
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)

    canonical = _canonical_phase()
    stale_doc = tmp_path / "docs/development_workflow.md"
    stale_text = stale_doc.read_text(encoding="utf-8").replace(canonical, STALE_LABEL)
    assert stale_text != stale_doc.read_text(encoding="utf-8"), (
        f"Canonical phase '{canonical}' not found in docs/development_workflow.md; "
        "doc sync test cannot exercise drift detection."
    )
    stale_doc.write_text(stale_text, encoding="utf-8")

    result = run_checker(tmp_path)

    assert result.returncode == 1
    assert "docs/development_workflow.md" in result.stdout
    assert STALE_LABEL in result.stdout


def test_agent_guides_must_not_hard_code_phase(tmp_path: Path) -> None:
    for path in (
        "docs/roadmap.md",
        "README.md",
        "AGENTS.md",
        "CLAUDE.md",
        "docs/development_workflow.md",
        "AI_CONTRACT.md",
    ):
        source = Path(path)
        if not source.is_file():
            continue
        target = tmp_path / path
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)

    claude = tmp_path / "CLAUDE.md"
    original = claude.read_text(encoding="utf-8")
    claude.write_text(
        original + "\nCurrent phase: Phase 0 - Repo Bootstrap\n",
        encoding="utf-8",
    )

    result = run_checker(tmp_path)
    assert result.returncode == 1
    assert "CLAUDE.md" in result.stdout
