"""Sotlas Intermediate Representation (SIR).

Módulo que implementa a representação intermediária em formato SSA
para análises estáticas de segurança e otimizações de baixo nível.
"""

from .instructions import (
    SIRValue,
    SIRInstruction,
    AllocStackInst,
    StoreInst,
    LoadInst,
    CallInst,
    ShareInst,
    RetainInst,
    ReleaseInst,
    DestroyInst,
    DeferUseInst,
    BranchInst,
    CondBranchInst,
    ReturnInst,
    SystemOpInst,
    AsmInst,
    AwaitInst,
    SIRBasicBlock,
    SIRFunction,
    SIRModule,
)
from .generator import SIRGenerator
from .ownership import (
    SharedOwnershipSIRSegment,
    SharedOwnershipSIRPlan,
    SharedOwnershipSIRPlacement,
    lower_shared_ownership_trace,
    place_shared_return_cleanup,
    place_shared_loop_control_cleanup,
    place_shared_loop_backedge_cleanup,
    apply_shared_ownership_trace,
)
from .passes import (
    SIRPassResult,
    SIRPassManager,
    DefiniteInitializationPass,
    SystemCapabilitySafetyPass,
    DeadCodeEliminationPass,
)

__all__ = [
    "SIRValue",
    "SIRInstruction",
    "AllocStackInst",
    "StoreInst",
    "LoadInst",
    "CallInst",
    "ShareInst",
    "RetainInst",
    "ReleaseInst",
    "DestroyInst",
    "DeferUseInst",
    "BranchInst",
    "CondBranchInst",
    "ReturnInst",
    "SystemOpInst",
    "SIRBasicBlock",
    "SIRFunction",
    "SIRModule",
    "SIRGenerator",
    "SharedOwnershipSIRSegment",
    "SharedOwnershipSIRPlan",
    "SharedOwnershipSIRPlacement",
    "lower_shared_ownership_trace",
    "place_shared_return_cleanup",
    "place_shared_loop_control_cleanup",
    "place_shared_loop_backedge_cleanup",
    "apply_shared_ownership_trace",
    "SIRPassResult",
    "SIRPassManager",
    "DefiniteInitializationPass",
    "SystemCapabilitySafetyPass",
    "DeadCodeEliminationPass",
]
