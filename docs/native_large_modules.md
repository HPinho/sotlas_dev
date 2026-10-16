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
