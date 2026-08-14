# Guidance Rule Packs

This directory holds versioned, source-backed rule packs that turn official
MDR / MDCG guidance into reviewed review rules.

The shipped SSCP pack evaluates four `RA_approved` deterministic rules during
`locus verify` on SSCP-routed dossiers. Output is `guidance_review.json` and
`guidance_review.md`. Those artifacts are human-review aids, not ECO findings
(`output_boundary: not_an_ECO_finding`).

Six additional SSCP rules remain `RA_pending`. No rule is promoted to an ECO
finding without a fixture-backed checker. See `docs/LIMITATIONS.md`.

## Layout

```text
docs/rules/guidance/
  README.md
  feedback_items.json
  sscp/
    README.md
    rule_pack.json
```

Companion file: `docs/guidance/source_inventory.json`.

## Validation

```bash
python scripts/validate_guidance_rules.py \
  --inventory docs/guidance/source_inventory.json \
  --rules    docs/rules/guidance/sscp/rule_pack.json \
  --feedback docs/rules/guidance/feedback_items.json
```

Exit 0 = clean; non-zero exit prints the issue list.

## Non-goals (V1)

- No LLM, no network, no PDF parsing at runtime for dossier verify.
- No final compliance / support / severity verdict from any source.
- No AI-assisted observation may be promoted to a deterministic ECO finding.
- No human-review-only or out-of-scope rule may carry an
  `implementation_status` other than `spec_only`.

The validator (`src/locuslab/guidance/validate.py`) enforces these boundaries.
