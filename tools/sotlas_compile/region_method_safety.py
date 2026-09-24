"""Fail-closed REGION reference escape checks for method calls.

The production safety pass already rejects REGION-derived references escaping
through returns, storage, and ordinary calls. Method calls need the same rule,
but must be validated against the resolved method signature rather than treated
as an untyped opaque call.

This pass is intentionally narrow: it does not create new borrowing semantics.
It only permits an existing REGION-derived reference to cross a method-call
boundary when the corresponding method parameter is explicitly ``direct`` or
``whisper``. Missing method/type facts fail closed.
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
            region_args = [
                self._reference_sources(argument, aliases, region_owners)
                for argument in call.args
            ]
            if not any(region_args):
                continue

            type_name, method = self._lookup_method(call, scope)
            if method is None:
                owner = sorted(set().union(*region_args))[0]
                self.error(
                    f"reference to region owner {owner!r} cannot escape through "
                    f"unresolved method {call.method!r}",
                    call.token,
                )

            params = self._explicit_method_params(method, len(call.args))
            for index, owners in enumerate(region_args):
                if not owners:
                    continue
                parameter = params[index] if index < len(params) else None
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

    def _check_statements(self, statements, scope, region_owners, aliases) -> None:
        b = self.b
        for item in statements:
            for expr in self._statement_exprs(item):
                self._check_expr(expr, scope, aliases, region_owners)

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

            nested = {
                b.If: ("then_body", "else_body"),
                b.While: ("body",),
                b.For: ("body",),
                b.Loop: ("body",),
                b.Unsafe: ("body",),
                b.Defer: ("body",),
            }.get(type(item), ())
            for attr in nested:
                self._check_statements(
                    getattr(item, attr, ()) or (),
                    dict(scope),
                    set(region_owners),
                    {name: set(owners) for name, owners in aliases.items()},
                )

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
