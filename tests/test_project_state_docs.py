from __future__ import annotations

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
