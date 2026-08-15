---
name: review-finding-language
description: Use when reviewing proposed or changed LocusLab finding evidence, remediation, provenance, or adjudication language.
---

# Review finding language

Review read-only. Do not edit files, fix findings, or mutate Git state; do not
stage, commit, push, switch branches, or open pull requests.

**Core principle:** A finding is not an approvable text fragment. Approval covers
the complete structured finding, its provenance, and its evidence boundary.

## Gate field completeness

Before approval, identify `eco_id`, `severity`, `checker_id`, `finding_type`,
`affected_object_ids`, `evidence`, `remediation_hint`, and
`adjudication_state`. Confirm `eco_id` matches the deterministic `make_eco_id`
derivation from the checker short token and sorted `affected_object_ids`.
Confirm severity is justified by the deterministic rule or attributable human
adjudication with event provenance, never model inference. When a generated
finding is presented, missing provenance fields or missing or invalid values
force `REJECT` or `NEEDS CONTEXT`, never a wording-only approval.

## Trace the finding

Inspect the actual deterministic rule and actual inputs, including the checker
function/version, affected objects, linking or extraction method, fixture or
test, and observed output. State the evidence boundary: what the rule proves and
what it does not. Keyword scanning is necessary but insufficient; review
equivalent overclaims and the relationship between every field.

An unresolved local link establishes a traceability gap, not truth, support, or
compliance. Guidance-review items remain non-ECO unless a fixture-backed
deterministic checker emits a finding. Human adjudication may be reported only
with event provenance and may not be laundered as checker output.

## Review language and proof

Scan evidence and remediation for banned or equivalent claims such as
`non-compliant`, `NB will reject` or `notified body will reject`, `unsupported`,
`must`, and `shall`. Reject them unless the deterministic rule truly establishes
the exact statement. Suggested replacements state only proven facts and preserve
object IDs and the observed method.

For changed finding behavior, run targeted checker and language tests and report
the exact result. An unrun or failing applicable test is not passing evidence.

## Decide

Use exactly one verdict under these disjoint rules:

- `APPROVE`: the finding is complete; inspected rule, inputs, test, and evidence
  boundary establish every statement; no unjustified overclaim remains; and
  applicable tests pass.
- `REJECT`: inspected evidence proves the proposed finding is incomplete,
  contradicts the deterministic rule or schema, crosses the evidence boundary,
  or contains an unjustified overclaim.
- `NEEDS CONTEXT`: required rule, input, provenance, event, fixture, or test
  cannot be inspected, so neither completeness nor a specific defect is proven.

## Report

- **Evidence boundary:** rule, inputs, method, fixture/test, proven scope.
- **Field completeness:** each required field and any omission.
- **Prohibited/equivalent language:** matches, equivalents, and replacements.
- **Tests:** exact commands/results or explicit omissions.
- **Decision:** one verdict with its controlling reason.
