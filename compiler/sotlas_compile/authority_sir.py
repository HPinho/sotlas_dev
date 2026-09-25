"""Bridge canonical Authority Domains into backend-neutral SIR facts.

Source ``@system`` functions remain encapsulated abstraction boundaries and are
certified through represented ``CallInst`` groups. Direct privileged ABI calls
use ``AuthorityABIInst``: a source-stable, zero-runtime semantic fact that keeps
named hardware authority visible at the backend-independent boundary without
pretending that the prototype SIR already lowers every intrinsic operand/result.

Only ABI symbols that already have named Authority contracts may use this path.
Legacy-uncontracted privileged intrinsics remain fail-closed in strict SIR.
"""
from __future__ import annotations

from dataclasses import dataclass

from .authority import AuthorityDomainPlan
from .canonical_sir import load_canonical_sir
from .typed_ast import Phase1SemanticError


class AuthoritySIRError(Phase1SemanticError):
    """Raised when canonical authority facts diverge from represented SIR."""


@dataclass(frozen=True)
class AuthoritySIRFunctionFact:
    function: str
    capabilities: tuple[str, ...]
    legacy_unrestricted: bool
    sir_is_system: bool

    @property
    def is_system(self) -> bool:
        return self.legacy_unrestricted or bool(self.capabilities)


@dataclass(frozen=True)
class AuthoritySIRCallGroup:
    caller: str
    callee: str
    source_point_ids: tuple[str, ...]
    required_capabilities: tuple[str, ...]
    requires_legacy_unrestricted: bool
    sir_call_count: int


@dataclass(frozen=True)
class AuthoritySIRABIFact:
    caller: str
    symbol: str
    point_id: str
    required_capabilities: tuple[str, ...]


@dataclass(frozen=True)
class AuthoritySIRCertificate:
    functions: tuple[AuthoritySIRFunctionFact, ...]
    call_groups: tuple[AuthoritySIRCallGroup, ...]
    abi_facts: tuple[AuthoritySIRABIFact, ...] = ()

    def function(self, name: str) -> AuthoritySIRFunctionFact:
        matches = tuple(item for item in self.functions if item.function == name)
        if len(matches) != 1:
            raise AuthoritySIRError(
                f"authority SIR certificate requires exactly one function {name!r}"
            )
        return matches[0]

    def calls_from(self, caller: str) -> tuple[AuthoritySIRCallGroup, ...]:
        self.function(caller)
        return tuple(item for item in self.call_groups if item.caller == caller)

    def abi_from(self, caller: str) -> tuple[AuthoritySIRABIFact, ...]:
        self.function(caller)
        return tuple(item for item in self.abi_facts if item.caller == caller)


def _unwrap_module(value: object):
    sir = load_canonical_sir()
    module = getattr(value, "module", value)
    if not isinstance(module, sir.SIRModule):
        raise AuthoritySIRError(
            "authority SIR certification requires canonical SIRModule"
        )
    return sir, module


def _function_map(module: object) -> dict[str, object]:
    functions: dict[str, object] = {}
    for function in tuple(getattr(module, "functions", ()) or ()):
        name = getattr(function, "name", None)
        if not isinstance(name, str) or not name:
            raise AuthoritySIRError("authority SIR function lacks canonical name")
        if name in functions:
            raise AuthoritySIRError(
                f"authority SIR contains duplicate function {name!r}"
            )
        functions[name] = function
    return functions


def _sir_call_counts(sir, function) -> dict[str, int]:
    counts: dict[str, int] = {}
    for block in tuple(getattr(function, "blocks", ()) or ()):
        for instruction in tuple(getattr(block, "instructions", ()) or ()):
            if not isinstance(instruction, sir.CallInst):
                continue
            callee = getattr(instruction, "callee", None)
            if not isinstance(callee, str) or not callee:
                raise AuthoritySIRError(
                    f"authority SIR call in {function.name!r} lacks callee identity"
                )
            counts[callee] = counts.get(callee, 0) + 1
    return counts


def place_authority_abi_facts(
    authority: AuthorityDomainPlan,
    sir_module: object,
) -> int:
    """Place named ABI authority metadata without inventing runtime lowering."""
    if not isinstance(authority, AuthorityDomainPlan):
        raise AuthoritySIRError(
            "authority ABI placement requires canonical AuthorityDomainPlan"
        )
    sir, module = _unwrap_module(sir_module)
    functions = _function_map(module)

    existing = []
    for function in functions.values():
        for block in tuple(getattr(function, "blocks", ()) or ()):
            existing.extend(
                instruction
                for instruction in tuple(getattr(block, "instructions", ()) or ())
                if isinstance(instruction, sir.AuthorityABIInst)
            )
    if existing:
        raise AuthoritySIRError(
            "authority ABI placement requires SIR without pre-existing ABI facts"
        )

    placed = 0
    terminators = (sir.ReturnInst, sir.BranchInst, sir.CondBranchInst)
    for edge in authority.calls:
        if edge.target_kind != "abi_intrinsic":
            continue
        function = functions.get(edge.caller)
        if function is None:
            raise AuthoritySIRError(
                f"authority ABI caller {edge.caller!r} is missing from SIR"
            )
        blocks = tuple(getattr(function, "blocks", ()) or ())
        if not blocks:
            raise AuthoritySIRError(
                f"authority ABI caller {edge.caller!r} has no SIR block"
            )
        block = blocks[0]
        instruction = sir.AuthorityABIInst(
            symbol=edge.callee,
            point_id=edge.point_id,
            required_capabilities=edge.required_capabilities,
        )
        insert_at = next(
            (
                index
                for index, current in enumerate(block.instructions)
                if isinstance(current, terminators)
            ),
            len(block.instructions),
        )
        block.instructions.insert(insert_at, instruction)
        placed += 1
    return placed


def _actual_abi_facts(sir, functions: dict[str, object]):
    actual: dict[tuple[str, str], object] = {}
    for function_name, function in functions.items():
        for block in tuple(getattr(function, "blocks", ()) or ()):
            for instruction in tuple(getattr(block, "instructions", ()) or ()):
                if not isinstance(instruction, sir.AuthorityABIInst):
                    continue
                point_id = getattr(instruction, "point_id", None)
                symbol = getattr(instruction, "symbol", None)
                capabilities = tuple(
                    getattr(instruction, "required_capabilities", ()) or ()
                )
                if not isinstance(point_id, str) or not point_id.startswith("call@"):
                    raise AuthoritySIRError(
                        f"authority ABI fact in {function_name!r} lacks source-stable call identity"
                    )
                if not isinstance(symbol, str) or not symbol:
                    raise AuthoritySIRError(
                        f"authority ABI fact {function_name}::{point_id} lacks symbol"
                    )
                if not capabilities or any(
                    not isinstance(item, str) or not item for item in capabilities
                ):
                    raise AuthoritySIRError(
                        f"authority ABI fact {function_name}::{point_id} lacks named capabilities"
                    )
                key = (function_name, point_id)
                if key in actual:
                    raise AuthoritySIRError(
                        f"authority SIR repeats ABI source identity {function_name}::{point_id}"
                    )
                actual[key] = instruction
    return actual


def certify_authority_sir(
    authority: AuthorityDomainPlan,
    sir_module: object,
) -> AuthoritySIRCertificate:
    """Certify source boundaries and named privileged ABI facts against SIR."""
    if not isinstance(authority, AuthorityDomainPlan):
        raise AuthoritySIRError(
            "authority SIR certification requires canonical AuthorityDomainPlan"
        )

    unsupported = tuple(
        edge
        for edge in authority.calls
        if edge.target_kind not in ("source", "abi_intrinsic")
    )
    if unsupported:
        summary = ", ".join(
            f"{edge.caller}->{edge.callee} ({edge.target_kind})"
            for edge in unsupported
        )
        raise AuthoritySIRError(
            "authority SIR cannot certify unsupported ABI/intrinsic authority "
            f"edges: {summary}"
        )

    sir, module = _unwrap_module(sir_module)
    sir_functions = _function_map(module)

    facts: list[AuthoritySIRFunctionFact] = []
    contract_by_name = {item.function: item for item in authority.contracts}
    if len(contract_by_name) != len(authority.contracts):
        raise AuthoritySIRError("authority plan contains duplicate function contracts")

    for contract in authority.contracts:
        function = sir_functions.get(contract.function)
        if function is None:
            raise AuthoritySIRError(
                f"authority SIR is missing function {contract.function!r}"
            )
        sir_is_system = bool(getattr(function, "is_system", False))
        if contract.legacy_unrestricted and not sir_is_system:
            raise AuthoritySIRError(
                f"legacy @system function {contract.function!r} lost its SIR system marker"
            )
        facts.append(
            AuthoritySIRFunctionFact(
                function=contract.function,
                capabilities=contract.capabilities,
                legacy_unrestricted=contract.legacy_unrestricted,
                sir_is_system=sir_is_system,
            )
        )

    expected_abi = {}
    for edge in authority.calls:
        if edge.target_kind != "abi_intrinsic":
            continue
        key = (edge.caller, edge.point_id)
        if key in expected_abi:
            raise AuthoritySIRError(
                f"authority plan repeats ABI source identity {edge.caller}::{edge.point_id}"
            )
        expected_abi[key] = edge

    actual_abi = _actual_abi_facts(sir, sir_functions)
    for key, edge in expected_abi.items():
        instruction = actual_abi.get(key)
        if instruction is None:
            raise AuthoritySIRError(
                f"authority SIR is missing ABI authority fact {edge.caller}::{edge.point_id} -> {edge.callee}"
            )
        if getattr(instruction, "symbol", None) != edge.callee:
            raise AuthoritySIRError(
                f"authority ABI fact {edge.caller}::{edge.point_id} targets the wrong symbol"
            )
        represented = tuple(
            getattr(instruction, "required_capabilities", ()) or ()
        )
        if represented != edge.required_capabilities:
            raise AuthoritySIRError(
                f"authority ABI fact {edge.caller}::{edge.point_id} capability contract diverges"
            )
    for key, instruction in actual_abi.items():
        if key not in expected_abi:
            raise AuthoritySIRError(
                f"authority SIR ABI fact {key[0]}::{key[1]} -> {instruction.symbol} has no certified source edge"
            )

    abi_facts = tuple(
        AuthoritySIRABIFact(
            caller=edge.caller,
            symbol=edge.callee,
            point_id=edge.point_id,
            required_capabilities=edge.required_capabilities,
        )
        for edge in authority.calls
        if edge.target_kind == "abi_intrinsic"
    )

    source_groups: dict[tuple[str, str], list[object]] = {}
    for edge in authority.calls:
        if edge.target_kind != "source":
            continue
        source_groups.setdefault((edge.caller, edge.callee), []).append(edge)

    call_groups: list[AuthoritySIRCallGroup] = []
    for caller_contract in authority.contracts:
        caller_sir = sir_functions[caller_contract.function]
        sir_counts = _sir_call_counts(sir, caller_sir)

        relevant_callees = {
            name
            for name, contract in contract_by_name.items()
            if contract.is_system and sir_counts.get(name, 0) > 0
        }
        relevant_callees.update(
            callee
            for (caller, callee) in source_groups
            if caller == caller_contract.function
        )

        for callee in sorted(relevant_callees):
            edges = tuple(
                source_groups.get((caller_contract.function, callee), ())
            )
            count = sir_counts.get(callee, 0)
            if count != len(edges):
                raise AuthoritySIRError(
                    f"authority SIR call group {caller_contract.function} -> {callee} "
                    f"requires {len(edges)} represented calls, got {count}"
                )
            if not edges:
                raise AuthoritySIRError(
                    f"authority SIR call {caller_contract.function} -> {callee} "
                    "has no certified source authority edge"
                )

            required = edges[0].required_capabilities
            if any(edge.required_capabilities != required for edge in edges):
                raise AuthoritySIRError(
                    f"authority source edges disagree for {caller_contract.function} -> {callee}"
                )
            target = contract_by_name[callee]
            call_groups.append(
                AuthoritySIRCallGroup(
                    caller=caller_contract.function,
                    callee=callee,
                    source_point_ids=tuple(edge.point_id for edge in edges),
                    required_capabilities=required,
                    requires_legacy_unrestricted=target.legacy_unrestricted,
                    sir_call_count=count,
                )
            )

    return AuthoritySIRCertificate(
        functions=tuple(facts),
        call_groups=tuple(call_groups),
        abi_facts=abi_facts,
    )


__all__ = [
    "AuthoritySIRError",
    "AuthoritySIRFunctionFact",
    "AuthoritySIRCallGroup",
    "AuthoritySIRABIFact",
    "AuthoritySIRCertificate",
    "place_authority_abi_facts",
    "certify_authority_sir",
]
