# Native program capacity

SV8.64 expands the bounded Sotlas-written compiler to 1,024 function
declarations and 2,048 string literal symbols per compilation. The unified
object writer allocates function symbols, offsets and sizes at the same bound.
Foreign declarations count toward the function limit. String occurrences are
not deduplicated.

The decoded string pool remains 65,536 bytes, including every terminating NUL.
Limits are independent: a program can exhaust the byte pool before the symbol
table. Accepted addresses retain their data relocations; neither strings nor
function tables are truncated.

## Evidence

The native fixture runners generate and verify these cases using the rebuilt
compiler, with Python, C compilers and external linkers absent from PATH:

| Input | Required result |
|---|---|
| Imported project with 1,024 functions, calling every helper | Execute and return 42 |
| Same project with one additional declaration | Reject with exit 8 |
| 2,048 distinct literals, reading a byte from every literal | Execute and return 42 |
| One additional literal | Reject with exit 7 |
| 65,535 decoded literal bytes plus NUL | Execute and return 42 |
| One additional decoded byte | Reject with exit 7 |

Both checking and compilation must reject overflow. Rejected compilation must
preserve the previous executable byte for byte. The object-level regression
also checks all 2,048 string symbols and their relocations.

Windows and Linux/WSL passed all six cases locally. Both compilers rebuilt
their original Sotlas modules with identical Stage 2/3 images. The existing
Windows, Linux and Intel macOS Stage 3 CI gates run these fixtures using their
already-built compiler. Intel macOS execution and remote CI have not been
validated locally for this change.

Run on Windows:

```powershell
powershell -NoProfile -File tests/native/large_modules/verify.ps1 build/native/sotlas-native.exe build/large-cases
```

Run on Linux or Intel macOS:

```sh
bash tests/native/large_modules/verify.sh ./build/native/sotlas-native ./build/large-cases
```

## Remaining limits

This closes a capacity barrier encountered while extending the compiler. It
does not add general generics, payload enums, automatic ARC or typed separate
compilation. Project imports still resolve to an internally combined source.
Other independent bounds remain, including source smaller than 2 MiB, 128
local bindings, 24 parameters per function and 2,048 blocks per function.
Use the native driver's `--limits` command for its reported capacities.

The changed compiler implementation is Sotlas. Shell scripts generate test
inputs and inspect process results; Python remains an optional test harness
and part of the initial hosted bootstrap, not the native self-build path.

## SV8.65 regression closure and full-limit Linux integration

The CI regressions from #1243 through #1248 were traced to a stale Python
*test expectation*, not to a compiler rejection failure: the Linux
`test_native_string_symbols_beyond_256_execute_and_overflow_preserves_output`
fixture previously expected exit 7 after adding a 513th live string, even
though SV8.64 explicitly permits **2,048** distinct occurrences.

The strengthened integration suite now checks and runs **512**, **513** and
**2,048** live literals using the compiled Sotlas-native Linux seed with
host tools excluded from PATH; verifies the compiler's `--limits` report;
rejects **2,049** literals with exit 7 in both `--check` and build mode;
and separately exercises the decoded **65,535 + NUL** byte boundary and its
65,536-byte one-over input. Rejected checks and builds must preserve the
previous executable exactly. The original Windows/Unix six-case capacity
scripts remain active and unchanged.

This is a corrected test contract, not an increase in native capacity or a
claim of complete frontend parity. The last fully green reference is
`2e93a8d` / CI #1242; later Linux jobs share the legacy 513th-literal
test failure. A new commit still requires its own complete Linux/Windows/
Intel macOS matrix, bootstrap chain, and native self-host fixed-point gates.
