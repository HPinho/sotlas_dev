# Flow CPU Preview Contract

The `flow-run` command executes a checked Flow plan through the reference
interpreter or compiles it to a temporary native C11 program. The reference
backend can schedule independent stages concurrently. C11 executes the same
checked scalar plan in deterministic serial order.

## Run a plan

```sh
sotlas flow-run examples/12_sotlas_by_example/04_flow_cpu.sotlas \
  --flow Compute --workers 4
```

The command runs the canonical frontend and checked SIR validation before any
stage starts. Its JSON result contains the module name, plan name, selected
backend, and each stage output. Object keys are sorted so the report is stable
across runs.

To compile and run the plan through C11, install Clang or GCC and use:

```sh
sotlas flow-run examples/12_sotlas_by_example/04_flow_cpu.sotlas \
  --flow Compute --backend c11
```

The C11 runner checks the source, compiles the generated C plus a temporary
caller, executes it, and collects every stage output through the generated C
ABI. `--workers` applies to the reference backend; C11 remains serial.

## Supported subset

- Stages have pure, non-system function bodies.
- Stage parameters and return values are scalars. The reference interpreter
  currently handles integer and boolean SIR; C11 also accepts pure `f32` and
  `f64` plans.
- Function bodies use the straight-line instructions accepted by the Flow SIR
  interpreter.
- Dependency layers are derived from the checked plan. Independent stages in a
  layer may run concurrently, up to `--workers`.
- A stage failure stops later layers, cancels work that has not started, and
  waits for already-running peer stages before returning.
- Cancellation is exposed by the runtime API; the CLI does not currently accept
  an external cancellation signal.

Effects, arbitrary control flow, ownership-bearing payloads, host/device memory
transfers, physical GPU/NPU dispatch, and native parallel scheduling remain
unsupported. C11 accepts pure scalar graphs, including `f32` and `f64`, and
evaluates independent stages in deterministic dependency order.

## Exit behavior

Successful execution prints one JSON object using schema
`sotlas.flow-result.v1`. Invalid source, a missing plan, an unsupported SIR
instruction, an invalid worker count, a stage failure, or cancellation prints a
diagnostic to stderr, emits no success JSON, and exits nonzero.
