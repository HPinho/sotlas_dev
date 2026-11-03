# Sotlas sovereignty: active plan

The goal is a usable native toolchain written in Sotlas, with Python and C
optional for interoperability and reference testing. A native seed already
builds and runs the declared profile without host compilers. That profile still
has limits; it is not full parity with the hosted compiler.

## Evidence and current delivery

Last directly verified green baseline: `9084cf8`,
[CI #1345](https://github.com/HPinho/sotlas_dev/actions/runs/41648523027).
The kernel delivery `9f761d8` failed CI #1346 in Mach-O conversion, legacy
C-oracle rebuilding and a historical object-flag expectation. The repair keeps
the raw-entry ELF linker usable by Mach-O conversion, enforces hosted-syscall
rejection in the dedicated kernel command and uses instruction words supported
by both native and legacy oracle emission. Bare-metal flag 4 is recognized;
unknown object bits continue to be rejected. The repaired candidate awaits CI.

The native profile includes
[layout queries and packed records](native_layout_queries.md), checked
[literal dimensions](native_array_dimensions.md),
[named capacities](native_named_dimensions.md),
[tagged result propagation](native_tagged_results.md) and
[explicit payload tags](native_payload_tags.md).

It also provides [fixed-array iteration](native_array_iteration.md),
[concrete optional values](native_optional.md), statement
[pattern control and field iteration](native_pattern_control.md), and
[Result error composition](native_error_composition.md) and
[if-let values](native_pattern_values.md). These share existing
snapshot, cleanup and native ABI paths.

The native profile also includes immutable aggregate constants, independent
POD copies and readonly receiver protection. See
[aggregate constants](native_aggregate_constants.md).

The native profile adds numeric compound updates to writable fields,
fixed-array elements and raw pointer dereferences, with single evaluation of
the address and explicit readonly rejection. Caller-backed f32 CPU kernels
provide dot, scale, AXPY and row-major GEMV, plus an executable projection and
residual example. See [numeric projection](native_numeric_projection.md).
GPU/NPU dispatch and generative model execution remain open.

The current delivery connects the native compiler to an executable kernel boot
path: barecore imports, typed privileged operations, the owned freestanding ELF
linker, a Multiboot image emitter and x86-64 startup. The example boots under
QEMU and verifies handoff, BSS/data, stack, arithmetic/SSE, serial and VGA memory
access before an explicit guest exit. See [kernel boot](native_kernel_boot.md).
Its full platform CI remains pending; complete OS/firmware support is not implied.

The maintainer's requested usability checkpoint is **2026-11-15**. Work follows
the existing roadmap and its closure criteria. Delivery is measured by runnable
capabilities, not helper count or unweighted checkbox percentages; the requested
date does not certify untested features.

## Remaining work, grouped by outcome

| Block | Available | Required to close the block |
| --- | --- | --- |
| Native frontend | Scalar and structured control flow; bounded arrays, records, payload matches, concrete results, raw pointer projections | Contracted generics, strings/slices as language values, module parity, full diagnostics and remaining accepted language forms |
| Resources and runtime | Explicit arenas, reference headers, growing text, reusable slots, checked views and bounded configuration collections | Automatic ARC/drop integration, general lifetime/escape and alias analysis, resource-bearing aggregates and all contracted domain transitions |
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
| SV6: applications/kernel without C11 | Native applications and a reproducible x86-64 kernel boot path execute; general OS, firmware and driver coverage remains separate |
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
