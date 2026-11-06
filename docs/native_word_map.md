# Native u64 maps

`runtime/native/word_map.sotlas` implements a heap-backed u64-to-u64 hash map.
It supports lookup, insertion/update, checked addition, removal, capacity
reservation, shrinking/compaction, clear, close and revision-checked iteration.
The same implementation runs in hosted programs and the native kernel.

## Ownership and results

Initialize stable caller-owned storage with `native_word_map_empty()`, then
call `native_word_map_open(descriptor, heap)`. An empty map allocates nothing.
The descriptor must stay outside the heap payload, control record and metadata.
Keep it and the heap alive while using the map or its cursors. Do not copy live
descriptors, reset revisions, change their fields or release their internal
allocation through raw heap APIs.

`native_word_map_get` returns `NativeWordLookup`: `valid` distinguishes an invalid
owner from a valid lookup, `found` distinguishes absence from a stored zero,
and `value` contains the value when found. All u64 keys and values, including
zero and U64_MAX, are ordinary entries. Removal returns the removed value with
the same valid/found distinction.

`native_word_map_set` returns false for invalid input, exhausted revision or
allocation failure. `native_word_map_add` inserts an absent counter or adds to
an existing one; overflow returns false without changing the map. Setting an
existing key needs no allocation, including when the heap is full. A failed
growth preserves entries, count, storage handle and revision.

This is an explicit library owner for word-sized data. Generic key/value types,
resource-bearing values and automatic ownership cleanup remain separate work.

## Buckets and growth

Capacity is a power of two starting at eight buckets. A deterministic bit-mixing
hash and bounded linear probing locate entries. Empty, occupied and deleted
states are separate from the key. Searches continue through deleted buckets;
removal cannot sever a collision chain, including one that wraps around the
end of the table. Even a table with no empty buckets terminates after at most
`capacity` probes and can reuse a deleted bucket.

Insertion grows before exceeding a 75% live load. Reserve takes an entry count,
not a bucket count. Rehash builds a separate zeroed table and copies all live
entries before committing and releasing the old table. For an allocated map,
both tables and two heap allocation slots must fit during rehash. Failure retains the original map and
releases any temporary allocation.

Shrink chooses the smallest supported capacity for the live entries and removes
tombstones. It can rebuild at the same capacity to compact a table. Shrinking an
empty map returns its allocation. Clear resets entries while retaining capacity;
close clears and releases the table. Old values are u64 copies and require no
destructors. The map does not promise secure erasure against external observers.

Expected lookup/update cost is constant under a well-distributed workload.
Worst-case probing is linear; rebuilding an adversarial collision cluster can
take quadratic work. The deterministic hash is
not a cryptographic or adversarial-collision defense. Iteration order is
unspecified and should not be treated as a serialization format.

## Iteration and lifetime

Create a `NativeWordCursor` with `native_word_map_cursor` and pass it to
`native_word_map_next`. A valid item has `valid=true`, `done=false`, copied key
and value fields, and a next cursor. Exhaustion has `valid=true, done=true`.
Stale or invalid cursors have `valid=false`.

Every successful set/add or removal invalidates previous cursors, even when
an update stores the same value. Capacity changes, compaction and nontrivial
clear also invalidate them. Missing removal, failed operations, already-satisfied
reserve, already-compact shrink and empty clear preserve them. Close/reopen
advances the revision; it never revives an old cursor. Revision exhaustion
refuses further mutations but still permits close and permanent retirement.
Copied item values remain ordinary values; only further cursor traversal is
invalidated by a mutation.

The implementation is single-threaded. When using a borrowed kernel heap,
serialize every map operation and iteration with IF clear under the existing
kernel heap borrow contract. Rehash and clearing run inside that critical
section; there is no SMP lock or real-time latency guarantee. Caller-provided
control pointers must refer to accessible memory. Shape and generation checks
cannot establish raw pointer provenance.

## Examples and verification

The [hosted histogram](../examples/native_word_map/README.md) counts 5000 tokens
across 61 keys, checks every frequency through iteration, and closes both map
and heap. Successful execution returns 42.

The [kernel collection example](../examples/native_kernel_collections/README.md)
counts 6000 tokens across 257 keys while timer handlers allocate temporary
buffers between serialized map operations. It verifies frequencies, removal,
stale-cursor rejection, compaction and cleanup before returning all heap pages.
The gate requires the map success marker in boots with 32, 64 and 128 MiB RAM.

`tests/test_sotlas_native_word_map.py` covers collision chains, tombstone reuse,
growth, iteration, byte/metadata exhaustion, failed compaction, overflow,
terminal revisions, descriptor overlap and stale backing. A 1200-operation
workload checks all keys and values against an independent fixed-array model.
Stage 3 fixtures import/build the hosted program, execute the host binary and
check owned ELF/PE/Mach-O output. Local execution is evidence for this profile;
platform CI certification remains required.
