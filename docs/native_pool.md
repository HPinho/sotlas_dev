# Reusable native storage and persistent text

The runtime now derives slot/control sizes and alignment through
[native layout queries](native_layout_queries.md). These sources require a
compiler rebuilt with query support; the documented current x86-64 sizes remain.

`runtime/native/pool.sotlas` allocates fixed-size blocks from caller-owned byte
storage and slot metadata. Unlike arena rewind, releasing one allocation does
not invalidate unrelated allocations. `pool_text.sotlas` adds strict UTF-8
creation, append, replacement, truncate and checked text views on those blocks.
Both modules are Sotlas code, without a C allocator, OS calls or hidden growth.

## Allocation identity

Initialize the control with `native_pool_empty`, then call `native_pool_open`
with disjoint accessible control, metadata and backing storage. The native
x86-64 layout is a 32-byte, 8-aligned slot and a 56-byte, 8-aligned control.
The example uses `native_pool_open_words` with four u64 metadata words per
slot. This wrapper checks the word capacity and projects the address in Sotlas,
then open initializes all slot fields. It avoids a record-array address conversion
that is outside the current frontend profile.
The pool supports 1–4096 slots, each containing 1–4294967295 bytes, subject to
the supplied backing capacity. Opening checks bounds, alignment and overlap
before initializing metadata. Byte storage is initialized when allocated.

| Operation | Contract |
| --- | --- |
| `allocate(pool, length)` | Zeroes a free block and returns a generation-checked handle; invalid handle on exhaustion or invalid size |
| `current(handle)` | Validates pool epoch, slot identity, live state and bounds before using backing bytes |
| `release(handle, wipe)` | Releases one allocation; optional full-block wipe; rejects a second release |
| `clone(handle)` | Copies into a different allocation with an independent lifetime; exhaustion leaves source unchanged |
| `resize(handle, length, wipe)` | Changes length within one block, zeroes newly exposed bytes, optionally wipes truncated bytes |
| `write(handle, offset, data, length)` | Bounded memmove; overlapping byte sources supported; rejects control/metadata sources |
| `view(handle, offset, length)` | Captures allocation generation and mutation revision |
| `read(view, destination, capacity)` | Rejects stale views and destinations overlapping pool bytes, control or metadata |
| `reset(pool, wipe)` | Explicitly invalidates every allocation/view by advancing epoch; optionally wipes all backing bytes |
| `close(pool)` | Refuses live allocations; later open advances epoch again |

Names in the table omit the `native_pool_` prefix. Generation, revision and
epoch counters never wrap: exhausted free-slot generations retire until reset;
revision saturation rejects edits; epoch saturation rejects reset/reopen.
Successful writes/resizes invalidate views of their allocation. Unrelated
allocations and their views stay valid. Failed operations preserve their data
and identity. Zero-length writes and unchanged resize do not invalidate views.

## UTF-8 operations

Scalar APIs locate/read codepoints, create checked scalar slices and replace
scalar ranges. Numeric append uses the checked u32 formatter. Scalar indices
count Unicode codepoints, not grapheme clusters or display columns.

Text creation validates all source bytes before allocation. Raw creation sources
inside pool backing are rejected; use clone for existing allocations. Append
allows an existing byte source in the same block. Replace rejects sources that
overlap its destination block, so shifting cannot corrupt the source. UTF-8
validation and scalar-boundary/capacity checks precede mutation. Errors preserve
text bytes, length and views. Text edits return the existing `NativeU32Result`
contract: status 7 for bounds/storage, 8 for malformed UTF-8/boundaries.

`native_pool_text_view` returns a checked `NativePoolView`, consumed by
`native_pool_read`. The buffer projection helper returns a raw borrowed
descriptor: callers must not retain or mutate it across pool edits/releases.
Direct descriptor, metadata or backing writes bypass the checked API.

For composition, scalar insert/remove/pop, independent slice cloning, checked
key/value splitting and numeric parsing, see
[persistent text composition](native_pool_text_composition.md) (SV8.103).
The same executable report now exercises these APIs on every supported native
Stage 3 platform. Previously validated pool identity rules remain unchanged.

## Limits

Handles copied by value identify the **same allocation**, not separate ownership
claims. Releasing any copy invalidates all copies; clone is the independent-copy
operation. This is explicit allocation management, not automatic ARC, weak
references or compiler-proven lifetimes. There is no thread synchronization.
Control and metadata must outlive stale-handle checks. Raw pointers and source
and destination ranges must refer to accessible caller storage; address checks
cannot prove pointer provenance or arbitrary pointer accessibility. Pools sharing
overlapping storage are outside the contract. Wiping is ordinary byte stores,
not a cryptographic secure-erasure guarantee. Text capacity does not grow past
the configured block size; use arena text when monotonic growth is preferable.

## Reproduce

[The example](../examples/native_pool_text/main.sotlas) builds a persistent text,
clones it, reuses the original slot and verifies stale-view rejection. Success
returns 42. The shared test helper stages imports in `build/pool/src`; with a
native seed and that staged source root:

```sh
sotlas-native --check-build build/pool/src build/pool/src/main.sotlas
sotlas-native --build build/pool/app build/pool/src build/pool/src/main.sotlas
```

Use `--build-win` for Windows or `--build-mac` for Intel macOS. The shared native
gate tests object output, direct application build, ELF/PE/Mach-O emission and
execution on the current host with host tools absent from PATH.
`tests/test_sotlas_native_pool.py` executes allocation reuse, stale identities,
clone independence, exhaustion, zeroing, counter saturation, overlap, UTF-8
editing and failure atomicity as machine code.
It also exercises repeated reuse while keeping a neighbor alive and deferred
release on both success and propagated-error paths.

Local candidate validation: 24 new pool tests passed through the hosted producer;
78 pool/arena/buffer/managed-runtime execution cases passed per native Windows
and Linux host. The imported example passed native check, object and direct build,
with host execution returning 42 and byte-identical object/ELF/PE/Mach-O artifacts
across those producers. Twenty-five roadmap/reality/manifest/self-host contract
checks and the generated phase-matrix check passed. Actual Intel macOS execution
and the new complete CI run remain pending; all three original-source Stage 3
platform gates now include the example. Compiler sources are unchanged, so this
delivery reuses the already fixed-point-verified native seeds.
