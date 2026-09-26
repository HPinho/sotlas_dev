# Phase 0 Reality Audit

**Updated:** 2026-09-26
**Authority:** [Implementation Status](sotlas_implementation_status.md) and
[Master Roadmap](sotlas_master_roadmap.md).

## Sotlas 1.0 reality contract

- The installed Python package comes from `compiler/` (`setup.py` and
  `pyproject.toml`). The production Stage-0 frontend is
  `compiler/sotlas_compile/bootstrap.py`; the historical SIR generator remains
  a prototype and is not the production lowering path.
- All numbered examples are explicitly classified in `examples/manifest.json`.
  Example smoke checks prove only the commands named by each manifest entry.
- Every Markdown file under `docs/` with a fenced `sotlas` block is classified
  by `docs/public_snippets.json`. Every `RUNNABLE` source is checked through the
  canonical CLI and emitted as C11 in an isolated temporary directory. Other
  snippets are explicitly experimental or design-only.
- The isolated Phase 1 semantic core is certified at `ISOLATED_PHASE1`. This
  does not promote the entire language, SIR, or backend.
- Package metadata and runtime version agree at `0.5.1`; package maturity is
  Alpha. Historical audits and progress snapshots are labeled as such.
- The `compiler/` and `tools/` trees are intentionally retained for compatibility
  with existing developer tools and tests. `compiler/` is the installed source
  of truth. Of 86 paired Python modules, 82 are byte-identical and four reviewed
  files differ: `sotlas/__init__.py`, `sotlas_compile/__init__.py`,
  `sotlas_compile/bootstrap.py`, and `sotlas_compile/language_safety.py`.
  There are 23 compiler-only and three tools-only modules. The reality gate
  checks the exact reviewed difference set and current unique-module counts.
  Consolidating compatibility imports is deferred until the old tools clients
  and tests are migrated; no claim is made that duplicate files were deleted.

## Verified public guide boundary

The README files and Portuguese Quickstart point to the checked-in example,
explain host-toolchain requirements, label the class example experimental, and
describe the local specification as design material. Only the numbered
Quickstart example currently has a runnable public-snippet contract. A snippet
classified `EXPERIMENTAL` or `DESIGN_ONLY` is not implementation evidence.

The historical v1 architecture audit and the older implementation-progress
snapshot are retained for context but are not canonical status sources. Current
support claims must be checked against the implementation status, the snippet
inventory, and the relevant automated gate.

## Gate

`tests/test_sotlas_reality_gate.py` verifies package metadata, example
classification, snippet coverage and runnable sources, public quickstarts,
production entrypoints, SIR prototype labeling, and the exact compiler/tools
mirror inventory. New fenced documents, mirror differences, or unique modules
must update their reviewed inventories in the same change.

Phase 0's Sotlas 1.0 contract is complete. Physical consolidation of the
historical compatibility tree and per-snippet promotion beyond the single
runnable Quickstart example remain post-1.0 work. CI success alone is not
evidence for broader language support.
