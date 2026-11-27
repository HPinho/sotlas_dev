# Native quench blocks

`quench { ... }` issues `SFENCE` and then `MFENCE` before entering its
body, matching the C11 reference lowering on x86-64. Every entry issues
both instructions, including entries into an empty block.

The fences order CPU memory accesses. Cache writeback, durable persistence
and device synchronization have separate target-specific requirements.
Interrupts keep their current state throughout the block.

The body has lexical scope. Ownership and `defer` follow the ordinary
block rules for fallthrough, `return`, `break` and `continue`. Raw memory
access inside the body requires the usual permissions.

The [native contracts](../tests/native/contracts/manifest.txt) exercise
the block at runtime. The
[machine-code regression test](../tests/test_sotlas_native_migration_sv851.py)
checks that the fence bytes survive lowering even when the body is empty.
