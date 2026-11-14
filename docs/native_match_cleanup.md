# Match-based resource cleanup

Owner-capturing `defer` blocks accept statement `match`, using the existing
native pattern checker, ownership merge and structured lowering.

```sotlas
defer {
    match order {
        CleanupOrder::BufferFirst(length) if length == 8 => {
            buffer.close();
            pages.close();
        },
        CleanupOrder::BufferFirst(_) => { buffer.close(); pages.close(); },
        CleanupOrder::PagesFirst => { pages.close(); buffer.close(); }
    }
}
```

## Selection and capture

The subject and guards execute at cleanup time. The subject is snapshotted
through the existing POD match path. Scalar, enum payload, record and fixed-array
patterns retain their ordinary coverage and binding checks. Arm-local names can
shadow outer bindings without reserving or consuming those outer bindings.

Subjects and guards must pass the existing argument-effect proof. They may read
local values, parameters and supported owner projections or call helpers proved
effect-free. They cannot transfer owners, call mutating helpers, access unsafe
state or propagate errors. Pattern bindings are readable only in their lexical
arm. Borrowing an owned POD subject does not consume it.

Every arm is checked before cleanup is registered. The existing ownership merge
rejects a read or second close after any arm consumed the owner. Consumption in
any possible arm reserves the captured binding and rejects subsequent use,
transfer or reassignment outside cleanup. A branch that does not close a resource
does not gain an implicit close; write the required release on every path.

## Execution

Only the selected arm runs. Calls retain source order, and separate deferred
actions retain LIFO order. Nested matches, conditionals and blocks share the
same cleanup path on normal scope exit, early return, tagged error propagation,
loop backedge, `break` and `continue`.

Calls that consume captured owners must return `void`. Declarations, assignments,
loops, nested defers and control transfers inside owner-capturing cleanup remain
outside this contract. The existing limits of 64 arms, 128 statements per block
and bounded nesting still apply. This does not add automatic aggregate drop,
resource-bearing pattern payloads or general borrow lifetimes.

## Verification

`tests/test_sotlas_native_match_cleanup.py` executes release ordering, LIFO,
late selection, payload guards, shadowing, record/array patterns, borrowed POD
snapshots, nested selection, loop exits and error propagation. Rejection cases
cover maybe-moved reads, double consumption, post-capture reassignment, borrowed
consumption, incomplete coverage, nonvoid consumption and effectful selection.

The kernel foundation uses an enum payload and guard to choose page/buffer
release order on ordinary and early returns, including with PIT interrupts
enabled. `tests/native_kernel_gate.py` rejects invalid selection and ownership
through both project checking and object emission. Its Linux execution gate
boots QEMU with 32, 64 and 128 MiB RAM and checks resource reclamation.
Platform CI for this delivery is pending.

Local verification passed 168 focused frontend/cleanup tests, eight additional
deferred-ownership tests, 54 self-hosting module checks and 35 contract/documentation
checks. All ten match-cleanup tests also passed using rebuilt native compilers
on Linux and Windows. Each target produced byte-identical Stage 2/3 compilers;
both hosts emitted the same kernel image, which passed all three QEMU memory
configurations. These results do not certify the pending platform CI.
