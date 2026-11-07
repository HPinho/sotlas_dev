# Native fixed-array iteration

The Sotlas-written native frontend accepts by-value iteration over supported
plain fixed arrays, alongside half-open and inclusive integer ranges.

```sotlas
fn total(values: [u32; 3]) -> u32 {
    let mut sum: u32 = 0;
    for value in values {
        sum = sum + value;
    }
    return sum;
}
```

## Snapshot and item rules

The array expression is evaluated once when the loop is entered and copied to
private loop storage. Updating the original array in the body does not change
the iteration sequence. Each item is a scalar or POD value; `for mut item in
values` permits changing the item copy without writing back to the source.
The existing `for let` and `for var` binding spellings retain their immutable
and mutable meanings. Item bindings end with the loop scope.

Sources include typed locals/parameters, supported inline fields, calls returning
arrays, and successful array values extracted with `?`. Scalar types, pointer-free
records and supported POD payload-enum elements retain their existing native
array/layout rules. Dimensions can use the existing unsigned module constants.
This does not infer a type for an uncontextualized array literal used directly
after `in`.

The snapshot profile is bounded to 256 elements and 4096 bytes. Existing layout,
field and local storage capacities still apply. Qualified array sources
(`sole`/`exclusive`, `direct`, `whisper` and unsupported ownership domains),
pointer/resource-bearing elements, dynamic slices, pointer iteration and
general collection/iterator protocols remain outside the contract. Safe array
snapshots do not establish general pointer or borrowed-reference lifetimes.

## Control flow and cleanup

Numeric `for` loops use `start..end` for a half-open range and `start..=end`
to include the final value. A literal bound, optionally signed, takes the
inferred integer type of the other bound. For example, `0..count` binds a
`usize` index when `count` is `usize`. Two untyped bounds default to `u32`.
Literals must fit the selected type, and explicitly typed bounds must match.
Bounds are evaluated once, in source order. A descending range is empty.
Equal inclusive bounds
produce one iteration. The cursor records exhaustion at the inclusive endpoint
before the user body, so `continue` runs cleanup and exits even at the maximum
integer value. Nested loops keep independent cursor state. The inclusive syntax
is available through the native compiler profile.

The frontend normalizes the construct to scoped bindings and the production
structured while CFG. Source-backed reserved keyword spellings give its hidden
bindings lexical hygiene. The item is captured before the cursor advances;
the cursor advances before the user body, so `continue` cannot repeat an item.
`break`, nested loops, early returns and per-iteration lexical defers reuse the
existing production cleanup paths. There is no automatic resource destructor
or new unwind ABI.

For a `?` array source, failure returns before the loop begins and executes
already-active function defers. A successful array is snapshotted once. The
nominal result and POD restrictions on propagation remain unchanged.

An internal `ExprArrayLength` AST node carries the checked snapshot's constant
bound as a u32; no public `.len` property or dynamic size operation is added.
The parser appends existing element TypeRefs for item inference. Inference of
hidden snapshots/items is restricted to generated markers, so arbitrary cyclic
inferred aliases are not newly accepted. The optional legacy Sotlas C emitter
fails closed on the unsupported internal length node.

## Example and gates

The [batch example](../examples/native_array_iteration/main.sotlas) combines
record arrays, named dimensions, explicit payload tags, `?`, mutable item copies,
`continue` and deferred observation. It checks the source records remain intact,
counts cleanup on success/error paths and checks an inclusive singleton at
`U64_MAX` with a typed start and a literal end. It exits with 42. Native
platform rebuild gates include original-source check/build, host execution
and ELF/PE/Mach-O output.

`tests/test_sotlas_native_array_iteration.py` covers snapshot independence,
one-time calls, scalar widths, records/enums, fields/parameters, nested range and
array loops, scope/shadowing, all structured exits, result propagation and bounds,
plus invalid source/ownership/resource cases. Full remote CI is still required.

The original fixed-array validation passed 181 focused tests per Windows/Linux producer,
including 21 iteration tests plus array assignment/ABI, ownership, payloads,
record fields, tagged/status results and named dimensions. Hosted focused runs
passed 137 iteration/CFG/ownership/result tests and 40 AST/inventory/contract
tests. The generated phase matrix remained consistent.

The original batch example passed check, object/direct build and host execution with
exit 42 on both systems. Its object, ELF, PE and Mach-O outputs matched byte for
byte across the two native producers. Original-source reconstruction used no
host build tools on PATH and retained strict Stage 2/3 identity:

- Windows SHA-256: `803bd85909644c5ccae6e1aa553b192b27e2310b507d6fd503f8d8eac7bfdc53`
- Linux SHA-256: `0f3557a4464481e4c267323a79c7502134285226e1da23f3d1b9486d148643d2`

The initial inclusive-range extension passed 72 control-flow, array iteration and
error-composition tests per rebuilt Windows/Linux compiler. The updated
example executed with exit 42 and its object, ELF, PE and Mach-O output matched
across both hosts. Stage 2 and Stage 3 matched byte for byte on each host.

Contextual bounds passed 76 tests per rebuilt compiler, covering typed calls,
nested loops, signed literals, narrow endpoints and rejected overflow. The
current batch example produced identical objects and executable formats across
Windows and Linux. Stage 2 and Stage 3 also matched on both hosts. The new full
platform CI remains pending.
