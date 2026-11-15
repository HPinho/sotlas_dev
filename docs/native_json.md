# Native JSON reader

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
member count, allocator, serializer, schema validator or implicit file/network I/O.

## Executable configuration path

The [configuration example](../examples/native_config_map/README.md) reads a nested
JSON document, selects two integers, decodes a Unicode label, copies values into
the existing owned configuration map and then exercises updates and cleanup.
It exits with 42 and checks that its backing pool closes without live slots.
Its staged runtime now includes `json.sotlas`; the existing native platform gate
checks imports, object emission, executable builds and ELF/PE/Mach-O linking.

`tests/test_sotlas_native_json.py` covers nested navigation, missing/null values,
top-level values, number syntax, original error offsets, duplicate/escaped names,
UTF-8 and surrogate handling, capacity/overlap atomicity, nesting boundaries,
wide arrays and forged descriptors. Python JSON is only a test oracle for decoded
string bytes; production parsing and decoding are entirely Sotlas.
Platform CI for this delivery is pending.

Local evidence: all 12 JSON tests passed with rebuilt native Sotlas compilers
on Linux and Windows. The imported configuration application passed checking,
object emission, host execution and ELF/PE/Mach-O linking on both hosts with
host tools absent from its build environment. Related map/numeric regression
tests and 35 contract/documentation checks also passed. These are local results,
not platform CI certification.
