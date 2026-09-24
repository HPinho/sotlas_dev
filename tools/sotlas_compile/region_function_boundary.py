"""Certified per-function REGION ownership boundaries.

This module derives a compact backend-neutral boundary view from the already
certified interprocedural REGION lifetime plan plus canonical Typed AST and
ownership summaries.  It does not change ownership semantics, SIR or backend
behavior.
"""
from __future__ import annotations

from dataclasses import dataclass

from .region_interprocedural import (
    RegionInterproceduralLifetimePlan,
    plan_checked_region_interprocedural,
)
from .typed_ast import (
    OwnershipDomain,
    OwnershipModuleAnalysis,
    Phase1SemanticError,
    TypedModule,
)


class RegionFunctionBoundaryError(Phase1SemanticError):
    """Raised when a per-function REGION ownership boundary cannot be certified."""


@dataclass(frozen=True)
class RegionFunctionOwnershipBoundary:
    function: str
    parameter_bindings: tuple[str, ...]
    call_root_point_ids: tuple[str, ...]
    call_terminal_point_ids: tuple[str, ...]
    return_bindings: tuple[str, ...]


@dataclass(frozen=True)
class RegionFunctionBoundaryPlan:
    boundaries: tuple[RegionFunctionOwnershipBoundary, ...]

    def function(self, name: str) -> RegionFunctionOwnershipBoundary:
        matches = tuple(item for item in self.boundaries if item.function == name)
        if len(matches) != 1:
            raise RegionFunctionBoundaryError(
                f"REGION function-boundary plan requires exactly one function {name!r}"
            )
        return matches[0]


def build_region_function_boundary_plan(
    interprocedural: RegionInterproceduralLifetimePlan,
    analysis: OwnershipModuleAnalysis,
    typed_module: TypedModule,
) -> RegionFunctionBoundaryPlan:
    if not isinstance(interprocedural, RegionInterproceduralLifetimePlan):
        raise RegionFunctionBoundaryError(
            "REGION function-boundary planning requires a certified interprocedural plan"
        )
    if not isinstance(analysis, OwnershipModuleAnalysis):
        raise RegionFunctionBoundaryError(
            "REGION function-boundary planning requires canonical ownership analysis"
        )
    if not isinstance(typed_module, TypedModule):
        raise RegionFunctionBoundaryError(
            "REGION function-boundary planning requires the canonical TypedModule"
        )

    typed_functions = {item.name: item for item in typed_module.functions}
    if len(typed_functions) != len(typed_module.functions):
        raise RegionFunctionBoundaryError("duplicate typed function in REGION boundary planning")

    summaries = {item.name: item for item in analysis.summaries}
    if len(summaries) != len(analysis.summaries):
        raise RegionFunctionBoundaryError(
            "duplicate ownership function summary in REGION boundary planning"
        )

    return_bindings_by_function: dict[str, list[str]] = {}
    for transfer in interprocedural.returns.transfers:
        return_bindings_by_function.setdefault(transfer.function, []).append(transfer.binding)

    boundaries: list[RegionFunctionOwnershipBoundary] = []
    for function_plan in interprocedural.functions:
        function_name = function_plan.function
        typed_function = typed_functions.get(function_name)
        summary = summaries.get(function_name)
        if typed_function is None or summary is None:
            raise RegionFunctionBoundaryError(
                f"REGION function {function_name!r} lacks typed/ownership summary"
            )
        if len(typed_function.params) != len(summary.params):
            raise RegionFunctionBoundaryError(
                f"REGION function {function_name!r} parameter summary diverges from Typed AST"
            )

        parameter_bindings: list[str] = []
        for parameter, contract in zip(
            typed_function.params,
            summary.params,
            strict=True,
        ):
            if parameter.name != contract.name:
                raise RegionFunctionBoundaryError(
                    f"REGION parameter identity mismatch in {function_name!r}"
                )
            if parameter.ownership_domain is not contract.domain:
                raise RegionFunctionBoundaryError(
                    f"REGION parameter domain mismatch for {function_name}.{parameter.name}"
                )
            if parameter.ownership_domain is OwnershipDomain.REGION:
                if not contract.takes_ownership:
                    raise RegionFunctionBoundaryError(
                        f"REGION parameter {function_name}.{parameter.name} is not ownership-taking"
                    )
                parameter_bindings.append(parameter.name)

        local_bindings = set(function_plan.local.bindings)
        missing_parameters = [
            binding for binding in parameter_bindings if binding not in local_bindings
        ]
        if missing_parameters:
            raise RegionFunctionBoundaryError(
                f"REGION parameters lack local lifetime owners in {function_name!r}: "
                + ", ".join(missing_parameters)
            )

        summary_view = interprocedural.call_path_summary(function_name)
        known_call_points = {item.point_id for item in interprocedural.call_points(function_name)}
        for point_id in (
            *summary_view.root_point_ids,
            *summary_view.terminal_point_ids,
        ):
            if point_id not in known_call_points:
                raise RegionFunctionBoundaryError(
                    f"REGION call boundary {function_name}::{point_id} lacks certified call point"
                )

        return_bindings = tuple(return_bindings_by_function.get(function_name, ()))
        if len(set(return_bindings)) != len(return_bindings):
            raise RegionFunctionBoundaryError(
                f"duplicate REGION return boundary in {function_name!r}"
            )
        for binding in return_bindings:
            if binding not in local_bindings:
                raise RegionFunctionBoundaryError(
                    f"REGION return boundary {function_name}::{binding} lacks local lifetime owner"
                )

        boundaries.append(
            RegionFunctionOwnershipBoundary(
                function=function_name,
                parameter_bindings=tuple(parameter_bindings),
                call_root_point_ids=summary_view.root_point_ids,
                call_terminal_point_ids=summary_view.terminal_point_ids,
                return_bindings=return_bindings,
            )
        )

    return RegionFunctionBoundaryPlan(tuple(boundaries))


def plan_checked_region_function_boundaries(
    checked_module: object,
) -> RegionFunctionBoundaryPlan:
    semantic = getattr(checked_module, "semantic", None)
    if semantic is None:
        raise RegionFunctionBoundaryError(
            "REGION function-boundary planning requires a Phase1CheckedModule semantic snapshot"
        )
    interprocedural = plan_checked_region_interprocedural(checked_module)
    return build_region_function_boundary_plan(
        interprocedural,
        getattr(semantic, "ownership", None),
        getattr(semantic, "typed_module", None),
    )


__all__ = [
    "RegionFunctionBoundaryError",
    "RegionFunctionOwnershipBoundary",
    "RegionFunctionBoundaryPlan",
    "build_region_function_boundary_plan",
    "plan_checked_region_function_boundaries",
]
