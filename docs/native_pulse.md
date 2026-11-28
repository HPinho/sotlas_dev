# Native pulse fences

The native x86-64 compiler supports `pulse;` as a memory fence. An
explicit order selects the machine instruction:

| Statement | x86-64 instruction |
|---|---|
| `pulse;`, `pulse();`, `pulse(seq_cst);` | `MFENCE` |
| `pulse(acquire);` | `LFENCE` |
| `pulse(release);` | `SFENCE` |

The order is a fixed keyword argument. Unsupported names and expressions
are syntax errors. The compiler preserves each fence at its statement
position, including statements in match arms and deferred blocks.

The fences order memory operations on the CPU. Shared data still needs
the appropriate atomic operations and synchronization protocol. Flow
signal delivery is a separate roadmap item.

The [native contracts](../tests/native/contracts/manifest.txt) cover
execution and syntax rejection. A
[machine-code test](../tests/test_sotlas_native_migration_sv851.py) checks
the emitted instruction sequence and order defaults.
