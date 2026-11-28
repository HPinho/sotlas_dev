# Native mould assertions

A module can contain one or more `mould { ... }` blocks of `probe`
statements. Each condition must fold to a boolean. The native compiler
evaluates these assertions after resolving scalar module constants and
type layouts, including declarations later in the same module.

Use a layout query such as `probe span_of::<Header>() == 8, "wire header layout";`
to check a binary layout. A false condition is a compilation error at the
`probe` statement. An optional string literal explains the invariant in
the source.

The block accepts compile-time assertions. Calls and reads of runtime
storage are rejected, including calls in a short-circuited operand. A
successful block emits no machine instructions or storage.

The [native contracts](../tests/native/contracts/manifest.txt) exercise
layout, constants, and rejection paths. A
[native object test](../tests/test_sotlas_native_migration_sv851.py) verifies
that a passing block leaves the generated object byte-for-byte identical.
