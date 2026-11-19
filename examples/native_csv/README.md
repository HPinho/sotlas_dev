# Native CSV inventory round trip

## Normalize a CSV file

The installed SDK verifier builds a second executable, `csv-normalize`, from
`normalize.sotlas`. It reads CSV from standard input and writes canonical CSV
to standard output. Run it from the fresh directory produced by SDK verification.
On Linux and Intel macOS:

```bash
./csv-normalize < input.csv > normalized.csv
```

On Windows, run this in Command Prompt:

```cmd
csv-normalize.exe < input.csv > normalized.csv
```

The command accepts up to 4,096 input bytes. It keeps field bytes and record
boundaries, writes CRLF between records and quotes fields as needed. Embedded
line breaks inside quoted fields are preserved. The command buffers the result
until it has validated the whole document. Invalid CSV or input beyond the
limit produces no bytes on standard output. Use a distinct output path because
shell redirection opens the destination before the program runs.

| Exit code | Meaning |
| --- | --- |
| 0 | Complete conversion, including empty input |
| 2 | Malformed CSV |
| 3 | Standard input or output error |
| 4 | Input exceeds 4,096 bytes |
| 5 | Internal CSV buffer or metadata error |

## Build the inventory example

This original Sotlas application reads two inventory records, including a
quoted name containing a comma and a quoted count. It validates the two-column
header, decodes names/counts into caller storage, parses strict unsigned
integers and checks the total is 42. It then serializes canonical CSV and reads
the output again to verify all records and boundaries.

Success exits with code 0 and produces no console output. Nonzero codes identify
a failed parsing, capacity, numeric or round-trip check. It uses the native
compiler and runtime directly, without Python, a C compiler or a foreign CSV
library after receiving the seed.

The installed SDK verifier builds and runs this example automatically. For a
manual build, stage the original sources under a fresh source root. Linux:

```bash
mkdir -p build/csv-src/sotlas/runtime
cp runtime/native/text.sotlas runtime/native/csv.sotlas runtime/native/csv_writer.sotlas build/csv-src/sotlas/runtime/
cp examples/native_csv/main.sotlas build/csv-src/main.sotlas
/path/to/sotlas-native --check-build build/csv-src build/csv-src/main.sotlas
/path/to/sotlas-native --build build/csv-inventory build/csv-src build/csv-src/main.sotlas
./build/csv-inventory
```

Use `--build-win build/csv-inventory.exe` on Windows or
`--build-mac build/csv-inventory` on Intel macOS, keeping the source-root and
entry arguments. Quote paths containing spaces. The SDK includes these runtime
modules and original example sources.

See the [CSV API contract](../../docs/native_csv.md) for statuses, quoting,
record boundaries, byte-oriented encoding and storage obligations. This example
uses in-memory data; file I/O and application schemas remain explicit choices.
