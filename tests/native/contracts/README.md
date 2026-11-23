# Sotlas-native contract tests

Assertions, fixture data, loops and expected values in this suite are checked-in
`.sotlas` programs. They are compiled by the Sotlas-written native compiler and
executed with host tools absent from PATH. No Python test generator, Python
interpreter, C source generation, host compiler or external linker runs in this
test path after a native seed is obtained.

The shell scripts only stage sources, invoke the compiler/programs, compare
process statuses and publish reports. They do not implement JSON parsing,
numeric arithmetic or the assertions under test.

## Run locally

Linux x86-64 or Intel macOS:

```bash
bash scripts/test_native.sh /path/to/sotlas-native build/native-contract-results
```

Windows, with Windows PowerShell or PowerShell 7:

```powershell
./scripts/test_native.ps1 C:/path/to/sotlas-native.exe build/native-contract-results
```

Use a compiler rebuilt with native byte/word division. Output must be a fresh
directory; existing results are preserved. An optional third argument selects
another manifest using the same format. No recursive deletion is performed.

## Test protocol

`manifest.txt` names each case once and explicitly assigns its mode:

| Mode | Required result |
| --- | --- |
| `pass` | Native project check and build succeed; program exits zero |
| `reject` | Check and build return semantic/backend rejection (6 or 7); an existing output remains unchanged |
| `syntax` | Check and build return syntax rejection (5) and preserve an existing output |
| `fault` | Check and build succeed; the child process raises integer divide by zero |

Failed positive cases return their nonzero check number. Rejections cannot pass
because of a missing file or arbitrary launcher error. Faults run in child
processes with core dumps/crash dialogs suppressed. A wrong fault/status is a
failure. Empty suites, duplicate names, malformed rows and missing sources fail
the gate rather than silently skipping tests.

The current suite contains 56 cases. Three UI snapshot contracts cover copied scene
storage, validation/alias/capacity failure without partial publication, and
invalid-view rejection during input dispatch. They extend the initial 50-case
migration described below. The additional `ui_caret` contract covers Unicode
scalar boundaries, invalid positions and preserved snapshot carets. All checks
execute as original Sotlas programs. Grid contracts additionally validate
coverage, balanced tracks, gaps, geometry limits and rejected layouts.

The initial suite contains 50 cases: 36 positive programs, ten compiler
rejections and four arithmetic-fault cases. JSON parsing, construction,
traversal/re-emission and unsigned byte/word division are covered. The exhaustive
byte-division loop itself runs in Sotlas, including all 65,280 nonzero-divisor
operand pairs. [Migration mapping](MIGRATION.md) records the replaced tests.

## GitHub Actions

The `Sotlas tests` matrix runs on Linux, Windows and Intel macOS, with no Python
setup or invocation in that job. It consumes native compiler artifacts from the
bootstrap job. Bootstrap production still uses the existing Stage-0 producer;
this migration does not claim the entire repository or seed production has
become Python-independent.

Native seed production now starts alongside reference jobs, so the Sotlas test
matrix does not wait for the long Python matrix. Reference checks remain active
and still contribute to the overall workflow result; no failing gate was waived.

Each platform publishes a job summary, source-linked failure annotations, a
JUnit XML file and per-case logs. GitHub displays the named Sotlas jobs and their
summary; JUnit is an exported report, not a claim of built-in GitHub JUnit rendering.
The report artifact is named `sotlas-tests-linux`, `sotlas-tests-windows` or
`sotlas-tests-macos`.

This is separate from language statistics. GitHub's
[Linguist catalog](https://github.com/github-linguist/linguist/blob/main/lib/linguist/languages.yml)
does not currently register Sotlas. The repository's Rust highlighting fallback
does not make the files Rust code or register a new language. This change neither
hides Python files from statistics nor relabels them as Sotlas.

## Add a case

Write an original Sotlas source in `cases/`, with `pub fn main_entry()->u32`.
Use zero for success and nonzero values for failed checks, then add one manifest
row. Keep IDs lowercase ASCII letters/digits/underscores and use the matching
`cases/ID.sotlas` path. Native test additions should follow this source-first
path instead of adding another Python-generated program.

Local migration validation passed all 50 cases on native Linux and Windows
compilers. Deliberately failing programs also produced a failing gate and JUnit
failure on both hosts. Intel macOS and the new Actions wiring await CI.

The tensor delivery expanded the suite to 58 cases. Two Sotlas programs cover CPU tensor row
reductions/broadcasting, including numerical edge cases, empty dimensions,
range/shape/alias rejection and output preservation. Fresh installed SDK
verification passed all 58 cases on Windows and Linux for that delivery;
the complete three-host matrix subsequently passed CI #1399. See the
[tensor contract](../../../docs/native_tensor_ops.md) for the exact API scope.

Six [CSV contracts](../../../docs/native_csv.md)
cover reading, quote decoding, writing, metadata/range/alias rejections and
all-byte round trips.

Three
[pattern guard contracts](../../../docs/native_pattern_control.md#guards) check
success and fallback paths, loop cleanup, Boolean typing and ownership.

Three cases cover `while let ... else` completion. They check exhaustion,
guard failure, defer order, early exits,
outer loop jumps and rejection of out-of-scope bindings and jumps.
Three additional cases cover ordinary
`while ... else`, including condition evaluation, cleanup, early exit and
rejection of non-Boolean conditions and jumps without a target.
Three cases cover `for ... else`. They
exercise range and array exhaustion, the inclusive integer limit, cleanup
and explicit breaks, and reject invalid range types and escaped bindings.
The suite now has 79 contracts. Three cases exercise indexed array iteration
and reject writes to the index or two bindings on numeric ranges.
