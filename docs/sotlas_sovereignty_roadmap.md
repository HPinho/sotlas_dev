# Sotlas sovereignty: active plan

The goal is a usable native toolchain written in Sotlas, with Python and C
optional for interoperability and reference testing. A native seed already
builds and runs the declared profile without host compilers. That profile still
has limits; it is not full parity with the hosted compiler.

## Evidence and current delivery

Last inspected green baseline: `905c3c3c449268e30b15bf6f26c32ab46dc7366a`,
[CI #1317](https://github.com/HPinho/sotlas_dev/actions/runs/40654740906).
The current delivery adds reusable allocation slots and persistent UTF-8 text
in Sotlas. See [the allocation contract](native_pool.md) for tests and limits.
It is a candidate until its own CI passes.

## Remaining work, grouped by outcome

| Block | Available | Required to close the block |
| --- | --- | --- |
| Native frontend | Scalar and structured control flow; bounded arrays, records, payload matches, concrete results, raw pointer projections | Contracted generics, strings/slices as language values, module parity, full diagnostics and remaining accepted language forms |
| Resources and runtime | Explicit arena, reference-header and cleanup APIs; growing arena text; reusable slots and checked views in this candidate | Automatic ARC/drop integration, general lifetime/escape and alias analysis, resource-bearing aggregates and all contracted domain transitions |
| Machine pipeline | Sotlas Target IR, x86-64 emission, owned object/link paths for ELF/PE/Mach-O | Remaining ABI/resource lowering, promised linking modes, target/debug/unwind coverage and rejection of every unsupported combination |
| Self-build and delivery | Original-source native rebuilds and strict Stage 2/3 equality within the declared profile | Full compiler parity, native packaging/project tools and clean installation/rebuild certification without Python/C |
| User-facing preview | Native executable examples, numeric/results/text APIs and separate kernel/GUI experiments | A reproducible installed application path, documented limits and platform gates for each advertised experience |

These are closure criteria, not a new feature wishlist. Backend and runtime
work must connect to executable programs; helper APIs alone do not complete
language-level ownership or frontend parity.

## Sequence

1. Finish a usable native application path: persistent data, errors, reusable
   storage and installed examples. Reuse existing modules instead of adding
   parallel implementations of the same contract.
2. Connect native resource analysis and cleanup to those programs. Extend the
   accepted language profile only when positive, negative and native execution
   evidence agree.
3. Close frontend/module and machine ABI gaps needed by the compiler itself.
4. Rebuild the complete compiler, certify Stage 2/3 identity, then validate
   installation, development and reconstruction with Python/C absent.

Each delivery should finish a connected block with focused local checks. Full
CI remains the cross-platform certification gate.

## Original milestones

| Milestone | Status |
| --- | --- |
| SV0: certified baseline | Green baseline above |
| SV1: Sotlas Target IR | Implemented for the native profile; broader operations remain gated |
| SV2: native frontend to Target IR | Implemented for the declared profile; parity open |
| SV3: owned x86-64 backend | Executable native profile; broader lowering open |
| SV4: application semantics and ABI | Partial; general resources and frontend parity remain |
| SV5: owned objects and linker | Working ELF/PE/Mach-O paths; full promised linking coverage remains |
| SV6: applications/kernel without C11 | Demonstrations exist; general application/kernel readiness remains separate |
| SV7: native Stage 1 | Available for the bounded compiler profile |
| SV8: Stage 2/3 fixed point | Strict original-source identity within the tested profile; full parity open |
| SV9: independent default toolchain | Open: full parity, distribution and normal-development certification |

## Definition of completion

- All features advertised for the native release have executable acceptance,
  rejection and integration evidence on their supported platforms.
- The complete compiler rebuilds from original Sotlas sources with verified
  seed provenance and identical Stage 2/3 output.
- Installation, `check`, build, run and reconstruction work without Python,
  a C compiler, generated C or a mandatory external linker.
- Optional C/C++/Objective-C/Rust interoperability does not become an implicit
  prerequisite for unrelated Sotlas programs.
- Release documentation and the full platform CI match that evidence.

## Detailed references

- [Frontend and ownership inventory](sotlas_native_frontend_ownership_checklist.md)
- [Architecture and language roadmap](sotlas_master_roadmap.md)
- [Unified language and interoperability inventory](sotlas_unified_language_and_sovereignty.md)
- [Preserved implementation history](sotlas_sovereignty_history.md)

The detailed inventories retain unmet requirements. Historical checkpoints are
kept in the history document instead of being appended to this active plan.
