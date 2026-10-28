# Typed record-pointer projections in the native compiler

SV8.102 supports field chains such as `graph.head.next.counter.value`, mixing
inline records and typed raw record pointers in the structured native profile.
Each pointer boundary loads the stored address before projecting the next field;
it does not treat the address of a pointer slot as its pointed-to record.

Reads preserve scalar widths, Boolean and floating-point types. Writes support
scalar fields, inline record fields and existing bounded POD array fields.
Pointer-returning calls may provide receivers and are evaluated once before the
assignment's right-hand side. Recursive record-pointer layouts remain finite;
this does not allow recursive layouts by value.

The lowerer distinguishes **receiver identity** from **record value identity**.
Copying a raw pointer field into a pointer local preserves its address. Reading
an inline record into a value local copies its fields. An explicitly typed plain
record local initialized by unsafe dereference now captures an independent
snapshot, including inline arrays. Pointer fields inside a copied record still
copy addresses; this is not a deep clone of pointed-to objects.

New indirect field chains require an unsafe block. Mutable binding checks remain
in force, and const pointees cannot be written through a nested projection. The
frontend validates every newly crossed raw-pointer receiver before lowering,
including a pointer-returning call on the assignment path. An unsafe expression
that returns a pointer does not authorize a subsequent dereference outside its
lexical scope. Raw-pointer storage
must remain accessible and live: this does not introduce null guards, allocation
provenance or compiler-proven lifetimes. Pointer-bearing record arrays remain
outside the currently copyable native array profile and are rejected.

[The pointer graph](../examples/native_pointer_graph/README.md) exercises the
machine path. The arena runtime now uses chained access for its generation check
instead of an intermediate pointer local. Tests cover reads, stores, retargeting,
recursive pointers, call evaluation order, scalar widths, snapshots and negative
unsafe/const cases.

## Workflow regression fixed in this package

CI #1314 failed `test_scalar_insert_out_of_memory_preserves_arena_and_bytes`
across platforms. The fixture filled 16 bytes and expected a three-byte insertion
to exhaust a 20-byte arena, although its resulting 19-byte text fits. The runtime
correctly performed the insertion. The corrected exhaustion case provides only
18 bytes, preserves the original atomicity assertions, and a separate 19-byte
case verifies successful insertion exactly at capacity. Valid insertion is not
disabled to satisfy the failure case.

This block expands the native frontend/lowering path. It does not complete
arbitrary CFG, resource-bearing aggregates, automatic ARC or foreign aggregate ABI.

## Native seed transition

Plain record snapshots change code emitted for the compiler's own source.
Seeds from before this correction can therefore need an additional native
compiler generation before convergence. The regular build scripts still reject
unequal Stage 2/3 outputs. Validation uses an updated seed and separately checks
identity of the following two native generations; unequal intermediates are not
reported as a successful fixed point. Fresh hosted-seed CI reconstruction is also
checked. This transition requires no C/Python invocation after the seed is obtained.

## CI #1315: full-compiler cross-build timeout (2026-10-28)

[CI #1315](https://github.com/HPinho/sotlas_dev/actions/runs/40596394616)
failed in four Windows/Linux matrix jobs because the complete Darwin compiler
cross-build exceeded a 180-second timeout. That operation now has an explicit
900-second full-compiler budget, consistent with the Windows/macOS self-hosting
tests. Small-program and hosted-oracle timeouts remain unchanged. Exit status,
byte-for-byte oracle comparison, Mach-O magic and invalid-option preservation
assertions remain in place; no tests are skipped or retried automatically.

Local validation completed the exact Windows test with a 129.715-second native
build step. The Linux native cross-build, using the existing current-source seed
and the same freshly generated hosted oracle, completed in 127.486 seconds and
passed binary equality and invalid-option output preservation. Linux hosted
bootstrap was not rerun locally because its Clang toolchain is unavailable.
The new GitHub matrix result remains pending.
