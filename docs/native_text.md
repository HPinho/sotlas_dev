# Bounded UTF-8 text in the native runtime

SV8.98 adds `sotlas::runtime::utf8`, written in Sotlas. `NativeUtf8Text` owns an inline
`[u8;256]` and a byte length. It passes by value through the existing native
aggregate ABI; copying a value creates independent storage. There is no hidden
allocation, borrowed backing pointer or implicit NUL terminator.

All operations that inspect text validate the length before indexing and reject
malformed UTF-8, including overlong encodings, isolated continuations, surrogate
encodings, truncated sequences and code points above U+10FFFF. Error offsets refer
to the leading byte of a malformed sequence. Embedded U+0000 is a valid scalar;
it is not an end marker. Public fields permit construction of invalid values,
so operations validate their inputs rather than trusting constructors alone.

| Operation | Contract |
| --- | --- |
| `native_utf8_empty/from_bytes/from_u32` | Empty, validated byte-range or decimal construction |
| `native_utf8_from_slice` | Copy and validate the existing borrowed byte-slice representation |
| `native_utf8_validate` | Success value is Unicode scalar count |
| `native_utf8_concat/repeat` | Checked capacity, independent value output |
| `native_utf8_slice` | Half-open byte offsets on scalar boundaries |
| `native_utf8_trim` | Remove ASCII space and bytes 9 through 13 from both ends |
| `native_utf8_ascii_case` | Preserve/lower/upper ASCII; preserve other UTF-8 bytes |
| `native_utf8_equal/compare` | Exact bytes / UTF-8 byte lexicographic order |
| `native_utf8_find` | First byte offset; empty needle matches zero |
| `native_utf8_before/after` | Split around the first separator; empty separator at zero |
| `native_utf8_replace` | Non-overlapping matches; empty needle rejected |
| `native_utf8_push_scalar` | Encode one valid scalar with a capacity check |
| `native_utf8_parse_u32` | Strict checked decimal parsing via the numeric library |
| `native_utf8_write` | Check before publishing bytes; no terminator |

Text-producing operations return `NativeUtf8TextResult`: zero status succeeds and
the value is `NativeUtf8Text`. Other statuses preserve an error kind and byte offset.
Kind 8 means invalid UTF-8/boundary/scalar and kind 9 means no match. Null input
uses kind 1 and capacity/range errors use kind 7. Numeric operations retain the
[numeric result contract](native_result_propagation.md). Scalar count is not a
grapheme count; equality does not normalize Unicode and case conversion is ASCII.

Failures return an empty text value. Concatenation, replacement, repetition and
scalar insertion never mutate their input values. Writing to caller storage
checks validation, capacity, null and address arithmetic before its first write.
The caller must still supply valid readable/writable byte ranges: arithmetic
checks do not prove pointer provenance. Empty ranges require no dereference.

## Composition and error propagation

Text results use the concrete POD `status/value` schema and work with native `?`,
including lexical cleanup. SV8.98 also permits `?` directly on compatible
conditional and match expressions, their value blocks and inferred result locals.
Every branch must identify the same nominal concrete record; branch evaluation
and value-block cleanup happen before propagation captures the selected result.
Unselected branches do not run. General generic Result/error conversion and
resource-bearing result payloads remain outside this contract.

The [text pipeline](../examples/native_utf8_pipeline/README.md) composes imports,
parsing, normalization, numerical errors, report construction and cleanup.
Native tests cover capacity limits, invalid public storage, all UTF-8 sequence
widths, malformed encodings, independent copies, replacement expansion, numeric
round trips and transactional destination writes.

This is a bounded value library. Dynamic strings, general borrowed slices,
Unicode normalization/case folding, grapheme indexing and automatic ARC-backed
string storage remain open. Foreign byte-range interfaces are optional; this
module does not require C glue or a C runtime.

The existing `sotlas::runtime::text` byte-slice API retains its contract. The
new `utf8` module uses distinct names and can be imported with it. Converting a
borrowed slice copies its bytes into owned inline storage; later changes to the
original backing buffer do not change that value.
