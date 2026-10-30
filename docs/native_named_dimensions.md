# Module constants in native array dimensions

Fixed arrays can use unsigned module constants as well as literal arithmetic:

```sotlas
const COUNT: usize = HALF * 2;
const HALF: usize = 3;

fn make() -> [u32; COUNT] {
    return [7; COUNT];
}
```

The same count is available to local arrays, record fields, POD record arrays,
static tables, supported enum payloads, internal parameters/returns, repetition
and native layout queries. Reusing a capacity in a runtime function call uses
the ordinary module constant value. No runtime array size is introduced.

## Resolution and checks

Only explicit module `const` declarations typed `u8`, `u16`, `u32`, `u64` or
`usize` qualify. Forward references and acyclic dependencies are supported.
Their initializers use the checked unsigned arithmetic described in the
[dimension contract](native_array_dimensions.md). Each resolved value must also
fit its declared unsigned type. Existing canonical constant acceptance rules
still apply; this does not introduce implicit mixed-width conversions.

The native semantic resolver handles scope lookup for both raw type text and
repetition AST expressions. A visible local, parameter or pattern binding with
the same name is rejected as a dimension; the compiler cannot silently replace
a runtime value with a hidden global constant. Mutable module bindings and
statics, local constants, signed/float/bool constants, calls, casts and layout
queries inside dimension-constant initializers remain outside this profile.

Evaluation is bounded to 64 nested evaluation steps, including constant
dependencies. Cycles, excessive dependency depth, unknown names, arithmetic
overflow/underflow, division by zero and invalid final capacities fail closed,
including uses in unreachable code. The module's existing 64-constant limit
and the existing array element/byte limits remain enforced.

There is no general const-generic system, package-wide constant namespace,
dynamic array shape, automatic resource-array destruction or foreign array ABI
claim here. Imported sources use the native project's existing source-resolution
contract; separate-object semantic module parity remains open. The optional
legacy Sotlas C emitter retains its narrower supported forms.

## Native execution

The [example](../examples/native_named_dimensions/main.sotlas) uses named sizes
for inline samples, an enum's record-array payload and a reusable pool's storage
and typed metadata. It performs writes, explicit release/close and a payload
match, exiting with 42. All native platform rebuild gates include check/build,
host execution and ELF/PE/Mach-O emission for this original source.

The implementation is in `sema.sotlas` and native lowering. It shares lexical
binding resolution with ordinary expressions and retains a literal fast path.
No production Python/C implementation was added.

`tests/test_sotlas_native_named_dimensions.py` covers forward dependencies,
unsigned widths, calls, static tables, record arrays, payloads, queries, owned
moves, deferred borrows, shadowing and invalid/cyclic/dead-code cases. Full CI
certification is pending for this delivery.

Local evidence: 210 focused execution/rejection tests passed per native
Windows/Linux compiler, covering the new names plus existing dimensions, layout,
array ABI, assignment, payloads, record fields, ownership and pool behavior.
Hosted validation passed an 83-test focused run and a further 44-test parser,
AST, literal, inventory and contract run. The phase matrix consistency check
also passed. These focused runs overlap; they are not a new full-suite count.

Both original-source native rebuilds preserved strict Stage 2/3 byte identity
with host build tools absent from PATH. The named-capacity example passed
check, object/direct build and host execution with exit 42 in both environments.
Its object and ELF/PE/Mach-O bytes matched across the two native producers.
Intel macOS execution and the new full remote CI remain pending.

- Windows SHA-256: `db60b38ac3159a292f4a90557f1ec513c016fcda3602898e0f92eaf2298b45f1`
- Linux SHA-256: `da817711c36fd49a811269e2e46b4eac164275fe04bc41f8c58a8ec0fac50572`
