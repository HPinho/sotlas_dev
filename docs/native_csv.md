# Native CSV reading and writing

The native SDK provides allocation-free CSV operations in
`runtime/native/csv.sotlas` and `runtime/native/csv_writer.sotlas`. They use
`NativeByteSlice` from the native text module. The original Sotlas
[inventory example](../examples/native_csv/README.md) validates a header, reads
counts, writes canonical rows and reads its output again.

## Reading

Create a `NativeCsvReader` with `native_csv_open(input)`, then pass its address
to `native_csv_next`. Each successful result contains:

| Field | Meaning |
| --- | --- |
| `status` | 0 for a field, 1 for invalid metadata, 2 for EOF, 3 for malformed CSV |
| `raw` | Borrowed encoded contents, excluding enclosing quotes and separators |
| `length` | Decoded byte count, after collapsing doubled quotes |
| `quoted` | Whether the field used enclosing quotes |
| `row_end` | Last field in the record, including an unterminated final line |
| `row`, `column` | Zero-based record and field indices |
| `offset` | Field start on success, offending byte on syntax error |

Commas delimit fields; LF and CRLF delimit records outside quotes. A bare CR
outside a quoted field is an error. Quoted fields may contain commas, CR/LF
and doubled quotes. After a closing quote, only a separator or EOF is valid.
Quotes inside unquoted fields are errors. Spaces are data and are not trimmed.
The error offset for an unclosed quote is the input length.

An empty input contains zero records. A blank line contains one empty field.
A final comma produces a final empty field; a final line ending does not
produce an extra record. Records may contain different field counts: the
application decides whether that is valid for its schema.

`native_csv_next` advances only after a successful field. EOF and errors leave
the reader unchanged, so repeating a failed call reports the same result.
Earlier successful fields remain consumed when a later field fails. This is a
field iterator over a complete in-memory input, not an incremental file/socket
decoder or a whole-document transaction.

## Decoding fields

`native_csv_decode(field, output, capacity)` copies decoded bytes into separate
caller storage and returns `NativeCsvDecoded { status, length }`. It writes no
NUL terminator. Status 0 means success, 1 invalid metadata, 3 invalid encoded
field contents, 6 insufficient capacity, and 7 overlapping input/output.

The entire field and output range are validated before the first write. A
rejected decode leaves every destination byte unchanged. Empty fields can be
decoded into a null pointer with zero capacity. Output capacity, rather than
only the written prefix, must be disjoint from the raw input field.

The raw slice contains doubled quotes, so use the decoder before interpreting
a quoted field as a number or displaying its contents. Failed/EOF field
results cannot be decoded. Externally constructed results must have valid raw
syntax and a matching decoded length.

## Writing

Create `NativeCsvWriter` with `native_csv_writer_open(data, capacity)`. Append
each field with `native_csv_writer_field(writer, value)` and finish the record
with `native_csv_writer_end_row(writer)`. The writer inserts commas and emits
CRLF record endings. Empty fields are quoted. Fields containing commas,
quotes, CR or LF are quoted, and embedded quotes are doubled. Other fields
are copied unchanged.

| Status | Meaning |
| --- | --- |
| 0 | Success |
| 1 | Invalid writer or source metadata |
| 6 | Insufficient output capacity |
| 7 | Source overlaps writer storage or its control descriptor |
| 8 | Invalid operation state, including ending a row with no fields |

Each field append and each CRLF append is atomic with respect to rejection:
insufficient capacity or invalid metadata leaves bytes and writer state
unchanged. Previously appended fields are retained. This does not make an
entire record or document atomic. `native_csv_writer_view` exposes only output
ending at a complete record boundary; a partially written record returns an
invalid view. The initial zero-record output is valid.

## Storage and format boundaries

Input, output and control descriptors remain caller-owned. Keep all allocations
live, respect their capacities, and provide exclusive access to writable state.
Do not modify input during iteration, forge cursor state or use multiple active
writer copies for the same output. Range/alignment/overlap checks cannot prove
pointer provenance, allocation size, lifetime or concurrent access safety.
The reader rejects overlap between its input and control descriptor; the
writer rejects overlap between output and its descriptor.

Operations preserve bytes, including UTF-8, NUL and non-UTF-8 data. They do not
validate or normalize text encodings, infer column types, trim whitespace,
strip a BOM, choose dialects or open files. Applications can combine them with
the existing Unicode, text, numeric parsing and platform I/O APIs. There is no
hidden allocation, Python parser, C glue, external library or automatic
ownership/lifetime inference in this runtime path.

## Executable gates

Six original Sotlas programs cover reader values, syntax/range/metadata
rejections, writer values and rejections, and a writer/reader/decoder round
trip for every byte value. Tests include multiline and empty fields, exact
capacity, descriptor aliases, output preservation and a failure after an
already-consumed field. They run through the native contract manifest. The
installed SDK verifier separately compiles and executes the inventory example
with host build tools absent from its native subprocess PATH.

Local fresh-prefix SDK verification passed all 64 contracts and the inventory
example on Windows and Linux/WSL. The installed VSIX also passed its native
project creation, compilation, execution and diagnostic scenario with the new
Windows SDK. The three-host matrix subsequently passed
[CI #1400](https://github.com/HPinho/sotlas_dev/actions/runs/44545711063).

The SDK also includes a [terminal normalizer](../examples/native_csv/README.md#normalize-a-csv-file)
that reads a bounded document from standard input and emits canonical CSV after
the entire input passes validation.
