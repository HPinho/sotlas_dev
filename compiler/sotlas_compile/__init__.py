"""Sotlas Compile — frontend canônico, segurança e lowering de produção."""

# Há uma única rota de compilação de produção: bootstrap + extensões oficiais +
# política de segurança/FFI. Ferramentas podem expor ASTs auxiliares, mas não
# podem possuir um segundo lowering ou uma segunda semântica executável.
from . import bootstrap as bootstrap
from .frontend_extensions import install as _install_frontend_extensions
from .language_safety import install as _install_language_safety
from .authority_frontend_safety import install as _install_authority_frontend_safety
from .authority_typed_ast import install as _install_authority_typed_ast
from .region_indirect_safety import install as _install_region_indirect_safety
from .region_method_safety import install as _install_region_method_safety
from .state_frontend import (
    StateSpaceFrontendPlan,
    analyze_state_space_coverage,
    install as _install_state_space_frontend,
    require_exhaustive_state_space_coverage,
)

_install_frontend_extensions(bootstrap)
_install_language_safety(bootstrap)
_install_region_indirect_safety(bootstrap)
_install_region_method_safety(bootstrap)
_install_authority_frontend_safety(bootstrap)
_install_authority_typed_ast(bootstrap)
# Phase 4 installs last so it wraps the final canonical parser/check/backend
# boundary rather than introducing a parallel language route.
_install_state_space_frontend(bootstrap)
from .source_effects import (
    SourceEffectError,
    SourceEffectSummary,
    analyze_source_effects,
    install_c11_backend_effect_contract as _install_c11_backend_effect_contract,
    install as _install_source_effects,
)
_install_source_effects(bootstrap)
plan_state_space_frontend = bootstrap.plan_state_space_frontend

from .errors import SotlasError
from .state_typed_ast import StateSpaceTypedSnapshot
from .state_sir import StateTransitionSIRError, lower_typestate_transition
from .flow_graph import (
    FlowDependency,
    FlowGraphError,
    FlowGraphPlan,
    FlowNode,
    certify_flow_graph,
)
from .flow_runtime import (
    FlowCancelledError,
    FlowExecutionError,
    FlowExecutionResult,
    execute_flow,
    execute_typed_flow,
    execute_bound_sir_flow,
)
from .flow_frontend import (
    FlowFrontendError,
    TypedFlowPlan,
    TypedFlowStage,
    plan_source_flows,
    install as _install_flow_frontend,
)
_install_flow_frontend(bootstrap)
from .flow_sir import (
    FlowSIRError,
    FlowSIRValueRef,
    FlowSIRArgument,
    FlowSIRStage,
    FlowSIRPlan,
    lower_typed_flows_to_sir,
    validate_sir_flow_plans,
)
from .causality import (
    CausalityError, CausalStep, CausalExplanation,
    SourceCallStep, SourceCallExplanation, explain_source_call_causality,
    explain_flow_causality, explain_sir_flow_causality,
)
from .counterfactuals import (
    CounterfactualError, CounterfactualImpact,
    CounterfactualRecoveryCandidate, CounterfactualRecoveryOptions,
    analyze_flow_stage_unavailability,
    analyze_sir_flow_stage_unavailability,
    analyze_sir_flow_recovery_options,
)
from .transactions import (
    TransactionError, TransactionEffect, TransactionAudit,
    analyze_sir_flow_transaction_effects,
)
from .intent import (
    IntentError, IntentCandidateReview, IntentPlan, IntentExecutionResult,
    plan_sir_intent, execute_sir_intent,
)
from .trust_domains import (
    TrustBoundaryError, ForeignTrustBoundary,
    analyze_foreign_trust_boundaries,
)
from .contracts_frontend import (
    ContractFrontendError,
    ContractCallProof,
    ContractPrecondition,
    install as _install_contracts_frontend,
)
_install_contracts_frontend(bootstrap)
_install_c11_backend_effect_contract(bootstrap)
from .phase1_pipeline import (
    Phase1CheckedModule,
    analyze_module_phase1,
    analyze_source_phase1,
)
from .canonical_sir import (
    CheckedAuthoritySIR,
    build_canonical_checked_ownership_sir,
    build_canonical_checked_authority_sir,
)

SotlasBootstrapError = bootstrap.SotlasBootstrapError
compile_source = bootstrap.compile_source
compile_project = bootstrap.compile_project
emit_c_project = bootstrap.emit_c_project

__all__ = [
    "bootstrap", "SotlasError", "SotlasBootstrapError", "compile_source",
    "compile_project", "emit_c_project", "Phase1CheckedModule",
    "analyze_module_phase1", "analyze_source_phase1", "CheckedAuthoritySIR",
    "build_canonical_checked_authority_sir", "StateSpaceFrontendPlan",
    "build_canonical_checked_ownership_sir",
    "analyze_state_space_coverage", "require_exhaustive_state_space_coverage",
    "SourceEffectError", "SourceEffectSummary", "analyze_source_effects",
    "StateSpaceTypedSnapshot", "plan_state_space_frontend",
    "StateTransitionSIRError", "lower_typestate_transition",
    "FlowDependency", "FlowGraphError", "FlowGraphPlan", "FlowNode",
    "certify_flow_graph", "FlowCancelledError", "FlowExecutionError",
    "FlowExecutionResult", "execute_flow",
    "execute_typed_flow", "execute_bound_sir_flow",
    "FlowFrontendError", "TypedFlowPlan", "TypedFlowStage",
    "plan_source_flows", "FlowSIRError", "FlowSIRValueRef",
    "FlowSIRArgument", "FlowSIRStage", "FlowSIRPlan",
    "lower_typed_flows_to_sir", "validate_sir_flow_plans",
    "ContractFrontendError", "ContractCallProof",
    "ContractPrecondition", "CausalityError", "CausalStep",
    "CausalExplanation", "SourceCallStep", "SourceCallExplanation",
    "explain_source_call_causality", "explain_flow_causality",
    "explain_sir_flow_causality",
    "CounterfactualError", "CounterfactualImpact",
    "CounterfactualRecoveryCandidate", "CounterfactualRecoveryOptions",
    "analyze_flow_stage_unavailability",
    "analyze_sir_flow_stage_unavailability",
    "analyze_sir_flow_recovery_options",
    "TransactionError", "TransactionEffect", "TransactionAudit",
    "analyze_sir_flow_transaction_effects",
    "IntentError", "IntentCandidateReview", "IntentPlan",
    "IntentExecutionResult", "plan_sir_intent", "execute_sir_intent",
    "TrustBoundaryError", "ForeignTrustBoundary",
    "analyze_foreign_trust_boundaries",
]
