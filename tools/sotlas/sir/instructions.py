"""Sotlas Intermediate Representation (SIR) — Instruções SSA.

O SIR é uma representação estatisticamente tipada em formato SSA voltada para
análises de segurança de baixo nível, definite initialization e otimizações de ARC.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, List, Optional, Tuple


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


@dataclass
class OwnershipDomainTransferInst(SIRInstruction):
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


@dataclass
class SIRFunction:
    name: str
    parameters: List[SIRValue]
    return_type: str
    is_system: bool = False
    blocks: List[SIRBasicBlock] = field(default_factory=list)

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
        return "\n\n".join(lines)
