# Phase 0 Reality Audit

**Date:** 2026-09-22  
**Authority:** [Implementation Status](sotlas_implementation_status.md) and
[Master Roadmap](sotlas_master_roadmap.md).

## Verified boundaries

- The installed Python package comes from `compiler/` (`setup.py` and
  `pyproject.toml`). The production Stage-0 frontend is
  `compiler/sotlas_compile/bootstrap.py`; the SIR generator remains a prototype.
- All 12 numbered examples are listed in `examples/manifest.json` as
  `EXPERIMENTAL`. Four carry a C11 backend smoke contract. That smoke proves
  only `check` and C syntax for those examples.
- The isolated Phase 1 semantic core is certified at `ISOLATED_PHASE1`.
  The certification does not promote the whole language or backend.
- Package version metadata and the runtime version agree at `0.5.1`.
  Package maturity is Alpha. Public README clone and CI links point to the
  current repository.
- The earlier v1 architecture audit is preserved as a historical design note;
  its implementation claims are not current certification evidence.
- `current_implementation_progress.md` was a stale 2026-09-25 snapshot and
  incorrectly called itself canonical. It is now labeled historical and links
  to `sotlas_implementation_status.md` as the current index.

## Open Phase 0 work

1. Audit every public guide and specification example against the canonical
   frontend and label runnable, experimental, or design-only snippets.
2. Resolve the duplicated `compiler/` and `tools/` Python trees. The current
   inventory has 77 paired modules: 73 byte-identical and four different
   (`sotlas/__init__.py`, `sotlas_compile/__init__.py`,
   `sotlas_compile/bootstrap.py`, and `sotlas_compile/language_safety.py`).
   There are 23 Python modules only under `compiler/` and three only under
   `tools/`. The existing parity gate covers the shared modules outside its
   reviewed-difference allowlist; the large bootstrap divergence still needs
   a migration decision before the historical duplication checklist can close.
3. Keep the example manifest, docs, and package metadata under reality gates
   as the implementation changes.

Phase 0 remains open until the guide audit and duplicate-code migration are
complete. CI success alone is insufficient evidence for 100%.
