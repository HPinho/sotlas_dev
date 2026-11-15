# Native in-memory JSON

## Block completion

**Implementation status: closed for the in-memory contract below.** Further
language work can move to the remaining frontend, ownership and preview-delivery
blocks. Platform CI for this commit remains a separate certification gate.

- [x] Whole-document parsing of all JSON value kinds under the published UTF-8/depth rules.
- [x] Checked lookup and complete object/array traversal, including empty containers and duplicate names.
- [x] Lossless raw number tokens, checked `u32` conversion and Unicode string decoding.
- [x] Construction of every value kind with grammar checks and bounded caller storage.
- [x] Validated whole-value/subtree re-emission with combined-depth and alias checks.
- [x] No partial writes or construction-state changes on rejected write operations.
- [x] Original-source configuration read, map update, traversal, re-emission and readback before cleanup.
- [x] Local native execution and ELF/PE/Mach-O emission on Linux and Windows hosts.
- [ ] Cross-platform CI certification for this closing commit, including Intel macOS execution.

The closed block is a memory-format API. Files/networking, schema validation,
reflection-based serialization, implicit floating-point conversion, indexing
optimizations and compiler-proven borrow lifetimes belong to other contracts.

Closing evidence: all 31 reader/writer/exchange tests passed through native
Linux and Windows compilers. The focused JSON/map regression passed 51 tests,
and 35 contract/documentation checks passed. The original-source application
passed checking, native execution and ELF/PE/Mach-O emission on both hosts.
`tests/test_sotlas_native_json_exchange.py` adds the traversal, re-emission,
combined-depth, cursor-membership and failure-preservation closure cases.

`runtime/native/json.sotlas` reads JSON using the Sotlas-written compiler and
runtime. It validates a complete document, provides readonly object/array
navigation, decodes strings into caller storage and offers explicit checked
`u32` conversion. It allocates no memory and calls no foreign JSON library.

The grammar follows [RFC 8259](https://www.rfc-editor.org/rfc/rfc8259.html).
This profile requires valid Unicode scalar strings: malformed UTF-8, invalid
escapes and unpaired UTF-16 surrogate escapes are rejected. A valid surrogate
pair decodes to one scalar. A leading BOM is rejected. Whitespace is limited
to JSON's space, tab, CR and LF bytes; comments and trailing commas are errors.
Top-level scalars, objects and arrays are accepted.

## API

Import `sotlas::runtime::json::*` and the text module for `native_text_open`.
Names below omit `native_json_`.

| Operation | Behavior |
| --- | --- |
| `parse(source)` | Validate the entire source; return its root or a byte-positioned error |
| `object_get(value, key)` | Find a member by its decoded Unicode name |
| `array_at(value, index)` | Select a zero-based array item |
| `iter(value)` / `next(cursor)` | Traverse direct object members or array items |
| `depth(value)` | Count maximum nested containers; zero for scalar values |
| `raw(value)` | Borrow the exact source token, including quotes/escapes for strings |
| `u32(value)` | Convert an unsigned integer token with checked overflow |
| `string_copy(value, destination, capacity)` | Decode to UTF-8 without a terminating NUL |

`NativeJsonResult` contains `status`, `found`, `offset` and `value`. Successful
parsing has `status == 0 && found`. Missing keys/indices have `status == 0 &&
!found` and an invalid value. JSON `null` is a found value, not absence.
Inspect status before using a result; value conversion also validates descriptors.

Value kinds are: 1 object, 2 array, 3 string, 4 number, 5 true, 6 false and 7 null.
Objects retain duplicate names; lookup returns the first decoded-name match.
Escaped and raw spellings of the same name compare equally. No case folding or
Unicode normalization is performed. Object order has no semantic significance.

`NativeJsonIter` traverses one object or array in source order, preserving
duplicate names. `NativeJsonItem` has `status`, `done`, `offset`, `key`, `value`
and `next`. Loop with `next(cursor)`, check status, stop on `done`, then use
`item.next`. Object keys are string values and can be decoded with `string_copy`;
array keys are invalid. Empty containers and exhausted cursors return successful
`done` items with invalid key/value fields. Exhaustion is repeatable. A scalar
produces an invalid iterator. Invalid or forged cursor positions return status 1.

Cursor validation checks direct-member boundaries, not merely byte ranges, so
an interior position in a nested value cannot become a sibling. This requires
rescanning from the container start. Full traversal can be quadratic in source
length; the profile favors bounded configuration documents, without a hidden
index or allocation. Input storage must remain unchanged and alive.

Numbers retain their exact lexical bytes, including long integers and large
exponents. The reader does not round numbers to floats. `u32` accepts only
nonnegative decimal integer tokens; it rejects minus signs (including `-0`),
fractions, exponents and values above 4294967295. It returns `NativeU32Result`,
whose existing numeric statuses apply, with offsets adjusted to the original
source. This differs from the JSON navigation status table below.

## Errors and storage

| JSON status | Meaning |
| --- | --- |
| 0 | Success; `found` distinguishes presence from absence |
| 1 | Invalid source/value/output range metadata |
| 2 | Invalid syntax, unexpected EOF or trailing content |
| 3 | Invalid UTF-8, string control byte or escape sequence |
| 4 | Wrong value kind for the operation |
| 5 | More than 64 nested object/array containers |
| 6 | Insufficient string output capacity |
| 7 | String output overlaps the document source |

Offsets are zero-based bytes, not Unicode character positions. EOF errors may
point one byte past the last input byte. String-copy capacity failures report
the required decoded byte length. All string-copy checks finish before writing:
invalid metadata, insufficient capacity and overlap leave output unchanged.
Escaped U+0000 produces an embedded zero byte; no terminator is appended.

The input must remain readable, alive and unchanged for all values and queries.
Output storage must be writable for its declared capacity. Arithmetic checks
cannot prove pointer provenance or make an inaccessible address safe. Value
descriptors are revalidated; they are not ownership or lifetime tokens. Concurrent
source mutation, automatic borrowing, ARC and resource payloads are outside this
contract. Callers may copy decoded strings into their own managed storage.

Parsing is linear in input length with bounded recursive depth. Lookups revalidate
their selected value and scan members/items without building an index or AST.
Repeated queries can therefore rescan the same text. There is no fixed total
member count or allocator. The reader performs no schema validation or implicit
file/network I/O; JSON construction uses the separate writer below.

## Constructing JSON

`runtime/native/json_writer.sotlas` adds an explicit builder over the existing
`NativeUtf8Buffer`. Import `sotlas::runtime::json_writer::*` to use it. The writer
has no allocator or foreign dependencies. It supports every JSON value kind
through typed construction operations; it does not reflect arbitrary Sotlas
records or format floating-point values automatically.

```sotlas
let mut bytes:[u8;128]=0;
let mut writer:NativeJsonWriter=native_json_writer_open(unsafe{bytes as *mut u8},128);
let w:*mut NativeJsonWriter=unsafe{(&mut writer) as *mut NativeJsonWriter};
if native_json_writer_object(w)!=0
    || native_json_writer_key(w,native_text_open("answer",6))!=0
    || native_json_writer_u32(w,42)!=0
    || native_json_writer_end_object(w)!=0 { return 1; }
let json:NativeByteSlice=native_json_writer_view(w);
```

Writer names below omit `native_json_writer_`.

| Operation | Behavior |
| --- | --- |
| `open(data, capacity)` | Create an empty caller-backed control |
| `object(writer)` / `array(writer)` | Begin a container as the next value |
| `end_object(writer)` / `end_array(writer)` | Close the matching container |
| `key(writer, text)` | Escape a UTF-8 member name and require its value next |
| `string(writer, text)` | Escape a UTF-8 string value |
| `u32(writer, value)` | Format a checked decimal integer token |
| `number(writer, text)` | Append one validated number token, without leading/trailing whitespace |
| `value(writer, parsed_value)` | Copy any validated JSON value, including a whole container |
| `bool(writer, value)` / `null(writer)` | Append a literal value |
| `view(writer)` | Borrow a complete, validated document; invalid while incomplete |
| `reset(writer)` | Discard construction state without wiping backing bytes |
| `shape(writer)` | Check control metadata and backing disjointness |

Construction operations return 0 on success. Errors reuse JSON statuses 1
(metadata), 2 (number syntax), 3 (UTF-8), 4 (non-number token), 5 (depth),
6 (capacity) and 7 (alias). Status 8 means invalid construction order: for
example a key outside an object, a second key before its value, an unmatched
close or a second root value. Container nesting is limited to 64, matching the
reader. Capacities retain the UTF-8 buffer limit of 4294967295 bytes.

Every operation validates its full capacity requirement, including escaping,
commas, quotes and key colons, before touching backing bytes or construction
state. A rejected operation leaves both unchanged; it does not poison the writer.
Already successful operations are retained. This is operation-level atomicity,
not rollback of a caller's whole sequence. There is no hidden growth or
reservation of future closing delimiters: leave space to close containers.

Non-ASCII UTF-8 is preserved. Quotes and backslashes are escaped, and control
bytes use lowercase `\u00xx` escapes, including embedded NUL. Slash remains
unescaped. Number tokens retain their lexical precision and exponent spelling;
NaN, infinity, multiple values and non-number JSON are rejected. Keys are not
deduplicated. Output is compact and follows construction order; it is not a
canonicalization or signing format. No terminating NUL is written.

`value` bridges the reader and writer without a schema-specific field list. It
copies bytes into destination storage and retains no source reference. Number
spelling, escaped strings, duplicate names and internal whitespace are preserved.
Depth is checked for the **combined** writer and copied subtree before writing;
depth, metadata, overlap and capacity failures leave output and state unchanged.
Only the source value's token is copied, excluding surrounding root whitespace.

Hexadecimal escaping now uses [native byte division and remainder](native_narrow_division.md)
directly, widening only the computed nibble for indexing. Rebuild the native
compiler with that arithmetic delivery before compiling this writer version.

Keep the mutable control and backing separate, live and exclusive during use.
Input text must not overlap the writer control or any of its backing capacity.
Treat control fields as opaque and do not copy an active control as another
writer. Metadata checks do not prove pointer provenance or safe concurrent access.
`view` revalidates the complete document; the returned bytes are borrowed and
may be overwritten by reset/reuse or external mutation. General lifetime and
automatic ownership proofs remain outside this runtime contract.

## Executable configuration path

The [configuration example](../examples/native_config_map/README.md) reads a nested
JSON document, selects two integers, decodes a Unicode label, copies values into
the existing owned configuration map and then exercises updates and cleanup.
It then writes a nested document from the updated map, reparses it and checks
the numeric and Unicode values before deferred map cleanup. Both reader and
writer run through the same native compiler and original-source import path.
The closing example traverses every generated member, decodes/re-escapes keys,
copies each arbitrary value into a new document, reparses it and computes its
result from the copied configuration. It does not hardcode the traversal's
member names or silently truncate key buffers.
It exits with 42 and checks that its backing pool closes without live slots.
Its staged runtime includes `json.sotlas` and `json_writer.sotlas`; the existing native platform gate
checks imports, object emission, executable builds and ELF/PE/Mach-O linking.

`tests/test_sotlas_native_json.py` covers nested navigation, missing/null values,
top-level values, number syntax, original error offsets, duplicate/escaped names,
UTF-8 and surrogate handling, capacity/overlap atomicity, nesting boundaries,
wide arrays and forged descriptors. Python JSON is only a test oracle for decoded
string bytes; production parsing and decoding are entirely Sotlas.
Platform CI for this delivery is pending.

`tests/test_sotlas_native_json_writer.py` executes nested construction/readback,
Unicode/control-byte escaping, exact capacities, grammar-state rejection,
failure preservation, duplicate keys, reset/reuse, backing/control alias checks
and the 64-level boundary. All 11 writer tests and the imported configuration
read/write/read application passed locally using native Linux and Windows
compilers; ELF/PE/Mach-O emission also passed. Platform CI for the writer is pending.

Local evidence: all 12 JSON tests passed with rebuilt native Sotlas compilers
on Linux and Windows. The imported configuration application passed checking,
object emission, host execution and ELF/PE/Mach-O linking on both hosts with
host tools absent from its build environment. Related map/numeric regression
tests and 35 contract/documentation checks also passed. These are local results,
not platform CI certification.
