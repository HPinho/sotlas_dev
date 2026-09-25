"""Canonical least-authority contracts for privileged Sotlas ABI intrinsics.

This module is deliberately small and backend-neutral. It names only intrinsic
boundaries whose authority is already unambiguous in the language contract.
Unlisted privileged intrinsics remain legacy-unrestricted until a dedicated
contract is added and certified.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AuthorityABIContract:
    symbol: str
    capabilities: tuple[str, ...]
    kind: str = "abi_intrinsic"


_PORT_IO_SYMBOLS = (
    "__inb",
    "__outb",
    "__inw",
    "__outw",
    "__inl",
    "__outl",
)

_INTERRUPT_CONTROL_SYMBOLS = (
    "__irq_save_disable",
    "__irq_restore",
    "__interrupts_enabled",
    "__cli",
    "__sti",
)

AUTHORITY_ABI_CONTRACTS = (
    tuple(
        AuthorityABIContract(symbol=symbol, capabilities=("io.port",))
        for symbol in _PORT_IO_SYMBOLS
    )
    + tuple(
        AuthorityABIContract(symbol=symbol, capabilities=("cpu.interrupts",))
        for symbol in _INTERRUPT_CONTROL_SYMBOLS
    )
)

_BY_SYMBOL = {item.symbol: item for item in AUTHORITY_ABI_CONTRACTS}
if len(_BY_SYMBOL) != len(AUTHORITY_ABI_CONTRACTS):
    raise RuntimeError("duplicate canonical Authority ABI contract")


def authority_abi_contract(symbol: str) -> AuthorityABIContract | None:
    """Return the canonical named-authority contract for one ABI symbol."""
    return _BY_SYMBOL.get(symbol)


__all__ = [
    "AuthorityABIContract",
    "AUTHORITY_ABI_CONTRACTS",
    "authority_abi_contract",
]
