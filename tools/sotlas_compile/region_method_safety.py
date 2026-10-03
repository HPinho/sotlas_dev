"""Fail-closed REGION reference escape checks for method calls.

The production safety pass already rejects REGION-derived references escaping
through returns, storage, and ordinary calls. Method calls need the same rule,
but must be validated against the resolved method signature rather than treated
as an untyped opaque call.

This pass is intentionally narrow: it does not create new borrowing semantics.
A REGION-derived reference may cross an explicit method argument only through
``direct`` or ``whisper``.  A REGION owner or alias used as the method receiver
is likewise accepted only when the resolved self parameter is explicitly
``direct`` or ``whisper``.  Plain ``&T`` receivers do not acquire a hidden
REGION lifetime contract; a future reusable no-escape certificate may relax
that boundary without changing this rule implicitly. Missing method/type facts
fail closed.
"""
from __future__ import annotations


def _param_name_type(param):
    if isinstance(param, tuple) and len(param) == 2:
        return param[0], param[1]
    return getattr(param, "name", None), getattr(param, "type", None)


class _RegionMethodEscapeChecker:
    def __init__(
        self,
        bootstrap,
        module,
        imported_fns=None,
        imported_types=None,
    ) -> None:
        self.b = bootstrap
        self.module = module
        self.filename = getattr(module, "filename", None)
        self.source = getattr(module, "source", None)
        self.functions = dict(getattr(bootstrap, "BUILTIN_FUNCTIONS", {}))
        self.functions.update(imported_fns or {})
        self.functions.update(
            {function.name: function for function in module.functions}
        )
        self.types = {
            item.name: item
            for item in (*module.structs, *module.classes)
        }
        self.types.update(imported_types or {})

    def error(self, message: str, token) -> None:
        raise self.b.SotlasBootstrapError(
            message,
            token.line,
            token.column,
            self.filename,
            self.source,
        )

    def _children(self, expr):
        b = self.b
        if expr is None:
            return ()
        if isinstance(expr, b.Binary):
            return (expr.left, expr.right)
        if isinstance(expr, (b.Unary, b.MoveExpr, b.ShareExpr, b.UnsafeExpr)):
            return (expr.value,)
        if isinstance(expr, b.Cast):
            return (expr.expr,)
        if isinstance(expr, b.Member):
            return (expr.target,)
        if isinstance(expr, b.Index):
            return (expr.target, expr.index)
        if isinstance(expr, b.Call):
            return tuple(expr.args)
        if isinstance(expr, b.MethodCall):
            return (expr.target, *tuple(expr.args))
        if isinstance(expr, b.StructLit):
            return tuple(value for _, value in expr.fields)
        if isinstance(expr, b.ArrayLit):
            return tuple(expr.elements)
        if isinstance(expr, b.IfExpr):
            return (expr.condition, expr.then_expr, expr.else_expr)
        if isinstance(expr, b.TryExpr):
            return (expr.expr,)
        return ()

    def _root_name(self, expr):
        b = self.b
        if isinstance(expr, b.Name):
            return expr.value
        if isinstance(expr, (b.Member, b.Index)):
            return self._root_name(expr.target)
        return None

    def _reference_sources(self, expr, aliases, region_owners) -> set[str]:
        b = self.b
        if expr is None:
            return set()
        if isinstance(expr, b.Name):
            return set(aliases.get(expr.value, ()))
        if isinstance(expr, b.Unary) and expr.op == "&":
            root = self._root_name(expr.value)
            if root in region_owners:
                return {root}
            if root in aliases:
                return set(aliases[root])
            return self._reference_sources(expr.value, aliases, region_owners)
        if isinstance(expr, b.Cast):
            return self._reference_sources(expr.expr, aliases, region_owners)
        result: set[str] = set()
        for child in self._children(expr):
            result.update(
                self._reference_sources(child, aliases, region_owners)
            )
        return result

    def _receiver_sources(self, expr, aliases, region_owners) -> set[str]:
        """Resolve direct REGION owners/aliases used as a method receiver."""
        root = self._root_name(expr)
        if root in region_owners:
            return {root}
        if root in aliases:
            return set(aliases[root]).intersection(region_owners)
        return self._reference_sources(expr, aliases, region_owners)

    def _method_calls(self, expr):
        b = self.b
        if expr is None:
            return
        if isinstance(expr, b.MethodCall):
            yield expr
        for child in self._children(expr):
            yield from self._method_calls(child)

    def _expr_type(self, expr, scope):
        b = self.b
        if expr is None:
            return None
        if isinstance(expr, b.Name):
            return scope.get(expr.value)
        if isinstance(expr, b.Unary) and expr.op == "&":
            return self._expr_type(expr.value, scope)
        if isinstance(expr, b.Member):
            target_type = self._expr_type(expr.target, scope)
            declaration = self.types.get(getattr(target_type, "name", ""))
            if declaration is None:
                return None
            field = next(
                (
                    item for item in getattr(declaration, "fields", ())
                    if item.name == expr.field
                ),
                None,
            )
            return getattr(field, "type", None)
        return None

    def _lookup_method(self, call, scope):
        target_type = self._expr_type(call.target, scope)
        type_name = getattr(target_type, "name", None)
        if not type_name:
            return None, None

        method = self.functions.get(f"{type_name}_{call.method}")
        if method is None:
            declaration = self.types.get(type_name)
            method = next(
                (
                    item for item in getattr(declaration, "methods", ()) or ()
                    if getattr(item, "name", None) == call.method
                ),
                None,
            )
        return type_name, method

    def _explicit_method_params(self, method, argument_count: int):
        params = tuple(getattr(method, "params", ()) or ())
        if not params:
            return ()
        first_name, _ = _param_name_type(params[0])
        if first_name == "self" or len(params) == argument_count + 1:
            return params[1:]
        return params

    def _check_expr(self, expr, scope, aliases, region_owners) -> None:
        for call in self._method_calls(expr):
            receiver_owners = self._receiver_sources(
                call.target, aliases, region_owners
            )
            region_args = [
                self._reference_sources(argument, aliases, region_owners)
                for argument in call.args
            ]
            if not receiver_owners and not any(region_args):
                continue

            type_name, method = self._lookup_method(call, scope)
            all_owners = set(receiver_owners)
            for owners in region_args:
                all_owners.update(owners)
            if method is None:
                owner = sorted(all_owners)[0]
                self.error(
                    f"reference to region owner {owner!r} cannot escape through "
                    f"unresolved method {call.method!r}",
                    call.token,
                )

            params = tuple(getattr(method, "params", ()) or ())
            if receiver_owners:
                self_parameter = params[0] if params else None
                self_name, self_type = _param_name_type(self_parameter)
                self_domain = getattr(self_type, "ownership_domain", None)
                if self_domain not in ("direct", "whisper"):
                    owner = sorted(receiver_owners)[0]
                    method_label = (
                        f"{type_name}.{call.method}"
                        if type_name else call.method
                    )
                    self.error(
                        f"region owner {owner!r} cannot cross method receiver "
                        f"boundary {method_label!r} through parameter "
                        f"{self_name or 'self'!r}; REGION receivers require an "
                        "explicit direct or whisper self parameter",
                        call.token,
                    )

            explicit_params = self._explicit_method_params(method, len(call.args))
            for index, owners in enumerate(region_args):
                if not owners:
                    continue
                parameter = (
                    explicit_params[index]
                    if index < len(explicit_params)
                    else None
                )
                parameter_name, parameter_type = _param_name_type(parameter)
                domain = getattr(parameter_type, "ownership_domain", None)
                if domain not in ("direct", "whisper"):
                    owner = sorted(owners)[0]
                    label = parameter_name or f"argument {index + 1}"
                    method_label = (
                        f"{type_name}.{call.method}"
                        if type_name else call.method
                    )
                    self.error(
                        f"reference to region owner {owner!r} cannot escape "
                        f"through method {method_label!r} parameter {label!r}; "
                        "REGION references crossing method boundaries require "
                        "an explicit direct or whisper parameter",
                        call.token,
                    )

    def _check_handover_aliases(self, item, aliases, region_owners) -> None:
        """Mark aliases stale when their REGION owner is transferred."""
        b = self.b
        if not isinstance(item, b.Handover):
            return
        source = self._root_name(item.value)
        if source not in region_owners:
            return
        for alias, owners in aliases.items():
            if source in owners:
                aliases[alias] = {
                    f"\0invalid:{owner}" if owner == source else owner
                    for owner in owners
                }

    def _moved_region_owners(self, item, region_owners) -> set[str]:
        """Find direct REGION owners consumed by move expressions in a statement."""
        b = self.b
        moved: set[str] = set()

        def visit(expr):
            if expr is None:
                return
            if isinstance(expr, b.MoveExpr):
                owner = self._root_name(expr.value)
                if owner in region_owners:
                    moved.add(owner)
            for child in self._children(expr):
                visit(child)

        for expr in self._statement_exprs(item):
            visit(expr)
        return moved

    def _invalidate_moved_aliases(self, item, aliases, region_owners) -> None:
        for owner in self._moved_region_owners(item, region_owners):
            for alias, owners in aliases.items():
                if owner in owners:
                    aliases[alias] = {
                        f"\0invalid-move:{owner}" if candidate == owner else candidate
                        for candidate in owners
                    }

    def _check_deferred_handover(self, item, deferred_names, aliases) -> None:
        b = self.b
        if not isinstance(item, b.Handover):
            return
        source = self._root_name(item.value)
        if source is None:
            return
        for name in sorted(deferred_names):
            owners = {name} if name == source else aliases.get(name, set())
            if source in owners:
                self.error(
                    f"defer uses reference alias {name!r} after handover of "
                    f"owner {source!r}",
                    item.token,
                )

    def _check_invalid_alias_use(self, expr, aliases) -> None:
        if expr is None:
            return
        names = set()
        if isinstance(expr, self.b.Name):
            names.add(expr.value)
        for child in self._children(expr):
            self._collect_expr_names(child, names)
        for name in sorted(names):
            invalid = next((
                owner for owner in aliases.get(name, ())
                if owner.startswith(("\0invalid:", "\0invalid-move:"))
            ), None)
            if invalid is not None:
                if invalid.startswith("\0invalid-move:"):
                    owner = invalid.removeprefix("\0invalid-move:")
                    message = (
                        f"reference alias {name!r} to moved owner {owner!r} "
                        "is used after move"
                    )
                else:
                    owner = invalid.removeprefix("\0invalid:")
                    message = (
                        f"reference alias {name!r} to transferred owner {owner!r} "
                        "is used after handover"
                    )
                self.error(message, expr.token)

    def _collect_expr_names(self, expr, result) -> None:
        if isinstance(expr, self.b.Name):
            result.add(expr.value)
        for child in self._children(expr):
            self._collect_expr_names(child, result)

    def _defer_alias_uses(self, item) -> set[str]:
        names: set[str] = set()

        def visit(statements):
            for statement in statements or ():
                for expr in self._statement_exprs(statement):
                    self._collect_expr_names(expr, names)
                for attr in ("then_body", "else_body", "body"):
                    nested = getattr(statement, attr, None)
                    if nested:
                        visit(nested)
                for case in getattr(statement, "cases", ()) or ():
                    visit(getattr(case, "body", ()))

        visit(getattr(item, "body", ()) or ())
        self._collect_expr_names(getattr(item, "value", None), names)
        return names

    def _statement_exprs(self, item):
        b = self.b
        attrs = {
            b.Let: ("value",),
            b.Assign: ("target", "value"),
            b.Return: ("value",),
            b.Expression: ("value",),
            b.If: ("condition",),
            b.While: ("condition",),
            b.For: ("start", "end"),
            b.Handover: ("value", "destination"),
            b.Quarantine: ("value",),
            b.Defer: ("value",),
        }.get(type(item), ())
        expressions = [getattr(item, attr, None) for attr in attrs]
        if isinstance(item, b.Asm):
            expressions.extend(item.inputs)
            expressions.extend(item.outputs)
        return tuple(expr for expr in expressions if expr is not None)

    def _check_statements(
        self, statements, scope, region_owners, aliases, deferred_names=None
    ) -> None:
        b = self.b
        if deferred_names is None:
            deferred_names = set()
        for item in statements:
            self._check_deferred_handover(item, deferred_names, aliases)
            for expr in self._statement_exprs(item):
                is_rebinding_target = (
                    isinstance(item, b.Assign)
                    and expr is item.target
                    and isinstance(item.target, b.Name)
                )
                if not is_rebinding_target:
                    self._check_invalid_alias_use(expr, aliases)
                self._check_expr(expr, scope, aliases, region_owners)
            self._check_handover_aliases(item, aliases, region_owners)
            self._invalidate_moved_aliases(item, aliases, region_owners)

            if isinstance(item, b.Defer):
                deferred_names.update(self._defer_alias_uses(item))

            if isinstance(item, b.Let):
                typ = item.type
                if typ is not None:
                    scope[item.name] = typ
                    if getattr(typ, "ownership_domain", None) == "region":
                        region_owners.add(item.name)
                sources = self._reference_sources(
                    item.value, aliases, region_owners
                )
                if sources:
                    aliases[item.name] = set(sources)
                else:
                    aliases.pop(item.name, None)

            elif isinstance(item, b.Assign):
                target = self._root_name(item.target)
                if target is not None:
                    sources = self._reference_sources(
                        item.value, aliases, region_owners
                    )
                    if sources:
                        aliases[target] = set(sources)
                    else:
                        aliases.pop(target, None)

            nested_bodies = None
            may_skip = False
            if isinstance(item, b.If):
                nested_bodies = (
                    getattr(item, "then_body", ()) or (),
                    getattr(item, "else_body", ()) or (),
                )
                may_skip = True
            elif isinstance(item, (b.While, b.For, b.Loop)):
                nested_bodies = (getattr(item, "body", ()) or (),)
                may_skip = True
            elif isinstance(item, b.Unsafe):
                nested_bodies = (getattr(item, "body", ()) or (),)
            elif isinstance(item, b.Defer):
                # Deferred bodies execute at scope exit; checking them must not
                # make their later assignments appear to happen immediately.
                nested_bodies = (getattr(item, "body", ()) or (),)
                may_skip = True
            elif type(item).__name__ == "Discern":
                nested_bodies = tuple(case.body for case in item.cases)
                # Unless exhaustiveness is proven at this stage, preserve the
                # incoming alias state as an additional possible path.
                may_skip = True

            if nested_bodies is not None:
                # Inferred reference locals need not have an explicit entry in
                # ``scope``; aliases are still live bindings and must join at
                # the control-flow merge.
                outer_names = set(scope) | set(aliases)
                incoming_aliases = {
                    name: set(owners) for name, owners in aliases.items()
                }
                branch_aliases = []
                branch_local_names = []
                for statements_in_branch in nested_bodies:
                    branch_scope = dict(scope)
                    branch_state = {
                        name: set(owners)
                        for name, owners in incoming_aliases.items()
                    }
                    self._check_statements(
                        statements_in_branch,
                        branch_scope,
                        set(region_owners),
                        branch_state,
                        set(deferred_names),
                    )
                    branch_aliases.append(branch_state)
                    branch_local_names.append({
                        statement.name
                        for statement in statements_in_branch
                        if isinstance(statement, b.Let)
                    })
                if may_skip:
                    branch_aliases.append(incoming_aliases)

                # Carry aliases assigned on any path to a later use. The union
                # is intentionally conservative: a later opaque call must be
                # safe for every possible source, including REGION owners.
                for name in outer_names:
                    sources = set().union(*(
                        branch.get(name, set())
                        for branch, local_names in zip(
                            branch_aliases, branch_local_names
                        )
                        if name not in local_names
                    )) if branch_aliases else set()
                    if sources:
                        aliases[name] = sources
                    else:
                        aliases.pop(name, None)


    def _functions_to_check(self):
        result = []
        seen = set()
        for function in self.module.functions:
            if id(function) not in seen:
                result.append(function)
                seen.add(id(function))
        for declaration in self.types.values():
            for method in getattr(declaration, "methods", ()) or ():
                if id(method) not in seen:
                    result.append(method)
                    seen.add(id(method))
        return tuple(result)

    def check(self) -> None:
        for function in self._functions_to_check():
            scope = {
                name: typ
                for name, typ in (
                    _param_name_type(param)
                    for param in getattr(function, "params", ()) or ()
                )
                if name is not None and typ is not None
            }
            region_owners = {
                name for name, typ in scope.items()
                if getattr(typ, "ownership_domain", None) == "region"
            }
            self._check_statements(
                getattr(function, "body", ()) or (),
                scope,
                region_owners,
                {},
            )


def install(bootstrap) -> None:
    if getattr(bootstrap, "_REGION_METHOD_SAFETY_INSTALLED", False):
        return

    original_check = bootstrap.check

    def region_method_safe_check(
        module,
        imported_fns=None,
        imported_types=None,
        imported_enums=None,
        imported_globals=None,
    ):
        result = original_check(
            module,
            imported_fns,
            imported_types,
            imported_enums,
            imported_globals,
        )
        _RegionMethodEscapeChecker(
            bootstrap,
            module,
            imported_fns=imported_fns,
            imported_types=imported_types,
        ).check()
        return result

    bootstrap.check = region_method_safe_check
    bootstrap._REGION_METHOD_SAFETY_INSTALLED = True


__all__ = ["install"]
