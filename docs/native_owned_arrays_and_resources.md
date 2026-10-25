# Native array ownership and resource batches

This block connects bounded value arrays to the native ownership checker and
adds collective validation and suffix transfers to the Sotlas resource runtime.
The compiler and runtime changes are written in Sotlas.

## Internal array ABI

```sotlas
fn read(values:direct [u32;2])->u32 { return values[0]+values[1]; }
fn transfer(values:sole [u32;2])->sole [u32;2] { return values; }

pub fn main_entry()->u32 {
    let values:sole [u32;2]=[20,22];
    if read(values)!=42 { return 1; }
    let moved:sole [u32;2]=transfer(values);
    return moved[0]+moved[1];
}
```

- `sole` and its `exclusive` spelling consume ownership on calls, local moves
  and returns. Use-after-move, duplicate consumption and incompatible live-path
  joins are rejected. This applies to scalar and pointer-free POD record arrays.
- `whisper` and `direct` parameters cannot consume, mutate or escape their
  arguments. Forwarding to another compatible internal borrow is accepted.
- A `whisper` call uses an independent immutable POD snapshot, as the existing
  native record ABI does. `direct` passes the address of compatible storage;
  literals and contextual conditional/match arguments receive call-local storage.
  An unsafe alias can distinguish a snapshot from a direct view; ordinary owned
  code cannot manufacture that alias through a borrowed array.
- Scalar reads and array matching do not consume the owner. Deferred observers
  reserve their owners until cleanup, preventing an intervening transfer.
- Owner domains are retained on local storage, parameters and hidden return
  destinations in Target IR. Returns are captured before lexical cleanup.
- Existing bounds apply: 1–256 elements, at most 4096 bytes, private same-unit ABI.
  Foreign signatures, qualified fields/payloads, slices and arrays containing
  pointers or resources remain rejected.

These are ownership contracts for POD storage. They do not add automatic ARC or
resource destruction to array elements.

## Explicit resource transactions

`runtime/native/managed.sotlas` exposes two additional operations:

| Operation | Behavior |
| --- | --- |
| `native_managed_scope_claims_valid(scope)` | Validate all registered handles, generations, payload agreement and the number of strong claims per control block |
| `native_managed_scope_transfer_suffix(src,dst,mark)` | Move registrations from `mark` to the source depth into the destination, preserving order and reference counts |

Suffix transfer validates both complete scopes, disjoint table storage,
destination capacity, cross-scope handle uniqueness and combined strong claims
before the first write. Failure leaves registrations, handles, counts and payload
bytes unchanged. Success appends in original order and clears the vacated source
entries; subsequent destination cleanup runs in reverse registration order.
Transferring an empty suffix still validates the complete transaction.

Checked rewind/drain now use the same collective claim check. Previously, two
distinct handles copied without a matching retain could each appear live while
collectively exceeding their header's strong count. Cleanup could then release
one before discovering the other was invalid. That state now fails preflight.
Stale or inconsistent entries anywhere in the scope, including before the rewind
mark, must be repaired or detached before checked cleanup proceeds.

The runtime remains single-threaded and uses 1–64 caller-owned registrations per
scope. Tables, handles, headers and payload buffers must have valid, stable,
disjoint storage. Validation cannot make forged pointers safe or account for
unregistered claims outside the supplied scopes. Enrollment and cleanup remain
explicit API calls, usually paired with native `defer`; this is not compiler-
generated ARC or a general weak-reference lifetime proof.

## Pointer-backed metadata

Native record-field access now resolves typed pointer locals as well as pointer
parameters. Mutable pointer bindings load their current address before projection,
so reassignment changes the addressed object rather than corrupting the pointer's
stack slot. Making a `*const` binding mutable does not authorize writes through
its field or indexed projections; semantic analysis rejects those assignments.
Raw pointer validity and unsafe access retain their existing caller contracts.

## Evidence

- `tests/test_sotlas_native_owned_array_abi.py`: ownership transfers, borrowing,
  forwarding, stack arguments, cleanup and rejections.
- `tests/test_sotlas_native_resource_batches.py`: suffix transfers, combined
  counts, payload agreement, rollback, weak invalidation, empty/full boundaries
  and deferred cleanup.
- Existing managed runtime and SV8.66/SV8.67 scope suites remain enabled.
- Shared rebuilt Stage 3 fixtures check owned arrays and located failures before
  artifact publication. [The public example](../examples/native_match_values/main.sotlas)
  demonstrates borrowing followed by an owned array transfer.


## Local validation

Local validation: 330 native match, array-ABI and resource tests pass on each
Windows/Linux host, plus 72 shared rebuilt Stage 3 driver cases per host. The
29 new tests also pass through the hosted seed route. Another 269 focused
frontend, parser, semantic, numeric, record-storage, bootstrap and documentation
tests pass. Native Stage 2/3 fixed points hold within each host. The exact Windows
original-module CI gate passes with calculator, GUI and UI-model checks. Example
objects and ELF/PE/Mach-O images are identical across hosts, and the Windows/Linux
images execute with exit 42. The new GitHub matrix and actual Intel macOS
execution remain pending.

