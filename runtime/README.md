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
Control-block addresses cannot be directly reinitialized while old tokens remain. Arenas
stay at stable addresses while marks exist; rewind requires discarded pointers
to stop being used. Marks are issued by the API, not forged from public fields.
This is neither an atomic/SMP ARC implementation nor static lifetime proof.
Native tests verify explicit reference cleanup through defer and early returns;
automatic shared cleanup, drop glue and allocator integration remain open.

For the current explicit-source profile, compile an application using
`sotlas-native --project OUTPUT runtime/native/managed.sotlas APP.sotlas`.
The application calls the exported APIs directly. This profile combines source
modules; it does not provide separate compilation or installed package resolution.


## Reusable weak tokens and memory operations (SV8.51)

| API | New native contract |
|---|---|
| `native_ref_weak` | Capture a pointer/generation token; null/dead blocks produce an empty token |
| `native_weak_upgrade` | Acquire a strong reference from the token's own live control block |
| `native_ref_recycle` | Reuse fully released storage by advancing generation; reject live/zero/saturated headers |
| `native_ref_release_checked` | Return 0 for invalid release, 1 for remaining owners, 2 for final caller destruction |
| `native_arena_alloc_zero` | Allocate and clear the requested bytes, preserving failure behavior |
| `native_memory_copy` | Reject overlapping or overflowing nonempty ranges; allow empty null ranges |
| `native_memory_move` | Copy overlapping ranges in the required direction with checked arithmetic |
| `native_arena_rewind_zero` | Validate before clearing discarded bytes and invalidating marks |
| `native_authority_init` | Initialize mask and generation 1 |
| `native_authority_revoke` | Remove bits and advance generation without wrap |
| `native_authority_current` | Check all required bits at the exact observed generation |
| `native_state_transition_current` | Require current authority, expected state and a permitted destination among 64 states |

Control blocks and buffers remain caller-owned and must stay valid. Recycling
through the API is permitted with old weak tokens outstanding; direct header
reinitialization is not. Tokens/marks must be issued by the API, not forged.
These operations remain non-atomic; canonical shared/whisper/authority/state
syntax and automatic drop lowering are separate migration work. Cleared memory
is verified through native reads; secure erasure against devices is not claimed.

## SV8.53 explicit native operations

All operations below are implemented in `runtime/native/managed.sotlas` and
covered by native execution in `test_sotlas_native_migration_sv853`.

| API | Contract |
|---|---|
| `native_ref_retain_many` | Checked all-or-nothing local count increase; zero is a no-op on a live header |
| `native_ref_release_many` | Reject zero/underflow; return 0 invalid, 1 retained, 2 final destruction |
| `native_weak_current` | Observe owner/generation liveness without acquiring a reference |
| `native_ref_is_unique` | Observe a live header with one strong reference |
| `native_memory_fill` | Fill a valid caller-owned range; check address overflow first |
| `native_memory_equal` | Byte equality, not a constant-time operation; empty null ranges compare equal |
| `native_arena_remaining` | Return remaining capacity, or zero for invalid/full arenas |
| `native_arena_reset_zero` | Clear used bytes, reset cursor and advance epoch; caller proves discarded allocations are unused |
| `native_authority_capture` | Capture owner, generation and required mask; return empty on failure |
| `native_authority_token_current` | Validate captured rights against the current owner generation |
| `native_authority_delegate` | Derive a narrower current token; reject widening or revocation |
| `native_state_transition_token` | Require a current token, expected state and allowed destination |

Control blocks and authority owners require stable backing storage. Public
token fields are not unforgeable capabilities; the embedding application grants
rights. Observations do not synchronize concurrent accesses. These APIs do not
implement automatic ARC, a static lifetime graph or canonical authority syntax.
