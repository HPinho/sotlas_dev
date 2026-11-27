# Native gate blocks

Use `gate (condition) { ... }` to require a boolean precondition before a
block of code. The parentheses and braces are required. The condition runs
once and follows the usual short-circuit rules. It may read an owner, but it
cannot consume one.

On x86-64, a false condition issues an illegal-instruction trap before the
body starts, even if the condition is the literal `false`. The process stops
without unwinding. A true condition enters a lexical scope. Normal exits,
including `return`, `break` and `continue`, follow the surrounding language
rules for ownership and `defer`.

The guard orders execution of the predicate and the body. Use the target's
explicit memory-ordering operations for synchronization. Raw pointer and
hardware accesses inside the body require their usual permissions.

See [the native contract suite](../tests/native/contracts/manifest.txt) for
the execution, trap and rejection cases.
