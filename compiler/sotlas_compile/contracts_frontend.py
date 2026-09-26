"""Conservative function preconditions for the Sotlas 1.0 contract subset."""
from __future__ import annotations

from dataclasses import dataclass
import math
import re


class ContractFrontendError(ValueError):
    """Raised when a function precondition is malformed or cannot be proved."""


@dataclass(frozen=True)
class ContractCallProof:
    function: str
    line: int
    column: int
    predicate: str
    arguments: tuple[tuple[str, object], ...]
    refinements: tuple[str, ...] = ()


@dataclass(frozen=True)
class ContractPrecondition:
    function: str
    predicate: str


@dataclass(frozen=True)
class ContractPostcondition:
    function: str
    predicate: str


def _render(expr, bootstrap) -> str:
    if isinstance(expr, bootstrap.Name):
        return expr.value
    if isinstance(expr, bootstrap.Number):
        return expr.value
    if isinstance(expr, bootstrap.Boolean):
        return "true" if expr.value else "false"
    if isinstance(expr, bootstrap.Unary):
        return f"{expr.op}{_render(expr.value, bootstrap)}"
    if isinstance(expr, bootstrap.Binary):
        return (
            f"({_render(expr.left, bootstrap)} {expr.op} "
            f"{_render(expr.right, bootstrap)})"
        )
    raise ContractFrontendError(
        f"unsupported expression in contract: {type(expr).__name__}"
    )


def _referenced_parameters(expr, bootstrap) -> frozenset[str]:
    if isinstance(expr, bootstrap.Name):
        return frozenset((expr.value,))
    if isinstance(expr, bootstrap.Unary):
        return _referenced_parameters(expr.value, bootstrap)
    if isinstance(expr, bootstrap.Binary):
        return (
            _referenced_parameters(expr.left, bootstrap)
            | _referenced_parameters(expr.right, bootstrap)
        )
    return frozenset()


def _render_with_bindings(expr, bindings, bootstrap) -> str:
    if isinstance(expr, bootstrap.Name) and expr.value in bindings:
        return _render(bindings[expr.value], bootstrap)
    if isinstance(expr, bootstrap.Unary):
        return f"{expr.op}{_render_with_bindings(expr.value, bindings, bootstrap)}"
    if isinstance(expr, bootstrap.Binary):
        return (
            f"({_render_with_bindings(expr.left, bindings, bootstrap)} {expr.op} "
            f"{_render_with_bindings(expr.right, bindings, bootstrap)})"
        )
    return _render(expr, bootstrap)


def _refinement_terms(expr, bindings, bootstrap) -> tuple[str, ...]:
    if isinstance(expr, bootstrap.Binary) and expr.op == "&&":
        return (
            _refinement_terms(expr.left, bindings, bootstrap)
            + _refinement_terms(expr.right, bindings, bootstrap)
        )
    try:
        return (_render_with_bindings(expr, bindings, bootstrap),)
    except ContractFrontendError:
        # Complex arguments (calls, fields, indexing, and so on) stay guarded
        # in the callee until the contract model can describe their effects.
        return ()


_INVERT_COMPARISON = {
    "==": "!=", "!=": "==", "<": ">=", "<=": ">",
    ">": "<=", ">=": "<",
}

_COMPARISON_FACT = re.compile(
    r"^\(?\s*([A-Za-z_][A-Za-z0-9_]*)\s*(==|!=|<=|>=|<|>)\s*"
    r"(-?\d+)(?:[ui](?:8|16|32|64)|isize|usize)?\s*\)?$"
)
_REVERSED_COMPARISON = {
    "==": "==", "!=": "!=", "<": ">", "<=": ">=",
    ">": "<", ">=": "<=",
}


def _comparison_fact(fact):
    match = _COMPARISON_FACT.match(fact.strip())
    if match:
        name, op, value = match.groups()
        return name, op, int(value)
    # A constant on the left is equivalent after reversing the operator.
    match = re.match(
        r"^\(?\s*(-?\d+)(?:[ui](?:8|16|32|64)|isize|usize)?\s*"
        r"(==|!=|<=|>=|<|>)\s*([A-Za-z_][A-Za-z0-9_]*)\s*\)?$",
        fact.strip(),
    )
    if match:
        value, op, name = match.groups()
        return name, _REVERSED_COMPARISON[op], int(value)
    return None


def _facts_imply(required, facts):
    """Prove a simple integer comparison from branch comparison facts."""
    target = _comparison_fact(required)
    if target is None:
        return False
    name, op, value = target
    lower = None
    upper = None
    equal = None
    excluded = set()
    for fact in facts:
        constraint = _comparison_fact(fact)
        if constraint is None or constraint[0] != name:
            continue
        _, fact_op, boundary = constraint
        if fact_op == "==":
            if equal is not None and equal != boundary:
                return False
            equal = boundary
        elif fact_op == "!=":
            excluded.add(boundary)
        elif fact_op == ">":
            lower = boundary + 1 if lower is None else max(lower, boundary + 1)
        elif fact_op == ">=":
            lower = boundary if lower is None else max(lower, boundary)
        elif fact_op == "<":
            upper = boundary - 1 if upper is None else min(upper, boundary - 1)
        elif fact_op == "<=":
            upper = boundary if upper is None else min(upper, boundary)
    if equal is not None:
        if (lower is not None and equal < lower) or (
            upper is not None and equal > upper
        ):
            return False
        if equal in excluded:
            return False
        return {
            "==": equal == value, "!=": equal != value,
            "<": equal < value, "<=": equal <= value,
            ">": equal > value, ">=": equal >= value,
        }[op]
    if lower is not None and upper is not None and lower > upper:
        return False
    if op == "!=":
        return (
            value in excluded
            or (upper is not None and upper < value)
            or (lower is not None and lower > value)
        )
    if op == "==":
        return lower == upper == value
    if op == ">":
        return lower is not None and lower > value
    if op == ">=":
        return lower is not None and lower >= value
    if op == "<":
        return upper is not None and upper < value
    return upper is not None and upper <= value


def _condition_facts(expr, truth, bootstrap) -> frozenset[str]:
    """Return only facts that logically hold on the selected branch."""
    if any(isinstance(node, bootstrap.Call) for node in _walk(expr, bootstrap)):
        return frozenset()
    if isinstance(expr, bootstrap.Unary) and expr.op == "!":
        return _condition_facts(expr.value, not truth, bootstrap)
    if isinstance(expr, bootstrap.Binary):
        if expr.op == "&&" and truth:
            return (
                _condition_facts(expr.left, True, bootstrap)
                | _condition_facts(expr.right, True, bootstrap)
            )
        if expr.op == "||" and not truth:
            return (
                _condition_facts(expr.left, False, bootstrap)
                | _condition_facts(expr.right, False, bootstrap)
            )
        if expr.op in _INVERT_COMPARISON:
            op = expr.op if truth else _INVERT_COMPARISON[expr.op]
            try:
                fact = (
                    f"({_render(expr.left, bootstrap)} {op} "
                    f"{_render(expr.right, bootstrap)})"
                )
            except ContractFrontendError:
                return frozenset()
            return frozenset((fact,))
    if isinstance(expr, bootstrap.Boolean):
        return frozenset(("true" if truth else "false",))
    return frozenset()


def _calls_with_refinements(value, bootstrap, facts=frozenset()):
    if isinstance(value, (tuple, list)):
        active = facts
        for item in value:
            yield from _calls_with_refinements(item, bootstrap, active)
            if any(
                isinstance(node, bootstrap.Call)
                for node in _walk(item, bootstrap)
            ):
                active = frozenset()
            if isinstance(item, bootstrap.Assign) and isinstance(
                item.target, bootstrap.Name
            ):
                assigned = re.compile(
                    rf"(?<![A-Za-z0-9_]){re.escape(item.target.value)}"
                    rf"(?![A-Za-z0-9_])"
                )
                active = frozenset(
                    fact for fact in active if not assigned.search(fact)
                )
            elif isinstance(item, bootstrap.Let):
                shadowed = re.compile(
                    rf"(?<![A-Za-z0-9_]){re.escape(item.name)}"
                    rf"(?![A-Za-z0-9_])"
                )
                active = frozenset(
                    fact for fact in active if not shadowed.search(fact)
                )
        return
    if not isinstance(value, (bootstrap.Expr, bootstrap.Stmt)):
        return
    if isinstance(value, bootstrap.If):
        yield from _calls_with_refinements(value.condition, bootstrap, facts)
        yield from _calls_with_refinements(
            value.then_body, bootstrap,
            facts | _condition_facts(value.condition, True, bootstrap),
        )
        yield from _calls_with_refinements(
            value.else_body, bootstrap,
            facts | _condition_facts(value.condition, False, bootstrap),
        )
        return
    if isinstance(value, bootstrap.IfExpr):
        yield from _calls_with_refinements(value.condition, bootstrap, facts)
        yield from _calls_with_refinements(
            value.then_expr, bootstrap,
            facts | _condition_facts(value.condition, True, bootstrap),
        )
        yield from _calls_with_refinements(
            value.else_expr, bootstrap,
            facts | _condition_facts(value.condition, False, bootstrap),
        )
        return
    if isinstance(value, bootstrap.While):
        yield from _calls_with_refinements(value.condition, bootstrap, facts)
        body_facts = facts | _condition_facts(value.condition, True, bootstrap)
        yield from _calls_with_refinements(value.body, bootstrap, body_facts)
        return
    if isinstance(value, bootstrap.Call):
        yield value, facts
    for name, child in vars(value).items():
        if name in {"token", "type", "target_type"}:
            continue
        if isinstance(child, dict):
            yield from _calls_with_refinements(tuple(child.values()), bootstrap, facts)
        else:
            yield from _calls_with_refinements(child, bootstrap, facts)


def _contract_type(expr, scope, bootstrap):
    if isinstance(expr, bootstrap.Name):
        if expr.value not in scope:
            raise ContractFrontendError(
                f"requires references unknown parameter {expr.value!r}"
            )
        return scope[expr.value]
    if isinstance(expr, bootstrap.Number):
        try:
            return bootstrap.Type(bootstrap.numeric_literal_type(expr.value))
        except ValueError as error:
            raise ContractFrontendError(str(error)) from error
    if isinstance(expr, bootstrap.Boolean):
        return bootstrap.Type("bool")
    if isinstance(expr, bootstrap.Unary):
        inner = _contract_type(expr.value, scope, bootstrap)
        if expr.op == "!" and inner.name == "bool":
            return bootstrap.Type("bool")
        if expr.op == "+" and inner.name in (
            "u8", "u16", "u32", "u64", "usize", "i8", "i16", "i32",
            "i64", "isize", "f32", "f64",
        ):
            return inner
        raise ContractFrontendError(
            f"operator {expr.op!r} is unsupported in requires"
        )
    if isinstance(expr, bootstrap.Binary):
        left = _contract_type(expr.left, scope, bootstrap)
        right = _contract_type(expr.right, scope, bootstrap)
        if expr.op in ("&&", "||"):
            if left.name != "bool" or right.name != "bool":
                raise ContractFrontendError(
                    f"operator {expr.op!r} in requires expects bool operands"
                )
            return bootstrap.Type("bool")
        numeric = {
            "u8", "u16", "u32", "u64", "usize", "i8", "i16", "i32",
            "i64", "isize", "f32", "f64",
        }
        integers = numeric - {"f32", "f64"}
        comparators = ("==", "!=", "<", "<=", ">", ">=")
        if expr.op in comparators:
            compatible = left.name == right.name
            if isinstance(expr.left, bootstrap.Number):
                base, suffix = bootstrap.numeric_literal_parts(expr.left.value)
                compatible |= (
                    suffix is None
                    and "." not in base
                    and right.name in integers
                )
            if isinstance(expr.right, bootstrap.Number):
                base, suffix = bootstrap.numeric_literal_parts(expr.right.value)
                compatible |= (
                    suffix is None
                    and "." not in base
                    and left.name in integers
                )
            if compatible and (
                expr.op in ("==", "!=")
                or (left.name in numeric and right.name in numeric)
            ):
                return bootstrap.Type("bool")
        raise ContractFrontendError(
            f"requires supports only compatible comparisons and boolean operators; "
            f"invalid operands for {expr.op!r}"
        )
    raise ContractFrontendError(
        f"unsupported expression in requires contract: {type(expr).__name__}"
    )


def _constant(expr, names, bootstrap):
    if isinstance(expr, bootstrap.Name):
        return names.get(expr.value)
    if isinstance(expr, bootstrap.Number):
        try:
            base, suffix = bootstrap.numeric_literal_parts(expr.value)
            value = float(base) if "." in base else int(base, 0)
            if isinstance(value, float) and not math.isfinite(value):
                return None
            return value
        except (ValueError, OverflowError):
            return None
    if isinstance(expr, bootstrap.Boolean):
        return expr.value
    if isinstance(expr, bootstrap.Unary):
        value = _constant(expr.value, names, bootstrap)
        if value is None:
            return None
        if expr.op == "!" and isinstance(value, bool):
            return not value
        if expr.op == "+" and not isinstance(value, bool):
            return +value
        if expr.op == "-" and not isinstance(value, bool):
            return -value
        return None
    if not isinstance(expr, bootstrap.Binary):
        return None
    left = _constant(expr.left, names, bootstrap)
    if expr.op == "&&" and left is False:
        return False
    if expr.op == "||" and left is True:
        return True
    right = _constant(expr.right, names, bootstrap)
    if left is None or right is None:
        return None
    if isinstance(left, bool) != isinstance(right, bool):
        return None
    operations = {
        "+": lambda: left + right,
        "-": lambda: left - right,
        "*": lambda: left * right,
        "/": lambda: int(left / right) if isinstance(left, int) else left / right,
        "%": lambda: left - int(left / right) * right,
        "<<": lambda: left << right,
        ">>": lambda: left >> right,
        "&": lambda: left & right,
        "|": lambda: left | right,
        "^": lambda: left ^ right,
        "==": lambda: left == right,
        "!=": lambda: left != right,
        "<": lambda: left < right,
        "<=": lambda: left <= right,
        ">": lambda: left > right,
        ">=": lambda: left >= right,
        "&&": lambda: bool(left and right),
        "||": lambda: bool(left or right),
    }
    operation = operations.get(expr.op)
    if operation is None:
        return None
    try:
        value = operation()
    except (ArithmeticError, TypeError, ValueError):
        return None
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def _walk(value, bootstrap):
    if isinstance(value, (tuple, list)):
        for item in value:
            yield from _walk(item, bootstrap)
        return
    is_ast = isinstance(value, (bootstrap.Expr, bootstrap.Stmt))
    is_state_case = type(value).__name__ == "StateCase"
    if not is_ast and not is_state_case:
        return
    if is_ast:
        yield value
    for name, child in vars(value).items():
        if name in {"token", "type", "target_type"}:
            continue
        if isinstance(child, dict):
            yield from _walk(tuple(child.values()), bootstrap)
        else:
            yield from _walk(child, bootstrap)


def _error(bootstrap, message, token, module):
    raise bootstrap.SotlasBootstrapError(
        message,
        getattr(token, "line", 1),
        getattr(token, "column", 1),
        module.filename,
        module.source,
    )


def install(bootstrap) -> None:
    parser = bootstrap.Parser
    if getattr(parser, "_sotlas_contracts_installed", False):
        return
    original_function = parser.function

    def function_with_contracts(self, public, attributes=None):
        original_block = self.block
        parsed = []

        def block_with_contracts():
            self.block = original_block
            while (
                self.current.kind == "IDENT"
                and self.current.text in {"requires", "ensures"}
            ):
                token = self.current
                self.at += 1
                parsed.append((token.text, token, self.expression()))
            return original_block()

        self.block = block_with_contracts
        try:
            function = original_function(self, public, attributes)
        finally:
            self.block = original_block
        seen = set()
        for kind, token, expression in parsed:
            if kind in seen:
                raise bootstrap.SotlasBootstrapError(
                    f"function repeats {kind} contract",
                    token.line, token.column,
                    self.filename, self.source,
                )
            seen.add(kind)
            setattr(function, f"{kind}_token", token)
            setattr(function, kind, expression)
        return function

    parser.function = function_with_contracts
    parser._sotlas_contracts_installed = True

    original_check = bootstrap.check

    def check_with_contracts(module, *args, **kwargs):
        result = original_check(module, *args, **kwargs)
        functions = {function.name: function for function in module.functions}
        contracts = {
            name: getattr(function, "requires", None)
            for name, function in functions.items()
            if getattr(function, "requires", None) is not None
        }
        postconditions = {
            name: getattr(function, "ensures", None)
            for name, function in functions.items()
            if getattr(function, "ensures", None) is not None
        }
        proofs = []
        for name, expression in contracts.items():
            function = functions[name]
            token = getattr(function, "requires_token", None)
            if not function.body or "@extern(C)" in function.attributes:
                _error(
                    bootstrap,
                    "requires is supported only on functions with a checked body",
                    token,
                    module,
                )
            try:
                result_type = _contract_type(
                    expression, dict(function.params), bootstrap
                )
            except ContractFrontendError as error:
                _error(bootstrap, str(error), token, module)
            if result_type.name != "bool":
                _error(bootstrap, "requires expression must have type bool", token, module)

        for name, expression in postconditions.items():
            function = functions[name]
            token = getattr(function, "ensures_token", None)
            numeric_results = {
                "u8", "u16", "u32", "u64", "usize", "i8", "i16",
                "i32", "i64", "isize", "f32", "f64",
            }
            scalar_results = numeric_results | {"bool"}
            if (
                not function.body
                or "@extern(C)" in function.attributes
                or function.result.name not in scalar_results
            ):
                _error(
                    bootstrap,
                    "ensures currently requires a checked function with a scalar numeric or bool return",
                    token,
                    module,
                )
            if any(param_name == "result" for param_name, _ in function.params):
                _error(
                    bootstrap,
                    "ensures reserves the name 'result' for the returned value",
                    token,
                    module,
                )
            try:
                result_type = _contract_type(
                    expression,
                    {**dict(function.params), "result": function.result},
                    bootstrap,
                )
            except ContractFrontendError as error:
                _error(bootstrap, str(error), token, module)
            if result_type.name != "bool":
                _error(bootstrap, "ensures expression must have type bool", token, module)
            referenced = _referenced_parameters(expression, bootstrap)
            referenced_parameters = referenced - {"result"}
            if referenced_parameters - set(dict(function.params)):
                _error(
                    bootstrap,
                    "ensures references an unknown parameter",
                    token,
                    module,
                )
            scalar_contract_types = scalar_results
            invalid_parameters = tuple(
                parameter
                for parameter, parameter_type in function.params
                if parameter in referenced_parameters
                and (
                    parameter_type.name not in scalar_contract_types
                    or parameter_type.pointer
                    or parameter_type.is_reference
                    or parameter_type.is_array
                    or parameter_type.is_fn_ptr
                )
            )
            if invalid_parameters:
                _error(
                    bootstrap,
                    "ensures may reference only scalar numeric or bool parameters; "
                    "unsupported: " + ", ".join(invalid_parameters),
                    token,
                    module,
                )

        checked_roots = [function.body for function in module.functions]
        checked_roots.extend(global_value.value for global_value in module.globals)
        for root in checked_roots:
            for expression_node, active_facts in _calls_with_refinements(
                root, bootstrap
            ):
                predicate = contracts.get(expression_node.callee)
                if predicate is None:
                    continue
                target = functions[expression_node.callee]
                if len(expression_node.args) != len(target.params):
                    continue  # The ordinary type checker reports arity first.
                argument_values = tuple(
                    (param_name, _constant(argument, {}, bootstrap))
                    for argument, (param_name, _) in zip(
                        expression_node.args, target.params
                    )
                )
                bindings = dict(argument_values)
                proved = _constant(predicate, bindings, bootstrap)
                refinement_terms = _refinement_terms(
                    predicate,
                    {
                        param_name: argument
                        for argument, (param_name, _) in zip(
                            expression_node.args, target.params
                        )
                    },
                    bootstrap,
                )
                matched_refinements = []
                for term in refinement_terms:
                    if term in active_facts:
                        matched_refinements.append((term,))
                        continue
                    supporting_facts = tuple(
                        fact for fact in active_facts
                        if _facts_imply(term, (fact,))
                    )
                    if not supporting_facts and _facts_imply(term, active_facts):
                        supporting_facts = tuple(sorted(active_facts))
                    matched_refinements.append(supporting_facts)
                flow_proved = bool(refinement_terms) and all(matched_refinements)
                refinements = tuple(
                    fact for group in matched_refinements for fact in group
                )
                if proved is False:
                    _error(
                        bootstrap,
                        f"requires contract for call to {target.name!r} is not satisfied",
                        expression_node.token,
                        module,
                    )
                if proved is not True and not flow_proved:
                    # The callee enforces predicates that cannot be proved from
                    # call-site constants; the report records proofs only.
                    continue
                referenced = _referenced_parameters(predicate, bootstrap)
                proven_arguments = tuple(
                    (name, value)
                    for name, value in argument_values
                    if name in referenced
                )
                proofs.append(ContractCallProof(
                    target.name,
                    expression_node.token.line,
                    expression_node.token.column,
                    _render(predicate, bootstrap),
                    proven_arguments,
                    refinements if flow_proved and proved is not True else (),
                ))
        module.contract_proofs = tuple(proofs)
        module.contract_preconditions = tuple(
            ContractPrecondition(name, _render(expression, bootstrap))
            for name, expression in contracts.items()
        )
        module.contract_postconditions = tuple(
            ContractPostcondition(name, _render(expression, bootstrap))
            for name, expression in postconditions.items()
        )
        return result

    bootstrap.check = check_with_contracts


__all__ = [
    "ContractFrontendError", "ContractCallProof", "ContractPrecondition",
    "ContractPostcondition",
    "install",
]
