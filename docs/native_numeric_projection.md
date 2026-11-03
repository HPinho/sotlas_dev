# Native f32 buffers and CPU projection

The native frontend accepts numeric compound assignments to writable record
fields, fixed-array elements and raw pointer dereferences. Examples include
`layer.weights[i] += delta`, `record.value *= scale` and `*(buffer+i) += value`.
Raw pointer access requires `unsafe`. Raw pointer indexing (`buffer[i]`) is
still outside this profile; use pointer arithmetic and dereference instead.

The destination address is evaluated once, followed by loading the old value,
evaluating the right operand and storing the result. A failing `?` on the
right does not write the destination. Bounds checks run before the right
operand. Compound assignment preserves existing scalar arithmetic rules,
including integer wrapping and checked shift counts. Bool, whole aggregates,
enums and unsupported operator/type pairs are rejected. Readonly destinations
are rejected for both ordinary and compound stores. The legacy Sotlas C
emitter rejects this new place form rather than emitting a plain assignment.

## Caller-backed CPU kernels

`runtime/native/tensor_cpu.sotlas` provides concrete f32 buffer descriptors,
without allocation, C glue or Python in the generated application:

| Operation | Contract |
| --- | --- |
| `native_f32_dot_cpu(left, right)` | Equal lengths; returns status and scalar value |
| `native_f32_scale_cpu(output, scale)` | In-place multiplication |
| `native_f32_axpy_cpu(output, input, scale)` | `output += scale * input`; equal lengths |
| `native_f32_gemv_cpu(output, input, weights, rows, columns)` | Row-major matrix-vector product; exact descriptor lengths |

Status codes are 0 for success, 1 for invalid range metadata, 2 for incompatible
dimensions and 3 for unsafe overlap. Dot returns a zero value on metadata
failure. AXPY permits exact in-place input/output aliasing and rejects partial
overlap. GEMV rejects output overlap with either input; its readonly inputs
may overlap. All metadata checks precede output writes, so rejected metadata
does not partially update output.

Nonempty ranges require a nonnull, four-byte-aligned address and nonoverflowing
byte length/end address. Empty ranges allow null and do not dereference their
address. Matrix shape multiplication is checked for overflow. A zero-column
matrix writes zeros to its rows; a zero-row matrix writes nothing.

These checks do **not** prove pointer provenance, allocation size, lifetime or
absence of concurrent mutation. Callers must provide live, accessible buffers
with the declared capacities and exclusive output access. Invalid storage can
still trap. No allocation, hardware failure recovery or cancellation is provided.

Accumulation follows sequential f32 multiplication and addition, without
reassociation or fused operations. NaN and infinity follow the existing f32
arithmetic behavior; finite inputs/results are not enforced. This reference
does not claim numerical equivalence to a future parallel or reduced-precision
backend without an explicit tolerance contract.

## Example and validation

[`examples/native_numeric_projection/main.sotlas`](../examples/native_numeric_projection/main.sotlas)
computes a dense projection, adds a residual and scales the result. Its output
is `[30.0, 12.0]`; it exits with 42 after checking that result and a dot product.
It is a numerical building block, not an inference engine or a generative model.

The shared Stage 3 platform fixtures run the imported example through
`--check-build`, `--build-obj`, direct native build and ELF/PE/Mach-O linking,
then execute the host format with host tools absent from PATH. Focused tests
exercise single address evaluation, RHS side effects/failure, readonly writes,
invalid ranges, dimensions, overlap, empty shapes and f32 accumulation order.
A 1024-element raw buffer test avoids the fixed-array by-value snapshot limit.

Local package verification passed on Windows and Linux/WSL: the native
regression group ran 148 tests on Windows and 145 on Linux (one platform skip).
The Linux group excludes three C differential fixtures because that environment
has no C compiler; those fixtures passed on Windows. The compiler-internal
name-arena fixture ran in its original hosted group instead of the standalone
native adapter. The CFG/AST self-host group passed 87 tests; the example/phase
inventory group passed 21. Original-source rebuilds preserved strict Stage 2/3
identity on each host, with SHA-256 prefixes `c54b8cbedef6` (Windows) and
`e381fa185205` (Linux). Final Stage 3 compilers also passed the imported example
checks above. Intel macOS execution remains subject to platform CI.

CI #1344 exposed eight failed assertions in historical SV8.56/SV8.57 and
operator-tag tests: seven still expected indexed scalar compounds to be
rejected, and one expected opcode dispatch inside `lower_expression` after it
had moved to the shared arithmetic helper. The updated gates execute the
indexed operators, retain immutable-array rejection, reject owned aggregate
arithmetic for all six integer operators, and check the shared opcode mapping.
The affected local group passed 58 tests; 34 compound/kernel tests also passed
through the existing native Stage 3 on both Windows and Linux. Compiler sources
and the strict self-build identity check were unchanged by this test correction.
Full CI certification of the correction remains pending.

GPU and NPU execution, tensor language types, batching, attention, model
formats, tokenization, autodifferentiation, FP16/BF16 and quantization remain
outside this package. The CPU reference establishes a testable result for
future device dispatch; it does not route work to an accelerator today.
