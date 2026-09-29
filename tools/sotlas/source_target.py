"""Reconcile source execution profiles with concrete machine targets.

This module is the single policy boundary between the source-level target
profile (native/barecore/web) and the concrete execution target used by LLVM,
C11 and linkers. Keeping this policy here prevents each backend from inventing
its own interpretation of ``target barecore;``.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .execution_target import (
    ExecutionTarget,
    ExecutionTargetError,
    resolve_execution_target,
)


SUPPORTED_SOURCE_PROFILES = frozenset({"native", "barecore", "web"})


@dataclass(frozen=True)
class SourceExecutionTargetPlan:
    """Resolved relationship between source semantics and machine target."""

    source_profile: str
    source_profile_explicit: bool
    requested_target: str | None
    selected_target: str
    inferred_target: bool
    execution_target: ExecutionTarget

    @property
    def is_freestanding(self) -> bool:
        return self.execution_target.is_freestanding


def resolve_source_execution_target(
    source_profile: str,
    *,
    source_profile_explicit: bool = False,
    requested_target: str | None = None,
    cpu_features: Iterable[str] = (),
) -> SourceExecutionTargetPlan:
    """Resolve a source profile and machine target without semantic mismatch.

    ``barecore`` defaults to the canonical x86-64 freestanding target until a
    source-level architecture selector exists. Callers may explicitly select a
    different supported freestanding architecture such as AArch64.

    Existing sources that do not explicitly declare ``target native;`` retain
    the historical ability to request a freestanding target through the CLI.
    Once ``target native;`` is explicit, however, sending that module to a
    freestanding target is rejected because it contradicts the source contract.
    """

    if source_profile not in SUPPORTED_SOURCE_PROFILES:
        raise ExecutionTargetError(
            f"unsupported source target profile {source_profile!r}; supported "
            "profiles: barecore, native, web"
        )

    if source_profile == "web":
        raise ExecutionTargetError(
            "web source profile is not supported by native execution targets"
        )

    inferred_target = requested_target is None
    if requested_target is None:
        selected_target = (
            "x86_64-freestanding"
            if source_profile == "barecore"
            else "host"
        )
    else:
        selected_target = requested_target

    target = resolve_execution_target(
        selected_target,
        cpu_features=cpu_features,
    )

    if source_profile == "barecore" and not target.is_freestanding:
        raise ExecutionTargetError(
            "barecore source profile requires a freestanding execution target; "
            f"got {target.triple!r}"
        )

    if (
        source_profile == "native"
        and source_profile_explicit
        and target.is_freestanding
    ):
        raise ExecutionTargetError(
            "explicit native source profile cannot use a freestanding execution "
            f"target; got {target.triple!r}"
        )

    return SourceExecutionTargetPlan(
        source_profile=source_profile,
        source_profile_explicit=source_profile_explicit,
        requested_target=requested_target,
        selected_target=selected_target,
        inferred_target=inferred_target,
        execution_target=target,
    )


__all__ = [
    "SUPPORTED_SOURCE_PROFILES",
    "SourceExecutionTargetPlan",
    "resolve_source_execution_target",
]
