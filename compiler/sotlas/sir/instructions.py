"""Sotlas Intermediate Representation (SIR) — Instruções SSA.

O SIR é uma representação estatisticamente tipada em formato SSA voltada para
análises de segurança de baixo nível, definite initialization e otimizações de ARC.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class SIRValue:
    name: str
    type_name: str

    def __repr__(self) -> str:
        return f"%{self.name}: {self.type_name}"


@dataclass
class SIRInstruction:
    """Instrução base do SIR."""
    pass


@dataclass
class AllocStackInst(SIRInstruction):
    var_name: str
    type_name: str
    result: SIRValue

    def __str__(self) -> str:
        return f"  {self.result} = alloc_stack {self.type_name} // {self.var_name}"


@dataclass
class StoreInst(SIRInstruction):
    destination: SIRValue
    source: SIRValue

    def __str__(self) -> str:
        return f"  store {self.source} to {self.destination}"


@dataclass
class LoadInst(SIRInstruction):
    source: SIRValue
    result: SIRValue

    def __str__(self) -> str:
        return f"  {self.result} = load {self.source}"


@dataclass
class CallInst(SIRInstruction):
    callee: str
    arguments: List[SIRValue]
    result: Optional[SIRValue] = None
    is_system: bool = False
    defer_point_id: str | None = None

    def __str__(self) -> str:
        prefix = f"{self.result} = " if self.result else ""
        sys_mark = "@system " if self.is_system else ""
        args_str = ", ".join(str(a) for a in self.arguments)
        defer_mark = f" // {self.defer_point_id}" if self.defer_point_id else ""
        return f"  {prefix}{sys_mark}call @{self.callee}({args_str}){defer_mark}"


@dataclass
class OwnershipDomainPointInst(SIRInstruction):
    operation: str
    source_name: str
    destination_name: str | None
    point_id: str

    def __str__(self) -> str:
        destination = (
            f" -> {self.destination_name}"
            if self.destination_name is not None else ""
        )
        return (
            f"  ownership_point {self.operation} {self.source_name}"
            f"{destination} // {self.point_id}"
        )


class _OwnershipDomainTransferMeta(type):
    """Recognize the exact transfer schema across the legacy SIR mirror.

    ``tools/sotlas`` and ``compiler/sotlas`` are still importable during the
    migration to one canonical package.  Loading the same dataclass from both
    trees gives it two Python identities even though the SIR contract is
    identical.  Placement must not silently drop a transfer only because its
    class object came from the compatibility mirror.

    This is intentionally narrow: only the exact dataclass name and required
    field schema are accepted.  All semantic point/domain/destination checks
    remain in the ownership placement pass.
    """

    _required_fields = frozenset({
        "operation",
        "source",
        "source_domain",
        "target_domain",
        "destination",
        "point_id",
    })

    def __instancecheck__(cls, instance: object) -> bool:
        if type.__instancecheck__(cls, instance):
            return True
        instance_type = type(instance)
        if instance_type.__name__ != "OwnershipDomainTransferInst":
            return False
        fields = getattr(instance_type, "__dataclass_fields__", None)
        if not isinstance(fields, dict):
            return False
        return cls._required_fields.issubset(fields)


@dataclass
class OwnershipDomainTransferInst(
    SIRInstruction, metaclass=_OwnershipDomainTransferMeta
):
    operation: str
    source: SIRValue
    source_domain: str
    target_domain: str
    destination: Optional[SIRValue] = None
    point_id: str | None = None

    def __str__(self) -> str:
        destination = (
            f" -> {self.destination}" if self.destination is not None else ""
        )
        point = f" // {self.point_id}" if self.point_id else ""
        return (
            f"  ownership_transfer {self.operation} {self.source}"
            f"{destination} [{self.source_domain}->{self.target_domain}]"
            f"{point}"
        )


@dataclass
class StateTransitionInst(SIRInstruction):
    """Source-identified typestate transition with an explicit SSA result."""

    source: SIRValue
    result: SIRValue
    space_name: str
    source_state: str
    target_state: str
    point_id: str

    def __str__(self) -> str:
        return (
            f"  {self.result} = state_transition {self.source} "
            f"[{self.space_name}:{self.source_state}->{self.target_state}] "
            f"// {self.point_id}"
        )


@dataclass
class WhisperBorrowInst(SIRInstruction):
    """Backend-neutral call-scoped borrow fact; has no runtime effect."""

    source: SIRValue
    callee: str
    parameter: str
    source_domain: str
    point_id: str

    def __str__(self) -> str:
        return (
            f"  whisper_borrow {self.source} -> @{self.callee}.{self.parameter}"
            f" [{self.source_domain}] // {self.point_id}"
        )


@dataclass
class DirectAccessInst(SIRInstruction):
    """Backend-neutral, call-scoped direct access fact; no runtime effect."""

    source: SIRValue
    callee: str
    parameter: str
    source_domain: str
    point_id: str

    def __str__(self) -> str:
        return (
            f"  direct_access {self.source} -> @{self.callee}.{self.parameter}"
            f" [{self.source_domain}] // {self.point_id}"
        )


@dataclass
class SharedOwnershipPointInst(SIRInstruction):
    source_name: str
    alias_name: str
    point_id: str

    def __str__(self) -> str:
        return (
            f"  shared_ownership_point {self.source_name} -> {self.alias_name}"
            f" // {self.point_id}"
        )


@dataclass
class ShareInst(SIRInstruction):
    value: SIRValue

    def __str__(self) -> str:
        return f"  share_value {self.value}"


@dataclass
class RetainInst(SIRInstruction):
    value: SIRValue

    def __str__(self) -> str:
        return f"  retain_value {self.value}"


@dataclass
class ReleaseInst(SIRInstruction):
    value: SIRValue

    def __str__(self) -> str:
        return f"  release_value {self.value}"


@dataclass
class DestroyInst(SIRInstruction):
    value: SIRValue

    def __str__(self) -> str:
        return f"  destroy_value {self.value}"


@dataclass
class DeferUseInst(SIRInstruction):
    value: SIRValue
    defer_point_id: str

    def __str__(self) -> str:
        return f"  defer_use {self.value} // {self.defer_point_id}"


@dataclass
class BranchInst(SIRInstruction):
    target_block: str
    point_id: str | None = None
    control_kind: str | None = None

    def __str__(self) -> str:
        return f"  br bb{self.target_block}"


@dataclass
class CondBranchInst(SIRInstruction):
    condition: SIRValue
    true_block: str
    false_block: str

    def __str__(self) -> str:
        return f"  cond_br {self.condition}, bb{self.true_block}, bb{self.false_block}"


@dataclass
class CompareInst(SIRInstruction):
    operation: str
    left: SIRValue
    right: SIRValue
    result: SIRValue

    def __str__(self) -> str:
        return (
            f"  {self.result} = icmp {self.operation} "
            f"{self.left}, {self.right}"
        )


@dataclass
class BinaryOpInst(SIRInstruction):
    operation: str
    left: SIRValue
    right: SIRValue
    result: SIRValue

    def __str__(self) -> str:
        return f"  {self.result} = {self.operation} {self.left}, {self.right}"


@dataclass
class ReturnInst(SIRInstruction):
    value: Optional[SIRValue] = None
    point_id: str | None = None

    def __str__(self) -> str:
        if self.value:
            return f"  return {self.value}"
        return "  return void"


@dataclass
class SystemOpInst(SIRInstruction):
    operation: str
    operands: List[SIRValue]
    result: Optional[SIRValue] = None

    def __str__(self) -> str:
        prefix = f"{self.result} = " if self.result else ""
        ops_str = ", ".join(str(o) for o in self.operands)
        return f"  {prefix}system_op #{self.operation}({ops_str})"


@dataclass
class AsmInst(SIRInstruction):
    template: str
    is_volatile: bool = True
    arguments: List[SIRValue] = field(default_factory=list)
    result: Optional[SIRValue] = None

    def __str__(self) -> str:
        vol = "volatile " if self.is_volatile else ""
        args_str = ", ".join(str(a) for a in self.arguments)
        return f"  asm {vol}\"{self.template}\"({args_str})"


@dataclass
class AwaitInst(SIRInstruction):
    operand: SIRValue
    result: Optional[SIRValue] = None

    def __str__(self) -> str:
        prefix = f"{self.result} = " if self.result else ""
        return f"  {prefix}await {self.operand}"


@dataclass
class PhiInst(SIRInstruction):
    result: SIRValue
    incoming: List[Tuple[SIRValue, str]] = field(default_factory=list)

    def __str__(self) -> str:
        incoming_str = ", ".join(f"[{val}, bb{blk}]" for val, blk in self.incoming)
        return f"  {self.result} = phi {self.result.type_name} {incoming_str}"


@dataclass
class BoundsCheckInst(SIRInstruction):
    index: SIRValue
    length: SIRValue
    can_eliminate: bool = False

    def __str__(self) -> str:
        elim = " [bce-eliminated]" if self.can_eliminate else ""
        return f"  bounds_check {self.index} < {self.length}{elim}"


@dataclass
class SIRBasicBlock:
    label: str
    instructions: List[SIRInstruction] = field(default_factory=list)

    def add(self, inst: SIRInstruction) -> None:
        self.instructions.append(inst)

    def __str__(self) -> str:
        lines = [f"bb{self.label}:"]
        for inst in self.instructions:
            lines.append(str(inst))
        return "\n".join(lines)


@dataclass(frozen=True)
class SIREffectSummary:
    direct_effects: Tuple[str, ...] = ()
    transitive_effects: Tuple[str, ...] = ()
    unresolved_calls: Tuple[str, ...] = ()
    declared_effects: Tuple[str, ...] | None = None


@dataclass
class SIRFunction:
    name: str
    parameters: List[SIRValue]
    return_type: str
    is_system: bool = False
    blocks: List[SIRBasicBlock] = field(default_factory=list)
    declared_effects: Tuple[str, ...] | None = None
    inferred_effects: Tuple[str, ...] = field(default=(), init=False)
    source_effect_summary: Any = field(default=None, repr=False, compare=False)
    required_cpu_features: Tuple[str, ...] = ()

    def add_block(self, label: str) -> SIRBasicBlock:
        b = SIRBasicBlock(label=label)
        self.blocks.append(b)
        return b

    def __str__(self) -> str:
        sys_tag = "@system " if self.is_system else ""
        params_str = ", ".join(str(p) for p in self.parameters)
        header = f"sir_fn {sys_tag}@{self.name}({params_str}) -> {self.return_type} {{"
        body = "\n".join(str(b) for b in self.blocks)
        return f"{header}\n{body}\n}}"


@dataclass
class SIRModule:
    name: str
    functions: List[SIRFunction] = field(default_factory=list)
    effect_summaries: Dict[str, SIREffectSummary] = field(
        default_factory=dict, init=False
    )
    flow_plans: Tuple[Any, ...] = ()
    trust_boundaries: Tuple[Any, ...] = ()
    contract_proofs: Tuple[Any, ...] = ()
    contract_preconditions: Tuple[Any, ...] = ()

    def add_function(self, fn: SIRFunction) -> None:
        self.functions.append(fn)

    def dump(self) -> str:
        lines = [
            "// SIR PROTOTYPE — NOT THE PRODUCTION LOWERING PATH",
            "// Function bodies and systems semantics are not yet lowered end to end.",
            f"// Sotlas Intermediate Representation (SIR) — Módulo {self.name}",
        ]
        for fn in self.functions:
            lines.append(str(fn))
        if self.effect_summaries:
            lines.append("// inferred effect summaries:")
            for name in sorted(self.effect_summaries):
                summary = self.effect_summaries[name]
                effects = ",".join(summary.transitive_effects) or "pure"
                unresolved = ",".join(summary.unresolved_calls) or "none"
                declared = (
                    ",".join(summary.declared_effects)
                    if summary.declared_effects is not None else "unspecified"
                )
                lines.append(
                    f"// effects @{name}: inferred=[{effects}] "
                    f"declared=[{declared}] unresolved=[{unresolved}]"
                )
        for boundary in self.trust_boundaries:
            effects = ",".join(boundary.effects) or "pure"
            isolation = "verified" if boundary.isolation_verified else "unverified"
            lines.append(
                f"sir_foreign @{boundary.symbol} convention={boundary.convention} "
                f"trust={boundary.trust_domain} isolation={isolation} "
                f"effects=[{effects}]"
            )
        for plan in self.flow_plans:
            lines.append(f"sir_flow @{plan.name} {{")
            for index, stage_names in enumerate(plan.parallel_stages):
                members = ", ".join(f"%{name}" for name in stage_names)
                lines.append(f"  parallel_stage {index} = [{members}]")
            for stage in plan.stages:
                arguments = ", ".join(
                    f"%{argument.value.producer_stage}.result"
                    for argument in stage.arguments
                )
                effects = ",".join(stage.effects)
                lines.append(
                    f"  flow_stage %{stage.name} = call @{stage.function}"
                    f"({arguments}) -> {stage.result_type} effects=[{effects}]"
                )
            lines.append("}")
        for proof in self.contract_proofs:
            arguments = ", ".join(
                f"{name}={value!r}" for name, value in proof.arguments
            )
            lines.append(
                f"sir_proof call @{proof.function} at "
                f"{proof.line}:{proof.column} requires {proof.predicate} "
                f"arguments=[{arguments}]"
            )
            refinements = tuple(getattr(proof, "refinements", ()) or ())
            if refinements:
                lines[-1] += f" refinements=[{', '.join(refinements)}]"
        for precondition in self.contract_preconditions:
            lines.append(
                f"sir_requires @{precondition.function} "
                f"{precondition.predicate} enforcement=runtime"
            )
        return "\n\n".join(lines)
