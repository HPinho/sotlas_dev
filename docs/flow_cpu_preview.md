# Flow CPU Preview Contract

The `flow-run` command executes a checked Flow plan through the reference
interpreter or compiles it to a temporary native C11 program. The reference
backend can schedule independent stages concurrently. C11 executes the same
checked scalar plan or plain C-layout record plan in deterministic serial order.

## Run a plan

```sh
sotlas flow-run examples/12_sotlas_by_example/04_flow_cpu.sotlas \
  --flow Compute --workers 4
```

The command runs the canonical frontend and checked SIR validation before any
stage starts. Its JSON result contains the module name, plan name, selected
backend, and each stage output. Object keys are sorted so the report is stable
across runs.
Source-level Flow graph, dependency, and stage-signature errors point to the
offending flow or stage declaration. C11-lowering rejections point to the stage
whose value or function is outside the native subset.

To compile and run the plan through C11, install Clang or GCC and use:

```sh
sotlas flow-run examples/12_sotlas_by_example/04_flow_cpu.sotlas \
  --flow Compute --backend c11 --timeout 10
```

The C11 runner checks the source, compiles the generated C plus a temporary
caller, executes it, and collects every stage output through the generated C
ABI. `--workers` applies to the reference backend; C11 remains serial.
For C11, the JSON result includes recursively serialized fields for supported
plain `@repr(C)` records, including explicitly represented nested records.
`--timeout SECONDS` bounds Flow execution after compilation. The reference
backend requests cooperative cancellation at CFG block and instruction
boundaries and between dependency layers, using a monotonic deadline. C11 runs
in a temporary child process; on timeout that process is terminated and no
partial stage output is published. Compilation time is not included in the
execution timeout. The runtime API accepts an absolute monotonic deadline
consistently through graph, typed-plan, interpreted-SIR, bound-SIR,
intent-selection, and executable-CFG entrypoints; non-finite deadlines are
rejected before any stage starts. Cancellation remains a cancellation outcome
when it passes through the intent and provider-executor adapters.

## Supported subset

- Stages have pure, non-system function bodies.
- Before execution, both backends require a checked pure-effect summary and
  reject system/foreign stages, unresolved calls, contracts not yet integrated
  with Flow, and direct or transitively called access to module globals.
- The reference interpreter currently handles integer and boolean SIR. C11
  also accepts pure `f32` and `f64` values and non-owning `@repr(C)` records
  whose fields recursively resolve to supported scalars or explicitly
  represented nested records.
- Record payloads cross native stage boundaries by value. Pointer fields,
  arrays, bit-fields, packed/aligned layouts, register unions, and nested types
  without an explicit C representation are rejected. The native backend also
  supports linear chains of `sole @repr(C)` records when every field is a
  supported ownership-free C value or another trivial linear `sole @repr(C)`
  record, with no `deinit` method at any nested level. Flow rejects fan-out and
  dropped intermediate owners before lowering. These records have no owned
  resources or observable identity, so cancellation
  between stages needs no owner cleanup. Other ownership-bearing records remain
  unsupported.
- Flow's checked ownership edges reject a `sole` result consumed by multiple
  stages or dropped before the plan's final scheduled result. The native C11
  subset lowers a linear chain of trivial `sole @repr(C)` records by value;
  records with cleanup obligations remain rejected until stage transfer,
  destruction, and cancellation can be integrated for resource-bearing owners.
- Stage signatures and effects must satisfy the checked Flow contract. The
  reference interpreter supports the instruction subset accepted by Flow SIR;
  C11 stage functions may also use structured branches and early returns that
  the C11 source backend lowers. Native coverage includes those control paths
  in a record-valued stage with explicit `@repr(C)` layout.
- Dependency layers are derived from the checked plan. Independent stages in a
  layer may run concurrently, up to `--workers`.
- A stage failure stops later layers, cancels work that has not started, and
  waits for already-running peer stages before returning.
- Cancellation is exposed by the runtime API. The CLI provides `--timeout`, but
  it does not yet accept an external cancellation signal. Reference execution
  polls cooperatively; native C11 execution is bounded by terminating its
  isolated runner process, without language-level stack unwinding.

Effects, arbitrary control flow, resource-bearing ownership payloads,
host/device memory transfers, physical GPU/NPU dispatch, and native parallel
scheduling remain unsupported. C11 accepts the scalar, plain-record, and
trivial linear-owner values above and evaluates independent stages in
deterministic dependency order.

## Exit behavior

Successful execution prints one JSON object using schema
`sotlas.flow-result.v1`. Invalid source, a missing plan, an unsupported SIR
instruction, an invalid worker count, a stage failure, or cancellation prints a
diagnostic to stderr, emits no success JSON, and exits nonzero.
