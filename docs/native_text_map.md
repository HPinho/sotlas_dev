# Native UTF-8 configuration map

`runtime/native/text_map.sotlas` provides a bounded collection of UTF-8 keys and
values using the reusable native pool. Keys and values are copied into separate
owned slots. It supports lookup, replacement, deletion, numeric conversion,
checked-view insertion, iteration and explicit cleanup, without a C allocator,
Python process or OS dependency in the application.

This is a concrete runtime collection, not generic language-level `Map<K,V>` or
automatic ownership inference. [The example](../examples/native_config_map/main.sotlas)
loads a field from stored text, releases its source, changes configuration,
iterates the entries and computes 42 before deferred collection cleanup.

## Storage and identity

Initialize `NativeTextMap` with `native_text_map_empty`, then open it over a live
`NativePool` and a separate u64 entry table. Each entry needs seven words. Capacity
is 1–256 entries, each key/value fitting one pool block. The x86-64 map control
occupies 48 bytes with alignment 8; table alignment is also 8. Open validates
ranges, capacity, alignment and disjointness against map/pool control, pool slot
metadata and pool backing before writing the table. Caller storage must actually
be accessible and remain alive; arithmetic checks cannot establish provenance.

Each live entry records the indices, generations and revisions of its key/value
allocations. Validation rejects reset epochs, released/reused slots, changed
revisions, duplicate allocation identities and inconsistent occupancy/counts.
Pool epoch changes are rejected before accessing the old entry table.

Map operations retain no raw input pointers. An insertion needs two free slots;
updating an existing value operates transactionally in its existing block and
does not require a free slot, including when the pool is full. Removing an entry
releases both slots. Clearing releases every recorded entry and preserves pool
allocations owned by other callers. Optional wiping uses ordinary byte stores.

## API

Names below omit `native_text_map_`.

| Operation | Result |
| --- | --- |
| `open(map, pool, words, word_capacity, capacity)` | Validated empty map; rejects an already open control |
| `find(map, key, length)` | Entry index or structured error |
| `get(map, key, length)` | Checked value view; invalid view when absent/invalid |
| `get_u32(map, key, length)` | Strict decimal result, retaining parser error offsets |
| `set(map, key, key_length, value, value_length)` | Insert or replace, returning entry count |
| `set_u32(map, key, length, value)` | Format u32 and insert/replace |
| `set_views(map, key_view, value_view)` | Copy checked UTF-8 ranges, including from the destination pool |
| `remove(map, key, length, wipe)` | Release one key/value pair, returning remaining count |
| `cursor(map)` / `next(cursor)` | Validated iteration, with explicit invalid and end states |
| `clear(map, wipe)` | Release all entries, keeping the map reusable |
| `close(map, wipe)` | Clear entries and close control |
| `detach_stale(map)` | Forget obsolete entries after pool reset/close without releasing reused allocations |

Keys compare exact UTF-8 bytes: no case folding or Unicode normalization. Empty
keys and values are valid. The table uses linear search and reuses vacant entry
positions; iteration order is table order, not a stable insertion-order promise.
Full invariant validation includes pairwise allocation checks, so this bounded
implementation favors small configuration/state sets over large database use.

`NativeU32Result` status 7 denotes invalid storage, range, alias or saturation;
8 invalid UTF-8; 9 missing key; 10 insufficient entry/pool capacity. Numeric reads
preserve the numeric parser's existing statuses and offsets. Failed operations
leave existing map contents, count, revision and views unchanged. Exhaustion is
preflighted before allocating either half of a new pair.

## Views, iteration and cleanup

Updating a nonempty value invalidates its earlier views. Removing a key invalidates
both key and value views; unrelated entry views stay valid. All successful map
mutations advance the map revision and invalidate cursors. End of iteration is
`valid && done`; stale/corrupt cursors return `valid == false`. Failed mutations
preserve cursors. Revision counters never wrap; saturated mutations are rejected.

Raw insertion ranges must be outside pool backing, the entry table and both
controls. For stored inputs, use `set_views`: source allocation generations and
revisions are validated before reading, and slices must contain complete UTF-8.
Copying from live same-pool slots is safe because allocation cannot reuse them.
In-place replacement from the destination value's own bytes is rejected before
mutation; source views from another slot or disjoint pool are supported.

An active map control must not be copied as an independent owner. Map-owned
handles, backing and metadata must not be independently edited or released.
Such detectable violations fail closed before cleanup; recovery then requires
an explicit pool reset followed by stale detach. Reset invalidates all pool
owners, so coordinate it with other users of that pool. This API does not provide
thread synchronization, compiler-proven lifetimes, weak references or automatic
ARC/drop. Explicit `defer { native_text_map_close(map, true); }` composes with the
existing native result propagation on both success and failure.

## Evidence

`tests/test_sotlas_native_text_map.py` executes machine-code tests for ordinary
and Unicode keys, empty values, full-pool replacement, capacity failures,
no-half-insert behavior, removal/reuse, checked field copying, cross-pool source
lifetime, stale views/cursors, corrupted aliases, layout rejection, counter
saturation, numeric diagnostics and deferred cleanup after propagated failure.

The shared original-source Stage 3 gates for Linux, Windows and Intel macOS now
build the imported configuration example, produce ELF/PE/Mach-O artifacts and
execute the host image with host tools absent from PATH. Cross-format emission
does not substitute for execution on each actual platform. New CI certification
remains pending until that run completes.

Local validation for this candidate: 20 new collection tests passed through the
hosted producer; 60 collection/pool execution cases passed per Windows/Linux
native host. The imported application passed check, object and direct build
and returned 42 with host tools absent from PATH. Object, ELF, PE and Mach-O
outputs were byte-identical across the two native producers. Twenty-five phase,
reality, example-manifest and self-host contract checks passed, as did the
generated phase-matrix check. Compiler sources are unchanged; validation reused
the previously verified native seeds rather than repeating a compiler rebuild.
