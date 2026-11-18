# Native CPU row reductions and broadcasting

`runtime/native/tensor_ops.sotlas` extends the native numeric runtime with five
serial, allocation-free f32 kernels. Import `sotlas::runtime::tensor_cpu::*` for
the existing `NativeF32View` / `NativeF32MutView` records and
`sotlas::runtime::tensor_ops::*` for these operations. The
[preprocessing example](../examples/native_tensor_rows/README.md) composes them
with the existing CPU matrix-vector kernel using original Sotlas sources.

## Operations

All shapes are contiguous and row-major. `input.length` must be exactly
`rows * columns`; strides, inferred dimensions and arbitrary broadcasting are
not part of this API.

| Function | Output length | Operation |
| --- | --- | --- |
| `native_f32_row_sum_cpu(output, input, rows, columns)` | `rows` | Sequential sum of each row, starting at positive zero |
| `native_f32_row_mean_cpu(output, input, rows, columns)` | `rows` | Sequential row sum divided once by `columns as f32` |
| `native_f32_row_max_cpu(output, input, rows, columns)` | `rows` | Maximum of each row, preserving the first equal maximum |
| `native_f32_broadcast_add_cpu(output, input, vector, rows, columns)` | `rows * columns` | Add `vector[column]` to each input element |
| `native_f32_broadcast_mul_cpu(output, input, vector, rows, columns)` | `rows * columns` | Multiply each input element by `vector[column]` |

The broadcast vector must contain exactly `columns` elements, even when there
are zero rows. Sum accepts zero-width rows and writes positive zero for each.
Mean and max reject zero-width rows when `rows > 0`; all three accept zero
rows with empty input/output. Broadcasting with zero columns accepts empty
input, vector and output and performs no writes.

## Status and storage contract

Every function returns a u32 status:

| Status | Meaning |
| --- | --- |
| 0 | Success |
| 1 | Null nonempty range, misalignment, byte-count overflow or wrapped address range |
| 2 | Incompatible lengths, dimension-product overflow or undefined empty mean/max |
| 3 | Disallowed overlapping ranges |

Checks run in range, shape, then overlap order. All fallible validation finishes
before the first output write, so metadata rejection preserves the entire
output. Empty ranges require no dereference and may use null pointers.

Reductions require disjoint input and output. Broadcast operations allow exact
input/output aliasing with equal lengths; partial overlap is rejected. The
output must never overlap the broadcast vector, including exact aliases.
Read-only input and vector ranges may overlap each other when output is
separate. These rules prevent one row's writes from changing later reads.

Callers own all memory. They must provide live allocations covering every
declared range and exclusive writable access during the call. Numeric pointer
checks cannot prove provenance, allocation capacity, lifetime or thread safety.
The functions do not retain pointers, allocate storage, free storage or move
ownership. They do not convert these unsafe caller obligations into compiler
borrow guarantees.

## Floating-point behavior

Sums use left-to-right f32 additions without reassociation. Means perform that
sum and one f32 division; they are not compensated or overflow-resistant.
Max propagates the first encountered NaN and preserves the first value on ties,
including the sign of zero. Infinite values are accepted. Arithmetic overflow
and NaNs are ordinary floating-point results, not metadata failures.
Broadcast arithmetic uses one scalar f32 operation per element.

No hidden BLAS dependency, approximate exponential, FMA, GPU/NPU selection or
parallel scheduler is introduced. This is a reproducible CPU building block,
not a complete neural-network framework or accelerator support claim.

## Executable validation

`tests/native/contracts/cases/tensor_ops_values.sotlas` checks row statistics,
rectangular/in-place broadcasting, deterministic reduction order, NaN payloads,
signed zero, infinity, empty dimensions and a 1,024-element view.
`tensor_ops_reject.sotlas` checks all five operations against invalid ranges,
shape overflow, undefined empty reductions, conflicting aliases and output
preservation. They are original Sotlas assertions compiled and executed by the
native compiler, with no Python test generator.

Fresh SDK installation and verification passed both programs and the complete
58-case suite on Windows and Linux/WSL. The installed preprocessing example
also checked, compiled and exited successfully on both hosts, with host build
tools absent from the native subprocess PATH. Intel macOS execution and the
new complete CI result remain pending.
