from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path

CURRENT_PHASE_RE = re.compile(r"^## Current Phase: (?P<phase>.+)$", re.MULTILINE)
PHASE_LABEL_RE = re.compile(r"Phase\s+\d+\s+-\s+[A-Za-z0-9 /&-]+")

LIVE_STATE_DOCS = (
    Path("README.md"),
    Path("docs/development_workflow.md"),
    Path("AI_CONTRACT.md"),
)

AGENT_GUIDES = (
    Path("AGENTS.md"),
    Path("CLAUDE.md"),
)

HOOKS: tuple[Path, ...] = ()


@dataclass(frozen=True)
class Finding:
    path: Path
    message: str

    def render(self) -> str:
        return f"{self.path.as_posix()}: {self.message}"


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def current_phase(root: Path) -> str:
    roadmap = root / "docs/roadmap.md"
    if not roadmap.is_file():
        raise FileNotFoundError("docs/roadmap.md is required")

    match = CURRENT_PHASE_RE.search(read_text(roadmap))
    if not match:
        raise ValueError("docs/roadmap.md must contain '## Current Phase: ...'")
    return match.group("phase").strip()


def phase_section(text: str) -> str | None:
    match = re.search(r"^## Current Phase\s*$", text, flags=re.MULTILINE)
    if not match:
        return None

    next_heading = re.search(r"^## ", text[match.end() :], flags=re.MULTILINE)
    section_end = match.end() + next_heading.start() if next_heading else len(text)
    return text[match.end() : section_end]


def check_live_state_doc(path: Path, text: str, canonical_phase: str) -> list[Finding]:
    findings: list[Finding] = []
    section = phase_section(text)
    if section is not None:
        labels = {label.strip() for label in PHASE_LABEL_RE.findall(section)}
        stale_labels = sorted(label for label in labels if label != canonical_phase)
        for label in stale_labels:
            findings.append(
                Finding(
                    path,
                    f"Current Phase section mentions stale '{label}', expected '{canonical_phase}'",
                )
            )
        if canonical_phase not in section:
            findings.append(
                Finding(
                    path,
                    f"Current Phase section does not mention canonical '{canonical_phase}'",
                )
            )

    if path == Path("README.md") and "Phase 0 repo bootstrap" in text:
        findings.append(
            Finding(
                path,
                "README still describes live project state as Phase 0; "
                f"expected '{canonical_phase}'",
            )
        )

    return findings


def check_agent_guides(root: Path) -> list[Finding]:
    findings: list[Finding] = []
    for path in AGENT_GUIDES:
        full_path = root / path
        if not full_path.is_file():
            findings.append(Finding(path, "required agent guide is missing"))
            continue
        text = read_text(full_path)
        if re.search(r"^## Current Phase\s*$", text, flags=re.MULTILINE) or re.search(
            r"^Current phase:", text, flags=re.MULTILINE
        ):
            findings.append(
                Finding(path, "must not hard-code current phase; point to docs/roadmap.md")
            )
        if "docs/roadmap.md" not in text:
            findings.append(Finding(path, "must reference docs/roadmap.md as the slice source"))
    return findings


def check_hooks(root: Path) -> list[Finding]:
    findings: list[Finding] = []
    for path in HOOKS:
        full_path = root / path
        if not full_path.is_file():
            continue
        text = read_text(full_path)
        if "docs/roadmap.md" not in text:
            findings.append(
                Finding(path, "session-start hook should read phase from docs/roadmap.md")
            )
        if 'Pattern "^Current phase:"' in text or 'grep -m1 "^Current phase:" "CLAUDE.md"' in text:
            findings.append(
                Finding(path, "session-start hook still reads stale phase text from CLAUDE.md")
            )
    return findings


def collect_findings(root: Path) -> tuple[str, list[Finding]]:
    canonical_phase = current_phase(root)
    findings: list[Finding] = []

    for path in LIVE_STATE_DOCS:
        full_path = root / path
        if not full_path.is_file():
            findings.append(Finding(path, "required live-state document is missing"))
            continue
        findings.extend(check_live_state_doc(path, read_text(full_path), canonical_phase))

    findings.extend(check_agent_guides(root))
    findings.extend(check_hooks(root))
    return canonical_phase, findings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Check that live project-state docs match docs/roadmap.md."
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="check docs and exit non-zero on drift",
    )
    parser.parse_args(argv)

    try:
        canonical_phase, findings = collect_findings(Path.cwd())
    except (FileNotFoundError, ValueError) as error:
        print(f"Project state docs check failed: {error}", file=sys.stderr)
        return 2

    if findings:
        print(f"Project state docs drift detected; canonical phase is '{canonical_phase}'.")
        for finding in findings:
            print(f"- {finding.render()}")
        return 1

    print(f"Project state docs are in sync: {canonical_phase}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
