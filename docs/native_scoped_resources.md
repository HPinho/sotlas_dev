# Native managed resource scopes — SV8.66

**Scope:** compiled Sotlas machine code, bounded single-threaded profile,
not a replacement for the canonical Python frontend's entire ownership
language. The implementation lives in
`runtime/native/managed.sotlas`; tests are in
`tests/test_sotlas_native_migration_sv866.py`.

## Problem and result

SV8.58 introduced reference-counted, generation-bound byte resources and
SV8.59 introduced an explicit slot close. SV8.60 added independently
retained clone/upgrade/take/swap slots. These operations previously
required every scope to hand-register a separate `defer` for every slot.

SV8.66 groups independently owned strong claims into one scope ledger:
a program can register multiple live slots, selectively detach or
transfer them to an outer scope, create nested depth marks, and close the
remaining registered claims in **last-in, first-out** order with a
single native lexical `defer`. The compiler emits the deferred call;
the resource ledger and its cleanup are written entirely in Sotlas.
There is no C intermediate or implicit Python semantic fallback
in the generated resource execution.

### SV8.66.1 — CI #1250 portable address-slot repair (2026-10-16)

The Linux/Windows/Intel-macOS jobs of
[CI #1250](https://github.com/HPinho/sotlas_dev/actions/runs/38949008917)
failed the same 14 new positive native test compilations, all at the
first pointer-to-pointer local cast from a scalar address array.
The previous SV8.65 [CI #1249](https://github.com/HPinho/sotlas_dev/actions/runs/38940935785)
is green. The native profile supports machine-pointer addresses but its
nested pointer-to-pointer array cast is not certified.

Keep the same complete 15-test ownership suite and its check/build/execute
contracts. Store registered stable handle addresses in caller-owned
`usize` entries (`*mut usize`) and cast each loaded scalar address
explicitly back to the native handle pointer. This retains every LIFO,
transactional preflight, detach/transfer and weak/strong lifetime guard.
No test removal, test skip, previous code rollback or Python/C fallback.
The repair is a **candidate** until its full cross-platform CI is green.

## Public API

| Function | Contract |
|---|---|
| `native_managed_scope_init(entries, capacity)` | Initializes 1–64 caller-owned `usize` address slots (pointer to `usize`); invalid extent/capacity yields an inert scope |
| `native_managed_scope_valid(scope)` | Checks table shape and bounded count |
| `native_managed_scope_depth(scope)` | Reads the current number of registrations |
| `native_managed_scope_contains(scope, handle)` | Tests registration by handle identity |
| `native_managed_scope_push(scope, handle)` | Registers a live generation-matched handle once, rejecting duplicates/full tables |
| `native_managed_scope_detach(scope, handle)` | Removes a registration without releasing its strong claim |
| `native_managed_scope_release_last(scope)` | Closes and poisons the latest handle; removes its table entry |
| `native_managed_scope_rewind(scope, depth)` | Checks a complete suffix, then closes it in reverse order; invalid/stale suffix leaves other live claims unchanged |
| `native_managed_scope_drain(scope)` | Checked cleanup down to depth zero |
| `native_managed_scope_close(scope)` | Void wrapper for compiler-lowered lexical `defer` |
| `native_managed_scope_transfer(src, dst, handle)` | Promotes a registered handle between distinct scopes with no retain/release |

A depth mark is simply the previously observed count. It is a
single-threaded, caller-controlled snapshot, **not a lifetime-proof
token**; callers must not reuse old depths after unrelated mutation.
The scope table itself, each handle, control block and backing buffer
must remain live and at stable, pairwise disjoint locations during the
entire operation. Distinct scopes must not alias each other's table
storage. Every independently registered handle must own a real strong
claim. Manual closing without detachment creates a stale scope entry;
a checked rewind then rejects rather than partly destroying the rest.

## Validation and negative boundaries

Fifteen cross-platform native tests cover table initialization,
null and excess-capacity rejection, duplicate registration,
membership/depth checks, strict LIFO observability, nested rewind,
out-of-range marks, stale-entry transactional failure, recovery by
detachment, claim-preserving transfers, full destination rejection,
64-bit capacity handling, cloned strong claims, weak generation
invalidation, lexical deferred cleanup on early return and loop jumps,
and native rejection of owner use-after-move/deferred consumption.

Actual tests run the Sotlas-written runtime in machine code produced by
the same owned frontend, object writer and linker as the certified
SV8.60 gates. Python orchestrates unit tests during CI; it is not a
dependency of the resulting native resource program. Existing OS,
bootstrap and stage-identity gates remain enabled.

**Certified baseline before this cut:** `768b6d1`, green
[CI #1249](https://github.com/HPinho/sotlas_dev/actions/runs/38940935785).
The SV8.66 commit is **candidate** until its complete workflow is green.

## Open work toward Python/C independence

- Compiler-synthesized exactly-once cleanup/drop glue for a frozen
  resource-bearing language subset, including partial initialization
  and branch/return/error paths
- General `sole`/`direct`/`whisper` lifetime and escape proofs,
  shared ownership ARC integration and multi-threaded reference counting
- Typed, separately compiled modules and ownership/effect/capability
  signatures verified by native object/link stages
- Native seed creation, packaging and installation paths with **zero**
  mandatory Python/C tools, measured by reproducible build audits

Nothing in this contract claims those four broader migrations are done.
