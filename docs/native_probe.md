# Native probes

Use `probe condition;` to check a boolean invariant. Use
`probe condition, "message";` to record the reason in the source.

The native frontend requires a boolean condition and a string literal if a
message is present. A probe cannot consume an owner. A condition that folds to
true emits no runtime check. A condition that folds to false is rejected during
compilation.

At runtime, the condition is evaluated once using the usual short-circuit
rules. A true result continues execution. On x86-64, a false result executes
`UD2`, terminating the process with an illegal-instruction fault. The trap
performs no unwinding and emits no message.

The [native contract suite](../tests/native/contracts/manifest.txt) covers
successful execution, the fault status and invalid uses.
