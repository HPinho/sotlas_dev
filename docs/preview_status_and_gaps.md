# Sotlas Preview: Implemented Work and Remaining Gaps

**Repository:** [HPinho/sotlas_dev](https://github.com/HPinho/sotlas_dev)  
**Snapshot date:** 2026-09-28  
**Status:** Working-tree snapshot; this document does not describe a tagged release.

This report summarizes behavior supported by the current phase-gate matrix and
the tests documented there. “Implemented” means that a stated subset has
implementation and evidence; it does not mean that the whole language feature
is complete.

## Implemented and exercised

### Native preview path and control flow

- The repository has a reproducible native C11 example path, including
  verification, compilation, execution, and an example manifest.
- The C11 source backend executes the currently represented structured control
  flow, including branches, loops, `break`, `continue`, nested exits, and early
  returns. The tested scalar LLVM subset also lowers conditional expressions
  and selected loop-carried values.
- The canonical frontend reports source locations for many parser, type,
  control-flow, and backend-subset errors. Flow source and C11-lowering errors
  identify the affected flow or stage.

### Ownership and resource handling

- `sole` moves and use-after-move checks, ownership-domain graph facts, and
  selected transfers are checked through the canonical pipeline.
- `region` has interprocedural no-escape checks for tested calls, forwarding,
  nested aggregates, and structured control flow. The tested native arena
  subset executes on C11.
- `shared`/ARC has native evidence for tested aliases, retain/release, early
  returns, `defer`, cleanup paths, and destruction counts.
- `whisper` and `direct` have call-scoped, non-owning subsets. The checker
  verifies no-escape for eligible internal calls and forwarding chains;
  supported C11 and LLVM parameters lower to const pointers where documented.
- `island`, `handover`, and `quarantine` have graph checks and tested
  transitions. C11 covers selected `ISLAND`-to-`EXCLUSIVE` handover and
  `EXCLUSIVE`-to-`ISLAND` quarantine behavior.
- `external` has a tested `repr(C)` wrapper subset. Unsupported ownership
  storage and transitions fail closed in the covered backends.

### Flow and heterogeneous execution

- Flow checks stage signatures, dependencies, effects, and selected ownership
  constraints before execution. The reference CPU runner propagates failures
  and cancellation; the C11 ABI has stage dispatch, failure status,
  cancellation between stages, and output publication only after success.
- `flow-run --backend c11` executes tested scalar, plain `repr(C)` record, and
  trivial linear-owner plans. C11 execution is serial and deterministic.
- The repository contains one end-to-end OpenCL C interop workload: `f32`
  vector addition with explicit buffers, synchronous dispatch, readback, CPU
  fallback policy, and host-side result comparison. Fake-provider tests exercise
  success, no-device, fallback, and provider failures. An optional hardware test
  runs the same workload when an OpenCL GPU is available.

### Standard library

- Native tests cover `ResultBool`, `ResultU32`, `ResultI32`, and `ResultU64`,
  including error codes, boundary values, and preservation of caller output on
  failure.
- String tests cover byte operations, UTF-8 validation, integer parsing,
  malformed input, overflow, and buffer boundaries.
- `VecU32` and `HashMapU64` provide caller-backed, fixed-capacity native
  collections. Tests cover bounds, empty/full states, collisions, malformed
  counts/lengths, and unchanged storage on rejected operations.

## Remaining gaps

### Compiler profile and control flow

- The self-hosted/native frontend is still an experimental, limited parser and
  emitter subset. It does not replace the production semantic pipeline and
  does not prove a stage-one/stage-two fixed point.
- Arbitrary CFG, complete type inference, general all-path return analysis,
  and consistent lowering of every accepted construct across C11 and LLVM
  remain open.
- LLVM still depends on LLVM for target code generation. Sotlas does not yet
  emit machine code with its own complete ABI, register allocator, object
  writer, and linker path.

### Ownership domains and cleanup

- `region` still lacks a general lifetime graph and sound escape proof for
  arbitrary CFG, all aggregate shapes, and all call patterns; physical arena
  allocation and reuse are not implemented by the symbolic lifetime facts.
- Shared ARC is not complete for every payload, backend, and control-flow
  shape. Complete unwind/defer integration and resource-bearing Flow payloads
  remain open.
- `whisper` still lacks storage and return support, FFI/indirect-call support,
  and runtime weak-handle invalidation. `direct` still lacks broad alias-graph
  and arbitrary-CFG coverage.
- `island` does not enforce physical thread or processor confinement.
  `quarantine` does not provide runtime weak-reference invalidation. Only
  selected `handover` destinations and branch shapes are supported.
- Device and external ownership do not yet provide complete runtime,
  synchronization, or backend-neutral lowering across all domains.

### Flow, GPU/NPU, and standard library

- Flow does not yet lower stages to GPU/NPU, transfer ownership-bearing
  payloads between devices, or provide native parallel scheduling. C11
  cancellation is checked between stages; it does not interrupt a running
  stage or perform language-level stack unwinding.
- The OpenCL vector-add path is a C ABI interoperability workload, not general
  Flow-to-GPU lowering. NPU backends, asynchronous device APIs, durable device
  identity, and end-to-end performance comparisons remain open.
- Generic `Vec<T>` is not available in the current native C11 subset. The
  caller-backed vector and hashmap do not grow or allocate; broader generic
  collections and richer standard-library error, string, and I/O facilities
  remain future work.

### Current validation note

The phase-gate matrix describes the expected test coverage in
[`phase_gate_matrix.md`](phase_gate_matrix.md). A recent isolated run of the
phase-one pipeline passed **110 tests**. The latest full discovery run completed
**2,042 tests with 6 failures and 9 skips**; the failures were concentrated in
SIR/ownership tests whose instruction classes came from different dynamically
loaded copies of the canonical SIR package. Treat the full suite as **not
currently green** until that test-loading inconsistency is fixed and the full
run passes again.

## Evidence and detailed contracts

- [Phase gate matrix](phase_gate_matrix.md)
- [Language reference](language_reference_en.md)
- [Flow CPU preview](flow_cpu_preview.md)
- [OpenCL GPU preview](opencl_gpu_preview.md)
- [Core and foundation library contracts](../stdlib/core/README.md)
