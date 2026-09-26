"""Deterministic stage failure analysis over certified Sotlas Flow plans."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass

from .flow_graph import certify_flow_graph
from .flow_sir import FlowSIRError, validate_sir_flow_plans
from .source_effects import EFFECT_ORDER, KNOWN_EFFECTS


class CounterfactualError(ValueError):
    """Raised when a stage availability scenario lacks canonical evidence."""


@dataclass(frozen=True)
class CounterfactualImpact:
    flow: str
    unavailable_stage: str
    affected_stages: tuple[str, ...]
    unaffected_stages: tuple[str, ...]
    affected_dependencies: tuple[tuple[str, str], ...]


@dataclass(frozen=True)
class CounterfactualRecoveryCandidate:
    flow: str
    stage: str
    function: str
    result_type: str
    effects: tuple[str, ...]
    effects_added: tuple[str, ...]
    effects_removed: tuple[str, ...]
    semantic_equivalence_verified: bool = False
    semantic_equivalence_evidence: str | None = None
    effect_policy: tuple[str, ...] | None = None
    effects_disallowed: tuple[str, ...] = ()


@dataclass(frozen=True)
class CounterfactualRecoveryOptions:
    impact: CounterfactualImpact
    target_stage: str
    candidates: tuple[CounterfactualRecoveryCandidate, ...]


@dataclass(frozen=True)
class CounterfactualFunctionEquivalence:
    left_function: str
    right_function: str
    result_type: str
    semantic_equivalence_verified: bool
    semantic_equivalence_evidence: str | None


@dataclass(frozen=True)
class CounterfactualRollbackPlan:
    flow: str
    failed_stage: str
    completed_stages: tuple[str, ...]
    compensation_stages: tuple[str, ...]
    failed_stage_effects: tuple[str, ...]
    blockers: tuple[str, ...]
    rollback_proven_complete: bool


_PURE_INTEGER_TYPES = {
    "u8": 8, "u16": 16, "u32": 32, "u64": 64, "usize": 64,
}
_MAX_POLYNOMIAL_TERMS = 256


def _normalize_unsigned_operation(operation, type_name, left, right):
    """Canonicalize safe identities and constants under modular unsigned math."""
    width = _PURE_INTEGER_TYPES[type_name]
    modulus = 1 << width
    left_constant = left[0] == "constant" and left[1] == type_name
    right_constant = right[0] == "constant" and right[1] == type_name
    if left_constant and right_constant:
        left_value, right_value = left[2], right[2]
        value = {
            "add": lambda: left_value + right_value,
            "sub": lambda: left_value - right_value,
            "mul": lambda: left_value * right_value,
        }[operation]() % modulus
        return ("constant", type_name, value)

    zero = ("constant", type_name, 0)
    one = ("constant", type_name, 1)
    if operation == "add":
        if left == zero:
            return right
        if right == zero:
            return left
    elif operation == "sub" and right == zero:
        return left
    elif operation == "mul":
        if left == zero or right == zero:
            return zero
        if left == one:
            return right
        if right == one:
            return left

    if operation in {"add", "mul"} and repr(left) > repr(right):
        left, right = right, left
    return (operation, type_name, left, right)


def _unsigned_polynomial(expression):
    """Canonicalize a pure unsigned expression in the modular polynomial ring."""
    try:
        return _unsigned_polynomial_inner(expression)
    except RecursionError:
        return None


def _unsigned_polynomial_inner(expression):
    kind, type_name = expression[:2]
    width = _PURE_INTEGER_TYPES.get(type_name)
    if width is None:
        return None
    modulus = 1 << width
    if kind == "parameter":
        return {(expression[2],): 1}
    if kind == "constant":
        return {(): expression[2] % modulus} if expression[2] % modulus else {}
    if kind not in {"add", "sub", "mul"}:
        return None
    left = _unsigned_polynomial(expression[2])
    right = _unsigned_polynomial(expression[3])
    if left is None or right is None:
        return None
    result = dict(left)
    if kind in {"add", "sub"}:
        sign = 1 if kind == "add" else -1
        for monomial, coefficient in right.items():
            value = (result.get(monomial, 0) + sign * coefficient) % modulus
            if value:
                result[monomial] = value
            else:
                result.pop(monomial, None)
        return result if len(result) <= _MAX_POLYNOMIAL_TERMS else None

    result = {}
    for left_monomial, left_coefficient in left.items():
        for right_monomial, right_coefficient in right.items():
            monomial = tuple(sorted(left_monomial + right_monomial))
            coefficient = (
                result.get(monomial, 0) + left_coefficient * right_coefficient
            ) % modulus
            if coefficient:
                result[monomial] = coefficient
            else:
                result.pop(monomial, None)
            if len(result) > _MAX_POLYNOMIAL_TERMS:
                return None
    return result


def _polynomial_parameter_indices(polynomial) -> frozenset[int]:
    return frozenset(index for monomial in polynomial for index in monomial)


def _pure_integer_result_expression(function):
    """Return a normalized expression for a narrow, pure integer SIR body."""
    if getattr(function, "is_system", False):
        return None
    parameters = tuple(getattr(function, "parameters", ()) or ())
    blocks = tuple(getattr(function, "blocks", ()) or ())
    result_type = getattr(function, "return_type", None)
    if result_type not in _PURE_INTEGER_TYPES or len(blocks) != 1:
        return None

    expressions = {}
    parameter_indices = {}
    definitions = set()
    for index, parameter in enumerate(parameters):
        name = getattr(parameter, "name", None)
        type_name = getattr(parameter, "type_name", None)
        if (
            not isinstance(name, str)
            or not name
            or name in definitions
            or type_name not in _PURE_INTEGER_TYPES
        ):
            return None
        definitions.add(name)
        parameter_indices[name] = index
        expressions[name] = ("parameter", type_name, index)

    slots = {}
    initialized_slots = set()
    instructions = tuple(getattr(blocks[0], "instructions", ()) or ())
    returned = None
    for index, instruction in enumerate(instructions):
        kind = type(instruction).__name__
        if kind == "AllocStackInst":
            slot = getattr(instruction, "result", None)
            slot_name = getattr(slot, "name", None)
            variable = getattr(instruction, "var_name", None)
            type_name = getattr(instruction, "type_name", None)
            if (
                not isinstance(slot_name, str)
                or slot_name in definitions
                or variable not in parameter_indices
                or getattr(slot, "type_name", None) != type_name
                or parameters[parameter_indices[variable]].type_name != type_name
            ):
                return None
            definitions.add(slot_name)
            slots[slot_name] = (variable, type_name)
        elif kind == "StoreInst":
            destination = getattr(instruction, "destination", None)
            source = getattr(instruction, "source", None)
            slot_name = getattr(destination, "name", None)
            slot = slots.get(slot_name)
            if (
                slot is None
                or slot_name in initialized_slots
                or getattr(source, "name", None) != slot[0]
                or getattr(source, "type_name", None) != slot[1]
                or getattr(destination, "type_name", None) != slot[1]
            ):
                return None
            initialized_slots.add(slot_name)
        elif kind == "ConstantIntInst":
            target = getattr(instruction, "result", None)
            name = getattr(target, "name", None)
            type_name = getattr(target, "type_name", None)
            value = getattr(instruction, "value", None)
            width = _PURE_INTEGER_TYPES.get(type_name)
            if (
                not isinstance(name, str)
                or name in definitions
                or width is None
                or not isinstance(value, int)
                or isinstance(value, bool)
                or not 0 <= value < (1 << width)
            ):
                return None
            definitions.add(name)
            expressions[name] = ("constant", type_name, value)
        elif kind == "BinaryOpInst":
            target = getattr(instruction, "result", None)
            name = getattr(target, "name", None)
            type_name = getattr(target, "type_name", None)
            operation = getattr(instruction, "operation", None)
            left = getattr(instruction, "left", None)
            right = getattr(instruction, "right", None)
            left_name = getattr(left, "name", None)
            right_name = getattr(right, "name", None)
            if (
                not isinstance(name, str)
                or name in definitions
                or operation not in {"add", "sub", "mul"}
                or type_name not in _PURE_INTEGER_TYPES
                or left_name not in expressions
                or right_name not in expressions
                or getattr(left, "type_name", None) != type_name
                or getattr(right, "type_name", None) != type_name
            ):
                return None
            definitions.add(name)
            expressions[name] = _normalize_unsigned_operation(
                operation,
                type_name,
                expressions[left_name],
                expressions[right_name],
            )
        elif kind == "ReturnInst":
            value = getattr(instruction, "value", None)
            value_name = getattr(value, "name", None)
            if (
                returned is not None
                or index != len(instructions) - 1
                or value_name not in expressions
                or getattr(value, "type_name", None) != result_type
            ):
                return None
            returned = expressions[value_name]
        else:
            return None
    if (
        returned is None
        or returned[1] != result_type
        or initialized_slots != set(slots)
    ):
        return None
    return returned


def _expression_parameter_indices(expression) -> frozenset[int]:
    if expression[0] == "parameter":
        return frozenset((expression[2],))
    if expression[0] in {"add", "sub", "mul"}:
        return (
            _expression_parameter_indices(expression[2])
            | _expression_parameter_indices(expression[3])
        )
    return frozenset()


def _prove_stage_expression_equivalence(
    left_plan,
    left_stage,
    right_plan,
    right_stage,
    functions,
    summaries,
    memo=None,
    active=None,
) -> bool:
    """Prove exact pure-expression equivalence through matching input values."""
    if left_stage.result_type != right_stage.result_type:
        return False
    key = (left_plan.name, left_stage.name, right_plan.name, right_stage.name)
    memo = {} if memo is None else memo
    active = set() if active is None else active
    if key in memo:
        return memo[key]
    if key in active:
        return False

    left_summary = summaries.get(left_stage.function)
    right_summary = summaries.get(right_stage.function)
    left_function = functions.get(left_stage.function)
    right_function = functions.get(right_stage.function)
    if (
        left_stage.effects
        or right_stage.effects
        or (
            left_summary is not None
            and (left_summary.transitive_effects or left_summary.unresolved_calls)
        )
        or (
            right_summary is not None
            and (right_summary.transitive_effects or right_summary.unresolved_calls)
        )
    ):
        return False
    left_expression = _pure_integer_result_expression(left_function)
    right_expression = _pure_integer_result_expression(right_function)
    if left_expression is None or right_expression is None:
        return False
    left_polynomial = _unsigned_polynomial(left_expression)
    right_polynomial = _unsigned_polynomial(right_expression)
    if left_polynomial is None or left_polynomial != right_polynomial:
        return False

    left_stages = {stage.name: stage for stage in left_plan.stages}
    right_stages = {stage.name: stage for stage in right_plan.stages}
    left_arguments = {item.parameter_index: item for item in left_stage.arguments}
    right_arguments = {item.parameter_index: item for item in right_stage.arguments}
    active.add(key)
    for index in _polynomial_parameter_indices(left_polynomial):
        left_argument = left_arguments.get(index)
        right_argument = right_arguments.get(index)
        if (
            left_argument is None
            or right_argument is None
            or left_argument.type_name != right_argument.type_name
        ):
            active.remove(key)
            memo[key] = False
            return False
        left_producer = left_stages.get(left_argument.value.producer_stage)
        right_producer = right_stages.get(right_argument.value.producer_stage)
        if (
            left_producer is None
            or right_producer is None
            or not _prove_stage_expression_equivalence(
                left_plan, left_producer, right_plan, right_producer,
                functions, summaries, memo, active,
            )
        ):
            active.remove(key)
            memo[key] = False
            return False
    active.remove(key)
    memo[key] = True
    return True


def _analyze(flow_name, graph, stage_names, unavailable_stage):
    if not isinstance(unavailable_stage, str) or not unavailable_stage:
        raise CounterfactualError("unavailable Flow stage must be a non-empty name")
    try:
        canonical = certify_flow_graph(graph.nodes, graph.dependencies)
    except (AttributeError, TypeError, ValueError) as error:
        raise CounterfactualError(f"invalid canonical Flow graph: {error}") from error
    if canonical != graph:
        raise CounterfactualError("Flow graph is not in canonical certified form")
    graph_names = tuple(node.name for node in canonical.nodes)
    if len(set(stage_names)) != len(stage_names) or set(stage_names) != set(graph_names):
        raise CounterfactualError("Flow stage facts differ from the certified graph")
    if unavailable_stage not in graph_names:
        raise CounterfactualError(f"unknown Flow stage {unavailable_stage!r}")

    successors = {name: [] for name in graph_names}
    for edge in canonical.dependencies:
        successors[edge.producer].append(edge.consumer)
    impacted = {unavailable_stage}
    pending = [unavailable_stage]
    while pending:
        current = pending.pop(0)
        for consumer in successors[current]:
            if consumer not in impacted:
                impacted.add(consumer)
                pending.append(consumer)
    affected = tuple(name for name in graph_names if name in impacted)
    unaffected = tuple(name for name in graph_names if name not in impacted)
    edges = tuple(
        (edge.producer, edge.consumer)
        for edge in canonical.dependencies
        if edge.consumer in impacted
    )
    return CounterfactualImpact(
        flow_name, unavailable_stage, affected, unaffected, edges
    )


def analyze_flow_stage_unavailability(plan, unavailable_stage: str) -> CounterfactualImpact:
    """Report transitive downstream impact without executing Flow actions."""
    if not isinstance(getattr(plan, "name", None), str) or not plan.name:
        raise CounterfactualError("Flow plan must have a name")
    return _analyze(
        plan.name, plan.graph, tuple(stage.name for stage in plan.stages),
        unavailable_stage,
    )


def analyze_sir_flow_stage_unavailability(
    module, flow_name: str, unavailable_stage: str,
) -> CounterfactualImpact:
    """Analyze one uniquely attached canonical Flow plan in SIR."""
    try:
        plans = validate_sir_flow_plans(module)
    except FlowSIRError as error:
        raise CounterfactualError(f"invalid canonical SIR Flow plan: {error}") from error
    matches = tuple(plan for plan in plans if plan.name == flow_name)
    if len(matches) != 1:
        raise CounterfactualError(f"SIR has no unique checked Flow plan {flow_name!r}")
    plan = matches[0]
    # SIR stores source-stable arguments instead of the frontend graph record;
    # validation reconciles those references before reconstructing the graph.
    from .flow_graph import FlowDependency, FlowNode
    graph = certify_flow_graph(
        tuple(FlowNode(stage.name) for stage in plan.stages),
        tuple(
            FlowDependency(argument.value.producer_stage, stage.name)
            for stage in plan.stages for argument in stage.arguments
        ),
    )
    return _analyze(flow_name, graph, tuple(stage.name for stage in plan.stages), unavailable_stage)


def analyze_sir_flow_recovery_options(
    module, flow_name: str, unavailable_stage: str, target_stage: str,
    *, allowed_effects: tuple[str, ...] | None = None,
) -> CounterfactualRecoveryOptions:
    """Find type-compatible alternate Flow implementations for an impacted stage.

    Candidate equivalence is proved only for identical pure unsigned SIR
    expressions whose referenced producer stages are recursively equivalent.
    """
    if not isinstance(target_stage, str) or not target_stage:
        raise CounterfactualError("recovery target stage must be a non-empty name")
    if allowed_effects is not None:
        if not isinstance(allowed_effects, tuple) or any(
            not isinstance(effect, str) for effect in allowed_effects
        ):
            raise CounterfactualError(
                "allowed recovery effects must be a tuple of effect names"
            )
        if len(set(allowed_effects)) != len(allowed_effects):
            raise CounterfactualError("allowed recovery effects repeat an effect")
        unknown = set(allowed_effects) - KNOWN_EFFECTS
        if unknown:
            raise CounterfactualError(
                "unknown allowed recovery effects: "
                + ", ".join(sorted(unknown))
            )
        allowed_effects = tuple(
            effect for effect in EFFECT_ORDER if effect in allowed_effects
        )
    try:
        plans = validate_sir_flow_plans(module)
    except FlowSIRError as error:
        raise CounterfactualError(f"invalid canonical SIR Flow plan: {error}") from error
    matches = tuple(plan for plan in plans if plan.name == flow_name)
    if len(matches) != 1:
        raise CounterfactualError(f"SIR has no unique checked Flow plan {flow_name!r}")
    failed_plan = matches[0]
    failed_stages = {stage.name: stage for stage in failed_plan.stages}
    if target_stage not in failed_stages:
        raise CounterfactualError(f"unknown recovery target stage {target_stage!r}")
    impact = analyze_sir_flow_stage_unavailability(
        module, flow_name, unavailable_stage
    )
    if target_stage not in impact.affected_stages:
        return CounterfactualRecoveryOptions(impact, target_stage, ())

    target = failed_stages[target_stage]
    failed_effects = tuple(target.effects)
    functions = {
        function.name: function
        for function in tuple(getattr(module, "functions", ()) or ())
    }
    summaries = getattr(module, "effect_summaries", {})
    candidates = []
    for plan in plans:
        if plan.name == flow_name:
            continue
        stage_by_name = {stage.name: stage for stage in plan.stages}
        replacement = stage_by_name.get(target_stage)
        if replacement is None or replacement.result_type != target.result_type:
            continue
        # Follow the replacement's transitive dependency ancestry. A candidate
        # that still consumes the failed stage cannot recover the requested output.
        producers = {
            stage.name: tuple(
                argument.value.producer_stage for argument in stage.arguments
            )
            for stage in plan.stages
        }
        ancestry = set()
        pending = [target_stage]
        while pending:
            current = pending.pop()
            for producer in producers.get(current, ()):
                if producer not in ancestry:
                    ancestry.add(producer)
                    pending.append(producer)
        if unavailable_stage in ancestry:
            continue
        candidate_effects = tuple(replacement.effects)
        equivalent = _prove_stage_expression_equivalence(
            failed_plan, target, plan, replacement, functions, summaries
        )
        effects_disallowed = (
            tuple(effect for effect in candidate_effects if effect not in allowed_effects)
            if allowed_effects is not None else ()
        )
        candidates.append(CounterfactualRecoveryCandidate(
            plan.name,
            target_stage,
            replacement.function,
            replacement.result_type,
            candidate_effects,
            tuple(effect for effect in candidate_effects if effect not in failed_effects),
            tuple(effect for effect in failed_effects if effect not in candidate_effects),
            semantic_equivalence_verified=equivalent,
            semantic_equivalence_evidence=(
                "normalized-pure-unsigned-sir-polynomial"
                if equivalent else None
            ),
            effect_policy=allowed_effects,
            effects_disallowed=effects_disallowed,
        ))
    candidates.sort(key=lambda candidate: (candidate.flow, candidate.function))
    return CounterfactualRecoveryOptions(impact, target_stage, tuple(candidates))


def analyze_pure_sir_function_equivalence(
    module, left_function: str, right_function: str,
) -> CounterfactualFunctionEquivalence:
    """Compare two pure unsigned straight-line functions outside Flow plans."""
    if any(not isinstance(name, str) or not name for name in (
        left_function, right_function,
    )):
        raise CounterfactualError("function names must be non-empty strings")
    try:
        from .canonical_sir import load_canonical_sir
        inferred_module = deepcopy(module)
        inference = load_canonical_sir().EffectInferencePass().run(inferred_module)
    except (AttributeError, TypeError, ValueError) as error:
        raise CounterfactualError(f"invalid SIR module for equivalence: {error}") from error
    if not inference.success:
        raise CounterfactualError(
            "SIR effect inference failed before equivalence: "
            + "; ".join(inference.errors)
        )
    functions = {
        function.name: function
        for function in tuple(getattr(inferred_module, "functions", ()) or ())
    }
    if len(functions) != len(tuple(getattr(inferred_module, "functions", ()) or ())):
        raise CounterfactualError("SIR module repeats function names")
    if left_function not in functions or right_function not in functions:
        raise CounterfactualError("function equivalence references an unknown function")
    left = functions[left_function]
    right = functions[right_function]
    result_type = getattr(left, "return_type", None)
    equivalent = (
        result_type == getattr(right, "return_type", None)
        and tuple(getattr(parameter, "type_name", None) for parameter in left.parameters)
        == tuple(getattr(parameter, "type_name", None) for parameter in right.parameters)
        and not getattr(left, "is_system", False)
        and not getattr(right, "is_system", False)
    )
    summaries = inferred_module.effect_summaries
    if equivalent:
        for name in (left_function, right_function):
            summary = summaries.get(name)
            if summary is None or summary.transitive_effects or summary.unresolved_calls:
                equivalent = False
                break
    left_expression = _pure_integer_result_expression(left)
    right_expression = _pure_integer_result_expression(right)
    left_polynomial = (
        _unsigned_polynomial(left_expression)
        if equivalent and left_expression is not None else None
    )
    right_polynomial = (
        _unsigned_polynomial(right_expression)
        if equivalent and right_expression is not None else None
    )
    equivalent = (
        equivalent
        and left_polynomial is not None
        and left_polynomial == right_polynomial
    )
    return CounterfactualFunctionEquivalence(
        left_function,
        right_function,
        result_type if isinstance(result_type, str) else "unknown",
        bool(equivalent),
        "normalized-pure-unsigned-sir-polynomial" if equivalent else None,
    )


def analyze_sir_flow_failure_rollback(
    module,
    flow_name: str,
    failed_stage: str,
    effect_policies: dict[str, str],
    compensation_handlers: dict[str, str] | None = None,
) -> CounterfactualRollbackPlan:
    """Analyze rollback after one stage fails in a canonical sequential Flow."""
    try:
        plans = validate_sir_flow_plans(module)
    except FlowSIRError as error:
        raise CounterfactualError(f"invalid canonical SIR Flow plan: {error}") from error
    matches = tuple(plan for plan in plans if plan.name == flow_name)
    if len(matches) != 1:
        raise CounterfactualError(f"SIR has no unique checked Flow plan {flow_name!r}")
    plan = matches[0]
    if any(len(batch) != 1 for batch in plan.parallel_stages):
        raise CounterfactualError(
            "counterfactual rollback analysis requires a sequential Flow"
        )
    stages = tuple(plan.stages)
    names = tuple(stage.name for stage in stages)
    if failed_stage not in names:
        raise CounterfactualError(f"unknown failed Flow stage {failed_stage!r}")
    failure_index = names.index(failed_stage)
    completed = names[:failure_index]
    from .transactions import (
        TransactionError, analyze_sir_flow_transaction_effects,
    )
    try:
        audit = analyze_sir_flow_transaction_effects(
            module, flow_name, effect_policies, compensation_handlers
        )
    except TransactionError as error:
        raise CounterfactualError(f"invalid rollback policy: {error}") from error
    relevant = set(completed) | {failed_stage}
    blockers = tuple(
        blocker for blocker in audit.blockers
        if blocker.partition(":")[0] in relevant
    )
    compensatable = {
        effect.stage for effect in audit.effects
        if effect.classification == "compensatable"
        and effect.compensation is not None
    }
    compensation_stages = tuple(
        stage for stage in reversed(completed) if stage in compensatable
    )
    failed_effects = tuple(
        stage.effects for stage in stages if stage.name == failed_stage
    )[0]
    return CounterfactualRollbackPlan(
        flow_name,
        failed_stage,
        completed,
        compensation_stages,
        failed_effects,
        blockers,
        not blockers and not failed_effects,
    )


__all__ = [
    "CounterfactualError", "CounterfactualImpact",
    "CounterfactualRecoveryCandidate", "CounterfactualRecoveryOptions",
    "CounterfactualFunctionEquivalence",
    "CounterfactualRollbackPlan",
    "analyze_flow_stage_unavailability",
    "analyze_sir_flow_stage_unavailability",
    "analyze_sir_flow_recovery_options",
    "analyze_pure_sir_function_equivalence",
    "analyze_sir_flow_failure_rollback",
]
