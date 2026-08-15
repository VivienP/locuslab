from __future__ import annotations

import importlib.util
import subprocess
import sys
import tomllib
from pathlib import Path
from types import ModuleType

import pytest

SCRIPT = Path("scripts/check_agentic_layer.py")
READ_ONLY_PROHIBITION = (
    "Do not edit files, stage, commit, push, switch branches, or open pull requests."
)
RELEASE_AUDITOR_PROHIBITION = (
    "Do not edit repository or source files, stage, commit, push, switch branches, "
    "or open pull requests."
)
RELEASE_AUDITOR_TEMP_WRITE_ALLOWANCE = (
    "Ephemeral writes are allowed only in an approved external temporary workspace."
)
ROLE_INSTRUCTION_SUFFIXES = {
    "locuslab-reviewer": (READ_ONLY_PROHIBITION,),
    "release-auditor": (
        RELEASE_AUDITOR_PROHIBITION,
        RELEASE_AUDITOR_TEMP_WRITE_ALLOWANCE,
    ),
}

SKILLS = {
    "verify-change": "Use when verifying a LocusLab change before review.",
    "audit-release": "Use when auditing a LocusLab release candidate.",
    "review-finding-language": "Use when reviewing deterministic finding language.",
}

ROLES = {
    "locuslab-reviewer": (
        "Use when reviewing LocusLab changes against repository invariants.",
        ("verify-change", "review-finding-language"),
    ),
    "release-auditor": (
        "Use when auditing a LocusLab release for reproducible evidence.",
        ("audit-release",),
    ),
}


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8", newline="\n")


def _frontmatter(name: str, description: str) -> str:
    return f"---\nname: {name}\ndescription: {description}\n---\n"


def _adapter_instructions(role_name: str, skill_names: tuple[str, ...]) -> str:
    lines = [f"Canonical role: docs/agentic/roles/{role_name}.md"]
    lines.extend(
        f"Required skill: .agents/skills/{skill_name}/SKILL.md"
        for skill_name in skill_names
    )
    lines.extend(ROLE_INSTRUCTION_SUFFIXES[role_name])
    return "\n".join(lines)


def _valid_tree(root: Path) -> None:
    _write(
        root / "docs/agentic/README.md",
        "# Agentic Development Kit\n\n"
        "See `.agents/skills/<name>/SKILL.md` and "
        "https://example.invalid/agentic-compatibility.\n"
        "Record live evidence only when the named client is actually run.\n",
    )

    for name, description in SKILLS.items():
        content = _frontmatter(name, description) + f"# {name}\n\nFollow the public workflow.\n"
        canonical = root / f".agents/skills/{name}/SKILL.md"
        mirror = root / f".claude/skills/{name}/SKILL.md"
        _write(canonical, content)
        mirror.parent.mkdir(parents=True, exist_ok=True)
        mirror.write_bytes(canonical.read_bytes())

    for role_name, (description, skill_names) in ROLES.items():
        role_path = f"docs/agentic/roles/{role_name}.md"
        instructions = _adapter_instructions(role_name, skill_names)
        _write(
            root / role_path,
            _frontmatter(role_name, description)
            + f"# {role_name}\n\nThis canonical role is read-only.\n",
        )
        _write(
            root / f".codex/agents/{role_name}.toml",
            f'name = "{role_name}"\n'
            f'description = "{description}"\n'
            'sandbox_mode = "read-only"\n'
            'developer_instructions = """\n'
            f"{instructions}\n"
            '"""\n',
        )
        _write(
            root / f".claude/agents/{role_name}.md",
            _frontmatter(role_name, description).replace(
                "\n---\n", "\npermissionMode: plan\n---\n", 1
            )
            + f"{instructions}\n",
        )


def _load_checker() -> ModuleType:
    assert SCRIPT.is_file(), f"missing checker: {SCRIPT}"
    spec = importlib.util.spec_from_file_location("check_agentic_layer", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _rendered_findings(root: Path) -> list[str]:
    checker = _load_checker()
    return [finding.render() for finding in checker.collect_findings(root)]


def test_real_repository_agentic_layer_is_clean() -> None:
    checker = _load_checker()

    findings = checker.collect_findings(Path.cwd())

    assert findings == [], "\n".join(finding.render() for finding in findings)


def test_ci_runs_quality_gates_in_required_order() -> None:
    workflow = Path(".github/workflows/ci.yml").read_text(encoding="utf-8")
    commands = (
        "python scripts/check_project_state_docs.py --check",
        "python scripts/check_agentic_layer.py --check",
        "python -m pytest",
        "python -m ruff check src tests scripts",
        "python -m mypy src/locuslab",
    )

    for command in commands:
        assert command in workflow
    positions = [workflow.index(command) for command in commands]
    assert positions == sorted(positions)


def test_compatibility_status_records_observed_smoke_evidence() -> None:
    guide = Path("docs/agentic/README.md").read_text(encoding="utf-8")

    for evidence in (
        "Static checker | PASS locally",
        "Codex CLI 0.128.0 release scenario | PASS",
        "Codex CLI 0.128.0 reviewer scenario | PARTIAL/BLOCKED",
        "Claude Code | UNAVAILABLE",
        "unknown agent_type 'locuslab-reviewer'",
    ):
        assert evidence in guide
    assert "| Pending |" not in guide


def test_repository_role_specs_and_adapters_match_the_public_contract() -> None:
    checker = _load_checker()

    for role_name, (description, _skill_names) in ROLES.items():
        role_path = Path(f"docs/agentic/roles/{role_name}.md")
        role_frontmatter, role_body = checker.parse_frontmatter(
            role_path.read_text(encoding="utf-8")
        )
        assert role_frontmatter == {"name": role_name, "description": description}
        assert "read-only" in role_body.lower()

        expected = checker.expected_instructions(role_name)
        assert expected is not None

        codex_path = Path(f".codex/agents/{role_name}.toml")
        codex = tomllib.loads(codex_path.read_text(encoding="utf-8"))
        assert codex == {
            "name": role_name,
            "description": description,
            "sandbox_mode": "read-only",
            "developer_instructions": f"{expected}\n",
        }

        claude_path = Path(f".claude/agents/{role_name}.md")
        claude_frontmatter, claude_body = checker.parse_frontmatter(
            claude_path.read_text(encoding="utf-8")
        )
        assert claude_frontmatter == {
            "name": role_name,
            "description": description,
            "permissionMode": "plan",
        }
        assert claude_body == expected


def test_release_auditor_uses_a_role_specific_external_write_template() -> None:
    checker = _load_checker()

    reviewer_expected = checker.expected_instructions("locuslab-reviewer")
    assert reviewer_expected is not None
    assert reviewer_expected.endswith(READ_ONLY_PROHIBITION)
    assert RELEASE_AUDITOR_TEMP_WRITE_ALLOWANCE not in reviewer_expected

    release_expected = "\n".join(
        (
            "Canonical role: docs/agentic/roles/release-auditor.md",
            "Required skill: .agents/skills/audit-release/SKILL.md",
            RELEASE_AUDITOR_PROHIBITION,
            RELEASE_AUDITOR_TEMP_WRITE_ALLOWANCE,
        )
    )
    assert checker.expected_instructions("release-auditor") == release_expected

    codex = tomllib.loads(
        Path(".codex/agents/release-auditor.toml").read_text(encoding="utf-8")
    )
    assert codex["developer_instructions"].strip() == release_expected
    _claude_frontmatter, claude_body = checker.parse_frontmatter(
        Path(".claude/agents/release-auditor.md").read_text(encoding="utf-8")
    )
    assert claude_body == release_expected

    role = " ".join(
        Path("docs/agentic/roles/release-auditor.md")
        .read_text(encoding="utf-8")
        .split()
    )
    assert "Runtime read-only sandboxes may still force Path B and `HOLD`" in role


def test_repository_verify_change_skill_encodes_proportional_fresh_evidence() -> None:
    checker = _load_checker()
    canonical = Path(".agents/skills/verify-change/SKILL.md")
    mirror = Path(".claude/skills/verify-change/SKILL.md")

    frontmatter, body = checker.parse_frontmatter(
        canonical.read_text(encoding="utf-8")
    )

    assert frontmatter == {
        "name": "verify-change",
        "description": (
            "Use when verifying a LocusLab change before review, handoff, "
            "integration, or completion claims."
        ),
    }
    assert len(body.split()) < 500
    assert canonical.read_bytes() == mirror.read_bytes()
    normalized_body = " ".join(body.split())
    changed_path_taxonomy = normalized_body.split(
        "Classify every changed path:", maxsplit=1
    )[1].split(".", maxsplit=1)[0]

    for label in (
        "Python/runtime",
        "tests",
        "project-state docs",
        "agentic configuration",
        "packaged byte resource",
        "release/public claim",
    ):
        assert label in changed_path_taxonomy

    assert "| Tests |" in normalized_body
    tests_gate = normalized_body.split("| Tests |", maxsplit=1)[1].split(
        "|", maxsplit=1
    )[0]
    for requirement in (
        "directly changed tests",
        "nearest affected regression scope",
        "broader suite only when shared behavior or invariants justify it",
    ):
        assert requirement in tests_gate.lower()

    required_text = (
        "exact diff, base, and dirty state",
        "Run new commands in the current worktree",
        "another agent's summary",
        "not every change requires every repository gate",
        "python scripts/check_agentic_layer.py --check",
        "focused agentic tests",
        "run, not run, or unavailable",
        "static success is not live-client evidence",
        "python scripts/check_project_state_docs.py --check",
        "pytest",
        "Ruff",
        "mypy",
        "byte and EOL",
        "audit-release",
        "Do not edit files or mutate Git state",
        "Stop when all changed paths are classified",
        "each applicable row has fresh",
        "when a blocker prevents that evidence",
        "Stop immediately",
        "**Scope/base/dirty state:**",
        "**Commands run:**",
        "**Pass/fail:**",
        "**Omissions:**",
        "**Blockers:**",
        "**Conclusion:**",
    )
    for text in required_text:
        assert text in normalized_body


def test_repository_review_finding_language_skill_prevents_fragment_approval() -> None:
    checker = _load_checker()
    canonical = Path(".agents/skills/review-finding-language/SKILL.md")
    mirror = Path(".claude/skills/review-finding-language/SKILL.md")

    frontmatter, body = checker.parse_frontmatter(
        canonical.read_text(encoding="utf-8")
    )

    assert frontmatter == {
        "name": "review-finding-language",
        "description": (
            "Use when reviewing proposed or changed LocusLab finding evidence, "
            "remediation, provenance, or adjudication language."
        ),
    }
    assert len(body.split()) < 500
    assert canonical.read_bytes() == mirror.read_bytes()

    normalized_body = " ".join(body.split())
    for field in (
        "eco_id",
        "severity",
        "checker_id",
        "finding_type",
        "affected_object_ids",
        "evidence",
        "remediation_hint",
        "adjudication_state",
    ):
        assert field in normalized_body

    for requirement in (
        "A finding is not an approvable text fragment",
        "missing provenance fields",
        "missing or invalid values",
        "never a wording-only approval",
        "checker short token",
        "sorted `affected_object_ids`",
        "matches the deterministic `make_eco_id` derivation",
        "severity is justified by the deterministic rule or attributable human adjudication",
        "never model inference",
        "deterministic rule",
        "actual inputs",
        "fixture or test",
        "evidence boundary",
        "Keyword scanning is necessary but insufficient",
        "equivalent overclaims",
        "non-compliant",
        "notified body will reject",
        "unsupported",
        "must",
        "shall",
        "traceability gap",
        "truth, support, or compliance",
        "Guidance-review items remain non-ECO",
        "event provenance",
        "checker output",
        "preserve object IDs and the observed method",
        "targeted checker and language tests",
        "Do not edit files, fix findings, or mutate Git state",
        "Use exactly one verdict",
        "`APPROVE`",
        "`REJECT`",
        "`NEEDS CONTEXT`",
        "**Evidence boundary:**",
        "**Field completeness:**",
        "**Prohibited/equivalent language:**",
        "**Tests:**",
        "**Decision:**",
    ):
        assert requirement in normalized_body

    incomplete_rule = normalized_body.split(
        "When a generated finding is presented", maxsplit=1
    )[1].split("## Trace", maxsplit=1)[0]
    assert "`REJECT` or `NEEDS CONTEXT`" in incomplete_rule
    assert "`APPROVE`" not in incomplete_rule

    decision_rules = normalized_body.split("## Decide", maxsplit=1)[1].split(
        "## Report", maxsplit=1
    )[0]
    assert "exactly one" in decision_rules
    assert "complete" in decision_rules
    assert "contradicts" in decision_rules
    assert "cannot be inspected" in decision_rules


def test_repository_audit_release_skill_requires_target_specific_release_evidence() -> None:
    checker = _load_checker()
    canonical = Path(".agents/skills/audit-release/SKILL.md")
    mirror = Path(".claude/skills/audit-release/SKILL.md")

    frontmatter, body = checker.parse_frontmatter(
        canonical.read_text(encoding="utf-8")
    )

    assert frontmatter == {
        "name": "audit-release",
        "description": (
            "Use when deciding whether a LocusLab source repository snapshot or "
            "Python distribution release is publishable."
        ),
    }
    assert len(body.split()) < 500
    assert canonical.read_bytes() == mirror.read_bytes()

    normalized_body = " ".join(body.split())
    target_instruction = "Classify the exact target before running gates"
    assert target_instruction in normalized_body
    assert normalized_body.index(target_instruction) < normalized_body.index(
        "python -m pytest"
    )

    required_text = (
        "source repository publication",
        "Python distribution release",
        "exact target ref and commit",
        "comparison base",
        "dirty state",
        "remote ref",
        "CI run",
        "python -m pytest",
        "python -m ruff check src tests scripts",
        "python -m mypy src/locuslab",
        "python scripts/check_project_state_docs.py --check",
        "python scripts/check_agentic_layer.py --check",
        "public documentation",
        "public claims",
        "licence",
        "repository hygiene",
        "supported public demo",
        "wheel and sdist",
        "contents, metadata, licence, and packaged resources",
        "clean temporary environment",
        "non-editably",
        "installed `locus`",
        "artifact inventory",
        "openability",
        "manifest hashes",
        "deterministic rerun",
        "private data",
        "secrets",
        "generated logs",
        "claims and `docs/LIMITATIONS.md`",
        "Do not edit repository or source files or mutate Git state",
        "Missing required evidence can never yield `PUBLISHABLE`",
        "**Target/ref/base/dirty/remote/CI:**",
        "**Commands and results:**",
        "**Omissions:**",
        "**Blockers:**",
        "**Limitations:**",
        "**Verdict:**",
    )
    for text in required_text:
        assert text in normalized_body

    assert "Do not require distribution-only gates for source repository publication" in (
        normalized_body
    )
    assert "source publication still requires supported public demo evidence" in (
        normalized_body
    )
    for clean_target_requirement in (
        "external temporary workspace",
        "Path A permits ephemeral writes only inside the approved external temporary workspace",
        "clean export",
        "repository status before and after",
        "prove it is unchanged",
        "Path B remains strictly read-only",
        "trusted CI- or operator-prepared immutable evidence bundle",
        "exact target commit and ref",
        "tracked-byte identity",
        "commands and results",
        "artifacts and hashes",
        "verifies bundle binding, freshness, and readability",
        "does not prepare the bundle",
        "If neither path is available or bundle identity or freshness is unproven",
        "For source repository publication, audit that clean target tree",
        "For a Python distribution release, build from that clean target tree",
        "install the artifact produced from it",
        "Never treat the current dirty repository as the clean target",
        "Never write build or demo outputs into the repository",
        "verdict is `HOLD`",
    ):
        assert clean_target_requirement in normalized_body

    hold_rule = normalized_body.split("- `HOLD`:", maxsplit=1)[1].split(
        "- `NOT PUBLISHABLE`:", maxsplit=1
    )[0]
    for evidence_state in (
        "missing",
        "omitted",
        "unrun",
        "unavailable",
        "stale",
        "inconclusive",
        "identity-unproven",
    ):
        assert evidence_state in hold_rule
    assert "no proven target failure" in hold_rule

    not_publishable_rule = normalized_body.split(
        "- `NOT PUBLISHABLE`:", maxsplit=1
    )[1].split("Missing required evidence", maxsplit=1)[0]
    for target_failure in (
        "target-matched failing gate",
        "build",
        "install",
        "demo",
        "hash",
        "documented contradiction",
    ):
        assert target_failure in not_publishable_rule
    for verdict in ("`PUBLISHABLE`", "`HOLD`", "`NOT PUBLISHABLE`"):
        assert verdict in normalized_body


def test_repository_release_auditor_role_requires_safe_evidence_acquisition() -> None:
    checker = _load_checker()
    role = Path("docs/agentic/roles/release-auditor.md")
    frontmatter, body = checker.parse_frontmatter(role.read_text(encoding="utf-8"))
    normalized_body = " ".join(body.split())

    assert frontmatter == {
        "name": "release-auditor",
        "description": "Use when auditing a LocusLab release for reproducible evidence.",
    }
    for requirement in (
        "Evidence acquisition is a prerequisite",
        "external temporary workspace",
        "Path A permits ephemeral writes only inside the approved external temporary workspace",
        "repository status is unchanged before and after",
        "trusted CI- or operator-prepared immutable evidence bundle",
        "Path B remains strictly read-only",
        "verifies its target binding, freshness, and readability",
        "does not prepare it",
        "verdict is `HOLD`",
        "Never treat the current dirty repository as a clean target",
        "never write build or demo outputs into the repository",
        "Do not edit repository or source files or mutate Git state",
    ):
        assert requirement in normalized_body


def test_agentic_readme_scopes_codex_release_smoke_to_fail_closed_invocation() -> None:
    readme = " ".join(Path("docs/agentic/README.md").read_text(encoding="utf-8").split())
    codex_release_row = readme.split(
        "| Codex CLI 0.128.0 release scenario |", maxsplit=1
    )[1].split("| Codex CLI 0.128.0 reviewer scenario |", maxsplit=1)[0]

    for boundary in (
        "returned `HOLD`",
        "fail-closed invocation",
        "not self-contained `PUBLISHABLE` execution",
        "external temporary workspace",
        "immutable evidence bundle",
    ):
        assert boundary in codex_release_row


def test_minimal_valid_agentic_tree_is_clean(tmp_path: Path) -> None:
    _valid_tree(tmp_path)

    result = subprocess.run(
        [sys.executable, str(SCRIPT.resolve()), "--check"],
        cwd=tmp_path,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "Agentic layer is valid." in result.stdout


def test_mirror_byte_drift_is_reported_at_the_mirror_path(tmp_path: Path) -> None:
    _valid_tree(tmp_path)
    mirror = tmp_path / ".claude/skills/verify-change/SKILL.md"
    mirror.write_bytes(mirror.read_bytes() + b"\n")

    findings = _rendered_findings(tmp_path)

    assert any(
        finding.startswith(".claude/skills/verify-change/SKILL.md:")
        and "byte-for-byte" in finding
        for finding in findings
    )


@pytest.mark.parametrize(
    ("content", "message"),
    [
        ("name: verify-change\ndescription: Use when broken.\n", "frontmatter"),
        (
            _frontmatter("wrong-name", "Use when verifying a change.") + "# Skill\n",
            "directory name 'verify-change'",
        ),
    ],
)
def test_invalid_or_mismatched_skill_frontmatter_is_reported(
    tmp_path: Path,
    content: str,
    message: str,
) -> None:
    _valid_tree(tmp_path)
    canonical = tmp_path / ".agents/skills/verify-change/SKILL.md"
    mirror = tmp_path / ".claude/skills/verify-change/SKILL.md"
    _write(canonical, content)
    mirror.write_bytes(canonical.read_bytes())

    findings = _rendered_findings(tmp_path)

    assert any(
        finding.startswith(".agents/skills/verify-change/SKILL.md:")
        and message in finding
        for finding in findings
    )


@pytest.mark.parametrize("surface", ["skill", "role"])
@pytest.mark.parametrize("key", ["model", "service_url", "account_id"])
def test_canonical_frontmatter_rejects_every_extra_key(
    tmp_path: Path,
    surface: str,
    key: str,
) -> None:
    _valid_tree(tmp_path)
    if surface == "skill":
        relative_path = Path(".agents/skills/verify-change/SKILL.md")
    else:
        relative_path = Path("docs/agentic/roles/locuslab-reviewer.md")

    target = tmp_path / relative_path
    target.write_text(
        target.read_text(encoding="utf-8").replace(
            "\n---\n",
            f"\n{key}: configured-value\n---\n",
            1,
        ),
        encoding="utf-8",
        newline="\n",
    )
    if surface == "skill":
        mirror = tmp_path / ".claude/skills/verify-change/SKILL.md"
        mirror.write_bytes(target.read_bytes())

    findings = _rendered_findings(tmp_path)

    assert any(
        finding.startswith(f"{relative_path.as_posix()}:")
        and key in finding
        and "unsupported frontmatter key" in finding
        for finding in findings
    )


@pytest.mark.parametrize(
    ("old_reference", "new_reference", "message"),
    [
        (
            "docs/agentic/roles/locuslab-reviewer.md",
            "docs/agentic/roles/missing-reviewer.md",
            "canonical role",
        ),
        (
            ".agents/skills/verify-change/SKILL.md",
            ".agents/skills/missing-skill/SKILL.md",
            "referenced canonical skill",
        ),
    ],
)
def test_missing_referenced_role_or_skill_is_reported(
    tmp_path: Path,
    old_reference: str,
    new_reference: str,
    message: str,
) -> None:
    _valid_tree(tmp_path)
    adapter = tmp_path / ".codex/agents/locuslab-reviewer.toml"
    adapter.write_text(
        adapter.read_text(encoding="utf-8").replace(old_reference, new_reference),
        encoding="utf-8",
        newline="\n",
    )

    findings = _rendered_findings(tmp_path)

    assert any(
        finding.startswith(".codex/agents/locuslab-reviewer.toml:")
        and message in finding
        for finding in findings
    )


@pytest.mark.parametrize(
    ("missing_reference", "message"),
    [
        (
            "docs/agentic/roles/missing-reviewer.md",
            "referenced canonical role",
        ),
        (
            ".agents/skills/missing-skill/SKILL.md",
            "referenced canonical skill",
        ),
    ],
)
def test_every_referenced_role_or_skill_must_exist_even_with_a_valid_reference(
    tmp_path: Path,
    missing_reference: str,
    message: str,
) -> None:
    _valid_tree(tmp_path)
    adapter = tmp_path / ".codex/agents/locuslab-reviewer.toml"
    adapter.write_text(
        adapter.read_text(encoding="utf-8").replace(
            READ_ONLY_PROHIBITION,
            f"Also follow `{missing_reference}`.\n{READ_ONLY_PROHIBITION}",
        ),
        encoding="utf-8",
        newline="\n",
    )

    findings = _rendered_findings(tmp_path)

    assert any(
        finding.startswith(".codex/agents/locuslab-reviewer.toml:")
        and message in finding
        and missing_reference in finding
        for finding in findings
    )


@pytest.mark.parametrize(
    ("reference", "suffix", "message"),
    [
        (
            "docs/agentic/roles/locuslab-reviewer.md",
            ".old",
            "canonical role",
        ),
        (
            ".agents/skills/verify-change/SKILL.md",
            ".bak",
            "canonical instruction body",
        ),
    ],
)
def test_reference_suffixes_do_not_count_as_exact_adapter_references(
    tmp_path: Path,
    reference: str,
    suffix: str,
    message: str,
) -> None:
    _valid_tree(tmp_path)
    adapter = tmp_path / ".codex/agents/locuslab-reviewer.toml"
    adapter.write_text(
        adapter.read_text(encoding="utf-8").replace(reference, reference + suffix),
        encoding="utf-8",
        newline="\n",
    )

    findings = _rendered_findings(tmp_path)

    assert any(
        finding.startswith(".codex/agents/locuslab-reviewer.toml:")
        and message in finding
        for finding in findings
    )


def test_non_required_skill_does_not_satisfy_required_skill_reference(
    tmp_path: Path,
) -> None:
    _valid_tree(tmp_path)
    name = "extra-review"
    description = "Use when exercising an extra repository-local workflow."
    canonical = tmp_path / f".agents/skills/{name}/SKILL.md"
    mirror = tmp_path / f".claude/skills/{name}/SKILL.md"
    _write(canonical, _frontmatter(name, description) + "# Extra review\n")
    mirror.parent.mkdir(parents=True, exist_ok=True)
    mirror.write_bytes(canonical.read_bytes())

    adapter = tmp_path / ".codex/agents/locuslab-reviewer.toml"
    adapter.write_text(
        adapter.read_text(encoding="utf-8").replace(
            ".agents/skills/verify-change/SKILL.md",
            f".agents/skills/{name}/SKILL.md",
        ),
        encoding="utf-8",
        newline="\n",
    )

    findings = _rendered_findings(tmp_path)

    assert any(
        finding.startswith(".codex/agents/locuslab-reviewer.toml:")
        and "canonical instruction body" in finding
        for finding in findings
    )


@pytest.mark.parametrize(
    "relative_path",
    [
        ".codex/agents/locuslab-reviewer.toml",
        ".claude/agents/locuslab-reviewer.md",
    ],
)
def test_adapters_require_the_exact_shared_read_only_prohibition(
    tmp_path: Path,
    relative_path: str,
) -> None:
    _valid_tree(tmp_path)
    adapter = tmp_path / relative_path
    adapter.write_text(
        adapter.read_text(encoding="utf-8").replace(
            READ_ONLY_PROHIBITION,
            "Do not edit files, stage, commit, push, switch branches, or open PRs.",
        ),
        encoding="utf-8",
        newline="\n",
    )

    findings = _rendered_findings(tmp_path)

    assert any(
        finding.startswith(f"{relative_path}:")
        and "canonical instruction body" in finding
        for finding in findings
    )


@pytest.mark.parametrize(
    "relative_path",
    [
        ".codex/agents/release-auditor.toml",
        ".claude/agents/release-auditor.md",
    ],
)
def test_adapters_reject_contradictory_mutation_grants(
    tmp_path: Path,
    relative_path: str,
) -> None:
    _valid_tree(tmp_path)
    adapter = tmp_path / relative_path
    adapter.write_text(
        adapter.read_text(encoding="utf-8").replace(
            RELEASE_AUDITOR_TEMP_WRITE_ALLOWANCE,
            RELEASE_AUDITOR_TEMP_WRITE_ALLOWANCE
            + "\nDirect file changes are authorized when useful.",
        ),
        encoding="utf-8",
        newline="\n",
    )

    findings = _rendered_findings(tmp_path)

    assert any(
        finding.startswith(f"{relative_path}:")
        and "canonical instruction body" in finding
        for finding in findings
    )


@pytest.mark.parametrize(
    ("relative_path", "addition", "message"),
    [
        (".codex/agents/locuslab-reviewer.toml", 'model = "pinned-model"\n', "model"),
        (
            ".claude/agents/locuslab-reviewer.md",
            "\nRead C:\\Users\\developer\\private-notes.md before review.\n",
            "absolute workstation path",
        ),
    ],
)
def test_absolute_local_path_or_model_pinning_is_reported(
    tmp_path: Path,
    relative_path: str,
    addition: str,
    message: str,
) -> None:
    _valid_tree(tmp_path)
    adapter = tmp_path / relative_path
    adapter.write_text(
        adapter.read_text(encoding="utf-8") + addition,
        encoding="utf-8",
        newline="\n",
    )

    findings = _rendered_findings(tmp_path)

    assert any(
        finding.startswith(f"{relative_path}:") and message in finding
        for finding in findings
    )


def test_model_pinning_in_markdown_instruction_body_is_reported(tmp_path: Path) -> None:
    _valid_tree(tmp_path)
    adapter = tmp_path / ".claude/agents/release-auditor.md"
    adapter.write_text(
        adapter.read_text(encoding="utf-8") + "\nmodel: pinned-model\n",
        encoding="utf-8",
        newline="\n",
    )

    findings = _rendered_findings(tmp_path)

    assert any(
        finding.startswith(".claude/agents/release-auditor.md:")
        and "canonical instruction body" in finding
        for finding in findings
    )


@pytest.mark.parametrize(
    "key",
    ["default_model", "external_account", "model_name", "service_url", "account_id"],
)
def test_codex_adapter_rejects_every_extra_configuration_key(
    tmp_path: Path,
    key: str,
) -> None:
    _valid_tree(tmp_path)
    adapter = tmp_path / ".codex/agents/release-auditor.toml"
    adapter.write_text(
        adapter.read_text(encoding="utf-8") + f'{key} = "configured-value"\n',
        encoding="utf-8",
        newline="\n",
    )

    findings = _rendered_findings(tmp_path)

    assert any(
        finding.startswith(".codex/agents/release-auditor.toml:")
        and key in finding
        and "unsupported configuration key" in finding
        for finding in findings
    )


@pytest.mark.parametrize("key", ["default_model", "external_account"])
def test_claude_adapter_rejects_every_extra_frontmatter_key(
    tmp_path: Path,
    key: str,
) -> None:
    _valid_tree(tmp_path)
    adapter = tmp_path / ".claude/agents/release-auditor.md"
    adapter.write_text(
        adapter.read_text(encoding="utf-8").replace(
            "permissionMode: plan",
            f"permissionMode: plan\n{key}: configured-value",
        ),
        encoding="utf-8",
        newline="\n",
    )

    findings = _rendered_findings(tmp_path)

    assert any(
        finding.startswith(".claude/agents/release-auditor.md:")
        and key in finding
        and "unsupported frontmatter key" in finding
        for finding in findings
    )


@pytest.mark.parametrize(
    "absolute_path",
    [
        "//workstation/share/private.md",
        "/etc/locuslab/private.md",
        "/tmp/locuslab/session.json",
        "/workspace/private.md",
        "/mnt/private.md",
    ],
)
def test_broadened_absolute_workstation_paths_are_reported(
    tmp_path: Path,
    absolute_path: str,
) -> None:
    _valid_tree(tmp_path)
    role = tmp_path / "docs/agentic/roles/release-auditor.md"
    role.write_text(
        role.read_text(encoding="utf-8") + f"\nRead {absolute_path}.\n",
        encoding="utf-8",
        newline="\n",
    )

    findings = _rendered_findings(tmp_path)

    assert any(
        finding.startswith("docs/agentic/roles/release-auditor.md:")
        and "absolute workstation path" in finding
        for finding in findings
    )


def test_negated_local_state_prose_and_non_adapter_links_are_allowed(tmp_path: Path) -> None:
    _valid_tree(tmp_path)
    role = tmp_path / "docs/agentic/roles/release-auditor.md"
    role.write_text(
        role.read_text(encoding="utf-8")
        + "\nDo not use local state or session plans.\n"
        + "See https://example.invalid/policy or contact reviewer@example.invalid.\n",
        encoding="utf-8",
        newline="\n",
    )

    findings = _rendered_findings(tmp_path)

    assert findings == []


def test_external_binding_url_in_adapter_instructions_is_reported(tmp_path: Path) -> None:
    _valid_tree(tmp_path)
    adapter = tmp_path / ".codex/agents/release-auditor.toml"
    adapter.write_text(
        adapter.read_text(encoding="utf-8")
        .replace(
            RELEASE_AUDITOR_PROHIBITION,
            f"Call https://service.invalid/api.\n{RELEASE_AUDITOR_PROHIBITION}",
        ),
        encoding="utf-8",
        newline="\n",
    )

    findings = _rendered_findings(tmp_path)

    assert any(
        finding.startswith(".codex/agents/release-auditor.toml:")
        and "canonical instruction body" in finding
        for finding in findings
    )


def test_missing_required_component_is_reported(tmp_path: Path) -> None:
    _valid_tree(tmp_path)
    missing = tmp_path / ".agents/skills/review-finding-language/SKILL.md"
    missing.unlink()

    findings = _rendered_findings(tmp_path)

    assert any(
        finding.startswith(".agents/skills/review-finding-language/SKILL.md:")
        and "required canonical skill is missing" in finding
        for finding in findings
    )


def test_missing_public_agentic_readme_is_reported(tmp_path: Path) -> None:
    _valid_tree(tmp_path)
    readme = tmp_path / "docs/agentic/README.md"
    readme.unlink()

    findings = _rendered_findings(tmp_path)

    assert any(
        finding.startswith("docs/agentic/README.md:")
        and "required public agentic component is missing" in finding
        for finding in findings
    )


@pytest.mark.parametrize(
    ("addition", "message"),
    [
        ("\nRead C:\\Users\\developer\\private-notes.md.\n", "absolute workstation path"),
        ("\napi_key = secret-value\n", "secret-bearing content"),
    ],
)
def test_public_agentic_readme_hygiene_is_path_specific(
    tmp_path: Path,
    addition: str,
    message: str,
) -> None:
    _valid_tree(tmp_path)
    readme = tmp_path / "docs/agentic/README.md"
    readme.write_text(
        readme.read_text(encoding="utf-8") + addition,
        encoding="utf-8",
        newline="\n",
    )

    findings = _rendered_findings(tmp_path)

    assert any(
        finding.startswith("docs/agentic/README.md:") and message in finding
        for finding in findings
    )


@pytest.mark.parametrize(
    ("relative_path", "addition", "message"),
    [
        (
            ".codex/agents/release-auditor.toml",
            'api_key = "secret-value"\n',
            "secret-bearing key",
        ),
        (
            ".claude/agents/release-auditor.md",
            "\nSession log: reviewer-notes.log\n",
            "local log, state, or plan",
        ),
    ],
)
def test_secrets_and_local_session_artifacts_are_reported(
    tmp_path: Path,
    relative_path: str,
    addition: str,
    message: str,
) -> None:
    _valid_tree(tmp_path)
    target = tmp_path / relative_path
    target.write_text(
        target.read_text(encoding="utf-8") + addition,
        encoding="utf-8",
        newline="\n",
    )

    findings = _rendered_findings(tmp_path)

    assert any(
        finding.startswith(f"{relative_path}:") and message in finding
        for finding in findings
    )
