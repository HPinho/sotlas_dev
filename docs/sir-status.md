# SIR Reality Gate

**Maturity: PROTOTYPE**

SIR exists as research/tooling code under `compiler/sotlas/sir/`. It is **not**
the production lowering path.

The current production acceptance path is:

```text
source -> compiler/sotlas_compile/bootstrap.py
       -> semantic/safety extensions
       -> C11 lowering
```

The current `SIRGenerator` does not lower complete function bodies. It creates
function shells, parameter stack slots, and a synthetic return. Therefore a
successful `sotlas dump-sir` or `sotlas dump-llvm` result is not evidence that
the corresponding source semantics are represented by SIR.

SIR must not be promoted to **SUPPORTED** or become the production backend until
it carries and verifies, end to end:

- typed function-body control flow and values;
- ownership/move facts;
- effects and system capabilities;
- unsafe boundaries and raw-pointer provenance;
- state/typestate transitions;
- causal/flow dependencies and guarantees required by the master specification;
- source spans suitable for diagnostics;
- positive, negative, verifier, lowering and end-to-end tests.

Until that gate is met, C11 Stage-0 remains the production lowering route and
SIR/LLVM commands are experimental inspection tools.
