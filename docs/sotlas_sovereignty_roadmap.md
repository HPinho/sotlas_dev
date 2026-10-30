# Sotlas sovereignty: active plan

The goal is a usable native toolchain written in Sotlas, with Python and C
optional for interoperability and reference testing. A native seed already
builds and runs the declared profile without host compilers. That profile still
has limits; it is not full parity with the hosted compiler.

## Evidence and current delivery

Starting green baseline: `a09afc3` (constant dimensions `c12cd9a`),
confirmed by the user after the full workflow completed. The earlier inspected
[CI #1321](https://github.com/HPinho/sotlas_dev/actions/runs/40840985644) also
certified the UTF-8 collection baseline across all 19 jobs.
The current compiler delivery implements native size, stride, alignment and
field-offset queries, including constant evaluation and dead-code validation.
The pool and map now derive memory-check layouts from their declarations.
See [native layout queries](native_layout_queries.md) for the supported profile.
CI #1325 failed the existing minimal-kernel test because `@packed` was rejected.
The follow-up implements native packed-record layout, unaligned scalar access,
nested records, array stride and by-value copies rather than removing that gate.
The packed packet example is included in all three native host rebuild gates.
The user confirmed that this follow-up completed with a green workflow.
The next delivery adds checked literal arithmetic in fixed-array dimensions
and repetitions across storage, internal calls and POD payloads. See the
[dimension contract](native_array_dimensions.md). The user confirmed green CI
after the public-snippet inventory repair. The current candidate resolves
unsigned module constants in array shapes and repetitions, sharing lexical
binding checks across storage, internal ABI, payloads and deferred POD borrows.
See [named dimensions](native_named_dimensions.md); its CI certification is pending.

## Remaining work, grouped by outcome

| Block | Available | Required to close the block |
| --- | --- | --- |
| Native frontend | Scalar and structured control flow; bounded arrays, records, payload matches, concrete results, raw pointer projections | Contracted generics, strings/slices as language values, module parity, full diagnostics and remaining accepted language forms |
| Resources and runtime | Explicit arenas, reference headers, growing text, reusable slots and checked views; bounded configuration collection in this candidate | Automatic ARC/drop integration, general lifetime/escape and alias analysis, resource-bearing aggregates and all contracted domain transitions |
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
