# Growing UTF-8 text on the native heap

`runtime/native/heap_text.sotlas` provides an explicit UTF-8 text owner backed
by a dynamic byte vector. Hosted programs and the barecore kernel use the same
implementation. Validation and scalar encoding reuse the existing Unicode and
UTF-8 buffer routines.

The API supports append, byte-range replacement at scalar boundaries,
scalar-indexed replacement/insertion/removal, scalar lookup and slices,
self-append/replacement, decimal u64/i64 formatting, shrinking and close.
Allocation failure preserves the previous text and checked views.

## Ownership and views

Start with `native_heap_text_empty()` in stable caller-owned storage, then open
it with `native_heap_text_open(descriptor, heap)`. The descriptor must remain
outside the heap backing, control and metadata. The heap and descriptor must
outlive every view. Do not copy live descriptors, reset revisions, manipulate
their internal vector or free its allocation through lower-level heap APIs.

`native_heap_text_view` returns a revision-checked `NativeVectorView` over all
initialized UTF-8 bytes. `native_heap_text_slice(text, first, end)` selects
Unicode scalar indices, with an exclusive end, and returns the corresponding
byte view. Copy bytes using `native_vector_read`; its offset/count are bytes
for these views. Successful edits and capacity changes invalidate earlier
views. Close/reopen does not revive them.

The text owner has an explicit library lifecycle. Language-level string type
parity and automatic ownership cleanup remain separately tracked. There is no
implicit NUL terminator. Embedded U+0000 is valid. Character indices count
Unicode scalars, without grapheme segmentation or normalization.

## Edits and errors

`native_heap_text_replace(text, start, end, data, length)` uses byte offsets and
requires both ends to be scalar boundaries. The scalar replacement variant
resolves scalar indices before editing. Full source validation happens before
allocation or movement. Partial sequences, overlong encodings, surrogates and
values beyond U+10FFFF are rejected by the shared decoder.

The underlying `native_vector_replace` performs replacement in one splice.
It can shrink using existing capacity even when no additional heap bytes are
available. Sources within initialized text are snapshotted before resizing or
shifting; allocation failure releases the snapshot and leaves the text intact.
Self-edits can therefore require temporary heap space even without growth.

Append, replace, number formatting and shrink return a `NativeU32Result` whose
success value is the resulting byte length. Check returns the scalar count;
scalar offset returns a byte position; scalar lookup/removal return the scalar
value. Status 1 means null nonempty input, 7 means invalid shape/range or retired
revision, 8 means malformed UTF-8/scalar boundary, and 10 means allocation
failure. Validation offsets identify the malformed source position or the
rejected boundary in the existing text. Text length is limited to u32 bytes.

Decimal formatting builds the full number before appending it once. It handles
zero, U64_MAX, I64_MAX and I64_MIN without signed negation overflow; failed
formatting does not leave a partial sign or digit sequence.

External raw ranges must remain accessible and disjoint from descriptor and
allocator metadata. Views check lifetime/revision and bounds, not physical
pointer provenance. Full UTF-8 validation is linear in current text length;
the module does not promise constant-time edits or interrupt latency bounds.
Close can still release a structurally valid allocation whose payload was
corrupted, without first decoding that payload.

## Executable examples

The [hosted example](../examples/native_heap_text/README.md) builds a report,
formats U64_MAX, edits its prefix, checks a four-byte scalar slice and returns
all heap bytes. Successful native execution returns 42.

The [kernel collection example](../examples/native_kernel_collections/README.md)
now also generates a Unicode report using a page-backed heap:

```sh
bash scripts/build_kernel.sh build/native/sotlas-native build/text-kernel --collections --run
```

It prints `Sotlas: é events=2000 min=-9223372036854775808`, rejects an edit
inside `é`, checks view invalidation and closes text before releasing the heap
and physical pages. Collection/text operations on a borrowed kernel heap run
with IF clear under the existing single-processor serialization contract.

## Verification

`tests/test_sotlas_native_heap_text.py` covers Unicode edits, aliases, failed
growth and snapshot cleanup, full-heap shrinking, precise source errors,
integer limits, stale views, reopen, terminal revisions and corrupted-payload
cleanup. Vector tests also exercise multi-element POD replacement.

The original-source Stage 3 fixtures import and build the hosted example,
execute the host format and check owned ELF/PE/Mach-O emission. The kernel gate
boots the report with 32, 64 and 128 MiB in directories containing spaces, and
requires the actual Unicode report and success markers. Local Windows/Linux
execution passed; the new delivery still requires platform CI certification.
