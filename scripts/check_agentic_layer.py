from __future__ import annotations

import argparse
import re
import tomllib
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

REQUIRED_SKILLS = (
    "verify-change",
    "audit-release",
    "review-finding-language",
)
REQUIRED_ROLES = (
    "locuslab-reviewer",
    "release-auditor",
)
ROLE_SKILLS = {
    "locuslab-reviewer": ("verify-change", "review-finding-language"),
    "release-auditor": ("audit-release",),
}

CANONICAL_SKILL_ROOT = Path(".agents/skills")
MIRRORED_SKILL_ROOT = Path(".claude/skills")
ROLE_ROOT = Path("docs/agentic/roles")
CODEX_ADAPTER_ROOT = Path(".codex/agents")
CLAUDE_ADAPTER_ROOT = Path(".claude/agents")
REQUIRED_PUBLIC_COMPONENTS = (Path("docs/agentic/README.md"),)

AGENTIC_ROOTS = (
    CANONICAL_SKILL_ROOT,
    MIRRORED_SKILL_ROOT,
    ROLE_ROOT,
    CODEX_ADAPTER_ROOT,
    CLAUDE_ADAPTER_ROOT,
)

LOWERCASE_HYPHEN_NAME_RE = re.compile(r"^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$")
FRONTMATTER_SCALAR_RE = re.compile(
    r"^(?P<key>[A-Za-z][A-Za-z0-9_-]*):\s*(?P<value>.*?)\s*$"
)
CANONICAL_SKILL_REFERENCE_RE = re.compile(
    r"(?<![A-Za-z0-9._/-])"
    r"\.agents/skills/(?P<name>[a-z][a-z0-9-]*)/SKILL\.md"
    r"(?![A-Za-z0-9._/-])"
)
CANONICAL_ROLE_REFERENCE_RE = re.compile(
    r"(?<![A-Za-z0-9._/-])"
    r"docs/agentic/roles/(?P<name>[a-z][a-z0-9-]*)\.md"
    r"(?![A-Za-z0-9._/-])"
)
ABSOLUTE_WORKSTATION_PATH_RE = re.compile(
    r"(?i)(?<![A-Za-z0-9._/\\:>])(?:"
    r"[A-Z]:[\\/]|"
    r"\\\\[^\s\\/]+[\\/]|"
    r"//[^\s\\/]+/|"
    r"/[A-Za-z0-9._~-]"
    r")"
)
SECRET_CONTENT_RE = re.compile(
    r"(?im)(?:"
    r"-----BEGIN [A-Z ]*PRIVATE KEY-----|"
    r"\b(?:api[_-]?key|access[_-]?token|password|client[_-]?secret|credential)"
    r"\s*[:=]\s*[^\s]+|"
    r"\b(?:AKIA[0-9A-Z]{16}|ghp_[A-Za-z0-9]{20,}|sk-[A-Za-z0-9]{20,})\b"
    r")"
)
LOCAL_ARTIFACT_PATH_RE = re.compile(
    r"(?i)(?<![A-Za-z0-9._/-])(?:"
    r"(?:\.claude[\\/])?plans?[\\/][^\s`'\"]+|"
    r"logs?[\\/][^\s`'\"]+|"
    r"state[\\/][^\s`'\"]+|"
    r"[A-Za-z0-9_.-]+\.log\b"
    r")"
)
SECRET_KEY_RE = re.compile(
    r"(?i)(?:secret|password|credential|api[_-]?key|access[_-]?token|private[_-]?key)"
)
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
CODEX_ADAPTER_KEYS = frozenset(
    {"name", "description", "sandbox_mode", "developer_instructions"}
)
CLAUDE_ADAPTER_KEYS = frozenset({"name", "description", "permissionMode"})
SKILL_FRONTMATTER_KEYS = frozenset({"name", "description"})
ROLE_FRONTMATTER_KEYS = frozenset({"name", "description"})


@dataclass(frozen=True)
class Finding:
    path: Path
    message: str

    def render(self) -> str:
        return f"{self.path.as_posix()}: {self.message}"


@dataclass(frozen=True)
class RoleSpec:
    name: str
    description: str


def parse_frontmatter(text: str) -> tuple[dict[str, str], str]:
    """Parse a YAML-frontmatter subset containing only single-line scalars."""
    lines = text.splitlines()
    if not lines or lines[0] != "---":
        raise ValueError("YAML frontmatter must start with '---'")

    try:
        closing_index = lines.index("---", 1)
    except ValueError as error:
        raise ValueError("YAML frontmatter is missing its closing '---'") from error

    values: dict[str, str] = {}
    for line in lines[1:closing_index]:
        if not line.strip():
            continue
        match = FRONTMATTER_SCALAR_RE.fullmatch(line)
        if match is None:
            raise ValueError(f"unsupported YAML frontmatter line: {line!r}")
        key = match.group("key")
        if key in values:
            raise ValueError(f"duplicate YAML frontmatter key: {key}")
        value = match.group("value")
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
            value = value[1:-1]
        if not value:
            raise ValueError(f"YAML frontmatter key '{key}' needs a scalar value")
        values[key] = value

    body = "\n".join(lines[closing_index + 1 :])
    return values, body


def _read_text(root: Path, relative_path: Path) -> tuple[str | None, list[Finding]]:
    try:
        return (root / relative_path).read_text(encoding="utf-8"), []
    except (OSError, UnicodeError) as error:
        return None, [Finding(relative_path, f"cannot read UTF-8 text: {error}")]


def _parse_frontmatter_file(
    root: Path, relative_path: Path
) -> tuple[dict[str, str] | None, str, list[Finding]]:
    text, findings = _read_text(root, relative_path)
    if text is None:
        return None, "", findings
    try:
        frontmatter, body = parse_frontmatter(text)
    except ValueError as error:
        return None, "", [Finding(relative_path, f"invalid YAML frontmatter: {error}")]
    return frontmatter, body, []


def _relative_files(root: Path, relative_root: Path) -> dict[Path, Path]:
    full_root = root / relative_root
    if not full_root.is_dir():
        return {}
    return {
        path.relative_to(full_root): path
        for path in sorted(full_root.rglob("*"))
        if path.is_file()
    }


def _check_skill_mirror(root: Path) -> list[Finding]:
    findings: list[Finding] = []
    canonical_files = _relative_files(root, CANONICAL_SKILL_ROOT)
    mirrored_files = _relative_files(root, MIRRORED_SKILL_ROOT)

    for relative_path in sorted(canonical_files.keys() - mirrored_files.keys()):
        findings.append(
            Finding(
                MIRRORED_SKILL_ROOT / relative_path,
                f"mirror is missing canonical file {CANONICAL_SKILL_ROOT / relative_path}",
            )
        )
    for relative_path in sorted(mirrored_files.keys() - canonical_files.keys()):
        findings.append(
            Finding(
                MIRRORED_SKILL_ROOT / relative_path,
                "mirror file has no canonical counterpart",
            )
        )
    for relative_path in sorted(canonical_files.keys() & mirrored_files.keys()):
        try:
            matches = canonical_files[relative_path].read_bytes() == mirrored_files[
                relative_path
            ].read_bytes()
        except OSError as error:
            findings.append(
                Finding(MIRRORED_SKILL_ROOT / relative_path, f"cannot compare bytes: {error}")
            )
            continue
        if not matches:
            findings.append(
                Finding(
                    MIRRORED_SKILL_ROOT / relative_path,
                    f"must match {CANONICAL_SKILL_ROOT / relative_path} byte-for-byte",
                )
            )
    return findings


def _frontmatter_security_findings(
    path: Path, frontmatter: Mapping[str, str]
) -> list[Finding]:
    findings: list[Finding] = []
    for key in sorted(frontmatter):
        normalized = key.lower()
        if SECRET_KEY_RE.search(normalized):
            findings.append(Finding(path, f"obvious secret-bearing key '{key}' is forbidden"))
    return findings


def _check_skills(root: Path) -> tuple[set[str], list[Finding]]:
    findings = _check_skill_mirror(root)
    skill_names: set[str] = set()
    name_paths: dict[str, Path] = {}

    for required_name in REQUIRED_SKILLS:
        required_path = CANONICAL_SKILL_ROOT / required_name / "SKILL.md"
        if not (root / required_path).is_file():
            findings.append(Finding(required_path, "required canonical skill is missing"))

    canonical_files = _relative_files(root, CANONICAL_SKILL_ROOT)
    skill_paths = sorted(
        CANONICAL_SKILL_ROOT / path
        for path in canonical_files
        if len(path.parts) == 2 and path.name == "SKILL.md"
    )
    for path in skill_paths:
        directory_name = path.parent.name
        if not LOWERCASE_HYPHEN_NAME_RE.fullmatch(directory_name):
            findings.append(
                Finding(path, "skill directory name must be lowercase-hyphen format")
            )

        frontmatter, _body, parse_findings = _parse_frontmatter_file(root, path)
        findings.extend(parse_findings)
        if frontmatter is None:
            continue
        findings.extend(_frontmatter_security_findings(path, frontmatter))
        for key in sorted(set(frontmatter) - SKILL_FRONTMATTER_KEYS):
            findings.append(Finding(path, f"unsupported frontmatter key '{key}'"))

        name = frontmatter.get("name")
        description = frontmatter.get("description")
        if name is None:
            findings.append(Finding(path, "skill frontmatter requires scalar 'name'"))
        elif name != directory_name:
            findings.append(
                Finding(
                    path,
                    f"skill name '{name}' must match directory name '{directory_name}'",
                )
            )
        elif not LOWERCASE_HYPHEN_NAME_RE.fullmatch(name):
            findings.append(Finding(path, "skill name must be lowercase-hyphen format"))
        else:
            if name in name_paths:
                findings.append(
                    Finding(path, f"skill name '{name}' is also declared by {name_paths[name]}")
                )
            else:
                name_paths[name] = path
                skill_names.add(name)

        if description is None:
            findings.append(Finding(path, "skill frontmatter requires scalar 'description'"))
        elif not description.startswith("Use when"):
            findings.append(Finding(path, "skill description must begin with 'Use when'"))

    return skill_names, findings


def _check_roles(root: Path) -> tuple[dict[str, RoleSpec], list[Finding]]:
    findings: list[Finding] = []
    roles: dict[str, RoleSpec] = {}
    for role_name in REQUIRED_ROLES:
        path = ROLE_ROOT / f"{role_name}.md"
        if not (root / path).is_file():
            findings.append(Finding(path, "required canonical role spec is missing"))
            continue
        frontmatter, _body, parse_findings = _parse_frontmatter_file(root, path)
        findings.extend(parse_findings)
        if frontmatter is None:
            continue
        findings.extend(_frontmatter_security_findings(path, frontmatter))
        for key in sorted(set(frontmatter) - ROLE_FRONTMATTER_KEYS):
            findings.append(Finding(path, f"unsupported frontmatter key '{key}'"))
        name = frontmatter.get("name")
        description = frontmatter.get("description")
        if name != role_name:
            findings.append(
                Finding(path, f"role name must be '{role_name}', found {name!r}")
            )
        if not description:
            findings.append(Finding(path, "role frontmatter requires scalar 'description'"))
        if name == role_name and description:
            roles[role_name] = RoleSpec(name=name, description=description)
    return roles, findings


def _nested_keys(value: object) -> list[str]:
    keys: list[str] = []
    if isinstance(value, Mapping):
        for key, nested_value in value.items():
            if isinstance(key, str):
                keys.append(key)
            keys.extend(_nested_keys(nested_value))
    elif isinstance(value, list):
        for nested_value in value:
            keys.extend(_nested_keys(nested_value))
    return keys


def _toml_security_findings(path: Path, data: Mapping[str, object]) -> list[Finding]:
    findings: list[Finding] = []
    for key in sorted(set(_nested_keys(data))):
        normalized = key.lower()
        if SECRET_KEY_RE.search(normalized):
            findings.append(Finding(path, f"obvious secret-bearing key '{key}' is forbidden"))
    return findings


def _reference_findings(
    root: Path,
    path: Path,
    role_name: str,
    instructions: str,
) -> list[Finding]:
    findings: list[Finding] = []
    role_reference = (ROLE_ROOT / f"{role_name}.md").as_posix()
    referenced_roles = {
        match.group(0) for match in CANONICAL_ROLE_REFERENCE_RE.finditer(instructions)
    }
    if role_reference not in referenced_roles:
        findings.append(
            Finding(path, f"adapter must reference canonical role '{role_reference}'")
        )
    elif not (root / role_reference).is_file():
        findings.append(Finding(path, f"referenced canonical role '{role_reference}' is missing"))

    for referenced_role in sorted(referenced_roles):
        if not (root / referenced_role).is_file():
            findings.append(
                Finding(path, f"referenced canonical role '{referenced_role}' is missing")
            )

    referenced_skill_paths = {
        match.group(0): match.group("name")
        for match in CANONICAL_SKILL_REFERENCE_RE.finditer(instructions)
    }
    for referenced_path in sorted(referenced_skill_paths):
        if not (root / referenced_path).is_file():
            findings.append(
                Finding(path, f"referenced canonical skill '{referenced_path}' is missing")
            )

    referenced_skills = set(referenced_skill_paths.values())
    for required_skill in ROLE_SKILLS.get(role_name, ()):
        if required_skill not in referenced_skills:
            findings.append(
                Finding(path, f"adapter must reference required canonical skill '{required_skill}'")
            )
    return findings


def _identity_findings(
    path: Path,
    role_name: str,
    expected_role: RoleSpec | None,
    declared_name: object,
    declared_description: object,
) -> list[Finding]:
    findings: list[Finding] = []
    if expected_role is None:
        findings.append(Finding(path, f"corresponding canonical role '{role_name}' is unavailable"))
        return findings
    if declared_name != expected_role.name:
        findings.append(
            Finding(path, f"adapter name must be '{expected_role.name}', found {declared_name!r}")
        )
    if declared_description != expected_role.description:
        findings.append(
            Finding(path, "adapter description must exactly match its canonical role")
        )
    return findings


def expected_instructions(role_name: str) -> str | None:
    """Return the canonical normalized adapter instructions for a required role."""
    skill_names = ROLE_SKILLS.get(role_name)
    if skill_names is None:
        return None
    lines = [f"Canonical role: {(ROLE_ROOT / f'{role_name}.md').as_posix()}"]
    lines.extend(
        f"Required skill: {(CANONICAL_SKILL_ROOT / name / 'SKILL.md').as_posix()}"
        for name in skill_names
    )
    lines.extend(ROLE_INSTRUCTION_SUFFIXES[role_name])
    return "\n".join(lines)


def _instruction_template_findings(
    path: Path, role_name: str, instructions: str
) -> list[Finding]:
    expected = expected_instructions(role_name)
    if expected is None:
        return [Finding(path, f"no canonical instruction body exists for role '{role_name}'")]
    if instructions.strip() != expected:
        return [Finding(path, "adapter must use the exact canonical instruction body")]
    return []


def _check_codex_adapter(
    root: Path,
    path: Path,
    roles: Mapping[str, RoleSpec],
) -> list[Finding]:
    text, findings = _read_text(root, path)
    if text is None:
        return findings
    try:
        data = tomllib.loads(text)
    except tomllib.TOMLDecodeError as error:
        return [Finding(path, f"invalid TOML adapter: {error}")]

    role_name = path.stem
    findings.extend(_toml_security_findings(path, data))
    for key in sorted(set(data) - CODEX_ADAPTER_KEYS):
        findings.append(Finding(path, f"unsupported configuration key '{key}'"))
    findings.extend(
        _identity_findings(
            path,
            role_name,
            roles.get(role_name),
            data.get("name"),
            data.get("description"),
        )
    )
    if data.get("sandbox_mode") != "read-only":
        findings.append(Finding(path, "Codex adapter requires sandbox_mode = 'read-only'"))
    instructions = data.get("developer_instructions")
    if not isinstance(instructions, str) or not instructions.strip():
        findings.append(Finding(path, "Codex adapter requires developer_instructions text"))
    else:
        findings.extend(_reference_findings(root, path, role_name, instructions))
        findings.extend(_instruction_template_findings(path, role_name, instructions))
    return findings


def _check_claude_adapter(
    root: Path,
    path: Path,
    roles: Mapping[str, RoleSpec],
) -> list[Finding]:
    frontmatter, body, findings = _parse_frontmatter_file(root, path)
    if frontmatter is None:
        return findings

    role_name = path.stem
    findings.extend(_frontmatter_security_findings(path, frontmatter))
    for key in sorted(set(frontmatter) - CLAUDE_ADAPTER_KEYS):
        findings.append(Finding(path, f"unsupported frontmatter key '{key}'"))
    findings.extend(
        _identity_findings(
            path,
            role_name,
            roles.get(role_name),
            frontmatter.get("name"),
            frontmatter.get("description"),
        )
    )
    if frontmatter.get("permissionMode") != "plan":
        findings.append(Finding(path, "Claude adapter requires permissionMode: plan"))
    findings.extend(_reference_findings(root, path, role_name, body))
    findings.extend(_instruction_template_findings(path, role_name, body))
    return findings


def _check_adapters(root: Path, roles: Mapping[str, RoleSpec]) -> list[Finding]:
    findings: list[Finding] = []
    for role_name in REQUIRED_ROLES:
        codex_path = CODEX_ADAPTER_ROOT / f"{role_name}.toml"
        claude_path = CLAUDE_ADAPTER_ROOT / f"{role_name}.md"
        if not (root / codex_path).is_file():
            findings.append(Finding(codex_path, "required Codex role adapter is missing"))
        if not (root / claude_path).is_file():
            findings.append(Finding(claude_path, "required Claude role adapter is missing"))

    codex_files = _relative_files(root, CODEX_ADAPTER_ROOT)
    for relative_path in sorted(path for path in codex_files if path.suffix == ".toml"):
        path = CODEX_ADAPTER_ROOT / relative_path
        findings.extend(_check_codex_adapter(root, path, roles))

    claude_files = _relative_files(root, CLAUDE_ADAPTER_ROOT)
    for relative_path in sorted(path for path in claude_files if path.suffix == ".md"):
        path = CLAUDE_ADAPTER_ROOT / relative_path
        findings.extend(_check_claude_adapter(root, path, roles))
    return findings


def _content_hygiene_findings(path: Path, text: str) -> list[Finding]:
    findings: list[Finding] = []
    if ABSOLUTE_WORKSTATION_PATH_RE.search(text):
        findings.append(Finding(path, "absolute workstation path is forbidden"))
    if SECRET_CONTENT_RE.search(text):
        findings.append(Finding(path, "obvious secret-bearing content is forbidden"))
    if LOCAL_ARTIFACT_PATH_RE.search(text) or LOCAL_ARTIFACT_PATH_RE.search(path.as_posix()):
        findings.append(Finding(path, "local log, state, or plan content is forbidden"))
    return findings


def _check_required_public_components(root: Path) -> list[Finding]:
    return [
        Finding(path, "required public agentic component is missing")
        for path in REQUIRED_PUBLIC_COMPONENTS
        if not (root / path).is_file()
    ]


def _check_surface_hygiene(root: Path) -> list[Finding]:
    findings: list[Finding] = []
    visited: set[Path] = set()
    for surface_root in AGENTIC_ROOTS:
        for relative_path in sorted(_relative_files(root, surface_root)):
            path = surface_root / relative_path
            if path in visited:
                continue
            visited.add(path)
            text, read_findings = _read_text(root, path)
            findings.extend(read_findings)
            if text is not None:
                findings.extend(_content_hygiene_findings(path, text))
    for path in REQUIRED_PUBLIC_COMPONENTS:
        if path in visited or not (root / path).is_file():
            continue
        text, read_findings = _read_text(root, path)
        findings.extend(read_findings)
        if text is not None:
            findings.extend(_content_hygiene_findings(path, text))
    return findings


def collect_findings(root: Path) -> list[Finding]:
    """Return deterministic, path-specific validation findings for ``root``."""
    _canonical_skills, skill_findings = _check_skills(root)
    roles, role_findings = _check_roles(root)
    findings = [
        *skill_findings,
        *role_findings,
        *_check_required_public_components(root),
        *_check_adapters(root, roles),
        *_check_surface_hygiene(root),
    ]
    return sorted(set(findings), key=lambda finding: (finding.path.as_posix(), finding.message))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Validate the public, deterministic agentic development layer."
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="check the agentic layer and exit non-zero on validation findings",
    )
    parser.parse_args(argv)

    findings = collect_findings(Path.cwd())
    if findings:
        print("Agentic layer validation failed:")
        for finding in findings:
            print(f"- {finding.render()}")
        return 1

    print("Agentic layer is valid.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
