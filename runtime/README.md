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


## Explicit native Sotlas runtime (SV8.50)

`native/managed.sotlas` is a separate caller-owned, single-threaded runtime API
compiled by the Sotlas-written x86-64 backend. Native project execution gates
compile this actual source with the platform driver and run with host tools absent.
It does not replace the C runtime used by reference backends or automatically
lower language ownership/state/effect syntax.

| API | Contract |
|---|---|
| `native_arena_init` | Caller provides a valid backing buffer and capacity; null storage has zero capacity |
| `native_arena_alloc` | Positive size, power-of-two alignment up to 4096; align the actual address; overflow/capacity failures preserve the cursor |
| `native_arena_mark` | Capture used bytes, generation and stable arena identity |
| `native_arena_rewind` | Accept a mark from the same arena/generation at or before its current cursor; invalidate previous marks; preserve state on failure |
| `native_ref_init` | Begin a new local control block with one strong reference |
| `native_ref_retain` | Reject null, dead, zero or saturated counts |
| `native_ref_release` | Return true exactly once on the last valid release, authorizing caller payload destruction; do not free or invoke a destructor |
| `native_ref_upgrade` | Match a live generation and acquire one additional strong reference; reject expired tokens |
| `native_authority_allows` | Require every requested capability bit |
| `native_authority_narrow` | Write a delegated subset only if granted; leave output unchanged on rejection |
| `native_state_transition` | Check expected state and authority before mutation |
| `native_contract_range` | Validate offset and size using subtraction to avoid overflow |

Callers retain the lifetime and validity of non-null pointers and control blocks.
Control-block addresses cannot be reinitialized while old tokens remain. Arenas
stay at stable addresses while marks exist; rewind requires discarded pointers
to stop being used. Marks are issued by the API, not forged from public fields.
This is neither an atomic/SMP ARC implementation nor static lifetime proof.
Native tests verify explicit reference cleanup through defer and early returns;
automatic shared cleanup, drop glue and allocator integration remain open.

For the current explicit-source profile, compile an application using
`sotlas-native --project OUTPUT runtime/native/managed.sotlas APP.sotlas`.
The application calls the exported APIs directly. This profile combines source
modules; it does not provide separate compilation or installed package resolution.
