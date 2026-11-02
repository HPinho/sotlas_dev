# Native if-let expressions

`if let` can produce a native value as well as select a statement block:

```sotlas
enum Maybe { None, Some(u32) }

fn number(input: Maybe, fallback: u32) -> u32 {
    return if let Maybe::Some(value)=input {
        let selected: u32=value;
        selected
    } else {
        fallback
    };
}
```

An expression requires an else. Each non-returning branch yields its final
expression without a trailing semicolon. Branches can declare locals, run
structured control flow and register lexical defers. Locals and pattern
bindings end with their branch. The subject is evaluated once; only the
selected branch executes. Tail values are snapshotted before branch defers
run in LIFO order.

Else chains can combine ordinary `else if` expressions and `else if let`.
The current value-block grammar requires parentheses around a control
expression used directly as another block's tail, for example
`{ (if let Maybe::Some(n)=other { n } else { 0 }) }`. It is also valid to bind
that expression to a local and yield the local. This package does not change
the ordinary if-expression block grammar.

## Values and ownership

Accepted positions include typed locals, assignments, returns, call arguments
and composed expressions. Values can be scalars, plain records, bounded arrays
or POD payload enums, under existing match type/context rules. The same
recursive, named, array, float and alternative patterns are available here.

The selected branch can return from its enclosing function. `?` can propagate
from the subject or a selected block; an if-let result can itself feed `?`.
Existing nominal error composition and lexical cleanup apply. A value branch
must yield a value or have a proven function return; a bare break/continue is
not a general value-producing divergence form.

Ownership-bearing branch results use existing match analysis: consumption on
the selected edge, merges and unavailable-owner checks. No new ARC, destructor,
borrow-lifetime or exception-unwind behavior is added. Resource/pointer payload
subjects retain match POD restrictions. Generic Option/Result and foreign
aggregate ABI support are outside this block.

Missing else/tails, incompatible types or nominal results, binding escapes,
unsupported resource payloads and invalid ownership merges are rejected. Existing
statement if-let/while-let contracts remain. The legacy C11 emitter is outside
this native expression contract.

## Implementation and application

The parser normalizes the decision to ExprMatch with MatchValueBlock branches.
It shares the pattern resolver, inference, branch storage, ownership checker
and machine lowering. No IR opcode, runtime dispatcher or production Python/C
implementation is added. Existing optional-library interfaces are unchanged.

The [readings example](../examples/native_pattern_values/main.sotlas) parses two
valid numbers and one invalid field into records. An explicit caller-selected
default is retained together with the parse error. It iterates those records,
adds with checked arithmetic, verifies cleanup and exits 42. Malformed input
is not relabeled as a successful parse.

`tests/test_sotlas_native_pattern_values.py` covers expression positions, lazy
branches, scalar/record/array/enum values, nested patterns, snapshots, locals,
defers, returns, propagation and ownership acceptance/rejection. Platform
rebuilt-driver gates include imported check, object/direct build, execution and
ELF/PE/Mach-O emission. Full CI certification remains pending.

## Local validation

The final expression suite passed 20 tests, alongside 108 shared CFG, match
value and AST tests and 21 inventory/phase checks. A native run passed 199
tests per Linux/Windows producer, including prior errors, options, statement
patterns, splitting, arrays and ownership. The generated phase matrix remained
consistent.

The imported readings application passed check, object generation, direct
build and execution with exit 42 in both environments, with host tools absent
from PATH. Its object, ELF, PE and Mach-O outputs matched byte for byte across
the two producers. Actual Mach-O execution awaits the macOS platform gate.

Original-source rebuilds completed with host tools absent from PATH and strict
Stage 2/3 byte equality per host. Focused native tests used Stage 2; the Stage 3
images are identical. Compiler SHA-256 values:

- Windows: `72e3c399076107e5fe3b62d067e51bfcd3b148ca52d229b29d50be7f40427f96`
- Linux: `b5ee2f9ed5d8dc18030c39b6ab7880f6e6f1e1834b13e54a5a06ba23791641c1`

These checks validate the declared native profile; they do not close general
frontend parity, automatic resource management or independent distribution.
