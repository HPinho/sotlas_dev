"""Source-declared trust metadata for C foreign boundaries."""
from __future__ import annotations

from dataclasses import dataclass
import re


class TrustBoundaryError(ValueError):
    """Raised when foreign-boundary trust evidence is malformed."""


_TRUST_ATTRIBUTE = re.compile(r"^@trust\((trusted|unsafe|isolated)\)$")


@dataclass(frozen=True)
class ForeignTrustBoundary:
    symbol: str
    convention: str
    trust_domain: str
    effects: tuple[str, ...]
    isolation_verified: bool
    required_context: tuple[str, ...] = ("system",)


def analyze_foreign_trust_boundaries(
    module, *, require_explicit_trust: bool = False,
) -> tuple[ForeignTrustBoundary, ...]:
    """Extract and validate trust labels for checked ``@extern(C)`` symbols.

    A source label records the programmer's declaration. ``isolated`` is never
    considered sandbox proof; this API does not construct a target sandbox.
    """
    functions = tuple(getattr(module, "functions", ()) or ())
    summaries = getattr(module, "source_effect_summaries", {}) or {}
    names = [getattr(function, "name", None) for function in functions]
    if len(set(names)) != len(names):
        raise TrustBoundaryError("foreign trust analysis found duplicate functions")

    boundaries = []
    for function in functions:
        attributes = tuple(getattr(function, "attributes", ()) or ())
        trust_attributes = tuple(
            attribute for attribute in attributes
            if isinstance(attribute, str) and attribute.startswith("@trust")
        )
        is_foreign = "@extern(C)" in attributes
        if trust_attributes and not is_foreign:
            raise TrustBoundaryError(
                f"trust annotation on {function.name!r} requires @extern(C)"
            )
        if not is_foreign:
            continue
        if len(trust_attributes) > 1:
            raise TrustBoundaryError(
                f"foreign function {function.name!r} repeats its trust annotation"
            )
        trust_domain = "unspecified"
        if trust_attributes:
            match = _TRUST_ATTRIBUTE.fullmatch(trust_attributes[0])
            if match is None:
                raise TrustBoundaryError(
                    f"foreign function {function.name!r} has an invalid trust annotation"
                )
            trust_domain = match.group(1)
        if require_explicit_trust and trust_domain == "unspecified":
            raise TrustBoundaryError(
                f"foreign function {function.name!r} requires an explicit trust annotation"
            )
        summary = summaries.get(function.name)
        if summary is None:
            raise TrustBoundaryError(
                f"foreign function {function.name!r} has no checked effect summary"
            )
        effects = tuple(summary.transitive_effects)
        if "ffi" not in effects:
            raise TrustBoundaryError(
                f"foreign function {function.name!r} is missing the ffi effect"
            )
        boundaries.append(ForeignTrustBoundary(
            function.name,
            "C",
            trust_domain,
            effects,
            False,
            ("system", "unsafe")
            if trust_domain == "unsafe" or "@unsafe" in attributes
            else ("system",),
        ))
    return tuple(boundaries)


__all__ = [
    "TrustBoundaryError", "ForeignTrustBoundary",
    "analyze_foreign_trust_boundaries",
]
