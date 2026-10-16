# Native UTF-8 text and Windows UI labels

The Sotlas-written runtime now validates UTF-8 scalar sequences and converts
them to caller-backed UTF-16. UI labels use the same validator and the Windows
renderer passes the converted code-unit count to the drawing API.

## API contract

Implementation: `runtime/native/unicode.sotlas`.

| API | Result |
|---|---|
| `native_utf8_scalar(data, length, offset)` | One scalar, next byte offset and validity |
| `native_utf8_measure_utf16(data, length)` | Validity and required UTF-16 unit count |
| `native_utf8_to_utf16(data, length, destination, capacity)` | Validity, written unit count and invalid-sequence byte offset |

The decoder accepts shortest-form encodings of Unicode scalar values. It
rejects lone continuation bytes, invalid/truncated continuations, overlong
encodings, surrogate values and code points above U+10FFFF. Supplementary
scalars produce two UTF-16 units. These encoding rules follow
[Unicode section 3.9](https://www.unicode.org/versions/Unicode16.0.0/core-spec/chapter-3/).

Input lengths and error offsets are bytes; capacity/output lengths are `u16`
code units. A failed scalar decode leaves `next` at its supplied offset. Text
validation reports the start of the first malformed sequence. Storage/capacity
failures report offset zero. Failed results have zero output units.

Null input with zero length is valid empty text. Conversion of empty text
requires no destination. Nonempty conversion requires a writable destination,
sufficient capacity, checked address ranges and nonoverlapping input/output.
The entire input and required capacity are validated before writing output.
Stable input is a caller precondition for both conversion passes. No heap
allocation, NUL terminator, normalization or replacement of malformed input
is performed. Encoded NUL is valid in the general encoding utility.

Pointer shape checks do not prove memory accessibility or lifetimes. The
caller must keep readable input and writable output live for the call; other
threads must not mutate input concurrently. Partial overlapping conversions
are rejected. On failure within these preconditions, output remains unchanged.

## UI integration

`ui_label_valid` checks at most 128 UTF-8 bytes and rejects NUL, C0 and C1
controls, including DEL. A label limit is measured in bytes; a scalar split by
that limit is rejected. Other valid scalars are accepted as encoded text;
their glyph availability depends on the Windows font environment.

The renderer revalidates borrowed labels and converts into its 128-unit local
buffer before drawing. A 128-byte UTF-8 label cannot require more than 128
UTF-16 units. Existing clipping and paint cleanup apply to failed conversions.
The calculator displays `×`, `÷` and `←` while preserving its ASCII operation
IDs and arithmetic grammar. Calculator input/editing remains ASCII.

## Evidence and remaining scope

The native fixture `tests/native/ui/unicode.sotlas` covers scalar boundaries,
BMP/supplementary conversion, combining sequences, invalid forms, truncation,
error offsets, embedded NUL, exact/short capacity, overlap in both directions
and unchanged output on failure. It also checks the 128-byte UI label boundary.
These gates passed on Windows and Linux/WSL.

The Windows renderer gate also draws a mixed-script label and retains the
invalid-label cleanup regression. The graphical calculator build script stages
the new module; existing platform Stage 3 gates run these tests through
`tests/native_ui_gate.py`. Remote CI and Intel macOS execution remain pending.

This does not certify font coverage, complex-script shaping, bidirectional
layout, normalization, grapheme-aware cursor/editing or IME. The native
frontend's general first-class string/slice and ownership work remains open.
