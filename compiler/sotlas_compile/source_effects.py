"""Conservative source-level effect contracts for the production frontend."""
from __future__ import annotations

from dataclasses import dataclass
import re


EFFECT_ORDER = (
    "alloc", "blocking", "async", "io", "sync", "unsafe", "volatile",
    "system", "ffi", "unknown_call",
)
KNOWN_EFFECTS = frozenset(EFFECT_ORDER)
CALL_EFFECTS = {
    "alloc": "alloc", "allocate": "alloc", "heap_allocate": "alloc",
    "malloc": "alloc", "sleep": "blocking", "block_on": "blocking",
    "wait_for_event": "blocking", "blocking_read": "blocking",
    "io_read": "io", "io_write": "io", "print": "io", "println": "io",
    "read": "io", "write": "io", "lock": "sync", "unlock": "sync",
    "mutex_lock": "sync", "mutex_unlock": "sync", "spin_lock": "sync",
    "spin_unlock": "sync", "__outb": "system", "__outw": "system",
    "__outl": "system", "__inb": "system", "__inw": "system",
    "__inl": "system", "__rdmsr": "system", "__wrmsr": "system",
    "__cli": "system", "__sti": "system", "__hlt": "system",
    "__unknown_intrinsic": "system",
}
_CONTRACT = re.compile(r"^@effects\((.*)\)$")


class SourceEffectError(ValueError):
    """A source effect contract is malformed or cannot be proven."""


@dataclass(frozen=True)
class SourceEffectSummary:
    function: str
    direct_effects: tuple[str, ...]
    transitive_effects: tuple[str, ...]
    unresolved_calls: tuple[str, ...]
    declared_effects: tuple[str, ...] | None


def _walk(value, bootstrap):
    if isinstance(value, (tuple, list)):
        for item in value:
            yield from _walk(item, bootstrap)
        return
    if isinstance(value, (bootstrap.Expr, bootstrap.Stmt)):
        yield value
        for name, child in vars(value).items():
            if name in {"token", "type", "target_type"}:
                continue
            if isinstance(child, dict):
                for nested in child.values():
                    if isinstance(nested, (bootstrap.Expr, bootstrap.Stmt)):
                        yield from _walk(nested, bootstrap)
                    elif isinstance(nested, (tuple, list)):
                        for item in nested:
                            if isinstance(item, (bootstrap.Expr, bootstrap.Stmt)):
                                yield from _walk(item, bootstrap)
                continue
            if isinstance(child, (tuple, list)):
                for item in child:
                    if isinstance(item, (bootstrap.Expr, bootstrap.Stmt)):
                        yield from _walk(item, bootstrap)
                    elif isinstance(item, (tuple, list)):
                        yield from _walk(item, bootstrap)
                    elif type(item).__name__ == "StateCase":
                        yield from _walk(getattr(item, "body", ()), bootstrap)
                continue
            if isinstance(child, (bootstrap.Expr, bootstrap.Stmt)):
                yield from _walk(child, bootstrap)


def _declared_effects(function) -> tuple[str, ...] | None:
    contracts = [item for item in function.attributes if item.startswith("@effects")]
    if not contracts:
        return None
    if len(contracts) != 1:
        raise SourceEffectError(
            f"function {function.name!r} declares @effects more than once"
        )
    match = _CONTRACT.fullmatch(contracts[0])
    if match is None:
        raise SourceEffectError(
            f"malformed @effects contract on {function.name!r}"
        )
    names = tuple(part.strip() for part in match.group(1).split(","))
    if not names or any(not name for name in names):
        raise SourceEffectError(
            f"@effects contract on {function.name!r} requires effect names"
        )
    if len(set(names)) != len(names):
        raise SourceEffectError(
            f"@effects contract on {function.name!r} repeats an effect"
        )
    unknown = set(names) - KNOWN_EFFECTS
    if unknown:
        raise SourceEffectError(
            f"unknown effects on {function.name!r}: {', '.join(sorted(unknown))}"
        )
    return tuple(effect for effect in EFFECT_ORDER if effect in names)


def analyze_source_effects(module, bootstrap) -> dict[str, SourceEffectSummary]:
    """Infer effects over the source call graph and validate explicit contracts."""
    module_functions = {function.name: function for function in module.functions}
    functions = dict(module_functions)
    functions.update(bootstrap.BUILTIN_FUNCTIONS)
    direct = {name: set() for name in functions}
    callees = {name: set() for name in functions}
    unresolved = {name: set() for name in functions}
    declared = {name: _declared_effects(function) for name, function in functions.items()}

    for name, function in functions.items():
        contract = declared[name]
        if name in bootstrap.BUILTIN_FUNCTIONS and name not in module_functions:
            continue
        if not function.body:
            if "@extern(C)" in function.attributes:
                direct[name].add("ffi")
            if contract is None:
                direct[name].add("unknown_call")
                unresolved[name].add(name)
            else:
                direct[name].update(contract)
        for node in _walk(function.body, bootstrap):
            if isinstance(node, bootstrap.Asm):
                direct[name].add("unsafe")
                # The current C11 emitter always emits asm as volatile.
                direct[name].add("volatile")
            elif isinstance(node, bootstrap.Call):
                effect = CALL_EFFECTS.get(node.callee)
                if effect is not None:
                    direct[name].add(effect)
                elif node.callee in functions:
                    callees[name].add(node.callee)
                elif node.callee in bootstrap.BUILTIN_FUNCTIONS:
                    # Builtins without a classified contract cannot be claimed pure.
                    direct[name].add("unknown_call")
                    unresolved[name].add(node.callee)
                elif node.callee.startswith("__"):
                    direct[name].add("unknown_call")
                    unresolved[name].add(node.callee)
                else:
                    # Type checking reports undeclared calls; retain conservative
                    # behavior for source APIs that analyze before full checking.
                    direct[name].add("unknown_call")
                    unresolved[name].add(node.callee)
            elif isinstance(node, bootstrap.MethodCall):
                effect = CALL_EFFECTS.get(node.method)
                if effect is not None:
                    direct[name].add(effect)

    inferred = {name: set(values) for name, values in direct.items()}
    reachable_unknown = {name: set(values) for name, values in unresolved.items()}
    changed = True
    while changed:
        changed = False
        for name in functions:
            for callee in callees[name]:
                before = len(inferred[name]), len(reachable_unknown[name])
                inferred[name].update(inferred[callee])
                reachable_unknown[name].update(reachable_unknown[callee])
                changed |= before != (
                    len(inferred[name]), len(reachable_unknown[name])
                )

    summaries = {}
    for name in functions:
        contract = declared[name]
        if contract is not None:
            omitted = inferred[name] - set(contract)
            if reachable_unknown[name] and "unknown_call" not in contract:
                omitted.discard("unknown_call")
            if omitted:
                raise SourceEffectError(
                    f"@effects contract for {name!r} omits inferred effects: "
                    + ", ".join(
                        effect for effect in EFFECT_ORDER if effect in omitted
                    )
                )
            if reachable_unknown[name] and "unknown_call" not in contract:
                raise SourceEffectError(
                    f"@effects contract for {name!r} cannot prove calls: "
                    + ", ".join(sorted(reachable_unknown[name]))
                )
        summaries[name] = SourceEffectSummary(
            function=name,
            direct_effects=tuple(
                effect for effect in EFFECT_ORDER if effect in direct[name]
            ),
            transitive_effects=tuple(
                effect for effect in EFFECT_ORDER if effect in inferred[name]
            ),
            unresolved_calls=tuple(sorted(reachable_unknown[name])),
            declared_effects=contract,
        )
    return summaries


def install(bootstrap) -> None:
    """Attach source effect analysis to the canonical production checker."""
    original_check = bootstrap.check

    def check_with_effects(module, *args, **kwargs):
        result = original_check(module, *args, **kwargs)
        try:
            module.source_effect_summaries = analyze_source_effects(module, bootstrap)
        except SourceEffectError as error:
            raise bootstrap.SotlasBootstrapError(
                str(error), 1, 1, module.filename, module.source
            ) from error
        return result

    bootstrap.check = check_with_effects


def install_c11_backend_effect_contract(bootstrap) -> None:
    """Reject source effects the current C11 backend cannot lower."""
    original_emit_c = bootstrap.emit_c

    def emit_c_with_effect_contract(module, *args, **kwargs):
        summaries = getattr(module, "source_effect_summaries", None)
        if summaries is None:
            bootstrap.check(module)
            summaries = getattr(module, "source_effect_summaries", None)
        summaries = summaries or {}
        for function in module.functions:
            if any(
                isinstance(attribute, str)
                and (
                    attribute == "@target_feature"
                    or attribute.startswith("@target_feature(")
                )
                for attribute in getattr(function, "attributes", ())
            ):
                raise bootstrap.SotlasBootstrapError(
                    "C11 backend does not lower function-specific CPU feature requirements yet",
                    1, 1, module.filename, module.source,
                )
            summary = summaries.get(function.name)
            if summary is None:
                raise bootstrap.SotlasBootstrapError(
                    f"C11 backend effect contract has no summary for "
                    f"function {function.name!r}",
                    1, 1, module.filename, module.source,
                )
            effects = set(summary.transitive_effects)
            effects.update(summary.declared_effects or ())
            unsupported = effects - (set(EFFECT_ORDER) - {"async"})
            if unsupported:
                raise bootstrap.SotlasBootstrapError(
                    "C11 backend effect contract rejected lowering for "
                    f"{function.name!r}: " + ", ".join(
                        effect for effect in EFFECT_ORDER if effect in unsupported
                    ),
                    1, 1, module.filename, module.source,
                )
        return original_emit_c(module, *args, **kwargs)

    bootstrap.emit_c = emit_c_with_effect_contract


__all__ = [
    "SourceEffectError", "SourceEffectSummary", "analyze_source_effects",
    "install", "install_c11_backend_effect_contract",
]
