"""Canonical CPU execution target contracts for the LLVM prototype backend."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


class ExecutionTargetError(ValueError):
    """An unsupported target triple or CPU feature was requested."""


_DATA_LAYOUT_X86_64_ELF = (
    "e-m:e-p270:32:32-p271:32:32-p272:64:64-i64:64-f80:128-n8:16:32:64-S128"
)
_DATA_LAYOUT_X86_64_WINDOWS = (
    "e-m:w-p270:32:32-p271:32:32-p272:64:64-i64:64-f80:128-n8:16:32:64-S128"
)
_FEATURE_ORDER = (
    "sse2", "sse3", "ssse3", "sse4.1", "sse4.2", "popcnt", "aes",
    "pclmul", "avx", "bmi", "bmi2", "fma", "avx2", "avx512f", "sha",
    "cx16",
)
_FEATURES = frozenset(_FEATURE_ORDER)
_FEATURE_DEPENDENCIES = {
    "sse3": ("sse2",),
    "ssse3": ("sse3",),
    "sse4.1": ("ssse3",),
    "sse4.2": ("sse4.1",),
    "avx2": ("avx",),
    "avx512f": ("avx",),
    "fma": ("avx",),
}
_AARCH64_FEATURE_ORDER = ("aes", "crc", "lse", "sha2", "sve", "sve2")
_AARCH64_FEATURES = frozenset(_AARCH64_FEATURE_ORDER)
_AARCH64_FEATURE_DEPENDENCIES = {"sve2": ("sve",)}


@dataclass(frozen=True)
class ExecutionTarget:
    triple: str
    architecture: str
    abi: str
    pointer_width: int
    endianness: str
    cpu: str
    cpu_features: tuple[str, ...]
    data_layout: str | None
    is_freestanding: bool

    @property
    def llvm_target_features(self) -> str:
        return ",".join(f"+{feature}" for feature in self.cpu_features)


@dataclass(frozen=True)
class _TargetPreset:
    architecture: str
    abi: str
    data_layout: str | None
    is_freestanding: bool


_TARGETS = {
    "x86_64-unknown-none-elf": _TargetPreset(
        "x86_64", "sysv", _DATA_LAYOUT_X86_64_ELF, True
    ),
    "x86_64-pc-none": _TargetPreset(
        "x86_64", "unknown", None, False
    ),
    "x86_64-unknown-linux-gnu": _TargetPreset(
        "x86_64", "sysv", _DATA_LAYOUT_X86_64_ELF, False
    ),
    "x86_64-pc-windows-msvc": _TargetPreset(
        "x86_64", "msvc", _DATA_LAYOUT_X86_64_WINDOWS, False
    ),
    "x86_64-apple-darwin": _TargetPreset(
        "x86_64", "darwin", _DATA_LAYOUT_X86_64_ELF, False
    ),
    "aarch64-unknown-none-elf": _TargetPreset(
        "aarch64", "aapcs64", None, True
    ),
    "aarch64-unknown-linux-gnu": _TargetPreset(
        "aarch64", "aapcs64", None, False
    ),
    "aarch64-apple-darwin": _TargetPreset(
        "aarch64", "darwin-aarch64", None, False
    ),
    "aarch64-pc-windows-msvc": _TargetPreset(
        "aarch64", "winarm64", None, False
    ),
}
_ALIASES = {
    "host": "x86_64-pc-none",
    "x86_64-freestanding": "x86_64-unknown-none-elf",
    "aarch64-freestanding": "aarch64-unknown-none-elf",
}


def resolve_execution_target(
    triple: str | ExecutionTarget | None = None,
    *,
    is_baremetal: bool = False,
    cpu_features: Iterable[str] = (),
) -> ExecutionTarget:
    """Resolve a supported target and normalize architecture-specific features.

    x86-64's architectural `sse2` baseline is always present. AArch64 starts
    with the architectural ARMv8-A baseline. Unknown features are rejected.
    """
    if isinstance(triple, ExecutionTarget):
        canonical = triple.triple
        requested_values = tuple(triple.cpu_features) + tuple(cpu_features)
    else:
        if triple is None:
            canonical = (
                "x86_64-unknown-none-elf"
                if is_baremetal else "x86_64-pc-none"
            )
        elif not isinstance(triple, str):
            raise ExecutionTargetError("target triple must be a string")
        else:
            canonical = _ALIASES.get(triple, triple)
        requested_values = tuple(cpu_features)

    if any(not isinstance(feature, str) for feature in requested_values):
        raise ExecutionTargetError("CPU feature names must be strings")
    requested = set(requested_values)

    preset = _TARGETS.get(canonical)
    if preset is None:
        raise ExecutionTargetError(
            f"unsupported execution target {canonical!r}; supported targets: "
            + ", ".join(sorted(_TARGETS))
        )
    feature_order = (
        _AARCH64_FEATURE_ORDER
        if preset.architecture == "aarch64"
        else _FEATURE_ORDER
    )
    features = _AARCH64_FEATURES if preset.architecture == "aarch64" else _FEATURES
    dependencies = (
        _AARCH64_FEATURE_DEPENDENCIES
        if preset.architecture == "aarch64"
        else _FEATURE_DEPENDENCIES
    )
    unsupported = requested - features
    if unsupported:
        architecture_name = (
            "x86-64" if preset.architecture == "x86_64" else "aarch64"
        )
        raise ExecutionTargetError(
            f"unsupported {architecture_name} CPU features: "
            + ", ".join(sorted(unsupported))
        )

    enabled = set(requested)
    if preset.architecture == "x86_64":
        enabled.add("sse2")
    pending = list(enabled)
    while pending:
        feature = pending.pop()
        for dependency in dependencies.get(feature, ()):
            if dependency not in enabled:
                enabled.add(dependency)
                pending.append(dependency)
    return ExecutionTarget(
        triple=canonical,
        architecture=preset.architecture,
        abi=preset.abi,
        pointer_width=64,
        endianness="little",
        cpu="generic" if preset.architecture == "aarch64" else "x86-64",
        cpu_features=tuple(
            feature for feature in feature_order if feature in enabled
        ),
        data_layout=preset.data_layout,
        is_freestanding=preset.is_freestanding,
    )


__all__ = [
    "ExecutionTarget",
    "ExecutionTargetError",
    "resolve_execution_target",
]
