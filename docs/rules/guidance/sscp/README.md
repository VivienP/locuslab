# SSCP Guidance Rule Pack

`pack_id`: `guidance.sscp.v1`  
`pack_version`: `0.3.0`  
`pack_status`: `draft`  
`document_family`: `SSCP`

## State

MDCG 2019-9 Rev.1 (March 2022) is pinned locally (`ingestion_status:
uploaded_local`). Four deterministic rules are `RA_approved` with verbatim
excerpts:

- `guidance.sscp.required_section.intended_purpose`
- `guidance.sscp.required_section.device_description`
- `guidance.sscp.metadata.basic_udi_di_present`
- `guidance.sscp.metadata.notified_body_identifier`

Six subjective or conditional rules remain `RA_pending` with
`source_excerpt_pending: true`. All ten rules keep
`implementation_status: spec_only`.

On SSCP-routed `locus verify` runs the four approved rules are evaluated
against dossier spans (`observed_evidence` or `missing_candidate`). Pending
rules stay `not_evaluated`. Output is `guidance_review.json` and
`guidance_review.md`. No ECO finding is produced.

## Why SSCP first

- Public-facing document family, suitable for the synthetic demo path.
- Strong MDCG basis for structure, metadata, and source alignment.
- Many checks are deterministic (sections, Basic UDI-DI, notified-body
  identifier).

## Boundary discipline

- `automation_readiness: deterministic` may later become checker-backed ECO
  findings only with fixture-backed tests.
- `automation_readiness: ai_assisted_observation` stays a separate observation
  stream, never an ECO finding.
- `automation_readiness: human_review_only` stays a reviewer checklist.
- `automation_readiness: out_of_scope` is documented only.

The validator (`src/locuslab/guidance/validate.py`) enforces these boundaries.
