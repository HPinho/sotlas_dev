# Native terminal calculator

A complete terminal application written in Sotlas. The evaluator and result
formatter live in `runtime/native/calculator.sotlas`; a future graphical
application can call the same API. Windowing and GUI components are not part
of this example yet.

## Build and run

Obtain a native compiler seed or use the compiler produced by
`scripts/build_native.ps1` / `scripts/build_native.sh`. Building this example
uses that native compiler, its object writer and linker with host tools absent
from PATH. No Python, C compiler or external linker is invoked by these scripts.
Shell orchestration stages the original source files without editing them.

Windows, from the repository root:

```powershell
powershell -NoProfile -File examples/calculator/build.ps1 build/native/sotlas-native.exe build/calculator
./build/calculator/calculator.exe
```

Linux or Intel macOS:

```sh
bash examples/calculator/build.sh ./build/native/sotlas-native ./build/calculator
./build/calculator/calculator
```

Choose a fresh output directory for each build. Enter one expression per line;
results appear after Enter. End input with the terminal's EOF sequence (Ctrl+D
on Unix, Ctrl+Z followed by Enter on Windows). Redirected input also works:

```sh
printf '2+3*4\n(2+3)*4\n1/0\n40+2\n' | ./build/calculator/calculator
```

Expected output:

```text
14
20
error: division by zero at byte 1
42
```

Errors do not end the session. Exit codes are 0 for successful input (including
empty EOF), 2 if any expression failed, and 3 for an I/O or output failure.
The example intentionally emits no prompt so pipelines get only results.

## Expression contract

- Binary `+`, `-`, `*`, `/`; multiplication/division precede addition/subtraction.
- Operators at equal precedence associate left to right; parentheses override it.
- Unary signs, ASCII whitespace, integers and decimals including `.5` and `1.`.
- At most 1,024 bytes per expression, six fractional digits per literal and
  63 nested parentheses/unary signs (depth 64 is rejected).
- IEEE binary `f64` arithmetic; accepted literal values and each intermediate
  result must have magnitude at most 1,000,000,000,000.
- Display rounds to at most six fractional places and removes trailing zeroes;
  it suppresses a negative sign when the displayed result rounds to zero.

This is not exact financial decimal arithmetic. Display precision cannot exceed
`f64` precision at large magnitudes. Scientific notation, variables, functions,
implicit multiplication and locale decimal separators are outside this contract.
Input uses ASCII syntax; unsupported bytes, including embedded NUL, are rejected.
CRLF and LF line endings are accepted. Oversized lines are drained before the
next expression, preventing a partial expression from being evaluated.

## Reusable API

`calculator_evaluate(data, length)` returns a `CalculatorResult` containing
`value`, `error` and a zero-based byte `offset`. On error, `value` is zero.
The caller must provide readable, stable input storage; pointer shape checks
do not prove its lifetime or accessibility. A null pointer is rejected.

`calculator_format(value, destination, capacity)` returns the written byte
count, with no terminating NUL. It returns zero and leaves destination unchanged
on rejected values or insufficient capacity. Destination must be writable for
its capacity. The evaluator allocates no heap memory and retains no input.

| Error | Meaning |
|---|---|
| 1 | Invalid input shape or length |
| 2 | Expected number or opening parenthesis |
| 3 | Missing closing parenthesis |
| 4 | Division by zero; offset identifies the division operator |
| 5 | Magnitude exceeds the bound |
| 6 | Nesting limit reached |
| 7 | More than six fractional digits |
| 8 | Unexpected trailing input |

## Verification

Windows and Linux/WSL passed the native model regression and 12 CLI scenarios,
including repeated sessions, EOF, embedded NUL, malformed input, exact capacity,
overflow recovery and CRLF. `tests/native/calculator/model.sotlas` exercises
precedence, associativity, signed zero, precision, magnitude, nesting and
unchanged formatting output on failure. The process adapter is
`tests/native_calculator_gate.py`; all calculator logic is Sotlas.

Existing platform Stage 3 gates execute this example with their rebuilt native
compiler. Intel macOS execution and remote CI remain pending for this change.
Windows console API bindings and Unix syscall bindings are platform adapters;
the Windows executable uses KERNEL32 services without a C runtime.
