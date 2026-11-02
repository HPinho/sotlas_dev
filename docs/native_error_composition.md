# Native Result error composition

Concrete POD `Ok(T)`/`Err(E)` enums can propagate errors into a different
result enum when both declare exactly the same error payload type:

```sotlas
struct Error { pub code: u32; }
enum Number { Ok(u32), Err(Error) }
enum Accepted { Err(Error)=97, Ok(bool)=11 }

fn accept(input: Number) -> Accepted {
    let value: u32 = input?;
    return Accepted::Ok(value == 42);
}
```

The source is evaluated once and snapshotted. Success yields the source's
success payload, even when the enclosing function has another success type.
Failure copies the error payload to the destination's Err layout and writes
the destination's declared Err tag. Variant order, discriminants and payload
offsets need not match. The payload and tag are stored before lexical defers
execute in LIFO order. Later arguments and operations do not execute.

## Acceptance and rejection

Both enums must have exactly Ok and Err, each with one unqualified typed
payload. All payload graphs must satisfy the native POD contract. Error
payloads may be equal scalar types or the same nominal pointer-free record or
enum. An error record can contain supported arrays and nested POD enums.
Direct array error payloads remain supported for same-result propagation;
cross-result propagation rejects them until it has a standalone array-copy ABI.

Different scalar widths, signedness or nominal error declarations are rejected,
even if their layouts happen to match. There is no error constructor invocation,
coercion, trait-based conversion or generic Result instantiation. Resource and
pointer payloads, qualified result bindings, extra variants and propagation
inside defer remain rejected. Fabricated invalid source tags remain outside
the native contract.

Conversion is specific to postfix `?`. Ordinary bindings and copies of these
aggregate results require the same nominal type. This delivery also closes a local-copy hole:
identifier and field initializers now check their actual aggregate identity,
instead of accepting a different record/enum with a compatible layout.

`Some`/`None` and status/value records retain their same-result propagation
contract. This change does not convert between those schemas and Ok/Err. The
optional legacy C11 emitter is outside the native composition contract.

## Checked numeric parsing library

`runtime/native/parse.sotlas` composes the existing checked numeric and text
APIs using concrete enums with `NativeNumericError` as their shared error type.

| API/type | Contract |
| --- | --- |
| `NativeParsedU32` | Ok(u32) or Err(NativeNumericError) |
| `NativeU32Pair` | Two parsed u32 fields |
| `NativeParsedPair` | Ok(NativeU32Pair) or the same nominal error |
| `native_u32_tagged` | Explicit adapter from the existing checked numeric record; preserves error metadata |
| `native_parse_u32_range` | Strict decimal parsing of a checked byte range; error offsets refer to the original source |
| `native_parse_u32_pair` | Split once at a nonempty byte delimiter, then parse both fields |
| `native_parse_u32_pair_sum` | Propagate pair errors and perform checked addition |

There is no trimming or implicit acceptance of signs, extra delimiters or
nondecimal bytes. Empty numeric fields use error kind 2; invalid digits use 3;
parse/arithmetic overflow uses 4. Invalid source/delimiter shape, an empty
delimiter or an invalid range uses 7. A missing delimiter reports kind 7 at the
source length. Right-field parse errors include the right field's starting
offset. Checked arithmetic errors retain their existing offset zero convention.

The implementation reuses `native_parse_u32`, checked optional lookup,
`native_text_sub` and `native_u32_add`; it adds no parallel numeric or search
algorithm. Returned values contain no borrowed pointers and need no allocator.
Input storage remains caller-owned and must be readable throughout the call;
shape and address-range checks do not establish pointer provenance or lifetimes.

## Example and gates

The [report example](../examples/native_error_composition/main.sotlas) connects
scalar parsing, a record success value, checked arithmetic and an array report
with a different explicit Err tag. It validates success, original byte offsets,
overflow and one deferred cleanup per report before exiting 42.

`tests/test_sotlas_native_error_composition.py` covers scalar widths, layouts,
tags, chained conversions, aggregate successes, nested errors, snapshots,
evaluation order, cleanup and invalid conversions. Platform rebuilt-driver
gates include imported check/build, host execution and ELF/PE/Mach-O output.
Full CI certification for this candidate remains pending.

### Local validation

The final sources passed 23 focused composition/library tests, 153 CFG and
aggregate-copy tests, and 21 inventory/phase checks. The generated phase matrix
remained consistent. A separate native run passed 179 tests on each of Linux
and Windows, including prior result/optional propagation, pattern control,
text splitting, array iteration and match ownership cases.

The imported report passed check, object generation, direct build and execution
with exit 42 on both hosts, with host tools absent from PATH. The two producers
emitted byte-identical object, ELF, PE and Mach-O files. Mach-O execution still
requires the macOS platform gate.

Original-source native rebuilds completed without host tools on PATH and
retained strict Stage 2/3 byte equality on each host. Native focused tests used
Stage 2; the final Stage 3 images are identical. Compiler SHA-256 values:

- Windows: `76cfec199b6f2116a00a7ed0c1c103e15b2238ce67c5f554ea9480e8ae2862c4`
- Linux: `1299654a1ddd681e50500e4a9241be1faeeec78066654767ba71cff9b2de7fb8`

This validates the declared concrete profile, not generic frontend parity,
automatic resource cleanup or independent native packaging.
