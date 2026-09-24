"""Canonical safety and C-ABI policy for the production Sotlas frontend.

`@system` identifies code that may cross into privileged backend intrinsics.
It is not an implicit unsafe block.  Safe Sotlas may call a safe @system wrapper;
only direct privileged builtins, FFI entry points, and concrete raw-memory
operations are restricted by this pass.
"""
from __future__ import annotations

from dataclasses import dataclass
import importlib

_EXTERN_ATTR = "@extern(C)"
_UNSAFE_ATTR = "@unsafe"
_EXPORT_ATTR = "@export"

# Compatibility adapters may register narrowly audited @system builtins that
# are safe to call from ordinary code. Canonical safety policy itself remains
# platform/project agnostic; concrete names belong to adapters, not this module.
_SAFE_SYSTEM_BUILTINS: set[str] = set()


def register_safe_system_builtins(names) -> None:
    _SAFE_SYSTEM_BUILTINS.update(names)


def _attr(function, name: str) -> bool:
    return name in getattr(function, "attributes", ())


def _mark_pointer_kind(type_obj, *, raw=False, reference=False) -> None:
    if type_obj is None or not getattr(type_obj, "pointer", False):
        return
    if raw:
        object.__setattr__(type_obj, "_sotlas_raw_pointer", True)
    if reference:
        object.__setattr__(type_obj, "_sotlas_reference", True)


def _is_raw_pointer(type_obj) -> bool:
    return bool(
        type_obj is not None
        and getattr(type_obj, "pointer", False)
        and not getattr(type_obj, "is_array", False)
        and not getattr(type_obj, "_sotlas_reference", False)
        and not getattr(type_obj, "is_reference", False)
    )


def _mark_foreign(type_obj) -> None:
    if _is_raw_pointer(type_obj):
        object.__setattr__(type_obj, "_sotlas_foreign_pointer", True)


def _synthetic(bootstrap, kind: str, text: str, anchor):
    return bootstrap.Token(kind, text, anchor.line, anchor.column)


def _validate_abi(token, bootstrap, filename, source) -> None:
    text = token.text
    if len(text) < 2 or not text.startswith('"') or not text.endswith('"'):
        raise bootstrap.SotlasBootstrapError(
            'extern exige ABI explícita: extern "C"',
            token.line, token.column, filename, source,
        )
    abi = text[1:-1]
    if abi != "C":
        raise bootstrap.SotlasBootstrapError(
            f"ABI externa não suportada: {abi!r}; somente extern \"C\" é estável",
            token.line, token.column, filename, source,
        )


def _copy_extern_decl(tokens, index, bootstrap, anchor, filename, source):
    """Turn one FFI prototype into a normal canonical fn AST declaration.

    The signature tokens are not reparsed here.  They are copied verbatim and
    consumed by the normal bootstrap parser, which remains the sole type/body
    grammar.  Only the foreign-boundary metadata and synthetic empty body are
    introduced by this normalization.
    """
    attrs = []
    public = None
    is_unsafe = False
    while index < len(tokens):
        token = tokens[index]
        if token.kind == "ATTR":
            attrs.append(token); index += 1; continue
        if token.kind == "pub" and public is None:
            public = token; index += 1; continue
        if token.kind == "unsafe" and not is_unsafe:
            is_unsafe = True; index += 1; continue
        break

    if index >= len(tokens) or tokens[index].kind != "fn":
        token = tokens[index] if index < len(tokens) else anchor
        raise bootstrap.SotlasBootstrapError(
            'extern "C" aceita somente declarações fn',
            token.line, token.column, filename, source,
        )

    output = list(attrs)
    output.extend([
        _synthetic(bootstrap, "ATTR", _EXTERN_ATTR, anchor),
        _synthetic(bootstrap, "ATTR", _EXPORT_ATTR, anchor),
    ])
    if is_unsafe:
        output.append(_synthetic(bootstrap, "ATTR", _UNSAFE_ATTR, anchor))
    if public is not None:
        output.append(public)

    paren_depth = 0
    bracket_depth = 0
    while index < len(tokens):
        token = tokens[index]
        if token.kind == "EOF":
            break
        if token.kind == "(": paren_depth += 1
        elif token.kind == ")": paren_depth -= 1
        elif token.kind == "[": bracket_depth += 1
        elif token.kind == "]": bracket_depth -= 1
        if token.kind == ";" and paren_depth == 0 and bracket_depth == 0:
            output.append(_synthetic(bootstrap, "{", "{", token))
            output.append(_synthetic(bootstrap, "}", "}", token))
            return output, index + 1
        output.append(token)
        index += 1

    raise bootstrap.SotlasBootstrapError(
        "declaração extern sem ';'",
        anchor.line, anchor.column, filename, source,
    )


def _normalize_extern_tokens(tokens, bootstrap, filename, source):
    output = []
    index = 0
    while index < len(tokens):
        token = tokens[index]
        if token.kind != "extern":
            output.append(token); index += 1; continue

        anchor = token
        index += 1
        if index >= len(tokens) or tokens[index].kind != "STRING":
            current = tokens[index] if index < len(tokens) else anchor
            raise bootstrap.SotlasBootstrapError(
                'extern exige ABI explícita: extern "C"',
                current.line, current.column, filename, source,
            )
        _validate_abi(tokens[index], bootstrap, filename, source)
        index += 1

        if index < len(tokens) and tokens[index].kind == "{":
            index += 1
            while index < len(tokens) and tokens[index].kind != "}":
                normalized, index = _copy_extern_decl(
                    tokens, index, bootstrap, anchor, filename, source
                )
                output.extend(normalized)
            if index >= len(tokens) or tokens[index].kind != "}":
                raise bootstrap.SotlasBootstrapError(
                    "bloco extern sem '}'",
                    anchor.line, anchor.column, filename, source,
                )
            index += 1
        else:
            normalized, index = _copy_extern_decl(
                tokens, index, bootstrap, anchor, filename, source
            )
            output.extend(normalized)
    return output


@dataclass
class _ExprInfo:
    type_obj: object | None
    foreign: bool = False


class _StrictSafetyChecker:
    def __init__(self, bootstrap, module, imported_fns=None, imported_types=None,
                 imported_globals=None):
        self.b = bootstrap
        self.module = module
        self.filename = getattr(module, "filename", None)
        self.source = getattr(module, "source", None)
        self.functions = dict(getattr(bootstrap, "BUILTIN_FUNCTIONS", {}))
        self.functions.update({fn.name: fn for fn in module.functions})
        if imported_fns:
            self.functions.update(imported_fns)
        self.globals = {item.name: item.type for item in module.globals}
        self.globals.update({name: item.type for name, item in (imported_globals or {}).items()})
        self.structs = {item.name: item for item in module.structs}
        self.structs.update(imported_types or {})

    def error(self, message, token) -> None:
        raise self.b.SotlasBootstrapError(
            message, token.line, token.column, self.filename, self.source
        )

    def _require_unsafe(self, token, depth: int, operation: str) -> None:
        if depth <= 0:
            self.error(
                f"{operation} exige bloco unsafe explícito; @system não substitui unsafe",
                token,
            )

    def check(self) -> None:
        for function in self.module.functions:
            if _attr(function, _EXTERN_ATTR):
                continue
            self._validate_quarantine_aliases(function)
            self._statements(
                function.body,
                {name: typ for name, typ in function.params},
                0,
                _attr(function, "@system") or _attr(function, "@naked") or _attr(function, "@interrupt"),
            )
        self._validate_whisper_lifetimes()

    def _validate_whisper_lifetimes(self) -> None:
        def contains_whisper(type_obj) -> bool:
            if type_obj is None:
                return False
            if getattr(type_obj, "ownership_domain", None) in (
                "whisper", "direct"
            ):
                return True
            return (
                contains_whisper(getattr(type_obj, "elem_type", None))
                or any(
                    contains_whisper(item)
                    for item in getattr(type_obj, "fn_params", ())
                )
                or contains_whisper(getattr(type_obj, "fn_ret", None))
            )

        declared_types = [
            field.type
            for struct in self.module.structs
            for field in struct.fields
        ] + [item.type for item in self.module.globals]
        declared_types.extend(
            type_obj
            for function in self.module.functions
            for type_obj in (
                *(typ for _, typ in function.params), function.result
            )
        )
        declared_types.extend(
            variant.payload_type
            for enum in self.module.enums
            for variant in enum.variants
            if variant.payload_type is not None
        )
        declared_types.extend(
            type_obj
            for class_decl in self.module.classes
            for field in class_decl.fields
            for type_obj in (field.type,)
        )
        declared_types.extend(
            type_obj
            for class_decl in self.module.classes
            for function in class_decl.methods
            for type_obj in (*(typ for _, typ in function.params), function.result)
        )
        if not any(contains_whisper(item) for item in declared_types):
            return

        package = self.b.__package__ or "sotlas_compile"
        try:
            typed_ast = importlib.import_module(f"{package}.typed_ast")
        except ModuleNotFoundError as error:
            raise self.b.SotlasBootstrapError(
                "this frontend cannot validate whisper lifetimes",
                1, 1, self.filename, self.source,
            ) from error
        try:
            typed_ast.validate_whisper_lifetimes(self.module)
        except typed_ast.Phase1SemanticError as error:
            raise self.b.SotlasBootstrapError(
                str(error), 1, 1, self.filename, self.source
            ) from error

    def _validate_quarantine_aliases(self, function) -> None:
        """Prevent use of reference aliases after their owner is isolated.

        This production safety gate tracks direct borrows and aliases through
        locals in source order. It conservatively joins branch/loop source
        order until the ownership CFG can express path-specific invalidation.
        """
        b = self.b
        unary_expr_types = tuple(
            node_type for node_type in (
                getattr(b, "Unary", None), getattr(b, "MoveExpr", None),
                getattr(b, "ShareExpr", None), getattr(b, "UnsafeExpr", None),
            ) if isinstance(node_type, type)
        )
        scope = {name: typ for name, typ in function.params}
        owners = {
            name for name, typ in function.params
            if getattr(self.structs.get(getattr(typ, "name", "")), "is_sole", False)
            and not getattr(typ, "pointer", False)
            and not getattr(typ, "is_reference", False)
        }
        region_owners = {
            name for name, typ in function.params
            if name in owners and getattr(typ, "ownership_domain", None) == "region"
        }
        aliases: dict[str, set[str]] = {}
        invalid: dict[str, str] = {}
        quarantined_owners: set[str] = set()
        escaped_owners: set[str] = set()

        def children(expr):
            if expr is None:
                return ()
            if isinstance(expr, b.Binary):
                return (expr.left, expr.right)
            if unary_expr_types and isinstance(expr, unary_expr_types):
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

        def expr_names(expr) -> set[str]:
            if expr is None:
                return set()
            result = {expr.value} if isinstance(expr, b.Name) else set()
            for child in children(expr):
                result.update(expr_names(child))
            return result

        def root_name(expr):
            if isinstance(expr, b.Name):
                return expr.value
            if isinstance(expr, (b.Member, b.Index)):
                return root_name(expr.target)
            return None

        def expr_has_address(expr) -> bool:
            if expr is None:
                return False
            if isinstance(expr, b.Unary) and expr.op == "&":
                return True
            return any(expr_has_address(child) for child in children(expr))

        def expr_has_cast(expr) -> bool:
            if expr is None:
                return False
            return isinstance(expr, b.Cast) or any(
                expr_has_cast(child) for child in children(expr)
            )

        def call_arguments(expr):
            if expr is None:
                return ()
            if isinstance(expr, b.Call):
                return tuple(expr.args)
            if isinstance(expr, b.MethodCall):
                return (expr.target, *tuple(expr.args))
            return tuple(
                argument
                for child in children(expr)
                for argument in call_arguments(child)
            )

        def direct_calls(expr):
            if expr is None:
                return
            if isinstance(expr, b.Call):
                yield expr
            for child in children(expr):
                yield from direct_calls(child)

        def alias_sources(expr) -> set[str]:
            if expr is None:
                return set()
            names = expr_names(expr)
            inherited = set().union(
                *(aliases[name] for name in names if name in aliases)
            ) if any(name in aliases for name in names) else set()
            try:
                info = self._infer(expr, scope, 1, False)
                typ = info.type_obj
            except Exception:
                typ = None
            carries_reference = bool(
                typ is not None
                and (
                    getattr(typ, "pointer", False)
                    or getattr(typ, "is_reference", False)
                )
            )
            direct = names.intersection(owners) if (
                expr_has_address(expr) or carries_reference
            ) else set()
            if isinstance(expr, b.Cast):
                return inherited | direct | alias_sources(expr.expr)
            if carries_reference or expr_has_address(expr):
                return inherited | direct
            if any(name in aliases for name in names):
                # Aggregate initialization may store an alias in a field; the
                # source structure is conservatively treated as tainted.
                if typ is not None and getattr(typ, "name", "") in self.structs:
                    return inherited
            return set()

        def type_stores_reference(typ, visiting=frozenset()) -> bool:
            if typ is None:
                return False
            if (
                getattr(typ, "pointer", False)
                or getattr(typ, "is_reference", False)
                or getattr(typ, "is_fn_ptr", False)
            ):
                return True
            if getattr(typ, "is_array", False):
                return type_stores_reference(
                    getattr(typ, "elem_type", None), visiting
                )
            name = getattr(typ, "name", "")
            struct = self.structs.get(name)
            if struct is None or name in visiting:
                return False
            return any(
                type_stores_reference(field.type, visiting | {name})
                for field in struct.fields
            )

        def flatten(items):
            for item in items:
                yield item
                nested_attrs = {
                    b.If: ("then_body", "else_body"),
                    b.While: ("body",),
                    b.For: ("body",),
                    b.Loop: ("body",),
                    b.Unsafe: ("body",),
                    b.Defer: ("body",),
                }.get(type(item), ())
                for attr in nested_attrs:
                    yield from flatten(getattr(item, attr, ()) or ())

        loop_quarantines: set[int] = set()

        def collect_loop_quarantines(items, in_loop: bool = False) -> None:
            for item in items:
                if in_loop and isinstance(item, b.Quarantine):
                    loop_quarantines.add(id(item))
                nested = {
                    b.If: ("then_body", "else_body"),
                    b.While: ("body",),
                    b.For: ("body",),
                    b.Loop: ("body",),
                    b.Unsafe: ("body",),
                    b.Defer: ("body",),
                }.get(type(item), ())
                child_in_loop = in_loop or isinstance(item, (b.While, b.For, b.Loop))
                for attr in nested:
                    collect_loop_quarantines(
                        getattr(item, attr, ()) or (), child_in_loop
                    )

        collect_loop_quarantines(function.body)

        def statement_exprs(item):
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
            result = [getattr(item, attr, None) for attr in attrs]
            if isinstance(item, b.Asm):
                result.extend(item.inputs)
                result.extend(item.outputs)
            return tuple(expr for expr in result if expr is not None)

        branch_paths: dict[int, tuple[tuple[int, int], ...]] = {}

        def record_paths(items, path=()):
            for statement in items:
                branch_paths[id(statement)] = path
                if isinstance(statement, b.If):
                    record_paths(statement.then_body, path + ((id(statement), 0),))
                    record_paths(statement.else_body, path + ((id(statement), 1),))
                else:
                    nested = {
                        b.While: ("body",), b.For: ("body",), b.Loop: ("body",),
                        b.Unsafe: ("body",), b.Defer: ("body",),
                    }.get(type(statement), ())
                    for attr in nested:
                        record_paths(getattr(statement, attr, ()) or (), path)

        record_paths(function.body)
        statements = sorted(
            flatten(function.body),
            key=lambda item: (item.token.line, item.token.column),
        )
        invalidated_at: dict[str, tuple[tuple[int, int], ...]] = {}
        quarantine_paths: dict[str, tuple[tuple[int, int], ...]] = {}

        def paths_are_disjoint(left, right) -> bool:
            left_map = dict(left)
            return any(
                branch_id in left_map and left_map[branch_id] != branch
                for branch_id, branch in right
            )

        def quarantined_on_path(owner: str, statement) -> bool:
            return owner in quarantined_owners and not paths_are_disjoint(
                quarantine_paths.get(owner, ()),
                branch_paths.get(id(statement), ()),
            )

        for item in statements:
            exprs = statement_exprs(item)
            if isinstance(item, b.Return) and item.value is not None:
                returned = alias_sources(item.value).intersection(region_owners)
                if returned:
                    try:
                        result_type = self._infer(
                            item.value, scope, 1, False
                        ).type_obj
                    except Exception:
                        result_type = None
                    if type_stores_reference(result_type):
                        owner = sorted(returned)[0]
                        self.error(
                            f"reference to region owner {owner!r} cannot escape through return",
                            item.token,
                        )
            if isinstance(item, b.Let) and item.name in invalid:
                if item.name not in expr_names(item.value):
                    invalid.pop(item.name, None)
            if isinstance(item, b.Assign):
                target_name = root_name(item.target)
                if target_name in invalid and not (
                    expr_names(item.value) & invalid.keys()
                ):
                    invalid.pop(target_name, None)

            referenced = set().union(*(expr_names(expr) for expr in exprs)) if exprs else set()
            stale = referenced.intersection(invalid)
            stale = {
                name for name in stale
                if not paths_are_disjoint(
                    invalidated_at.get(name, ()), branch_paths.get(id(item), ())
                )
            }
            if stale:
                alias = sorted(stale)[0]
                self.error(
                    f"reference alias {alias!r} to quarantined owner "
                    f"{invalid[alias]!r} is used after quarantine",
                    item.token,
                )

            if not isinstance(item, (b.Let, b.Assign)):
                derived = set().union(
                    *(alias_sources(expr) for expr in exprs)
                ) if exprs else set()
                after_quarantine = {
                    owner for owner in derived if quarantined_on_path(owner, item)
                }
                if after_quarantine:
                    owner = sorted(after_quarantine)[0]
                    self.error(
                        f"cannot use a reference alias to quarantined owner {owner!r}",
                        item.token,
                    )

            for expr in exprs:
                for call in direct_calls(expr):
                    callee = self.functions.get(call.callee)
                    params = tuple(getattr(callee, "params", ()) or ())
                    for index, argument in enumerate(call.args):
                        borrowed_region = alias_sources(argument).intersection(
                            region_owners
                        )
                        if not borrowed_region:
                            continue
                        parameter_type = (
                            params[index][1]
                            if index < len(params)
                            and isinstance(params[index], tuple)
                            and len(params[index]) == 2
                            else None
                        )
                        if getattr(parameter_type, "ownership_domain", None) not in (
                            "direct", "whisper"
                        ):
                            owner = sorted(borrowed_region)[0]
                            self.error(
                                f"reference to region owner {owner!r} cannot escape through an opaque call",
                                call.token,
                            )
                for argument in call_arguments(expr):
                    for name in expr_names(argument):
                        escaped = aliases.get(name, ())
                        escaped_owners.update(escaped)
                        quarantined_escape = {
                            owner for owner in escaped
                            if quarantined_on_path(owner, item)
                        }
                        if quarantined_escape:
                            owner = sorted(quarantined_escape)[0]
                            self.error(
                                f"reference alias to quarantined owner "
                                f"{owner!r} cannot escape through an opaque call",
                                item.token,
                            )

            if isinstance(item, b.Let):
                typ = item.type
                if typ is None:
                    try:
                        typ = self._infer(item.value, scope, 1, False).type_obj
                    except Exception:
                        typ = None
                related = alias_sources(item.value)
                quarantined_related = {
                    owner for owner in related if quarantined_on_path(owner, item)
                }
                if quarantined_related:
                    owner = sorted(quarantined_related)[0]
                    self.error(
                        f"cannot create reference alias to quarantined owner {owner!r}",
                        item.token,
                    )
                if typ is not None:
                    scope[item.name] = typ
                    struct = self.structs.get(getattr(typ, "name", ""))
                    if (
                        struct is not None and getattr(struct, "is_sole", False)
                        and not getattr(typ, "pointer", False)
                        and not getattr(typ, "is_reference", False)
                    ):
                        owners.add(item.name)
                        if getattr(typ, "ownership_domain", None) == "region":
                            region_owners.add(item.name)
                if related:
                    aliases[item.name] = related
                else:
                    aliases.pop(item.name, None)

            elif isinstance(item, b.Assign):
                related = alias_sources(item.value)
                escaping_region = related.intersection(region_owners)
                if escaping_region and (
                    root_name(item.target) in self.globals
                    or isinstance(item.target, (b.Member, b.Index))
                ):
                    owner = sorted(escaping_region)[0]
                    self.error(
                        f"reference to region owner {owner!r} cannot escape through storage",
                        item.token,
                    )
                quarantined_related = {
                    owner for owner in related if quarantined_on_path(owner, item)
                }
                if quarantined_related:
                    owner = sorted(quarantined_related)[0]
                    self.error(
                        f"cannot create reference alias to quarantined owner {owner!r}",
                        item.token,
                    )
                target_name = root_name(item.target)
                if target_name is not None and target_name not in scope:
                    escaped_owners.update(related)
                if target_name is not None and related:
                    aliases[target_name] = aliases.get(target_name, set()) | related
                elif target_name is not None:
                    aliases.pop(target_name, None)

            elif isinstance(item, b.Quarantine) and isinstance(item.value, b.Name):
                owner = item.value.value
                if id(item) in loop_quarantines and any(
                    owner in targets for targets in aliases.values()
                ):
                    self.error(
                        f"quarantine of {owner!r} inside a loop with reference aliases requires path-sensitive lifetime analysis",
                        item.token,
                    )
                if owner in escaped_owners:
                    self.error(
                        f"cannot quarantine owner {owner!r} after a reference alias escaped to a call",
                        item.token,
                    )
                quarantined_owners.add(owner)
                quarantine_paths[owner] = branch_paths.get(id(item), ())
                for alias, targets in aliases.items():
                    if owner in targets:
                        invalid[alias] = owner
                        invalidated_at[alias] = branch_paths.get(id(item), ())

    def _infer(self, expr, scope, depth: int, system_context: bool) -> _ExprInfo:
        b = self.b
        if expr is None: return _ExprInfo(None)
        if isinstance(expr, b.UnsafeExpr):
            return self._infer(expr.value, scope, depth + 1, system_context)
        if isinstance(expr, b.MoveExpr):
            return self._infer(expr.value, scope, depth, system_context)
        if isinstance(expr, b.Number):
            try: return _ExprInfo(b.Type(b.numeric_literal_type(expr.value)))
            except Exception: return _ExprInfo(b.Type("u64"))
        if isinstance(expr, b.Boolean): return _ExprInfo(b.Type("bool"))
        if isinstance(expr, b.CharLit): return _ExprInfo(b.Type("u8"))
        if isinstance(expr, b.StringLit):
            typ = b.Type("u8", pointer=True)
            object.__setattr__(typ, "_sotlas_reference", True)
            return _ExprInfo(typ)
        if isinstance(expr, b.NullLit): return _ExprInfo(b.Type("null", pointer=True))
        if isinstance(expr, b.Name):
            typ = scope.get(expr.value, self.globals.get(expr.value))
            return _ExprInfo(typ, bool(getattr(typ, "_sotlas_foreign_pointer", False)))
        if isinstance(expr, b.EnumAccess): return _ExprInfo(b.Type(expr.enum_name))
        if isinstance(expr, b.ArrayLit):
            infos = [self._infer(e, scope, depth, system_context) for e in expr.elements]
            if not infos or infos[0].type_obj is None: return _ExprInfo(None)
            inner = infos[0].type_obj
            size = expr.repeat_size if expr.is_repeat else len(expr.elements)
            return _ExprInfo(b.Type(inner.name, pointer=inner.pointer, is_array=True,
                                    array_size=size, elem_type=inner))
        if isinstance(expr, b.StructLit):
            for _, value in expr.fields: self._infer(value, scope, depth, system_context)
            return _ExprInfo(b.Type(expr.struct_name))
        if isinstance(expr, b.IfExpr):
            self._infer(expr.condition, scope, depth, system_context)
            left = self._infer(expr.then_expr, scope, depth, system_context)
            self._infer(expr.else_expr, scope, depth, system_context)
            return left
        if isinstance(expr, b.Unary):
            inner = self._infer(expr.value, scope, depth, system_context)
            if expr.op == "*":
                if _is_raw_pointer(inner.type_obj):
                    self._require_unsafe(expr.token, depth, "desreferenciamento de ponteiro cru")
                if inner.type_obj is None: return _ExprInfo(None)
                return _ExprInfo(b.Type(inner.type_obj.name, mutable=inner.type_obj.mutable), inner.foreign)
            if expr.op == "&":
                if inner.type_obj is None: return _ExprInfo(None)
                typ = b.Type(
                    inner.type_obj.name,
                    pointer=True,
                    mutable=bool(getattr(expr, "mutable", False)),
                )
                object.__setattr__(typ, "_sotlas_reference", True)
                return _ExprInfo(typ)
            if expr.op == "!": return _ExprInfo(b.Type("bool"))
            return inner
        if isinstance(expr, b.Binary):
            left = self._infer(expr.left, scope, depth, system_context)
            self._infer(expr.right, scope, depth, system_context)
            if expr.op in ("==", "!=", "<", "<=", ">", ">=", "&&", "||"):
                return _ExprInfo(b.Type("bool"))
            return left
        if isinstance(expr, b.Call):
            for arg in expr.args: self._infer(arg, scope, depth, system_context)
            function = self.functions.get(expr.callee)
            if function is None: return _ExprInfo(None)
            is_extern = _attr(function, _EXTERN_ATTR)
            is_privileged_builtin = (
                expr.callee in getattr(b, "BUILTIN_FUNCTIONS", {})
                and _attr(function, "@system")
                and expr.callee not in _SAFE_SYSTEM_BUILTINS
            )
            if is_extern and not system_context:
                self.error('chamada a FFI extern "C" exige função @system', expr.token)
            if is_privileged_builtin and not system_context:
                self.error("chamada a intrínseco privilegiado exige função @system", expr.token)
            if is_extern and _attr(function, _UNSAFE_ATTR):
                self._require_unsafe(expr.token, depth, "chamada FFI marcada unsafe")
            return _ExprInfo(function.result, is_extern and _is_raw_pointer(function.result))
        if isinstance(expr, b.Index):
            target = self._infer(expr.target, scope, depth, system_context)
            self._infer(expr.index, scope, depth, system_context)
            if _is_raw_pointer(target.type_obj):
                self._require_unsafe(expr.token, depth, "indexação de ponteiro cru")
            typ = target.type_obj
            if typ is None: return _ExprInfo(None)
            if getattr(typ, "is_array", False) and getattr(typ, "elem_type", None):
                return _ExprInfo(typ.elem_type, target.foreign)
            return _ExprInfo(b.Type(typ.name, mutable=typ.mutable), target.foreign)
        if isinstance(expr, b.Member):
            target = self._infer(expr.target, scope, depth, system_context)
            if _is_raw_pointer(target.type_obj):
                self._require_unsafe(expr.token, depth, "acesso a campo via ponteiro cru")
            struct = self.structs.get(getattr(target.type_obj, "name", None))
            field = next((f for f in struct.fields if f.name == expr.field), None) if struct else None
            return _ExprInfo(field.type if field else None, target.foreign)
        if isinstance(expr, b.MethodCall):
            target = self._infer(expr.target, scope, depth, system_context)
            for arg in expr.args: self._infer(arg, scope, depth, system_context)
            if expr.method == "as_ptr":
                typ = target.type_obj
                element = getattr(typ, "elem_type", None) or typ
                return _ExprInfo(b.Type(element.name, pointer=True), target.foreign) if element else _ExprInfo(None)
            if _is_raw_pointer(target.type_obj):
                self._require_unsafe(expr.token, depth, "chamada de método via ponteiro cru")
            if expr.method in ("add", "abs"):
                return target
            method = None
            if target.type_obj is not None:
                method = self.functions.get(f"{target.type_obj.name}_{expr.method}")
            return _ExprInfo(method.result if method else None, target.foreign)
        if isinstance(expr, b.Cast):
            info = self._infer(expr.expr, scope, depth, system_context)
            target_is_raw = _is_raw_pointer(expr.target_type)
            source_is_raw = _is_raw_pointer(info.type_obj)
            # Requalifying/reinterpreting an already-raw pointer does not create
            # a new address and therefore needs no unsafe by itself. Address
            # creation from integers/references remains an explicit boundary.
            if target_is_raw and not source_is_raw and not isinstance(expr.expr, b.NullLit):
                self._require_unsafe(expr.token, depth, "criação/conversão para ponteiro cru")
            return _ExprInfo(expr.target_type, info.foreign)
        return _ExprInfo(None)

    def _statements(self, items, scope, depth: int, system_context: bool) -> None:
        b = self.b
        for item in items:
            if isinstance(item, b.Let):
                info = self._infer(item.value, scope, depth, system_context)
                typ = item.type or info.type_obj
                if typ is not None and info.foreign and _is_raw_pointer(typ): _mark_foreign(typ)
                scope[item.name] = typ
            elif isinstance(item, b.Assign):
                self._infer(item.target, scope, depth, system_context)
                self._infer(item.value, scope, depth, system_context)
            elif isinstance(item, b.Return): self._infer(item.value, scope, depth, system_context)
            elif isinstance(item, b.Handover): self._infer(item.value, scope, depth, system_context)
            elif isinstance(item, b.Quarantine):
                self._infer(item.value, scope, depth, system_context)
            elif isinstance(item, b.Expression): self._infer(item.value, scope, depth, system_context)
            elif isinstance(item, b.If):
                self._infer(item.condition, scope, depth, system_context)
                self._statements(item.then_body, dict(scope), depth, system_context)
                self._statements(item.else_body, dict(scope), depth, system_context)
            elif isinstance(item, b.While):
                self._infer(item.condition, scope, depth, system_context)
                self._statements(item.body, dict(scope), depth, system_context)
            elif isinstance(item, b.Loop): self._statements(item.body, dict(scope), depth, system_context)
            elif isinstance(item, b.For):
                self._infer(item.start, scope, depth, system_context)
                self._infer(item.end, scope, depth, system_context)
                nested = dict(scope); nested[item.var_name] = b.Type("usize")
                self._statements(item.body, nested, depth, system_context)
            elif isinstance(item, b.Unsafe):
                self._statements(item.body, dict(scope), depth + 1, system_context)
            elif isinstance(item, b.Asm):
                self._require_unsafe(item.token, depth, "asm inline")
                for expr in item.outputs:
                    self._infer(expr, scope, depth, system_context)
                for expr in item.inputs:
                    self._infer(expr, scope, depth, system_context)
            elif isinstance(item, b.Defer):
                if item.body is not None:
                    self._statements(item.body, dict(scope), depth, system_context)
                elif isinstance(item.value, b.Assign):
                    self._infer(item.value.target, scope, depth, system_context)
                    self._infer(item.value.value, scope, depth, system_context)
                else:
                    self._infer(item.value, scope, depth, system_context)


def _annotate_ffi(module) -> None:
    for function in module.functions:
        if _attr(function, _EXTERN_ATTR):
            for _, typ in function.params: _mark_foreign(typ)
            _mark_foreign(function.result)


def _signature(function) -> str:
    params = ", ".join(typ.c_decl(name) for name, typ in function.params) or "void"
    return f"{function.result.c()} {function.name}({params})"


def install(bootstrap) -> None:
    if getattr(bootstrap, "_LANGUAGE_SAFETY_INSTALLED", False): return

    bootstrap.KEYWORDS.add("extern")

    # Keep &T / &mut T distinct from raw *const/*mut even though both lower to
    # native C pointers. This metadata has zero runtime cost.
    original_type = bootstrap.Parser.type
    def strict_type(parser):
        starting = parser.current.kind
        result = original_type(parser)
        if starting == "*": _mark_pointer_kind(result, raw=True)
        elif starting == "&": _mark_pointer_kind(result, reference=True)
        return result
    bootstrap.Parser.type = strict_type

    original_parse = bootstrap.parse
    def canonical_parse(source: str, filename: str | None = None):
        if "extern" not in source:
            module = original_parse(source, filename=filename)
        else:
            tokens = _normalize_extern_tokens(
                bootstrap.lex(source, filename=filename), bootstrap, filename, source
            )
            module = bootstrap.Parser(tokens, filename=filename, source=source).parse()
        _annotate_ffi(module)
        return module
    bootstrap.parse = canonical_parse

    original_check = bootstrap.check
    def strict_check(module, imported_fns=None, imported_types=None,
                     imported_enums=None, imported_globals=None):
        # The old checker used @system as an implicit dereference exemption.
        # Temporarily neutralize only that legacy rule while retaining all of
        # its structural/type checks; the strict lexical pass below becomes the
        # single source of truth for unsafe memory.
        added_system = []
        for function in module.functions:
            if "@system" not in function.attributes:
                function.attributes.append("@system")
                added_system.append(function)
        try:
            result = original_check(
                module, imported_fns, imported_types, imported_enums, imported_globals
            )
        finally:
            for function in added_system:
                function.attributes.remove("@system")
        _StrictSafetyChecker(bootstrap, module, imported_fns, imported_types, imported_globals).check()
        return result
    bootstrap.check = strict_check

    original_emit_c = bootstrap.emit_c
    def strict_emit_c(module, *args, **kwargs):
        code = original_emit_c(module, *args, **kwargs)
        for function in module.functions:
            if not _attr(function, _EXTERN_ATTR): continue
            signature = _signature(function)
            code = code.replace(f"{signature};", f"extern {signature};", 1)
            code = code.replace(f"{signature} {{\n}}\n\n", "")
            code = code.replace(f"{signature} {{\n}}\n", "")
        return code
    bootstrap.emit_c = strict_emit_c

    original_emit_header = bootstrap.emit_header
    def strict_emit_header(module, *args, **kwargs):
        code = original_emit_header(module, *args, **kwargs)
        for function in module.functions:
            if _attr(function, _EXTERN_ATTR):
                signature = _signature(function)
                code = code.replace(f"{signature};", f"extern {signature};", 1)
        return code
    bootstrap.emit_header = strict_emit_header

    bootstrap._LANGUAGE_SAFETY_INSTALLED = True


__all__ = ["install", "register_safe_system_builtins"]
