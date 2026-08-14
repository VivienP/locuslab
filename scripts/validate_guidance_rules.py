"""Phase 6A local validator entry point.

Loads guidance JSON files (source inventory, rule packs, feedback items)
and runs the offline validator. No network, no PDF parsing, no LLM.

Usage:
    python scripts/validate_guidance_rules.py \\
        --inventory docs/guidance/source_inventory.json \\
        --rules    docs/rules/guidance/sscp/rule_pack.json \\
        --feedback docs/rules/guidance/feedback_items.json

Exits 0 on a clean validation, non-zero (with issue list on stdout) on
any validation error.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Allow running the script directly via `python scripts/...` without an
# installed package (mirrors the pattern used by other scripts).
_SRC = Path(__file__).resolve().parent.parent / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from locuslab.guidance import validate_all  # noqa: E402


def _load_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="validate_guidance_rules",
        description="Validate Phase 6A guidance rule pack files (offline).",
    )
    parser.add_argument(
        "--inventory",
        type=Path,
        required=True,
        help="Path to docs/guidance/source_inventory.json",
    )
    parser.add_argument(
        "--rules",
        type=Path,
        action="append",
        default=None,
        help="Path to a rule pack JSON file (repeatable).",
    )
    parser.add_argument(
        "--feedback",
        type=Path,
        default=None,
        help="Path to docs/rules/guidance/feedback_items.json",
    )
    args = parser.parse_args(argv)

    if not args.inventory.is_file():
        sys.stderr.write(f"Inventory file not found: {args.inventory}\n")
        return 2

    inventory = _load_json(args.inventory)

    rule_packs: list[dict[str, object]] = []
    for rules_path in args.rules or []:
        if not rules_path.is_file():
            sys.stderr.write(f"Rule pack file not found: {rules_path}\n")
            return 2
        rule_packs.append(_load_json(rules_path))

    feedback = None
    if args.feedback is not None:
        if not args.feedback.is_file():
            sys.stderr.write(f"Feedback file not found: {args.feedback}\n")
            return 2
        feedback = _load_json(args.feedback)

    issues = validate_all(
        inventory=inventory, rule_packs=rule_packs, feedback=feedback
    )

    n_sources = len(inventory.get("sources", []) or [])  # type: ignore[arg-type]
    n_rules = sum(len(p.get("rules", []) or []) for p in rule_packs)  # type: ignore[arg-type]
    n_feedback = (
        len(feedback.get("feedback_items", []) or []) if feedback else 0  # type: ignore[union-attr]
    )

    if issues:
        sys.stdout.write(
            f"Guidance validation FAILED: {len(issues)} issue(s) "
            f"({n_sources} sources, {len(rule_packs)} rule pack(s) with "
            f"{n_rules} rule(s), {n_feedback} feedback item(s)).\n"
        )
        for issue in issues:
            sys.stdout.write(f"  - {issue}\n")
        return 1

    sys.stdout.write(
        f"Guidance validation OK: validated {n_sources} source(s), "
        f"{len(rule_packs)} rule pack(s) with {n_rules} rule(s), "
        f"{n_feedback} feedback item(s).\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
