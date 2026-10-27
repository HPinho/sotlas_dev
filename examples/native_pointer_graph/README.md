# Native pointer graph and record snapshots

Traverse a small graph through typed record pointers, mutate an inline array,
capture a record snapshot and update storage through a pointer-returning call.
The executable verifies one-shot receiver evaluation and independence of copied
record/array fields. It returns **42** and prints no output.

With a compiler rebuilt from SV8.102 sources:

```sh
sotlas-native --check examples/native_pointer_graph/main.sotlas
sotlas-native examples/native_pointer_graph/main.sotlas build/pointer-graph
./build/pointer-graph
```

On Windows use an `.exe` output name. This uses native machine-code generation
and linking, without a host compiler/linker after the seed is obtained.

Raw pointers require accessible backing and explicit unsafe use. The example
does not add automatic ownership, allocation or ARC. See
[pointer projections](../../docs/native_pointer_projections.md) for the contract.
