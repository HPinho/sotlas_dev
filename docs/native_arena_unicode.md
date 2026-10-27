# Unicode scalar operations on arena text (SV8.101)

The `sotlas::runtime::arena_text` module extends the SV8.100 growing
`NativeArenaText` with scalar-indexed queries, editing and composition.
These operations are implemented in Sotlas, with no new Python/C runtime path.

| API | Contract |
| --- | --- |
| `native_arena_text_scalar_offset` | Map a scalar index (including end) to its byte offset |
| `native_arena_text_scalar_at` | Read the Unicode scalar at an index |
| `native_arena_text_slice_scalars` | Return a borrowed byte slice over a scalar range |
| `native_arena_text_append_text` | Append an entire live arena text, including itself |
| `native_arena_text_append_scalars` | Append a range of scalars from a live source |
| `native_arena_text_replace_scalars` | Replace a scalar range with validated UTF-8 |
| `native_arena_text_insert_scalar` | Insert one checked scalar at a scalar boundary |
| `native_arena_text_remove_scalar` | Remove one scalar and return its code point |
| `native_arena_text_pop_scalar` | Remove and return the last scalar |

**Indices count Unicode scalar values, not UTF-8 bytes, grapheme clusters or
display columns.** A valid end index maps to the byte length but cannot be
read or removed. A reversed or out-of-bounds range fails closed. Slice results
use `NativeByteSlice.valid=false` for invalid ranges. Other calls return
`NativeU32Result`; status 7 denotes invalid index, shape, generation or
alias, status 8 malformed UTF-8 or invalid scalar, and status 10 arena exhaustion.

All scalar lookups check the arena's generation and validate the complete UTF-8
content before reading individual bytes. Repeated lookup scans linearly; edits
may rescan. These routines are correct-by-contract primitives, not a cached
codepoint index. Replacement delegates its capacity, UTF-8, alias and failure
preflight to the existing transactional byte edit. The single-scalar encoder
validates its Unicode value before the edit. Self append and source-range append
are permitted: relocated data remains accessible in the same arena until rewind.

On failure, the editor preserves the current byte length, live text contents,
arena cursor and descriptor. As with SV8.100, raw caller-provided pointers must
be accessible and stable, descriptors may not overlap backing, and concurrent
edits are unsupported. A slice is a borrow: it does not retain a generation
token or prevent mutations, relocation, close or rewind. Descriptor copies are
not separately owned strings; these functions do **not** introduce automatic
ARC/drop, provenance guarantees, grapheme segmentation, normalization or an
OS heap allocator.

The regression gate exercises ASCII and 2/3/4-byte UTF-8, bounds, inline edits,
cross-text copying, self append across relocation, malformed data, stale
generations, alias rejection and out-of-memory atomicity. The arena report
example exercises the public APIs through the native module import. The
post-seed execution path does not call an external C compiler or Python; the
hosted CI harness still uses Python for tests and initial seed generation.

SV8.102 corrects the scalar-insertion exhaustion fixture and adds
[typed pointer projections and record snapshots](native_pointer_projections.md).
A native-managed persistent allocation profile and additional text lifetime
analysis remain open; automatic ARC and OS heap allocation are not claimed here.
