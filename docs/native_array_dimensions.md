# Native constant array dimensions

The Sotlas-written compiler evaluates bounded unsigned literal arithmetic in
fixed-array types and repetition counts. These values determine storage before
machine-code emission; they do not allocate variable-length arrays at runtime.

```sotlas
fn make() -> [u32; 2 * 3] {
    return [7; 12 / 2];
}
```

## Contract

- Operators: `+`, `-`, `*`, `/`, `%`, with ordinary precedence, left
  associativity and parentheses. Decimal, hexadecimal, octal, binary and the
  existing numeric separators use the native checked literal decoder.
- Every intermediate is an unsigned 64-bit value. Overflow, underflow and
  division/remainder by zero fail compilation. Runtime unsigned wrapping does
  not apply to dimensions. Final zero lengths remain unsupported.
- The type and repetition forms use the same checked arithmetic operations.
  Repetition still evaluates its element expression once and copies that value;
  it does not execute the element once per slot.
- Available in supported scalar/POD record arrays, local/field/global storage,
  internal array parameters and returns, enum payloads, contextual array values,
  whole-array updates and native layout queries. Equal evaluated counts preserve
  the existing element-type and ownership checks across different spellings.
- Existing limits still apply after evaluation: up to 4096 local elements and
  up to 256 inline field/payload elements, plus existing byte/ABI limits.
- Source dimension expressions are limited to 4096 bytes and evaluation depth
  is limited to 64. Invalid dimensions are rejected even in unreachable or
  uncalled code. Diagnostics retain the original source node.

Names (including module constants), function calls, layout queries inside a
dimension, casts, signed/unary expressions, shifts, bitwise operators, floating
point and dynamic lengths are not part of this contract. Comments inside raw
type-dimension text are not evaluated. This is not generic constant evaluation,
const generics, nested arrays or full canonical frontend parity. The optional
legacy Sotlas C emitter retains its narrower acceptance rules; it does not
silently execute a new unsupported repetition form.

## Implementation

`sema.sotlas` owns the checked arithmetic, bounded type-text evaluator and AST
repetition evaluator. The parser preserves repetition expressions as AST nodes.
Semantic array-shape checks and native lowering use those same evaluated counts
for static initialization, local/field construction and aggregate transfers.
The IR and machine backend continue to receive fixed layouts and literal counts.
No production Python/C compiler implementation was added.

## Execution evidence

[The example](../examples/native_array_dimensions/main.sotlas) returns an enum
containing two records with inline arrays, destructures it with `match`, and
checks queried storage sizes. Success exits with 42. All three platform-native
rebuild gates include check/build, host execution and ELF/PE/Mach-O emission.

`tests/test_sotlas_native_array_dimensions.py` includes arithmetic precedence,
all three nondecimal radices, local/field/static storage, internal calls,
payloads, conditional arrays, whole-array assignment, owned transfer,
use-after-move rejection, single evaluation, invalid/dead-code dimensions and
capacity/depth bounds. Full remote certification is required for this delivery.

Local validation passed 196 focused tests per native Windows/Linux compiler,
including 17 dimension tests and the array ABI, assignment, payload, record,
layout and pool suites. Focused hosted runs passed 82 tests covering the new behavior,
the kernel regression gate, parser/literal/AST contracts, manifests and phase
gates. The generated phase matrix remained consistent.

Original-source native rebuilds retained strict Stage 2/3 identity, using no
host build tools on PATH:

- Windows SHA-256: `ece89652b04993d573b630e97061059a97a7f6b71317276c5ba745ac328e7a7f`
- Linux SHA-256: `3ec36956dfcbfc3369d0ba56da51ec579fd9261827437482b5ba02feefb2a15c`

The example passed native check, object/direct build and host execution on both
hosts. Its object, ELF, PE and Mach-O outputs matched byte for byte across the
two producers. Actual Intel macOS execution and the new full CI remain pending.
