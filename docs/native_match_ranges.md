# Native integer match ranges

The Sotlas-written frontend and owned x86-64 backend accept closed integer
intervals (`first..=last`) and intervals excluding their upper bound
(`first..last`) in match statements. This is a native-profile feature; it does
not assert C11/LLVM reference-backend equivalence.

```sotlas
fn byte_class(value: u8) -> u32 {
    match value {
        48..=57 => return 1;
        65..91 => return 2;
        _ => return 0;
    }
}
```

## Contract

- Selectors use the already-supported fixed-width native integer types.
- Bounds must evaluate to integer constants of the selector's type. Integer
  literals, matching module constants and parenthesized constant expressions
  work. Runtime calls and enum-valued bounds are rejected.
- Every interval is nonempty and ordered in the selector's signedness.
- Earlier unguarded explicit patterns must not overlap later explicit cases.
  Earlier guarded patterns may overlap later cases because a false guard tries
  the next arm. See [native guards](native_match_guards.md).
- A final unguarded wildcard covers the remaining values. Without it, unguarded
  intervals and scalar cases must cover the integer domain without gaps. Guards
  do not contribute to coverage. Source order does not affect this proof.
- Inclusive maximum bounds are valid, including `u64::MAX` expressed as a
  literal. The proof never computes MAX + 1 or enumerates every integer.
- A selector is evaluated once. Only the selected body executes. Existing
  lexical scopes, returns, loop jumps, defer cleanup and supported POD ownership
  checks apply unchanged to the bodies.
- The existing limit of 64 match arms remains in place.

Ranges on Boolean and enum selectors are rejected. Their existing scalar
patterns and finite coverage checks still work. Payload patterns, pattern
bindings, open-ended ranges and match expressions remain outside this feature.
Guards are covered by their separate native contract linked above.

## Representation and execution

`PatternRange` in the native AST retains both expressions, the inclusive flag
and the source location of the range operator. Lowering folds typed bounds,
checks overlap and coverage using ordered integer keys, then emits ordinary
typed comparisons and Boolean conjunction. Existing CFG and machine emitters
execute the result. No range is expanded into a list of individual cases.

The three platform drivers report located diagnostics for invalid bounds,
empty/reversed intervals, overlap and incomplete coverage.

## Reproduce the focused checks

Use an updated native compiler, after rebuilding with the documented seed
workflow:

```powershell
.\tests\native\match_ranges\verify.ps1 .\build\native-check\sotlas-native.exe .\build\match-range-checks
```

```bash
bash tests/native/match_ranges/verify.sh ./build/native-check/sotlas-native ./build/match-range-checks
```

The fixtures are Sotlas programs. The scripts only invoke the native compiler,
assert execution/rejection results and check artifact preservation. Each
compiler/application invocation runs with host build tools absent from PATH.
The existing Windows, Linux and Intel macOS Stage 3 gates invoke these checks
using the compiler they have just rebuilt, avoiding an extra bootstrap.

Local evidence: all 13 cases passed on Windows x64 and Linux x86-64 through
WSL. Both changed compilers rebuilt with Stage 2/3 byte identity. The byte
classifier returned 42 on both. Intel macOS execution and the remote CI were
not run locally; the complete Python test suite was not rerun for this cut.

`examples/native_byte_classifier.sotlas` combines exhaustive byte classification
with arrays, function calls and a native for loop. Compile it as a single source
file with the native driver; success returns 42.
