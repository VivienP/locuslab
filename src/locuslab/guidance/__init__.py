"""Phase 6A — Guidance-backed rule pack foundation.

Pure-Python, offline. No network, no LLM, no PDF parsing. Defines the
data contract (schema constants) and the validator that catches boundary
violations the V1 guardrails care about (in particular: AI-assisted
observations cannot be promoted to deterministic findings).
"""

from locuslab.guidance.checklist import (
    CHECKLIST_SCHEMA_VERSION,
    OUTPUT_BOUNDARY,
    REVIEW_STATUS,
    build_checklist,
    render_markdown,
    write_checklist_outputs,
)
from locuslab.guidance.evaluate_sscp import (
    DETERMINISTIC_RULE_IDS,
    EVALUATION_METHOD_DETERMINISTIC,
    EVALUATION_METHOD_HUMAN,
    EVALUATION_STATUS_MISSING,
    EVALUATION_STATUS_NOT_EVALUATED,
    EVALUATION_STATUS_OBSERVED,
    evaluate_sscp_rules,
    is_sscp_run,
)
from locuslab.guidance.schema import (
    AUTOMATION_READINESS_VALUES,
    DOCUMENT_FAMILY_VALUES,
    FEEDBACK_CLASS_VALUES,
    FEEDBACK_STATUS_VALUES,
    IMPLEMENTATION_STATUS_VALUES,
    INGESTION_STATUS_VALUES,
    MODAL_STRENGTH_VALUES,
    PACK_STATUS_VALUES,
    RA_REVIEW_STATUS_VALUES,
    SOURCE_TYPE_VALUES,
)
from locuslab.guidance.validate import (
    GuidanceValidationError,
    validate_all,
    validate_feedback,
    validate_inventory,
    validate_rule_pack,
)

__all__ = [
    "AUTOMATION_READINESS_VALUES",
    "CHECKLIST_SCHEMA_VERSION",
    "DETERMINISTIC_RULE_IDS",
    "DOCUMENT_FAMILY_VALUES",
    "EVALUATION_METHOD_DETERMINISTIC",
    "EVALUATION_METHOD_HUMAN",
    "EVALUATION_STATUS_MISSING",
    "EVALUATION_STATUS_NOT_EVALUATED",
    "EVALUATION_STATUS_OBSERVED",
    "FEEDBACK_CLASS_VALUES",
    "FEEDBACK_STATUS_VALUES",
    "GuidanceValidationError",
    "IMPLEMENTATION_STATUS_VALUES",
    "INGESTION_STATUS_VALUES",
    "MODAL_STRENGTH_VALUES",
    "OUTPUT_BOUNDARY",
    "PACK_STATUS_VALUES",
    "RA_REVIEW_STATUS_VALUES",
    "REVIEW_STATUS",
    "SOURCE_TYPE_VALUES",
    "build_checklist",
    "evaluate_sscp_rules",
    "is_sscp_run",
    "render_markdown",
    "validate_all",
    "validate_feedback",
    "validate_inventory",
    "validate_rule_pack",
    "write_checklist_outputs",
]
