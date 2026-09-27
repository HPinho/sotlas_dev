# Target IR Preview

`target-ir-report` exposes the first target-independent lowering layer after
the canonical checked SIR. It is intended for compiler development and reports
virtual values, typed operations, basic blocks, control-flow targets, and
call attributes in deterministic JSON.

```sh
sotlas target-ir-report path/to/program.sotlas
```

The report is produced only after source checking, canonical SIR construction,
and Flow-plan reconciliation. Target IR v1 currently represents stack
allocation, loads and stores, integer constants, arithmetic, comparisons,
calls, branches, phi nodes, and returns. Checked ownership and state facts are
preserved as explicitly marked semantic annotations, including their domains
and source points. An operation without a defined lowering is rejected.
The canonical `return if ... else ...` form is tested through conditional
branches and typed phi inputs; this does not imply support for arbitrary CFGs.

This preview does not select machine instructions, allocate registers, lay out
stack frames, emit object files, or replace the LLVM backend. Source locations
and a complete ABI model are also still open work. Semantic annotations do
not provide an ownership runtime or lower transfers into executable code.
