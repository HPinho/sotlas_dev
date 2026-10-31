# Native tagged result propagation

The Sotlas-written native compiler accepts postfix `?` on concrete POD enums
with exactly two variants named `Ok` and `Err`, each carrying one typed payload.
Variant order does not determine success; the compiler compares the registered
tag of `Ok`.

```sotlas
enum Outcome { Ok(u32), Err(Error) }
struct Error { pub code: u32; pub offset: usize; }

fn forward(input: Outcome) -> Outcome {
    let value: u32 = input?;
    return Outcome::Ok(value + 1);
}
```

## Execution contract

The operand is evaluated once and snapshotted. On `Ok`, the expression yields
its payload using the existing scalar/aggregate value rules. On `Err`, the
complete nominal enum is copied to the enclosing function's return destination
before active lexical defers run in reverse order. Later arguments and operands
do not execute after this return. The enclosing function must return the same
unqualified nominal enum. There is no automatic error conversion.

Success and error payloads can be supported scalars, pointer-free records,
nested POD payload enums or bounded inline arrays. Array dimensions retain
their existing literal/named-constant contracts and storage limits. Conditional
and match operands, compatible inferred result locals, calls, stored values,
fields and indexed POD records use existing native value paths. Conditional
inference is extended only where both alternatives prove one concrete result
type; this does not establish general expression inference.

Invalid variant names/counts/arities, qualified result bindings, qualified or
pointer-bearing payloads, incompatible nominal returns and `?` inside `defer`
are rejected, including invalid uses after an unconditional return. Plain POD
snapshots do not implement resource moves, automatic ARC/drop or borrowed
lifetimes. Unsafe fabrication of an invalid enum tag is outside this contract.

This shares the existing [status/value result](native_result_propagation.md)
cleanup path and Target IR branches/loads/stores. No new exception ABI, general
unwind mechanism, generic `Result<T,E>` instantiation or foreign aggregate ABI
is introduced. The optional legacy C11 emitter retains its separate supported
generic Result path; this delivery targets the owned machine backend.

## Library integration and evidence

The [example](../examples/native_tagged_results/main.sotlas) adapts the existing
native checked numeric APIs into an application enum. It parses and adds 20 and
22, verifies invalid-input byte offsets and overflow, and counts cleanup on all
three paths. Success exits with 42. Original-source platform rebuild gates now
include check/build, host execution and ELF/PE/Mach-O emission for this example.

`tests/test_sotlas_native_tagged_results.py` exercises both tag orders,
single evaluation, metadata preservation, scalar widths and floating point,
record/array/nested-enum payloads, conditional and match inference, structured
loops, argument short-circuiting, return snapshots and LIFO cleanup. Negative
cases cover nominal/schema/ownership boundaries and invalid dead source.
Full remote certification remains pending for this delivery.

Local validation passed 185 focused tests per native Windows/Linux compiler,
covering tagged and status/value results, numeric APIs, ownership, array ABI,
payloads, composed values and reusable storage. Separate hosted runs passed
53 result/numeric tests and 123 CFG/inventory/Target IR checks, including the
complete production Sema name-comparison fixture. The phase matrix check passed.

The imported example passed native check, object/direct build and host execution
with exit 42 on both platforms. Its object and ELF/PE/Mach-O outputs were byte
identical across the Windows and Linux native producers. Actual Intel macOS
execution and full CI certification remain pending.

Original-source native self-builds retained strict Stage 2/3 identity with
host build tools absent from PATH:

- Windows SHA-256: `c13a06631a3a31589fe6ce0d2d284c25406019eb85c6d8aff1eaa9cd3a7848b9`
- Linux SHA-256: `3cf89ac945934e76bc3f8291bdb1984238253c0854c94cc959d9850d1d918c09`
