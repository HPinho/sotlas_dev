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
}
_ALIASES = {
    "host": "x86_64-pc-none",
    "x86_64-freestanding": "x86_64-unknown-none-elf",
}


def resolve_execution_target(
    triple: str | ExecutionTarget | None = None,
    *,
    is_baremetal: bool = False,
    cpu_features: Iterable[str] = (),
) -> ExecutionTarget:
    """Resolve a supported x86-64 target and normalize requested features.

    x86-64's architectural `sse2` baseline is always present. Higher features
    imply the lower feature dependencies LLVM expects, and unknown features are
    rejected rather than silently ignored.
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
    unsupported = requested - _FEATURES
    if unsupported:
        raise ExecutionTargetError(
            "unsupported x86-64 CPU features: " + ", ".join(sorted(unsupported))
        )

    enabled = set(requested)
    enabled.add("sse2")
    pending = list(enabled)
    while pending:
        feature = pending.pop()
        for dependency in _FEATURE_DEPENDENCIES.get(feature, ()):
            if dependency not in enabled:
                enabled.add(dependency)
                pending.append(dependency)
    return ExecutionTarget(
        triple=canonical,
        architecture=preset.architecture,
        abi=preset.abi,
        pointer_width=64,
        endianness="little",
        cpu="x86-64",
        cpu_features=tuple(
            feature for feature in _FEATURE_ORDER if feature in enabled
        ),
        data_layout=preset.data_layout,
        is_freestanding=preset.is_freestanding,
    )


__all__ = [
    "ExecutionTarget",
    "ExecutionTargetError",
    "resolve_execution_target",
]
