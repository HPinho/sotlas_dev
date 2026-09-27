# Flow CPU Preview Contract

The `flow-run` command executes a checked Flow plan through Sotlas's reference
interpreter and CPU scheduler. It is intended for experiments and validation;
it does not emit native parallel code.

## Run a plan

```sh
sotlas flow-run examples/12_sotlas_by_example/04_flow_cpu.sotlas \
  --flow Compute --workers 4
```

The command runs the canonical frontend and checked SIR validation before any
stage starts. Its JSON result contains the module name, plan name, and each
stage output. Object keys are sorted so the report is stable across runs.

## Supported subset

- Stages have pure, non-system function bodies.
- Stage parameters and return values are integer or boolean scalars.
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
unsupported. C11 accepts pure scalar graphs with independent stages and evaluates
them in deterministic dependency order as a serial fallback. The reference
runner may schedule independent stages concurrently.

## Exit behavior

Successful execution prints one JSON object using schema
`sotlas.flow-result.v1`. Invalid source, a missing plan, an unsupported SIR
instruction, an invalid worker count, a stage failure, or cancellation prints a
diagnostic to stderr, emits no success JSON, and exits nonzero.
