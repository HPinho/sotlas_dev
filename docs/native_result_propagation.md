# Native results and checked numeric operations

SV8.97 adds postfix `?` to the native structured-CFG profile. The operand is a
concrete, pointer-free POD record with fields named `status` and `value`. Status
must be `u32` or a scalar enum; zero means success. Other fields carry error
metadata and are preserved. The enclosing function returns the **same nominal
record type**, without an ownership qualifier.

```sotlas
struct SumResult { pub status:u32; pub value:u32; pub offset:usize; }
fn add_one(input:SumResult)->SumResult {
    let n:u32=input?;
    return SumResult{status:0,value:n+1,offset:0};
}
```

The operand is evaluated once and snapshotted. On success, `?` extracts the
value. On failure, the complete record is copied to the return destination
before active lexical defers execute in reverse order. Later operands, arguments
and initializers do not run after that return. Lazy Boolean operators retain
their short-circuit behavior. Cleanup on this path is an ordinary structured
return; there is no exception ABI or general unwind mechanism.

Success values may be scalars, POD records, payload enums or bounded arrays under
the existing internal value ABI. Fields, calls, stored values and indexed records
can supply an operand. Conditional/match results must be stored before applying
`?`. It cannot appear inside a defer. Borrowed/owned result bindings, resource-
bearing records and mismatched nominal return types are rejected, including in
dead source branches. Owned arguments consumed by a result-producing call still
participate in move checking.

Plain temporary arrays from calls or `?` can be indexed directly, including
record elements. The base and index are evaluated once in order and use the
existing checked array address operation. This does not extend the lifetime of
owned array temporaries. Existing array size and aggregate-layout limits apply.

The machine backend does not gain general `Result<T,E>` monomorphization,
automatic error conversion or foreign aggregate ABI support. The reference C11
route retains its existing generic Result checks separately.

## Numeric library

`runtime/native/results.sotlas` provides `NativeU32Result` and
`NativeNumericError { kind:u32, offset:usize }` with these APIs:

| API | Contract |
| --- | --- |
| `native_u32_add/sub/mul` | Checked arithmetic; no wrapping success |
| `native_u32_div/rem` | Zero divisor returns an error before division |
| `native_u32_narrow` | Reject values above the u32 maximum |
| `native_parse_u32` | Strict ASCII decimal; explicit range, no implicit NUL |
| `native_parse_u32_bounded` | Parse and check an inclusive maximum |
| `native_parse_u32_sum` | Parse two ranges and add with overflow checking |
| `native_format_u32` | Return digit count; no terminator; failure writes nothing |
| `native_u32_ok/error` | Construct results; error kind zero becomes kind 7 |

Error kinds are 1 null input, 2 empty input, 3 invalid digit, 4 overflow,
5 underflow, 6 division by zero and 7 out of range. Parse errors report the
offending byte. Decimal signs, whitespace, separators and NUL bytes are rejected.
Formatting stages digits before checking capacity and publishing output.

Nonempty byte ranges must point to readable/writable caller-owned storage as
appropriate. Null and address-overflow checks cannot establish pointer provenance
or validate an arbitrary address. The library allocates no memory and uses no C
glue. Resource-scope integration is tested through explicit managed-runtime APIs
and defer; this does not add automatic ARC or resource-bearing result payloads.

[The executable pipeline](../examples/native_numeric_pipeline/README.md) uses
native imports and validates successful, invalid and overflowing calculations.
Tests cover result snapshots, scalar widths, nested aggregates, lazy expressions,
loop/match exits, ownership rejection and managed-scope cleanup on both paths.
