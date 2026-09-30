"""M16.3 direct-call SysV ABI facade.

M16.3c extends the previously certified direct-call slice with canonical 8-byte
stack arguments for argument 7+, while retaining 16-byte call alignment and the
existing r10/r11 caller-saved preservation contract. Validation, allocation, ABI
transport and instruction emission are kept in separate modules so later linkage,
recursion and aggregate ABI work does not regrow one monolithic backend file.
"""
from ._machine_x86_64_call_emit import emit_x86_64_sysv_assembly
from ._machine_x86_64_call_plan import plan_x86_64_sysv_allocation
from ._machine_x86_64_call_validation import MachineBackendError


__all__ = [
    "MachineBackendError",
    "plan_x86_64_sysv_allocation",
    "emit_x86_64_sysv_assembly",
]
