# Native roadmap checkpoint

**Date:** 2026-10-21
**Repository:** [HPinho/sotlas_dev](https://github.com/HPinho/sotlas_dev)  
**Scope:** the Sotlas-written native compiler and the public preview.

The master phases describe language capabilities. The sovereignty track asks
which of those capabilities work through the Sotlas-written toolchain. A
completed bounded reference contract does not establish complete native parity.
This checkpoint reports executable deliveries and remaining gates separately.

## Delivered native blocks

| Block | What a developer can do |
| --- | --- |
| Embedded ABI | Check actual integer signatures across independently compiled ELF objects |
| Static libraries | Create deterministic libraries and resolve needed members, including transitive/cyclic imports |
| Executable targets | Link the same integer modules into ELF, Windows PE and static Intel Mach-O executables |
| Source-list builds | Compile units independently and build a library/application in one native command |
| Source-list integrity (SV8.88) | Reject duplicate input paths and byte-exact destination collisions with source/library files or manifests before publishing artifacts |
| Lexical path integrity (SV8.89a) | Normalize dot/parent components, repeated separators and Windows ASCII path case before native source-list duplicate and artifact checks; OS file identity remains open |
| No-clobber output mode (SV8.89b) | Create native library/executable artifacts with OS-exclusive creation so pre-existing files, hard links and symlink names are not truncated by opt-in source-list builds |
| Linux file identity (SV8.89c1) | Compare actual Linux x86-64 device/inode metadata for source/library duplicates and output collisions through hard links and symlink aliases, without Python or C |
| Inline record arrays | Store pointer-free record arrays inside structs and initialize, read, mutate, copy and return supported containers |
| Static record data | Serialize constant record configurations, including nested arrays, directly into native data/BSS and use them from native code |
| Global record tables | Declare initialized record lists/repetition, read indexed entries, copy elements and update mutable tables through checked native accesses |
| Match values | Select scalar, nominal enum and POD record results; destructure nested tagged payloads with exhaustive combinations of field filters; use scoped bindings, ranges, grouped/nested alternatives, named record fields, float patterns and value blocks; merge exclusive moves and cleanup |
| Array payloads | Store bounded scalar/record arrays directly in enums; construct, copy, pass/return and capture them; read named exclusive/borrowed POD subjects without consuming their owner |

See the [ABI](native_embedded_abi.md), [libraries](native_static_libraries.md),
[targets](native_library_targets.md), [module builds](native_module_builds.md)
and [record arrays](native_record_array_fields.md) contracts for precise limits.
Static record storage has its own [constant-data contract](native_static_records.md).
Global record arrays are covered by the [table contract](native_static_tables.md).
Scalar match values have a [CFG execution contract](native_match_values.md).
The expanded [POD match release profile](native_match_release_profile.md) records
implemented boundaries. The [payload contract](native_match_payloads.md) covers
constructors, transfer and destructuring; resource runtime dependencies remain open.

## Sovereignty status

| Area | Executable evidence | Remaining work |
| --- | --- | --- |
| Frontend/IR | Native compiler sources rebuild; scalar/record/structured CFG forms, inline arrays and tagged POD payload matches execute | Full canonical acceptance/rejection parity, generics, general resource enums, strings/slices/errors and remaining forms |
| Ownership | Bounded exclusive POD transfers, internal borrows and scoped resource runtime contracts; new POD array containers keep move/borrow checks | General resource payloads, integrated ARC/drop generation, lifetimes/escapes and all domain combinations |
| Backend/linker | Own x86-64 machine emission, objects, regular archives and three executable formats for documented profiles | General aggregate/pointer/foreign signatures, dynamic linking, optimizations/debug/unwind and other promised targets |
| Native tools | Source lists, independent units, native archive/application builds and native seed self-build scripts | Complete module/package resolution, namespace/visibility/mangling, essential tooling and installed CLI parity |
| Bootstrap | A supplied native seed recompiles original compiler sources; next generations prove byte identity for the native profile | Compiler-wide feature parity, final-profile reconstruction and first-seed/distribution independence |

Stage 2/3 identity is real for the implemented profile. It does not imply that
the native compiler accepts the entire master specification. Python/C remain
in hosted bootstrap, reference/tests and parts of the broader tooling until
their replacements pass the corresponding gates. The native post-seed build
path can already operate with host tools absent from PATH.

No whole-roadmap percentage is assigned here: the outstanding items have very
different scope, and a count of small subcontracts would misrepresent closure.
The [native checklist](sotlas_native_frontend_ownership_checklist.md) retains
open parent items while marking the completed executable subsets.

## Public preview status

| Launch gate | Current state | Required before closing it |
| --- | --- | --- |
| P1 application core | Native terminal calculator core and execution gates exist | Confirm the release-platform matrix and installed package behavior |
| P2 platform | Initial Windows window/drawing/input/resource path exists | Finish documented scale/focus/Unicode/error-path coverage |
| P3 UI | Initial declarative components, GUI calculator and UTF-8 labels exist | Close component/storage lifetime and failure-handling contracts |
| P4 examples | Terminal, GUI, independent modules and record-table examples are available | Audit reproducible release instructions, including the declared kernel profile |
| P5 installation | Native seed/build/distribution work exists | Prove the complete advertised installed workflow without mandatory Python/C |
| P6 certification | CI gates exist for compiler, artifacts and preview pieces | Certify one release candidate against the published support matrix |

This does not declare the preview ready for release. Its six launch gates are
tracked in the [preview roadmap](preview_launch_roadmap.md).

## Next closure priorities

1. Expand native language values: strings/slices, payload enums and error paths
   with concrete source-to-machine-code execution gates.
2. Integrate ownership/runtime operations for resource-bearing values, including
   cleanup across returns, branches, loops and deferred work.
3. Carry semantic module contracts into the independent-module path; complete
   visibility and package resolution before claiming general separate compilation.
4. Extend Linux-certified file-ID checks to Darwin and Win32 native APIs,
   then harden all platforms against races and partial output replacement
   without adding Python/C dependencies (SV8.89c2/c3).
5. Close the installed preview and release-platform gates against the actual
   shipped compiler, runtime, examples and extension.

Latest local validation for each delivery and its remote-certification limits
are recorded in the [sovereignty roadmap](sotlas_sovereignty_roadmap.md).
