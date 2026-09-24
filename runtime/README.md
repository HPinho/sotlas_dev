# Sotlas runtime sources

This directory contains runtime providers used by compiler/backends and native
conformance tests. A file existing here does **not** by itself make the
corresponding language feature globally `SUPPORTED`.

## General runtime

- `libsotlas_rt.h` / `libsotlas_rt.c` — allocation hooks, ARC primitives,
  panic handling and slice helpers.
- `memory.c` — low-level memory support.

## DEVICE ABI v1 reference provider

- `device_reference.h` / `device_reference.c` — deterministic, fixed-capacity,
  single-threaded conformance implementation of the reference C11 DEVICE ABI.

The reference provider implements the frozen lifecycle calls:

```text
submit -> complete -> synchronize -> reacquire
```

It validates queue identity, submission state, unique completion membership,
fence membership and final reacquisition. It intentionally performs **no** DMA,
GPU/accelerator submission, MMIO, cache maintenance, interrupts, driver I/O or
physical device synchronization. Address/extent ownership is mirrored only so
the compiler-generated ABI can be linked and executed in native conformance
tests.

Consequently:

```text
reference runtime executable != hardware DEVICE runtime supported
```

A real provider must implement the same validated ABI contract for its target
and must not weaken the compiler's ownership/completion/synchronization proofs.
