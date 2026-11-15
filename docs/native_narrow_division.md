# Native byte and word division

The Sotlas-written frontend, Target IR and x86-64 object backend now execute
unsigned `u8` and `u16` division and remainder without first widening operands.

```sotlas
let byte:u8=255;
let high:usize=(byte/16) as usize;
let low:u8=byte%16;
```

Both operands retain their declared type. A fitting literal takes that type;
mixed widths, signed/unsigned mixtures, boolean operands and out-of-range
literals remain rejected. A cast of a result happens after the narrow
operation. It does not change the type of the arithmetic inside parentheses.

For nonzero divisors the quotient is truncated toward zero, and the remainder
is smaller than the divisor. Unsigned operands are zero-extended for the
32-bit x86 `div` sequence; typed SSA slots retain normalized byte/word values.
No new IR opcode, C intermediate or foreign arithmetic helper is used.

The same operations work in returns, calls, nested arithmetic, conditional
values and `/=` or `%=` on supported writable locals, fields, array elements
and raw dereferences. Compound places retain single evaluation of the address
before the right operand. Readonly writes remain rejected; raw access still
requires `unsafe`.

Earlier narrow arithmetic keeps its existing width semantics. For example,
with `b:u8=255`, `(b+1)/2` first wraps the addition to zero and then divides.
An outer widening cast does not restore overflow bits. Signed arithmetic,
shift guards and numeric conversion behavior are unchanged.

## Failure behavior and scope

Runtime division or remainder by zero raises the existing machine arithmetic
fault, as for wider integers: `SIGFPE` on Unix hosts and integer-divide-by-zero
status on Windows. No recoverable result or panic unwinding is introduced.
Constant-evaluation contexts retain their rejection of invalid arithmetic.

This closes the missing unsigned byte/word division pair in the declared native
scalar profile. It does not complete generic numeric inference, arbitrary
integer widths, foreign ABI parity or the whole frontend roadmap.

## Executable evidence

`tests/test_sotlas_native_narrow_division.py` compares all 65,280 nonzero-divisor
`u8` operand pairs against widened arithmetic and the quotient/remainder identity.
It also checks `u16` boundaries, high-bit values, computed casts, wrap-before-divide,
compound places, single evaluation, rejected type combinations and child-process
zero-divisor faults for both operations and widths.
Module constants retain their declared widths and reject constant division
or remainder by zero.

The JSON writer uses narrow division directly to form hexadecimal escapes.
Its configuration application exercises original-source imports and native
ELF/PE/Mach-O emission. The kernel foundation executes byte/word quotient,
remainder, casts and indexed compound updates before its existing boot/resource
workload. Its QEMU gate retains 32, 64 and 128 MiB memory configurations.

Native compiler reconstruction and platform CI remain required release gates.
Platform CI for this delivery is pending.

Local verification passed the focused numeric/CFG/runtime regression, 54
self-hosting module checks and 35 contract/documentation checks. All seven
narrow-division tests and 11 JSON writer tests passed with rebuilt native
compilers on Linux and Windows. Both targets produced byte-identical Stage 2/3
compilers; both hosts emitted an identical kernel image, which passed QEMU with
32, 64 and 128 MiB RAM. These results do not certify pending platform CI.
