# Sotlas: Unified Language, Interoperability and Toolchain Roadmap

**Repository:** [HPinho/sotlas_dev](https://github.com/HPinho/sotlas_dev)

**Snapshot:** 2026-10-14, America/Sao_Paulo

**Source revision:** `b40a8fa` plus the SV8.50 local candidate

**Purpose:** one English reference for implemented contracts, remaining language work,
optional foreign interoperability and removal of mandatory Python/C toolchain dependencies.

## Contents

1. [Reading the status](#1-reading-the-status)
2. [Current implementation](#2-current-implementation)
3. [All roadmap phases](#3-all-roadmap-phases)
4. [Language feature inventory](#4-language-feature-inventory)
5. [Ownership domains](#5-ownership-domains)
6. [C, C++, Objective-C and Rust interoperability](#6-c-c-objective-c-and-rust-interoperability)
7. [Ten toolchain independence requirements](#7-ten-toolchain-independence-requirements)
8. [SV0 through SV9 and compiler generations](#8-sv0-through-sv9-and-compiler-generations)
9. [Kernel and application tracks](#9-kernel-and-application-tracks)
10. [Runtime, standard library and tooling](#10-runtime-standard-library-and-tooling)
11. [Acceptance and release gates](#11-acceptance-and-release-gates)
12. [Complete native migration checklist](#12-complete-native-migration-checklist)
13. [Detailed native driver contract](#13-detailed-native-driver-contract)
14. [Standard library API contracts](#14-standard-library-api-contracts)
15. [Documentation source inventory](#15-documentation-source-inventory)
16. [Standard library function inventory](#16-standard-library-function-inventory)

## 1. Reading the status

This is a topic-based consolidation of the tracked project Markdown documents.
The source inventory records every input document. Repeated material is grouped,
historical snapshots are identified, and the current native contracts are included
in full in sections 12–14. Original documents remain available for provenance.
Portuguese architectural material is summarized in English here.

There are three distinct scopes:

- **Canonical/reference path:** the Python frontend and its contracted C11/LLVM
  implementations. Some language features are implemented only in this path.
- **Sotlas-written native path:** the bounded lexer/parser/sema/Target IR/x86-64
  compiler, object writers, linkers and OS file drivers written in Sotlas.
- **Full architectural roadmap:** the broader language, runtimes, hardware,
  applications and ecosystem goals, including work outside the 1.0 release subset.

| Label | Meaning in this document |
|---|---|
| Implemented subset | A bounded implementation with identified tests or contracts |
| CI-certified subset | The documented revision passed the named CI gates for that scope |
| Candidate | A newer implementation whose certification is still pending |
| Partial | A useful subset exists; the complete requirement remains open |
| Planned | Design or backlog exists; production execution is not established |
| Historical | A dated report retained as evidence of an earlier state |

An unchecked parent requirement can contain completed subitems. A release-phase
label of “100%” applies to its frozen subset; it does not certify full native
frontend parity or complete removal of hosted build dependencies.

The Sotlas code fences reproduced in this consolidation are classified as
`DESIGN_ONLY` in `docs/public_snippets.json`: a copied snippet is not itself
a new executable acceptance test. Existing native/reference feature tests,
platform gates and the original source documents establish which bounded
contracts have actually executed. CLI command fences are illustrative
invocations and may require the stated seed, platform or toolchain. The historical
sovereignty checkpoint score measures selected architectural milestones, not the
percentage of Python/C dependencies eliminated or the amount of work remaining.

**Evidence boundary:** the latest inspected green baseline is `ce93fa9`,
CI #1221 / run `38621972769`. The subsequent #1222 rejection-contract regression
was repaired in `b40a8fa` with the SV8.49c ownership work and local regression
validation. This document describes the newer SV8.50 candidate. Its local gates
are recorded below; CI certification remains pending.

## 2. Current implementation

SV8.50 adds 36 bounded contracts across nine migration areas. Section 12 lists
the four advances per area and their gates. The explicit Sotlas runtime contains
arenas, local reference control blocks and authority/state/range guards. These
do not establish automatic ARC or full canonical ownership/effect/state parity.
Native pointer conversions, IR/object preflight, CLI reports and bootstrap audit
commands are implemented; broader migration parents remain open.


### 2.1 Native compiler and execution

- Lexer, parser, semantic checks, flat Target IR lowering and x86-64 machine
  emission execute in the Sotlas-written compiler for the documented profile.
- Linux, Windows and Intel macOS have native file-driver and generation gates.
- Given a native seed, the documented paths compile their original Sotlas source
  modules and generate applications without invoking Python, a C compiler or an
  external linker. The hosted bootstrap remains relevant to initial distribution.
- Stage 2/3 native generation identity is documented for the compiler-source
  profile. This does not establish complete canonical language parity.
- Native execution covers fixed-width integers, bounded floating operations,
  pointers under explicit safety checks, POD records, supported arrays,
  structured branches/loops, early returns and the documented match/defer subsets.
- The native writer/linker supports bounded ELF objects and executable images,
  with PE and static Intel macOS Mach-O driver paths. Object generation does not
  itself certify dynamic libraries, every foreign ABI or boot on physical hardware.
- Imports and project discovery use bounded native source resolution. Separate
  compilation and complete package semantics remain migration requirements.

### 2.2 Recent native semantic work

- Exclusive POD moves, consuming calls, returns and branch-state joins.
- Read-only `direct`/`whisper` parameters and matched instance receivers, including
  `Self`; direct record arguments use existing storage.
- Scalar record/array projections can be converted without allowing whole-owner
  or pointer escape.
- Typed scalar array field lists/repetition and independent field copies.
- Instance-method result inference and receiver identity validation.
- Ownership merging for runtime Boolean short-circuit paths.
- Qualified deferred read calls and bounded read-only deferred call blocks,
  with lexical reservations and rejection of consumption before cleanup.
- Specific native ownership diagnostics with source locations.
- Bounded effect-free deferred argument proofs across eligible internal calls.
- Typed Call metadata for plain/sole/whisper/direct roles, with capacity checking,
  callee-signature validation and distinctions for hidden record-result pointers.
- SV8.48d–g strengthens typed direct-call preflight at documented native emitter
  boundaries. Cross-object and full effect/capability guarantees stay open.

### 2.3 Reference implementations that still require migration

The canonical path has bounded ownership-domain, authority, state, effect,
Flow, guarantee, causality, counterfactual, transaction and Intent contracts.
These implementations and their tests are valuable reference behavior. Their
existence does not mean their complete semantics execute in the Sotlas-written
native toolchain. Sections 3–7 and the full checklist identify the remaining work.

## 3. All roadmap phases

Phase numbers follow Part II of the master roadmap. Part I preserves an older
ordering. The implementation-status document reports frozen 1.0 phase contracts
as complete; broader coverage and native migration remain separate obligations.

| Phase | Area | Implemented/documented work | Remaining full/native work |
|---:|---|---|---|
| 0 | Reality reset | Metadata, claims, examples, baseline and phase gates | Keep installed-path, platform and documentation evidence synchronized |
| 1 | Typed semantic core | Canonical typed AST/checker; bounded native name/type/return checks | Full native type inference, generics, diagnostics, symbols and package parity |
| 2 | Ownership domains | Canonical domain subsets; native exclusive POD and read-only borrow subsets | Native ARC/drop, region lifetimes, island isolation, weak invalidation, device/external and general cleanup |
| 3 | Authority domains | Checked capability/privilege subsets and explicit unsafe boundaries | Native capability values/graphs, delegation and complete target/FFI enforcement |
| 4 | State spaces | Contracted state/transition/refinement and coverage checks | Native state semantics, general CFG integration and runtime transitions |
| 5 | Effects | Canonical summaries/contracts; bounded native deferred-call proofs and call-role metadata | General native effect inference, transitive signatures and independently compiled module proofs |
| 6 | Flow | Checked graphs; CPU reference execution and bounded serial C11 plans | Owned native graph execution, general payloads/CFG, scheduling, failure/cancel ABI and native devices |
| 7 | Execution domains | Target contracts/reports; native x86-64 hosted and freestanding profiles | Additional architectures, complete ABI/capability lowering and broad domain runtime coverage |
| 8 | Heterogeneous compute | DEVICE reference provider and experimental OpenCL vector-add interop | Flow GPU/NPU lowering, DMA/device memory, asynchronous completion, scheduling and hardware failure recovery |
| 9 | Trust domains | Bounded foreign/enclave/trust checks and external-wrapper contracts | Native boundary semantics, broad foreign linking, marshalling and verified domain crossings |
| 10 | Guarantees | Contracted guarantee/precondition/postcondition analysis and guards | Native proof/guard parity, general bounds proofs and target-specific executable guarantees |
| 11 | Causality | Deterministic source/Flow causal reports and bounded provenance | Native semantic provenance, mutation/heap/CFG tracking and interactive causal debugger |
| 12 | Counterfactuals | Deterministic stage-availability/change impact analysis | Richer changes, native replanning, state/ownership/effect reconciliation and interactive exploration |
| 13 | Transactions | Sequential reference compensation and reverse dependency-order audit | Native journals, verified inverses, unwind, crash recovery, concurrency and external-effect policies |
| 14 | Intent | Explicit deterministic preferred/fallback planning API | Declarative source syntax, typed goals/guarantees and ownership-integrated native scheduling |
| 15 | Canonical SIR | Checked canonical subset; Sotlas-owned numeric Target IR with CFG/call validation | All language bodies and semantic domains, serialization, separate-module contracts and full runtime lowering |
| 16 | Native machine backend | LLVM reference subset plus owned bounded x86-64 writer/linker | General ABI, instruction coverage, allocation/optimization, dynamic linking, unwind/debug data and additional targets |
| 17 | Advanced tooling | CLI reports, source maps, VS Code/LSP and inspection tools | Native tooling parity, interactive domain/state/authority views, debugger/profiler and ABI/register/stack visualization |

## 4. Language feature inventory

### 4.1 General syntax and types

| Feature family | Existing implementation | Remaining work |
|---|---|---|
| Modules/imports/namespaces | Canonical resolution; bounded native graph/source resolution | Visibility/import aliases, complete dependencies and separate object compilation |
| Functions and bindings | Typed functions, mutable locals, calls, returns and native source checks | Remaining receivers, function values/indirect calls and canonical acceptance parity |
| Primitive integers | Signed/unsigned fixed widths, checked native operations and conversions | Full backend promotion/overflow parity and remaining literal forms |
| Floating values | Bounded f32/f64 arithmetic/comparisons/buffers and internal bit-pattern ABI | Wider literals, complete conversions/library math and foreign floating ABI |
| Boolean values | Conditions, logic, arrays and short-circuit paths | Remaining type/coercion and general control-flow combinations |
| Records/structs | POD layout, nested fields, value copies, native calls/returns | Resource-bearing fields, broader aggregate forms and complete foreign layout |
| Enums/ADTs | Canonical payload forms; native scalar explicit discriminants | Native payload layout, constructors, patterns and destruction |
| Arrays/indexing | Native scalar and pointer-free local record arrays; scalar array fields | Slices/slicing, arrays in general parameter/return positions and owned element lifetimes |
| Strings | Native compiler literal handling; tested stdlib byte/string contracts | First-class native strings/slices and ownership-integrated allocation/destruction |
| Generics | Canonical/experimental source constructs | Native generic resolution, monomorphization, generic aggregates/methods and libraries |
| Recursive types/calls | Bounded call/recursion contracts and native ABI evidence | General recursive resource layouts, runtime limits and broad ABI parity |
| Control flow | Structured branches/loops, break/continue, early returns and conditional values | General CFG, remaining expression bodies, all-path analyses and owned non-POD payloads |
| Match/discern | Native scalar/Boolean/explicit-enum match with coverage checks | Payload patterns/bindings, guards, ranges and match expressions |
| Constants/statics | Bounded typed scalar folding, forward dependencies and static scalar arrays | Aggregate/string/pointer initializers, wider numeric forms and complete constant evaluation |
| Errors/Option/Result | Canonical error forms and tested scalar library result records | Full native propagation, payloads, cleanup and unwind policy |
| Classes/shared resources | Canonical/reference subsets and runtime helpers | Native class/resource layouts, constructors/destructors and integrated ARC |

### 4.2 Sotlas-specific vocabulary and semantics

Reserved vocabulary describes intended semantics. Token recognition, highlighting
or an illustrative example does not establish production backend support.

| Construct | Intended role | Implementation boundary / remaining obligation |
|---|---|---|
| `sole`, `exclusive` | Exclusive owner and explicit transfer | Native POD subset; resource-bearing ownership and drop remain open |
| `shared`, `co-owned` | Explicit shared ownership/accounting | Canonical ARC subset; full native shared runtime remains open |
| `region` | Lifetime-bounded ownership | Reference no-escape/arena subsets; native lifetime graph remains open |
| `island` | Isolated ownership subgraph | Reference transitions; general alias isolation and physical confinement remain open |
| `whisper` | Immutable non-owning access; broader weak-reference design | Native call/receiver/deferred-read subset; stored weak references/invalidation remain open |
| `direct` | Access with explicit lifetime and no reference-count bookkeeping | Native read-only POD access; stored/general alias graphs remain open |
| `handover` | Explicit resource/cleanup responsibility transfer | Tested reference transitions; full native domain transition runtime remains open |
| `quarantine` | Isolation transition and incompatible alias invalidation | Static/reference subset; runtime weak invalidation and native generality remain open |
| `device` | Ownership of device-associated resources | Reference provider contract; physical device lifecycle/synchronization remains open |
| `external` | Foreign-owned resources and boundary policies | Reference wrappers; native FFI ownership and transfer closure remain open |
| `unsafe` | Explicit departure from checked safety assumptions | Implemented subsets; complete native audit/foreign validation remains open |
| `@system`, `capabilities`, `permits` | Authority to perform operations | Canonical subset; complete native authority graph and grants remain open |
| `effects`, `irqfree`, `@interrupt`, `@realtime` | Effect, interrupt and realtime contracts | Bounded verification; complete native signatures, ABI and runtime guarantees remain open |
| `barecore` | Freestanding compilation profile | Documented kernel/object/link profile; complete boot/runtime/hardware proof remains open |
| `*rawphys`, `*virtmap`, `*portwire`, `*dmazone` | Physical, virtual, port-I/O and DMA topologies | Reserved/target-specific contracts; full ordering, mapping/coherence and native lowering remain open |
| `*voidzero` | Opaque untyped pointer role with explicit conversions | Full contract must follow the master vocabulary; no universal null-trap guarantee is inferred |
| `mesh` | Explicit physical aggregate layout | Existing source/layout subset; general target layout and hardware integration remain open |
| `clinch`, `revert`, `rebound` | Critical-section entry, restoration and controlled exit | Source/design subsets; complete restoration on all exits and target execution remain open |
| `quench`, `gate` | Explicit ordering/persistence barrier and hardware guard | Target-dependent semantics and failure behavior need full native gates |
| `trapfn` | Interrupt handler with ISR ABI | Complete native interrupt ABI, stack/effect rules and hardware execution remain open |
| `probe`, `pulse` | Observability/verification point and deterministic event | Broad native event/instrumentation contracts remain open |
| `spec`, `adopts` | Verifiable API/protocol and conformance | Canonical/design subsets; native conformance and contract lowering remain open |
| `mould`, `moldable`, `reshape`, `forge` | Explicit specialization/override/generic construction | Final syntax/dispatch and native specialization need their own acceptance gates |
| `capsule`, `lineage` | Module/hierarchy visibility | Complete canonical and native visibility parity remains open |
| `shielded`, `nvkeep`, `seal` | Protected state, persistence and post-initialization immutability | Full target memory/persistence/concurrency semantics remain open |
| `.slit`, `.notch`, `.strand`, `.bound` | Bit ranges, bit tests, byte order and value-range refinement | Numeric primitives exist; complete accessor syntax/proofs and target lowering remain open |
| `space`, `state`, `view`, `when` | State-space declarations, refinements and observation | Canonical subset; full native typed/state runtime integration remains open |
| `guarantee`, `requires`, `ensures`, `proof` | Guarantees, executable contracts and proof obligations | Canonical subset; complete native guards/proof coverage remain open |
| `flow`, `compute`, `@target` | Dependency graph and explicit execution/device planning | Reference execution exists; owned native heterogeneous graph execution remains open |
| `intent` | Explicit desired outcome and admissible plans | Planning API subset; declarative native syntax/semantics remain open |
| `why`, `explain` | Causal explanation from verified semantic facts | Bounded reports; native integrated provenance/debugging remains open |
| `whatif`, `change` | Counterfactual change and affected dependents | Bounded analysis; general native replanning remains open |
| `transaction` | Reversible/compensatable/irreversible effect policy | Reference compensation; native journals/unwind/concurrency remain open |
| `enclave`, `trusted`, `isolated` | Explicit trust/isolation boundaries | Canonical/design subset; native boundary marshalling/enforcement remains open |
| `defer` | Lexical LIFO cleanup | Native bounded calls/assignments/blocks and readonly reservations; full owned cleanup/unwind remains open |

The architectural model also includes causal graphs, program knowledge graphs,
explainable compilation, safety manifests, deterministic execution, structured
concurrency/cancellation, dependency-derived parallelism, transactional effects
and state-driven UI. These are separate implementation obligations; preserving
their vocabulary is not evidence that each has a complete native runtime.

## 5. Ownership domains

| Domain | Canonical/reference evidence | Native profile | Still required |
|---|---|---|---|
| Exclusive | Moves, transfer/branch checks and bounded destruction | Fixed scalars and pointer-free POD records, including scalar array fields | Owned nested payloads, aliases and general exactly-once drop |
| Shared | Tested aliases, ARC accounts and cleanup/destruction paths | Metadata/rejection for unsupported execution; no complete native ARC | Allocation, retain/release, drop glue, all accepted paths and cycle policy |
| Region | Tested no-escape calls/aggregates and arena behavior | Complete native lifetime semantics remain open | Lifetime graph, arbitrary escapes, arena reset/reuse and call/return identity |
| Whisper | Call-scoped no-escape subset | Read-only POD calls/receivers and bounded deferred reads | Stored weak handles, invalidation, foreign and indirect boundaries |
| Direct | Explicit call-scoped no-transfer access | Original-storage POD borrowing, forwarding and overlap rejection | Stored aliases, general lifetimes/CFG and remaining capture forms |
| Island | Graph/isolation and selected transfer checks | Complete native domain implementation remains open | Stored alias restrictions, resource runtime and any promised physical confinement |
| Device | Reference ABI/provider and lifecycle tests | General physical execution remains open | Memory ownership, queues, completion, synchronization, failure and reacquisition |
| External | Foreign wrapper/layout/cleanup subsets | Complete native foreign ownership remains open | Caller/callee obligations, allocation provenance, callbacks and linking |
| Handover/quarantine | Selected checked reference transitions | General native transitions remain open | Every declared source/destination, invalidation and cleanup transfer |

All domains must integrate with bindings, fields, arrays, globals, calls, returns,
branch/loop merges, `defer`, errors and backend-neutral lowering. Unsupported
execution must produce an explicit diagnostic before artifact publication.

## 6. C, C++, Objective-C and Rust interoperability

### 6.1 Product decision

Sotlas will support optional interoperability with **C, C++, Objective-C and Rust**.
The first common boundary is the target's C ABI. A C ABI is a binary calling and
layout contract; it does not require generating C source or installing a C
compiler to compile a pure Sotlas program.

Building a foreign component may require its own compiler/runtime. Those are
optional project dependencies: C/C++/Objective-C tools for those components,
and Rust tools for Rust components. The Sotlas frontend/backend/runtime must
remain independently usable without any of them installed.

| Language | Initial boundary | Existing Sotlas repository evidence | Remaining acceptance |
|---|---|---|---|
| C | Imported/exported target C ABI functions and explicit layouts | `include/sotlas/sotlas_abi.h`, unsafe FFI tests and C interop examples/reference paths | Complete owned native foreign ABI, callbacks, libraries and bidirectional platform execution |
| C++ | C-linkage wrappers around C++ APIs | Header C++ linkage support and wrapper-oriented interop design | Build/run real C++ producer and consumer, opaque handles, errors, destruction and toolchain matrix |
| Objective-C | C ABI bridge to Objective-C objects/runtime | `objc_bridge.m` example and bridge-oriented design | Runtime execution on supported platforms, retain/release/autorelease/thread policies and error translation |
| Rust | `extern "C"` boundary, explicit `repr(C)` layouts and opaque handles | New planned contract in this consolidation; no dedicated Rust execution gate established here | Rust producer/consumer fixtures, native Sotlas linking, ownership/panic policies and platform CI |

This table does not promote examples or headers to full native interoperability.
Direct C++ class ABI, native Rust ABI and automatic Objective-C message dispatch
are separate future contracts.

### 6.2 Shared FFI contract

- [ ] Freeze symbol naming, visibility and linkage per supported target.
- [ ] Specify parameter/return classification, stack alignment and aggregate layout.
- [ ] Define fixed-width scalars, enums, buffers, pointer+length views and opaque handles.
- [ ] Specify nullability, alignment, bounds, mutability and lifetime obligations.
- [ ] Distinguish borrowed, transferred, retained and externally owned resources.
- [ ] Keep allocator/free pairs in their owning component; prohibit unverified cross-allocator frees.
- [ ] Define callback registration, context lifetimes, threading and unregistration.
- [ ] Define explicit error/status returns and prevent uncertified unwind across the boundary.
- [ ] Validate calling-convention/layout mismatches and reject unsupported signatures.
- [ ] Generate/export bindings from one reviewed ABI description.
- [ ] Support the necessary object/archive/library formats in the owned native linker.
- [ ] Run both directions on Linux, Windows and the declared macOS targets.
- [ ] Verify a pure Sotlas install/build/self-build with all foreign compilers absent.

### 6.3 C

- [ ] Import C functions/globals and export Sotlas functions under the target ABI.
- [ ] Test scalar, pointer, aggregate and callback signatures in both directions.
- [ ] Specify `repr(C)`/physical layout, alignment, padding and enum representation.
- [ ] Reject variadic or other signatures until their exact target ABI is implemented.
- [ ] Support static/dynamic library loading only when the selected native target promises it.
- [ ] Publish generated declarations and versioned ABI compatibility tests.

### 6.4 C++

- [ ] Start with C-linkage wrapper functions and opaque handles for C++ objects.
- [ ] Wrap constructors/destructors; state exactly who destroys each handle.
- [ ] Catch exceptions in the C++ adapter and return a defined error/status.
- [ ] Keep templates, overloaded names, vtables, STL containers and C++ references
  inside the foreign component unless a separate target-specific ABI is certified.
- [ ] Test GCC/Clang/MSVC combinations actually promised by the project.
- [ ] Treat direct class ABI, RTTI and exception interoperability as later explicit milestones.

C++ ABI includes layout, naming, calling and exception machinery; the
[Itanium C++ ABI specification](https://itanium-cxx-abi.github.io/cxx-abi/abi.html)
illustrates the scope beyond a C-linkage wrapper.

### 6.5 Objective-C

- [ ] Use C ABI bridge entry points with opaque object handles initially.
- [ ] Specify borrowed/retained return and argument ownership, release and autorelease pools.
- [ ] Define nil/null behavior, thread affinity, callbacks and cancellation.
- [ ] Translate Objective-C exceptions/errors within the bridge.
- [ ] Test Foundation/runtime integration on the explicitly supported platform.
- [ ] Add selectors, blocks and direct runtime dispatch only with separate ABI and lifetime gates.

Objective-C ownership conventions need an explicit bridge policy. See the
[Clang ARC specification](https://clang.llvm.org/docs/AutomaticReferenceCounting.html).
Sotlas shared ownership and Objective-C ARC are not interchangeable accounts.

### 6.6 Rust

- [ ] Import Rust-exported C ABI functions and let Rust import Sotlas C ABI exports.
- [ ] Use explicit C-compatible layouts and pointer+length views/opaque handles.
- [ ] Keep `String`, `Vec`, trait objects, Rust-layout enums and ownership-bearing
  Rust internals behind reviewed wrappers; do not infer layout from type names.
- [ ] Define destruction functions for Rust-owned allocations and handle transfers.
- [ ] Define panic handling inside Rust adapters; do not permit uncertified cross-boundary unwind.
- [ ] Test borrowed buffer lifetime, mutation exclusivity and callback context release.
- [ ] Build static/shared foreign artifacts according to the target/linker contract.
- [ ] Add bidirectional Rust/Sotlas execution and negative ABI tests to CI.

Rust's native ABI has no stability guarantee. The initial planned boundary uses
its explicit C ABI and reviewed layouts. See the
[Rust ABI reference](https://doc.rust-lang.org/reference/items/external-blocks.html)
and [type-layout reference](https://doc.rust-lang.org/reference/type-layout.html).

### 6.7 Other boundaries

Assembly, operating-system APIs, firmware and device APIs remain part of the
systems roadmap. Java/JNI, managed runtimes, Swift, scripting languages and
WebAssembly host bindings require separate plans and are not added to the
implemented support list by this document.

## 7. Ten toolchain independence requirements

These are the ten requested exit conditions for removing Python and C as mandatory
toolchain dependencies. Each stays open until its complete declared scope passes.

### 7.1 Native frontend parity

- [ ] Migrate every contracted canonical acceptance/rejection rule.
- [ ] Complete typed AST, symbol/namespace/visibility/import and package resolution.
- [ ] Complete inference/coercions, generics, methods, payload enums, match,
  arrays/slices/strings, errors, constants and numeric forms.
- [ ] Preserve source positions and provide consistent diagnostics across check/compile/run.
- [ ] Compile separate modules with compatible public semantic/ABI descriptions.

### 7.2 Complete native ownership

- [ ] Complete all declared ownership domains and transitions.
- [ ] Prove lifetimes, aliases, moves, escapes and merges for accepted CFGs/payloads.
  - [x] SV8.49a bounded native owner-state merge for identical nested loop exits; full CFG joins remain open.
  - [x] SV8.49b native mixed break/continue edges preserve outer sole owners, with deferred cleanup and negative ownership gates; general CFG edges remain open.
- [ ] Integrate bindings, arrays, aggregates, globals, calls, returns and cleanup.

### 7.3 Runtime in Sotlas

- [ ] Implement allocation, retain/release, destruction and drop glue in Sotlas.
- [ ] Complete early-return/defer/failure cleanup and exactly-once destruction.
- [ ] Define weak invalidation, external allocation and device completion behavior.
- [ ] Execute runtime integration tests without C-generated runtime glue.

### 7.4 States, effects, contracts and Flow

- [ ] Migrate canonical state/transition/effect/authority/contract validation.
- [ ] Preserve and validate those facts through native IR and object boundaries.
- [ ] Execute contracted Flow graphs, payloads, errors and cancellation natively.
- [ ] Add device execution only when discovery, buffers, synchronization and fallback are validated.

### 7.5 Sufficient owned backend and ABI

- [ ] Lower every accepted feature to implemented machine instructions/runtime operations.
- [ ] Complete accepted calls, aggregates, memory, layout, stack and register rules.
- [ ] Preserve checks/metadata or reject unsupported target/backend combinations explicitly.
- [ ] Provide the additional targets and optimization/debug/unwind behavior the release promises.

### 7.6 Objects and linking

- [ ] Generate/link the compiler, runtime, libraries and representative applications with owned tools.
- [ ] Complete required relocations, symbols, archives, entry/layout and library forms.
- [ ] Support declared foreign ABI/library boundaries without C intermediate output.
- [ ] Validate freestanding images separately from hosted process executables.

### 7.7 Native CLI and developer tools

- [ ] Install, resolve projects/dependencies, check, compile and run without starting Python.
- [ ] Complete native argument handling, diagnostics, configuration and artifact management.
- [ ] Define which formatter/LSP/package/build/testing tools are included in the independence claim.
- [ ] Replace any mandatory hosted helper in those user-facing paths.

### 7.8 Reproducible bootstrap

- [ ] Produce a reviewed native Stage 1 seed with versioned source/artifact provenance.
- [ ] Build Stage 2 from original Sotlas modules using Stage 1.
- [ ] Build Stage 3 using Stage 2 and prove the declared fixed point.
- [ ] Execute representative programs with the rebuilt compiler, including new full-parity features.
- [ ] Reproduce the chain with Python/C tools unavailable after seed acquisition.

### 7.9 Independent distribution

- [ ] Deliver native binaries, runtime/libraries, sources and ABI/profile metadata.
- [ ] Verify clean install, upgrade and self-build on every supported OS/architecture.
- [ ] Reject mismatched seeds, damaged packages and incompatible profiles clearly.
- [ ] Validate checksums/provenance, licensing and reproducible packaging.
- [ ] Ensure ordinary users do not need Python, pip, a C compiler or an external linker.

### 7.10 Retire mandatory hosted dependencies

- [ ] Audit launchers, build/packaging scripts, generated artifacts, examples and docs.
- [ ] Replace each mandatory Python/C step with its proven native counterpart.
- [ ] Keep reference/oracle tools optional and document any foreign-project tool requirements.
- [ ] Archive or remove obsolete bootstrap files only after replacement and recovery gates pass.
- [ ] Run a dependency-absence audit over install, use, self-build and release production.

Python/C files can remain as optional reference history after independence is
achieved. Their presence on disk and their necessity for the toolchain are
different questions. Deleting working bootstrap code does not prove independence.

## 8. SV0 through SV9 and compiler generations

| Milestone | Goal | Current scope | Required broader closure |
|---|---|---|---|
| SV0 | Green baseline | Named historical baseline gates | Preserve every declared platform/regression gate |
| SV1 | Target IR written in Sotlas | Numeric identities, flat tables and validated semantic opcodes | Represent all accepted language/effect/ownership facts |
| SV2 | AST/sema to owned Target IR | Compiler-source and bounded native language lowering | Full canonical frontend and module parity |
| SV3 | Owned x86-64 machine generation | Working bounded machine/object path | General ABI/instruction/runtime coverage |
| SV4 | Real-program CFG/calls/aggregates/semantics | Useful structured/POD subsets | Resource payloads, state/effect/ownership runtime and arbitrary accepted CFG |
| SV5 | Owned object writer/linker | Bounded objects, hosted/freestanding images and platform paths | Libraries, broader relocations/ABIs and complete foreign linking |
| SV6 | Application/kernel without C11 | Declared application/kernel object/image gates | Real workload breadth and boot/firmware/hardware execution |
| SV7 | Native Stage 1 | OS seeds run documented production core | Full language coverage and independent distribution on every target |
| SV8 | Stage 2/3 fixed point | Original-source native identity for declared profiles | Full compiler parity and representative feature/runtime coverage |
| SV9 | Native path becomes normal | Native default and documented installed Linux seed closure | Remove remaining mandatory hosted bootstrap/tooling dependencies |

Stage 0 is the initial bootstrap/oracle. Stage 1 is the first native compiler;
Stage 2 is built by Stage 1; Stage 3 is built by Stage 2. Generation identity
proves reproducibility of the tested profile, not support for omitted features.

SV8.48g adds bounded legacy single-function self-call preflight and conditional
side-table rejection. SV8.49a (candidate after the green CI #1220) additionally
lets the Sotlas-written ownership analyzer propagate uniform break/break or
continue/continue outcomes through nested if/else while merging sole owner
states. Moves on loop backedges and uncertain break exits fail closed.
SV8.49b (candidate after green CI #1221) accepts mixed break/continue
branches only with independently checked, unchanged live owner states and
lexical defer cleanup. CI #1222 exposed an outdated SV8.49a negative test for
that newly supported case; SV8.49c preserves it as execution coverage and adds
a consuming-condition rejection. SV8.49c also separates break/continue states:
consumption is allowed only on terminating break paths, post-loop use becomes
MAYBE_MOVED, direct match-arm exits propagate and nested loop summaries are
restored. General fallthrough/jump and nested mixed match-arm exits remain open.
SV8.48h remains the separate-module/foreign capability workstream; broader
resource-bearing loop-edge joins, ARC, lifetime enforcement and complete
effects are still open.

## 9. Kernel and application tracks

### 9.1 Kernel / barecore K0–K14

The full plan defines these exit goals. Its kernel status table is an earlier
snapshot; newer native object/link milestones must not be mistaken for QEMU boot.

| ID | Goal | Remaining acceptance boundary |
|---|---|---|
| K0 | Freestanding target profile | Preserve explicit profile/hosted-dependency rejection |
| K1 | Kernel source/ABI bootstrap | Freeze boot frame, entry and caller/callee contract |
| K2 | Real freestanding object | Verify compiler-produced objects on declared targets |
| K3 | Freestanding linker | Verify entry, sections, relocations and image layout |
| K4 | Startup/boot ABI | CPU/stack initial state, bootloader handoff and actual entry |
| K5 | Sections/image layout | text/rodata/data/bss alignment, addresses and special symbols |
| K6 | Bootable image | Build image for the selected boot protocol without hosted startup |
| K7 | QEMU boot | Boot to Sotlas entry and verify a deterministic marker |
| K8 | Early diagnostics | Working serial/framebuffer and freestanding panic/trap path |
| K9 | CPU initialization | GDT/IDT/exceptions/IRQ with certified interrupt ABI |
| K10 | Memory management | Memory map, pages, paging, address spaces and allocator |
| K11 | Timer/scheduler | Clock, interrupts and minimal checked scheduling |
| K12 | Drivers/MMIO/PCI/DMA | General primitives plus a real driver execution gate |
| K13 | UEFI/PE-COFF | Firmware ABI/entry/image and virtual firmware execution |
| K14 | Predominantly Sotlas kernel/toolchain | Validated native compiler/runtime and kernel without ad hoc mandatory bridges |

The same language frontend, IR, ownership/effects and ABI foundations serve
applications, kernels, drivers, firmware, bootloaders, libraries and the compiler.
OS-specific adapters remain explicit. A kernel image/link test does not certify
an operating system, scheduler or working hardware driver.

### 9.2 Shared foundations and vertical products

| Track | Complete target capability | Current boundary |
|---|---|---|
| Language/machine foundations | Types, semantic checks, ABI, memory and compiler correctness | Bounded implementations; general migration open |
| Runtime/OS foundation | Allocation, strings, files, time, randomness, threads, synchronization and libraries | Tested concrete APIs and platform adapters; full native closure open |
| NUM | Scalar math, SIMD, tensors/views, linear algebra and parallel numerics | Bounded scalar backend; general SIMD/tensor stack open |
| H | Providers, device memory, GPU/NPU kernels and multi-device scheduling | Reference provider/OpenCL workload; general native heterogeneity open |
| APP | CLI, services, desktop apps and production application gate | Examples and native programs; broad application runtime open |
| UI | Frame clocks, windows/input, graphics/compositor, animation and UI state | Architectural/library goals; no universal production UI claim |
| GAME | Timing, data-oriented memory, ECS, math, RHI/rendering, assets, scenes, animation, physics, audio, networking and editor | Examples/design tracks; complete game stack requires workload gates |
| AI | Tensors, CPU/GPU/NPU operations, graphs, autograd, optimizers, data, training, inference and model interchange | General AI execution/library track remains open |
| HPC | Numerical reliability, parallel CPU, devices, distributed execution and scientific ecosystem | General performance/reliability gates remain open |
| DATA | Binary layouts, file/block I/O, networking, servers, storage engines and database proof | Concrete low-level pieces; production workloads require integration |
| MEDIA | Realtime foundation, audio, image/video and streaming | General codecs/device/runtime integration remains open |
| WEB | WASM target/backend, browser interop and WASI | Separate target/tooling roadmap; website build is not WASM backend support |
| SH | Native modules, stages, fixed point, owned backend and sovereignty | Profile generation proven; full language/dependency closure open |
| TOOL | CLI, format/lint, LSP, packages, builds, tests, debugger/profiler, IDE and ecosystem | Existing tools include hosted components; complete native parity open |

## 10. Runtime, standard library and tooling

### Explicit native Sotlas runtime API (SV8.50)

The source [managed.sotlas](../runtime/native/managed.sotlas) has no foreign
calls. Use the current explicit-source native project profile with this library
and an application. The caller supplies storage and valid pointer lifetimes.
Automatic ownership lowering, heap allocation, atomic ARC and full canonical
state/effect inference remain open; these are explicit single-threaded APIs.

| API | Implemented contract |
|---|---|
| `native_arena_init` | Initialize a caller-backed arena |
| `native_arena_alloc` | Align the actual address and reject overflow/exhaustion without changing the cursor |
| `native_arena_mark` | Capture stable arena identity, cursor and generation |
| `native_arena_rewind` | Rewind a current mark from the same arena and invalidate old marks |
| `native_ref_init` | Initialize one strong reference |
| `native_ref_retain` | Reject dead, zero and saturated counts |
| `native_ref_release` | Authorize caller payload destruction once at the final release |
| `native_ref_upgrade` | Acquire a strong reference only from a live generation |
| `native_authority_allows` | Check all required capability bits |
| `native_authority_narrow` | Delegate a subset without changing output on rejection |
| `native_state_transition` | Guard a state write by expected state and authority |
| `native_contract_range` | Validate an offset/size range without addition overflow |

The detailed lifetime, mark, control-block and destruction obligations are in
[the runtime contract](../runtime/README.md#explicit-native-sotlas-runtime-sv850).


Existing standard-library contracts cover borrowed string slices, UTF-8
validation, bounded numeric parsing, caller-backed/arena/allocator-backed
strings, arenas/bump allocation, ring buffers, ARC counters, concrete vector/
hashmap/result records and other declared modules. Each API has its own
ownership, failure and cleanup obligations; section 14 includes the full
current core contract and section 16 inventories source function declarations.

Remaining runtime/library work includes native generic collections, richer
strings/errors/I/O, allocation failure handling, payload destruction, thread/
async/networking abstractions, math/SIMD/tensors, device runtime and complete
integration with compiler-generated ownership cleanup. A function declaration
or source file does not certify native execution on every backend.

The developer experience includes CLI reports, source mapping, LSP/editor
features, VS Code packaging, examples, docs/site and install gates. Complete
formatting/linting, debugger/profiler, domain/authority/state visualization,
causal inspection, register/stack/ABI views, package/build reproducibility and
native tool launchers remain scoped implementation/release obligations.

Repository organization/website/extension metadata must agree with released
compiler profiles. Updating this development document does not publish a stable
release, deploy the site, publish a VSIX or synchronize organization repositories.

## 11. Acceptance and release gates

For each language/backend/runtime feature, record specification, parser, typed
semantics, lowering, executable implementation, positive tests, negative tests
and end-to-end behavior before promoting its support label.

- [ ] Invalid inputs fail with useful diagnostics and preserve existing artifacts.
- [ ] No accepted semantic operation silently disappears during lowering.
- [ ] Differential reference/native tests cover shared promised behavior.
- [ ] Native runtime tests cover cleanup, failure, boundary values and ownership.
- [ ] Source examples compile and execute through the installed profile.
- [ ] OS/architecture gates execute on their actual supported targets.
- [ ] Stage generation, object and linker identity gates use original sources.
- [ ] FFI gates exercise both producer and consumer and reject unsupported ABI forms.
- [ ] Pure Sotlas install/use/self-build works with foreign compilers and Python absent.
- [ ] Package integrity, rollback/upgrade and release metadata are checked.
- [ ] README, website, examples, extension and support matrix name the same scope.
- [ ] Every candidate is distinguished from the last documented green baseline.

Release cycles follow the release roadmap: systems/kernel foundation,
applications, UI, concurrency/services, realtime/game/media, heterogeneous
compute and sovereignty. Freeze a coherent scope, harden it, produce a release
candidate, publish only after its gates pass, and continue maintenance without
relabeling unimplemented architectural goals as completed features.

## 12. Complete native migration checklist

The following is the current detailed checklist, incorporated from
`docs/sotlas_native_frontend_ownership_checklist.md` at the snapshot revision.
Checked subitems retain their original bounded contracts and evidence notes.

### Native frontend and ownership closure

Repository: [HPinho/sotlas_dev](https://github.com/HPinho/sotlas_dev).

This checklist tracks migration of the contracted canonical language into the
Sotlas-written compiler. A working bootstrap profile does not establish full
language parity. Parent items stay open until every contracted form has native
positive, negative and execution coverage. Subitems record smaller validated
contracts. Local validation must pass CI before being called certified.

#### Frontend parity

##### SV8.50 — four advances in each migration area (2026-10-14)

The following 36 bounded contracts are implemented in Sotlas. Native execution
gates cover accepted behavior and malformed inputs. They do not close the nine
parent migration areas. In particular, the new explicit runtime API does not
make native `shared`, `region`, `whisper` storage or automatic drop glue supported.

| Area | Four delivered contracts | Evidence |
|---|---|---|
| Frontend | Nested block comments; numeric separator/radix-prefix validation; string line-break rejection, including escaped breaks; source NUL rejection inside code/comments/literals | `test_sotlas_native_boundary_expansion` |
| Native ownership primitives | Initialize a local strong control block; checked retain; final release authorizes one destruction; generation-checked weak upgrade acquires a strong reference | `test_sotlas_native_managed_runtime` |
| Sotlas memory runtime | Initialize a caller-backed arena; allocate with actual-address alignment and checked capacity; capture an arena-specific mark; rewind with epoch invalidation and unchanged state on failure | `test_sotlas_native_managed_runtime` |
| State/effect/authority/contract guards | Check all required authority bits; delegate only a subset; guard a state transition with expected state and authority; validate a range without overflow | `test_sotlas_native_managed_runtime` |
| Native IR/lowering | Reject invalid/void SSA value types; reject unrecognized ownership IDs; distinguish parameter/value and return type sets; validate function/parameter/value source spans before call-aware emission | `test_sotlas_native_boundary_expansion`, Target IR contract gates |
| Owned backend/ABI | Pointer/U64 roundtrip; pointer/usize roundtrip and usize pointer offsets; require unsafe for address conversions; reject narrowing/signed/float address conversions | `test_sotlas_native_boundary_expansion` |
| Owned objects/linking | Validate ELF version/header envelope; reject a nonempty undefined section; validate the section-name table; reject a forged undefined symbol | `test_sotlas_native_boundary_expansion` |
| Native CLI | `--version` reports contract versions; `--limits` reports bounds; `--target` reports the platform and ABI limits; `--exit-codes` reports the error contract | `test_sotlas_native_tool_operations` |
| Bootstrap tooling | Stream byte comparison; stream FNV-1a fingerprints; check the native seed platform/architecture envelope; self-test frontend, typed IR and owned object emission | `test_sotlas_native_tool_operations`, platform Stage 2/3 gates |

The reference header is local, non-atomic and caller-owned. Its address must stay
valid while tokens exist; reinitializing a live control-block address with old
tokens outstanding is outside the contract. Final release returns permission to
destroy the payload; it does not free memory or invoke a destructor. Native
execution also verifies release through lexical `defer` and early returns.

Arena callers provide valid backing storage and retain its lifetime. Marks must
be produced by the API and used with the original arena at its stable address;
rewind invalidates old marks and requires the caller to stop using discarded
allocations. These APIs do not prove lifetimes statically or implement a heap.

Authority/state guards are explicit runtime operations, not canonical syntax
or complete native effect inference. The native x86-64 pointer conversion keeps
all 64 address bits and uses a distinct `PointerCast` instruction. It does not
validate mapping/provenance or change the foreign floating-point ABI. Scalar and
pointer assignments inside branches now select structured CFG lowering instead
of the incompatible legacy guard-return path.

The seed envelope check does not authenticate an executable or establish that
it is a compiler. FNV-1a is a reproducibility aid, not a cryptographic signature.
Stage 2/3 gates retain byte identity assertions and now exercise native compare,
fingerprint, envelope checks and self-tests with host tools absent. Complete
language parity, package distribution and broader fixed-point closure remain open.

Final local candidate validation: 2,967 Windows regression tests passed with 79
platform/toolchain skips in 897.171 seconds. All 40 added execution/audit gates
passed on Windows, Linux through WSL and Windows Python 3.10.11. Linux original
source Stage 2/3 byte identity and complete Darwin compiler cross-generation
passed in 104.232 seconds. The Windows generation gate also passed in the full
suite. These results do not substitute for native Intel macOS execution in CI.

- [ ] Migrate all acceptance and rejection rules still implemented by the Python frontend.
- [ ] Complete native typed AST representation for the remaining contracted features.
- [ ] Preserve types, ownership, states, effects, contracts and source positions through the backend.
- [ ] Complete symbol, namespace, visibility and import-alias resolution.
- [ ] Complete package and module dependency resolution.
- [ ] Compile modules separately rather than combining their source streams.
- [ ] Complete contracted type inference and coercions.
  - [x] Resolve instance-method result types for returns and nested call arguments; reject incompatible results.
- [ ] Complete methods, receivers and calls outside the current native profile.
  - [x] Accept internal direct/whisper POD receivers, including Self, and reject receivers naming a different record.
- [ ] Migrate generic features accepted by the canonical frontend.
- [ ] Implement payload enums and their native layout.
- [ ] Implement contracted `match` and selection forms with coverage checking.
  - [x] Execute native scalar/Boolean/explicit-enum match statements with single evaluation, typed patterns and a mandatory final wildcard.
  - [x] Reject duplicate patterns, incompatible enum variants, missing coverage, scope leaks and exhausted arm tables.
  - [x] Integrate nested selection, record returns, lexical defer and exclusive live-path state merges into the structured CFG.
  - [x] Prove wildcard-free Boolean and scalar-enum coverage, preserve nominal enum constant patterns and reject missing discriminants.
  - [x] Trap invalid raw selector representations before dispatch in wildcard-free matches.
  - [ ] Complete payload patterns/bindings, guards, ranges and match expressions.
- [ ] Complete general arrays, slices, indexing and slicing.
  - [x] Native local scalar arrays accept value lists and runtime repetition with exact length/type checking.
  - [x] Repetition evaluates its value once; large arrays use a bounded native fill loop.
  - [x] Boolean arrays participate in native conditions and indexed reads.
  - [x] Boolean array fields preserve POD layout, copying and independent mutation.
  - [x] Initialize fixed scalar array fields with typed lists and nonzero repetition; validate exact field lengths and element ranges.
  - [x] Move, return and borrow exclusive records containing scalar array fields, including recursively nested plain records and independent value storage.
  - [x] Copy local scalar arrays and scalar array fields into record fields with independent storage and exact element/count checks.
  - [x] Execute local pointer-free record array lists/repetition with independent copies, nested fields, element assignment, calls and record returns.
  - [x] Evaluate repeated record initializers once and copy large arrays in a native loop.
  - [x] Reject incompatible record layouts, owned-value erasure, pointer payloads, literal out-of-range indices and per-declaration storage exhaustion.
  - [ ] Complete slices, aggregate array parameters/returns, record array fields and remaining array forms.
- [ ] Implement string and slice values beyond the current literal forms.
- [ ] Complete conditional expressions and remaining control-flow forms.
  - [x] Parse standalone lexical blocks and preserve their local binding scopes in the structured CFG.
  - [x] Native scalar, float and Boolean `if/else` values execute one selected arm, including nested `else if`, calls, returns and loops.
  - [x] Execute record conditional values with independent storage, nested fields, calls, returns, loops and assignments.
  - [x] Transfer exclusive POD conditional results and merge moved states per selected path.
  - [x] Preserve pointer/reference conditional identity and reject record-to-pointer erasure.
  - [ ] Complete remaining ownership payloads and canonical control forms.
- [ ] Migrate canonical error handling and propagation.
- [ ] Complete constant-expression evaluation.
  - [x] Fold typed integer/float arithmetic, bit operations, shifts, Boolean logic and comparisons before emission.
  - [x] Reject signed overflow, division/remainder by zero, invalid shifts and nonfinite floating constant results.
  - [x] Validate folded operand/result types; float bits cannot become integer initializers through incompatible constant references.
  - [x] Register declarations before evaluation and resolve forward scalar dependencies with cycle detection.
  - [x] Fold conditional values and Boolean short-circuit expressions without executing inactive arithmetic.
  - [x] Validate types, names and permitted syntax in inactive arms; validation never caches provisional zero values.
  - [x] Bound dependency tables, expression depth and temporary instructions, with rollback of temporary identities.
  - [ ] Complete remaining contracted constant types/forms, numeric conversions and any canonical constant-call contract.
- [ ] Implement module constants with floats and other contracted types.
  - [x] Lower typed integer, Boolean, f32 and f64 literal constants, including unary-negative literals.
  - [x] Check unused constants with the same type and range rules as expressions.
  - [x] Restore temporary IR arena counts and value identities after declaration validation.
  - [x] References to scalar module constants emit their resolved folded bits, including later declarations.
  - [ ] Support other contracted constant types and remaining expression forms.
- [ ] Implement nonzero static initializers.
  - [x] Emit typed integer/float/Boolean scalar initializers and repeated scalar arrays into writable ELF `.data`.
  - [x] Preserve independent `.bss` zero storage, relocation identity and mutation in native PE/ELF execution.
  - [x] Fold exact-length scalar array lists, including forward constants, conditional values and mixed zero/nonzero elements.
  - [x] Preserve scalar widths and floating bits in writable native data; keep all-zero lists in zero storage.
  - [x] Execute global Boolean array elements in guards and preserve indexed mutation.
  - [ ] Complete general aggregate, string and pointer initializers.
- [ ] Expand numeric literals, including scientific notation and decimals outside current bounds.
  - [x] Parse native `e`/`E` notation and explicit exponent signs; convert the bounded rational without a host float parser.
  - [ ] Complete wider coefficients/exponents, numeric suffixes and remaining numeric forms.
- [ ] Complete overflow, promotion and numeric-conversion rules for every contracted backend.
- [ ] Match canonical diagnostics: file, line, column, cause and context.
  - [x] Native file drivers report the input path, line, column and compiler phase.
  - [x] Single-file diagnostics include a bounded source excerpt and caret.
  - [x] Reserved function/local binders report an expected identifier at the offending token.
  - [x] Native `check` and `compile` report the same syntax errors and preserve existing output on failure.
  - [x] Map combined project compiler positions back to original files, lines and columns after import removal and module reordering.
  - [x] Preserve original source excerpts and previous output artifacts on project syntax/semantic failures.
  - [x] Report specific moved-value, borrowed-mutation, escape and deferred-reservation causes through the native platform CLIs.
  - [ ] Complete detailed semantic causes, diagnostic context and canonical error parity.


##### SV8.47 — four bounded frontend cuts (2026-10-13)

- [x] **Symbols/scope:** identify parameter and preceding lexical-local bindings while checking effects of transitive native AST helper calls; unproven global/out-of-scope references fail closed.
- [x] **Methods/calls:** resolve internal instance/static helper call targets using the typed native call AST, evaluating receiver and argument nodes rather than mistaking callee names for local bindings.
- [x] **Expression acceptance:** reject unsafe, mutable assignment, assembly, trap, unknown call, nonterminating loop and unsupported effect-bearing forms in owned deferred argument evaluation.
- [x] **Diagnostics:** emit a source-positioned dedicated deferred-argument-effect cause consistently in the three Sotlas-native file drivers, preserving existing output artifacts.

These items are partial refinements of open parent migration contracts, not complete symbol parity, general expression typing or canonical diagnostic parity.

#### Ownership, states, effects and cleanup

- [ ] Migrate canonical ownership analysis into Sotlas.
- [ ] Preserve all ownership domains in native IR.
  - [x] Preserve explicit domain tags in parsed TypeRefs without erasing the qualifier source span.
  - [x] Preserve domains of accepted parameters, local bindings and aggregate return destinations in TargetValue metadata.
- [ ] Implement `sole`/`exclusive`, moves and use-after-move checking in the native path.
  - [x] Execute exclusive fixed scalars and pointer-free POD records with explicit local, parameter and return qualifiers.
  - [x] Reject use after a consuming call or binding move, duplicate consumption, implicit copies and pointer escape.
- [ ] Implement ownership merges and `MAYBE_MOVED` in the CFG.
  - [x] Merge exclusive states at structured branches and scalar conditional expressions; exclude returned paths.
  - [x] Reject repeated consumption of an outer owner across a loop backedge.
  - [x] Aggregate conditional result transfers preserve exclusive move state and reject domain erasure.
  - [x] Merge ownership states across runtime Boolean short-circuit operands; statically skipped literal paths preserve the original state.
  - [x] **SV8.49a bounded uniform loop-jump ownership:** a native `if/else` with both arms ending in the same `break` or `continue` now propagates that exit and merges sole states conservatively; moved owners on continue backedges and conditional break exits fail closed.
  - [x] **SV8.49b bounded mixed loop exits:** if/else break/continue or continue/break now executes natively only when each arm preserves every live outer owner; proof uses independent branch snapshots, with lexical defer cleanup verified.
  - [x] **SV8.49c bounded per-edge states:** mixed if/match break and continue exits keep separate break summaries; only terminating break paths may consume outer POD owners, while continue must preserve the backedge state. Loop exits conservatively mark differing states MAYBE_MOVED; nested loop summaries are saved/restored.
  - [ ] Complete fallthrough/jump mixtures, nested mixed exits inside match arms, early-return joins, resource-bearing payloads and general ownership CFG merges.
- [ ] Implement transfers through calls, returns, fields and payloads.
  - [x] Internal exclusive POD call, return and binding transfers execute natively.
  - [x] Static and instance method results preserve ownership; qualified consuming calls record the move.
  - [x] Transparent unsafe expressions preserve moves and independent POD value storage.
  - [x] Convert scalar fields and scalar array elements of qualified POD records without allowing whole-value or pointer escape.
  - [x] Reject domain erasure from owned return values, ordinary assignments, aggregate fields and transparent unsafe expressions.
- [ ] Implement `shared`, aliases and reference accounts.
- [ ] Implement retain, release, destroy and drop glue in Sotlas.
- [ ] Implement `region`, lifetimes and escape validation.
- [ ] Implement `whisper`, reference validity and weak invalidation.
  - [x] Internal POD parameters allow read-only calls and forwarding without consuming their caller's owner.
  - [x] Reject mutation, storage, whole-value return, pointer escape, borrowed-value FFI and borrow/consume overlap in one call.
  - [x] Execute read-only whisper instance receivers and reserve deferred read calls through lexical cleanup.
  - [ ] Implement stored weak references and runtime invalidation.
- [ ] Implement `direct`, alias graphs, forwarding and no-escape checking.
  - [x] Execute internal read-only direct POD parameters, direct forwarding and forwarding to whisper without consuming the caller's owner.
  - [x] Pass direct record arguments using their existing storage; preserve DIRECT metadata in actual parsed/lowered IR.
  - [x] Reject mutation, whole-value storage/return, foreign escape, consuming forwarding and borrow/consume overlap.
  - [x] Execute direct instance receivers and reject receiver borrowing that overlaps consumption in another argument.
  - [ ] Complete stored aliases, general alias graphs/lifetimes and remaining qualified receiver/capture forms.
- [ ] Implement `island` isolation rules.
- [ ] Implement contracted `handover` and `quarantine` transitions.
- [ ] Implement native `device` and `external` contracts.
- [ ] Integrate ownership with bindings, arrays, aggregates, globals and calls.
- [ ] Guarantee exactly-once destruction on every accepted path.
- [ ] Complete cleanup on branches, loops, early returns and failures.
  - [x] Execute ownership-free lexical defers once on block exit, early return and structured loop jumps.
- [ ] Complete `defer`, LIFO execution and cleanup interaction.
  - [x] Lower direct deferred calls, assignments and blocks in LIFO order.
  - [x] Preserve registration-time lexical binding identity while reading current mutable storage at cleanup.
  - [x] Evaluate scalar/record return values before executing deferred writes.
  - [x] Clean loop-scope defers before break, continue and backedge without cleaning enclosing function defers early.
  - [x] Reject nested defers, nonlocal control transfers, unsupported ownership captures and exhausted defer tables.
  - [x] Reserve qualified POD roots for read-only deferred calls, reject moves before cleanup and release reservations at lexical exit.
  - [ ] Complete qualified captures in general deferred blocks, ARC/drop and unwind.
  - [x] Execute bounded deferred blocks of direct read-only calls on qualified POD roots, preserving order and lexical reservations; reject consuming, mutating, nested and noncall payloads.
  - [ ] Complete owned captures, ARC/drop interaction, deferred internal loop jumps and error/unwind cleanup.
- [ ] Migrate effect analysis and propagation.
  - [x] Prove effect-free deferred owned-borrow argument evaluation across bounded internal call chains; reject unsafe, pointer, mutation and opaque callees without making observer bodies globally pure.
  - [ ] Preserve canonical effect domains, capability grants and transitive effect signatures across the full typed AST and native Target IR.
  - [x] SV8.48a bounded call-boundary proof: deferred helper parameters may use ordinary POD or checked readonly direct/whisper domains, but not consuming sole or unrecognized domains. Raw pointer parameters and owned/borrowed/pointer results fail closed; the native self:&Self receiver remains the certified exception.
  - [ ] General effect-capability signatures, cross-module inference and propagation into native Target IR remain open.
  - [x] **SV8.48b bounded typed call IR:** pack per-argument ordinary/sole/whisper/direct ownership facts into the existing 64-bit Call metadata without changing object ABI; validate the 24-operand capacity and reject forged/truncated profiles before machine emission.
  - [ ] Extend to all target capability/effect domains, prove callee-signature consistency across separately compiled modules, and serialize canonical semantic facts outside this in-memory IR.
  - [x] **SV8.48c bounded typed call-signature agreement:** attach ownership roles to native void-observer calls, compare tagged Call roles against declared SSA-parameter domains in the explicit call-signature validator, and require plain roles at external declarations without certified domain SSA metadata.
  - [ ] Wire canonical callee-capability signature validation into every emission boundary and across independently compiled modules; complete effect/escape analysis of foreign/system calls remains open.
  - [x] **SV8.48d bounded ELF writer gate:** require the existing typed call-signature validator with complete CFG, Phi and target buffers at the unified native ELF object emitter; reject callee-symbol, ABI-type, arity and tagged capability inconsistencies before emission.
  - [ ] Integrate this signature gate with the other specialized emitters and independently compiled module/foreign linking boundaries without weakening platform fixed-point acceptance.
  - [x] **SV8.48e bounded specialized CFG emitter gate:** require the full typed direct-call validator (including Phi/branch CFG) at the single-function ELF64 scalar object and x86-64 scalar CFG assembly entry points, preserving prior emitter-specific subsets and ABI.
  - [x] **SV8.48f legacy multi-function emission gate:** enforce CFG and typed call-signature checks before writing bytes in ELF64 scalar module objects and x86-64 multi-function assembly; reject nonempty missing Phi/target tables.
  - [x] **SV8.48g bounded legacy single-function signature gate:** accept typed plain U32 self-calls only with exact callee symbol/arity and known parameter types; reject typed foreign/borrow/move calls, and prohibit unavailable Phi/branch metadata in single-function/conditional/constant emitters before output.
  - [ ] Complete cross-object/inter-module capability signatures, foreign effects and all remaining unproven legacy untagged call contracts.





- [ ] Migrate `unsafe`, target-capability and foreign-boundary validation.
  - [x] Equal-width integer/float pointer reinterpretation requires explicit `unsafe`; missing `unsafe` and width changes fail before output.
- [ ] Migrate contracted state machines, transitions, refinements and coverage checks.
- [ ] Migrate contracts, preconditions, postconditions and executable guards.
- [ ] Replace semantic operations without runtime behavior with implementation or explicit rejection across the complete native profile.
  - [x] The owned x86-64 object writer rejects all eleven reserved semantic runtime opcodes before object emission.
  - [x] Backend-neutral IR can preserve these operations; unsupported execution never turns them into no-ops.
  - [x] Rejection resets output length, preserves IR, and leaves the output buffer unchanged.
  - [ ] Implement the corresponding ownership/state/cleanup runtime operations and their complete source-level diagnostics.


##### SV8.47 — four bounded ownership cuts (2026-10-13)

- [x] Trace **indexed array projections** to the owner for direct/whisper borrow masks, rather than treating indexed values as independent storage.
- [x] Trace **conditional guard operands**, in addition to selected arms, to their owner before deciding whether a call borrows an owner.
- [x] Reject **borrow/consume overlap in the same native call**, including borrowed array-field indexes and conditionally computed scalar arguments; fail closed for unknown owner-bearing expression forms.
- [x] Preserve **projected defer owner reservations** through lexical cleanup and allow ownership transfer after the enclosing scope exits, without ARC/drop or stored weak references.

The complete alias graph, retained borrows, general lifetimes and resource cleanup remain open.

#### New acceptance evidence

| Contract | Gate |
| SV8.49b mixed branch loop-edge owner preservation, defer cleanup and fail-closed moves | `test_sv849b_native_mixed_loop_edges_preserve_sole_owner`, `test_sv849b_native_mixed_edges_preserve_owned_defer_cleanup`, `test_sv849b_native_mixed_edges_reject_owner_moves_and_opaque_joins` |
| SV8.49a uniform nested branch loop-jump acceptance and owned CFG exit rejection | `test_sv849a_native_owned_uniform_loop_jumps_execute`, `test_sv849a_native_owned_loop_jump_states_fail_closed` |
| SV8.48g legacy scalar entry points reject unproven typed calls and absent side tables | `test_sv848g_legacy_scalar_entry_points_fail_closed_on_unproven_calls` |
| SV8.48f mandatory typed-call preflight for legacy multi-function emitters | `test_sv848f_legacy_multifunction_emitters_preflight_typed_calls` |
| SV8.48e mandatory signature proof at specialized single-function CFG emitters | `test_sv848e_specialized_cfg_emitters_validate_typed_calls` |
| SV8.48d mandatory full-CFG typed signature validation at unified ELF object writer | `test_sv848d_elf_writer_requires_full_typed_call_validation`, `test_sv848d_elf_boundary_accepts_typed_mixed_calls_with_cfg` |
| SV8.48c typed void-observer call capabilities and callee-domain signature agreement | `test_sv848c_typed_void_observers_preserve_borrow_and_effects`, `test_sv848c_void_observer_cannot_erase_sole_move`, `test_sv848c_void_call_capabilities_and_callee_domains_are_checked` |
| SV8.48b typed per-argument IR capabilities and hidden record return | `test_sv848b_target_ir_call_capabilities_preserve_owned_borrowed_and_plain`, `test_sv848b_target_ir_hidden_record_return_keeps_call_abi`, `test_native_call_capability_metadata_is_validated_before_emission` |
| SV8.48a bounded helper signature capabilities for deferred ownership | `test_sv848_deferred_helper_borrowed_input_is_effect_free`, `test_sv848_deferred_helper_sole_input_cannot_be_pure` |
| SV8.47 lexical locals, instance helper calls and unsupported effects | `test_sv847_frontend_lexical_local_effects_execute`, `test_sv847_frontend_method_effects_execute`, `test_sv847_frontend_unproven_effect_forms_fail_closed` |
| SV8.47 regression: nested typed scalar read result is independent of borrowed owner | `test_sv847_nested_read_result_does_not_retain_spurious_borrow` and existing `test_native_direct_scalar_and_static_calls_execute_with_typed_results` |
| SV8.47 direct scalar snapshot versus forbidden stored-borrow escape | `test_sv847_ownership_projected_defer_reservation_and_scope_release` and `test_sv847_deferred_direct_scalar_cannot_escape_to_global` |
| SV8.47 independently certified array-field preparation and unchanged indexed deferred cleanup | `test_native_array_fields_copy_local_and_record_arrays_independently` and `test_sv847_ownership_projected_defer_reservation_and_scope_release` |
| SV8.47 indexed/conditional borrow masks and deferred lexical release | `test_sv847_ownership_indexed_borrow_cannot_be_consumed_in_same_call`, `test_sv847_ownership_conditional_guard_borrow_cannot_be_consumed`, `test_sv847_ownership_projected_defer_reservation_and_scope_release` |
| SV8.47 native file driver effect reason (all three platforms) | `test_sv847_native_deferred_effect_specific_diagnostic` |
|---|---|
| Reserved semantic opcodes: neutral validation, native rejection and untouched output | `tests/test_sotlas_native_frontend_closure.py::test_semantic_runtime_markers_are_preserved_but_never_emitted_as_noops` |
| Float/Boolean/signed-minimum module constants and native/C11 result comparison | `tests/test_sotlas_native_frontend_closure.py::test_typed_module_constants_include_float_bool_and_signed_minimum` |
| Invalid unused constants rejected before output | `tests/test_sotlas_native_frontend_closure.py::test_invalid_unused_constants_fail_closed` |
| Unused constants do not leak temporary literal IR | `tests/test_sotlas_native_frontend_closure.py::test_unused_constants_do_not_leak_literal_ir_into_functions` |
| Native file diagnostics and check/compile consistency | `test_native_diagnostics_preserve_path_position_phase_and_context` in the Linux, Windows and Darwin driver suites |
| Exclusive POD call, binding and return execution | `test_native_exclusive_pod_call_binding_and_return_transfers` |
| Branch and scalar conditional ownership joins | `test_native_exclusive_branch_merge_and_live_return_path`, `test_native_exclusive_conditional_consumption_has_path_states` |
| Qualified/static and receiver method transfers | `test_native_exclusive_static_and_receiver_calls_preserve_transfers` |
| Ownership metadata from actual Sotlas parsing and lowering | `test_native_lowering_preserves_parameter_binding_and_return_domains` |
| Whisper forwarding, no-escape and overlapping consumption | `test_native_whisper_reads_and_forwarding_preserve_owner`, `test_native_whisper_rejects_mutation_escape_and_overlapping_move` |
| Independent POD storage through unsafe value bindings | `test_unsafe_pod_value_bindings_keep_independent_storage` |
| Forward dependencies and static initialization before constant declarations | `test_forward_constants_initialize_storage_before_functions` |
| Record conditional storage, ABI and exclusive transfers | `test_record_conditional_values_copy_nested_fields_and_select_one_arm`, `test_exclusive_conditional_values_move_owners_per_path` |
| Reference identity and conditional borrow/consume rejection | `test_conditional_pointer_values_preserve_reference_identity`, `test_conditional_borrow_cannot_overlap_owner_consumption` |
| Original project file positions after reordering/import removal | `test_project_diagnostics_map_original_files_after_import_removal` in the three driver suites |
| SV8.46 deferred borrowed-argument effect proofs, transitive local calls and fail-closed impure arguments | `test_native_deferred_owned_argument_pure_calls_execute_transitively`, `test_native_deferred_owned_argument_pure_call_in_single_defer`, `test_native_deferred_owned_argument_effects_fail_closed` |
| Qualified native deferred blocks: read-only borrowed POD calls, LIFO/lexical releases and rejection | `test_native_owned_defer_blocks_execute_checked_read_calls_in_order`, `test_native_owned_defer_blocks_preserve_lifo_and_scope_release`, `test_native_owned_defer_blocks_reject_consumption_mutation_and_noncall_payloads` |
| Native lexical defer LIFO and early return | `test_native_defer_calls_run_lifo_on_scope_and_early_return` |
| Static list constants, scalar widths, mutation and exact ELF section bytes | `test_static_lists_fold_forward_constants_and_preserve_mutable_storage`, `test_static_lists_preserve_scalar_widths_signedness_and_float_bits`, `test_static_list_object_bytes_and_zero_section_are_distinct` |
| Static list shape/type/runtime rejection and shared capacity bound | `test_static_lists_reject_shape_type_runtime_and_pointer_initializers`, `test_static_list_capacity_is_shared_across_declarations` |
| Local record array copies, fields and one-evaluation repetition | `test_local_record_array_lists_copy_and_mutate_nested_payloads`, `test_local_record_array_repetition_evaluates_once_and_copies_each_slot` |
| Record element return/conditional/defer integration and rejection | `test_local_record_array_element_returns_preserve_value_storage`, `test_local_record_arrays_cross_return_conditional_and_defer_paths`, `test_local_record_arrays_reject_layout_type_and_escape_errors` |
| Match evaluation, typed dispatch and cleanup | `test_native_match_selects_once_and_executes_only_one_arm`, `test_native_match_signed_boolean_and_enum_selectors`, `test_native_match_nested_scopes_loops_and_lexical_cleanup`, `test_native_match_record_returns_snapshot_before_cleanup` |
| Match ownership, widths, syntax, coverage and capacity | `test_native_match_merges_exclusive_states_and_excludes_returned_paths`, `test_native_match_integer_widths_and_constant_patterns`, `test_native_match_scopes_mutated_subject_and_rejected_forms`, `test_native_match_legacy_statement_arm_syntax`, `test_native_match_rejects_coverage_patterns_and_selector_types`, `test_native_match_arm_capacity_is_bounded` |
| Sotlas-written file CLI: match check/compile/run and preservation on coverage failure | `test_native_match_check_compile_run_without_host_tools` in the Windows, Linux and Darwin driver suites |
| Native direct forwarding, typed calls and original-storage IR evidence | `test_native_direct_forwarding_and_read_aliases_preserve_the_owner`, `test_native_direct_scalar_and_static_calls_execute_with_typed_results`, `test_native_direct_ir_preserves_domain_and_borrows_original_record_storage` |
| Direct structured execution and no-escape rejection | `test_native_direct_loops_branches_and_void_forwarding_do_not_consume`, `test_native_direct_rejects_mutation_storage_returns_ffi_and_overlap` |
| Sotlas-written direct CLI and preserved artifacts on rejection | `test_native_direct_check_compile_run_without_host_tools` in the three native driver suites |
| Finite match coverage, nominal constants and invalid-representation trap | `test_native_match_proves_boolean_and_enum_coverage_without_wildcards`, `test_native_match_missing_cases_and_nominal_constant_mismatches_fail`, `test_native_match_invalid_enum_representation_traps_before_an_arm` |
| Finite match cleanup, ownership, capacity and complete record strides | `test_native_match_finite_coverage_preserves_cleanup_and_ownership`, `test_native_match_complete_enum_capacity_executes_the_last_case`, `test_record_array_nonpower_and_large_strides_execute_checked_indexing` |
| Defer binding identity and return snapshots | `test_native_defer_blocks_preserve_shadowed_bindings_and_live_locals`, `test_native_defer_assignments_run_after_return_value_evaluation` |
| Defer loop cleanup and explicit unsupported/capacity rejection | `test_native_defer_loop_jumps_cleanup_once_before_backedge`, `test_native_defer_rejects_nonlocal_jumps_nested_defers_and_owned_capture`, `test_native_defer_capacity_fails_closed` |
| Conditional and Boolean constant short-circuit execution | `test_constant_conditional_and_boolean_arms_evaluate_lazily` |
| Cycle, inactive-arm validation, cache and capacity checks | `test_constant_cycles_and_invalid_forward_dependencies_fail_closed`, `test_constant_inactive_arms_still_check_types_names_and_calls`, `test_inactive_conditional_dependency_keeps_its_real_cached_value`, `test_constant_dependency_capacity_and_nested_depth_are_bounded` |

These gates build the current sources through the strict public Stage-0
frontend in a fresh directory. They do not select a cached Stage-1 executable.
Stage 0 remains necessary to produce the initial test seed; execution and
native generation gates use the Sotlas-owned compiler afterward.

Earlier SV8.32 results: all four frontend-closure tests passed on Windows and Linux
(WSL), and on Windows Python 3.10.11. The combined Windows driver/frontend
run passed 15 tests. Linux diagnostics, original-module generation identity
and the floating-point workload passed three additional execution gates.
The C11 regression job passed 707 tests. The complete Windows regression
suite passed 2,761 tests with 65 platform/tool skips. Intel macOS execution remains a CI
gate; a Windows cross-build does not substitute for that execution evidence.

SV8.34 local evidence: all 34 frontend-closure tests passed on Windows and
Linux (WSL), including the actual lowering-domain inspection and unsafe POD
copy gate. The same 34 tests passed with Windows Python 3.10.11. The final
Windows frontend/driver run passed 45 tests, including the independent-storage
guard and original-source Stage 2/3 identity. Linux ownership
commands, original-source native generation identity and Darwin compiler
cross-build passed three additional gates. The C11 regression step passed
707 tests. macOS runtime execution remains a CI requirement.
The complete Windows regression suite then passed 2,791 tests with 65
platform/toolchain skips in 785.416 seconds, using the final source revision.

SV8.35 local evidence: the complete Windows regression suite passed 2,798
tests with 65 platform/toolchain skips in 628.822 seconds. The expanded
41-test frontend set passed on Windows, Linux (WSL) and Windows Python
3.10.11. Windows/Linux native generation identity and the Darwin compiler
cross-build remained valid with the new constant dependency/control evaluator.

SV8.36 local evidence: the Windows regression run passed 2,805 tests with 65
skips in 639.199 seconds. The combined frontend/Windows-driver set passed 59
tests. All 47 frontend tests passed on Windows, Linux (WSL) and Windows Python
3.10.11. Linux source-map execution, native generation identity and Darwin
compiler cross-build passed three gates. Linux/macOS source-map methods added
after general-suite discovery were checked separately (two Windows skips),
with the Linux method executed in WSL. macOS runtime remains a CI gate.

SV8.37 local evidence: the Windows regression run passed 2,813 tests with 67
skips in 642.009 seconds. The final standalone-block selection adjustment then
passed 66 frontend/Windows-driver tests, including Stage 2/3 identity. All 54
frontend gates passed on Linux (WSL) and Windows Python 3.10.11. Linux native
generation and Darwin compiler cross-build remained valid. Full ownership
capture/drop/unwind integration and a 70% full-list claim remain uncertified.

#### Remaining limits

SV8.49c local evidence: 2,927 Windows tests passed with 79 platform/toolchain
skips in 843.420 seconds. All 137 frontend tests passed on Windows, Linux
(WSL) and Windows Python 3.10.11. Native Linux CLI, Stage 2/3 identity and
Darwin compiler cross-build passed three gates; all six hosted SV8 oracle
gates passed after preserving its structured-source contract. The previous
mixed-loop negative source is retained as a positive execution fixture, and
its negative slot now rejects consuming conditions before a continue backedge.
Intel macOS execution and the new full CI matrix remain required.

SV8.44 local evidence: four frontend and four ownership contracts advanced,
with ten new frontend gates and three platform CLI gates. The full Windows
suite passed 2,877 tests with 75 platform/toolchain skips in 847.858 seconds.
All 105 frontend tests passed on Windows, Linux (WSL) and Windows Python
3.10.11. Linux native CLI, Stage 2/3 identity and Darwin compiler cross-build
passed three additional gates. macOS runtime and CI certification remain required.

SV8.43 local evidence: the full Windows suite passed 2,864 tests with 73
platform/toolchain skips in 654.002 seconds. The frontend/Windows-driver run
passed 110 tests, including native generation identity. All 95 frontend tests
passed on Linux (WSL) and Windows Python 3.10.11. Linux native CLI execution,
original-source generation identity and Darwin compiler cross-build passed
three additional gates. The public owned-packet example executed on Windows.
Intel macOS runtime execution and CI certification remain required.

Native ownership analysis currently accepts explicit exclusive qualifiers on
fixed scalars and pointer-free POD records, and direct/whisper internal
parameters and matched receivers on the same POD types. Record parameters use the internal address ABI; scalar parameters
use immutable values. This does not establish a general borrowed-reference ABI.
Analysis tracks at most 256 bindings and 64 nested analysis levels. Owned fields,
globals, pointer payloads, custom destructors, shared accounts and heap cleanup
remain outside this contract. Unsupported domains are rejected semantically.
Owned record fields are limited to fixed scalars and recursively nested plain
records and fixed scalar array fields of 1 through 256 elements. Array elements
must be primitive integers, Boolean values or f32/f64; nested arrays, pointers,
qualified elements and arrays of records remain rejected. Record field lists
evaluate elements in source order once; repetition evaluates its value once.
Scalar record projections can be converted to scalar values. Whole qualified
values and array-to-pointer/address escapes remain rejected. Deferred read-only
calls can capture qualified POD roots; those roots cannot move before lexical
cleanup. Qualified captures in deferred blocks/assignments and resource cleanup
remain outside the contract. This does not add ARC or weak-reference storage.
Transparent unsafe value expressions retain independent POD binding storage.
Raw-pointer record dereferences retain the existing native record-view path;
general by-value loads from raw pointers are not certified by these new gates.
Nested break/continue merges and ownership-bearing non-POD conditional results
remain open. A POD move has no heap resource to release; these execution gates
must not be presented as proof of ARC or general exactly-once destruction.

Scalar module constants retain the native numeric bounds and 64-declaration
limit. Folding accepts up to 128 temporary IR instructions per expression;
general calls and remaining constant types/conversions remain outside this
contract. Declaration dependencies must be acyclic, including references in
inactive arms. Expression and evaluation nesting are bounded to 64 levels;
selected arithmetic follows the existing signed-overflow and unsigned-wrap
rules. Scientific exponents are bounded to 18 and the reduced
rational must fit the existing coefficient/denominator limits. Local scalar
arrays remain bounded to 4,096 elements. Diagnostics display at
most 160 source bytes. Project compiler diagnostics use checked source segments
to recover original file positions; at most 8,192 segments are retained for
64 files, with original paths bounded to 4,095 bytes each. Errors outside a
mapped source span retain the combined-stream fallback. Semantic opcode rejection protects users from
silently omitted behavior; it does not implement ARC, lifetimes or cleanup.

The broader items above remain open. Neither this checklist nor native compiler
fixed-point evidence authorizes deleting the Python reference implementation
or C bootstrap before their contracted features have native replacements.

## 13. Detailed native driver contract

The following incorporates `bootstrap/sotlas/native_driver/README.md` at the
snapshot revision. Commands, platform limits and implementation evidence remain
scoped to this driver profile.

### Native compiler drivers

`linux.sotlas` is a Linux x86-64 compiler driver written in Sotlas. It reads
source files, runs the production frontend and Target IR lowerer, writes ELF
objects and links executable images. File operations use kernel syscalls;
the generated compiler has no ELF interpreter or dynamic C runtime.

#### Initial seed

Build the current hosted Stage 1 producer once, then use its native object
writer and linker to create the seed:

```sh
./build/sotlas_stage1 --compile-obj \
  bootstrap/sotlas/native_driver/linux.sotlas build/linux_driver.o
./build/sotlas_stage1 --link-exe \
  build/linux_driver.o build/sotlas-native sotlas_linux_main
```

The initial producer still uses the hosted bootstrap. The resulting seed's
compilation and self-build paths do not invoke Python, Clang, a C emitter or
an external linker.

#### Compile files

```sh
./build/sotlas-native input.sotlas output
./build/sotlas-native input.sotlas output.o --object
./output
```

Executable input uses `main_entry() -> u32`. `--compiler` selects the checked
`sotlas_linux_main(argc: u64, argv: *const *const u8) -> u32` process ABI, which
receives the kernel's actual argument vector. Unknown options are rejected.

Input must be smaller than 2 MiB. Source storage reserves another 2 MiB for
synthetic symbols. Compiler tables are bounded and exhausted buffers fail
closed. Output is created only after frontend, lowering and linking succeed;
an I/O failure during writing can leave a partial file. Newly created outputs
use mode 0755; existing files retain their permissions.

String literals share a pool of 65,536 decoded bytes, including NUL terminators,
and at most 512 symbols per compilation. Exhausting either limit rejects
lowering before output is opened. Literals are never truncated to fit the pool,
and every accepted string address has a data-symbol relocation.

#### Experimental Windows executable output

```sh
./build/sotlas-native input.sotlas output.exe --windows
./build/sotlas-native --build-win output.exe /path/to/source-root /path/to/entry.sotlas
```

The native Linux compiler can cross-compile PE32+ executables for Windows x64.
The writer and linker are Sotlas source. They resolve the existing internal
object format, retain the internal SysV calling convention and emit a Win64
startup bridge importing `KERNEL32.dll!ExitProcess`. No C compiler or external
linker is used after the Linux seed is available. The entry takes no parameters;
its low 32 result bits become the process exit code.

Calls, strings, pointer arrays and zero-initialized globals are covered by
execution tests. Unrecognized foreign symbols and Linux system operations are
rejected. Object platform flags record actual Linux SystemOps; matching bytes
inside integer immediates are accepted. Input must carry the Sotlas entry ABI
note. The image uses a fixed base and currently has writable executable
sections; ASLR, separate memory protections, unwind tables, general Win64 FFI
and macOS output remain open.

#### Native Windows compiler

`windows.sotlas` runs the same Lexer, Parser, Sema, Target IR and x86 backend as
the Linux driver. Its file adapters call Win32 APIs directly. Given a seed,
compilation and native Stage 2/3 generation require no Python or C tooling.
The Linux bundle includes its original source and can build the seed:

```sh
./bin/sotlas-native --build-win sotlas-native.exe ./src ./src/sotlas/compiler/windows_driver.sotlas
```

On Windows, executable output defaults to PE32+:

```powershell
.\sotlas-native.exe --check .\main.sotlas
.\sotlas-native.exe .\main.sotlas .\application.exe
.\sotlas-native.exe --build-cc .\stage2.exe .\src .\src\sotlas\compiler\windows_driver.sotlas
.\stage2.exe --build-cc .\stage3.exe .\src .\src\sotlas\compiler\windows_driver.sotlas
```

The driver supports single files, the bounded explicit/resolved project modes,
source discovery and checks. `--object` writes the internal ELF object format.
The argv adapter handles Windows spaces, quotes and backslashes, with at most
67 arguments and 4,095 bytes per argument. Paths use the Windows ANSI code page;
full Unicode paths and environment argument expansion are outside this profile.
The same one-megabyte source and bounded compiler tables apply.

##### Windows platform imports

The native PE backend resolves these reserved `@extern(C)` names to KERNEL32
through a SysV-to-Win64 bridge. Parameter count and machine types are checked
before object emission. Pointee validity and buffer bounds remain the caller's
responsibility at this raw API boundary.

| Sotlas name | Win32 API | Machine parameters | Result |
|---|---|---|---|
| `sotlas_windows_exit` | ExitProcess | u32 | void |
| `sotlas_windows_get_command_line` | GetCommandLineA | none | pointer |
| `sotlas_windows_create_file` | CreateFileA | pointer, u32, u32, pointer, u32, u32, u64 | u64 |
| `sotlas_windows_read_file` | ReadFile | u64, pointer, u32, pointer, pointer | u32 |
| `sotlas_windows_write_file` | WriteFile | u64, pointer, u32, pointer, pointer | u32 |
| `sotlas_windows_close_handle` | CloseHandle | u64 | u32 |
| `sotlas_windows_get_std_handle` | GetStdHandle | u32 | u64 |
| `sotlas_windows_get_last_error` | GetLastError | none | u32 |

The bridge follows the [Microsoft x64 calling convention](https://learn.microsoft.com/en-us/cpp/build/x64-calling-convention),
including register mapping, shadow space and stack arguments. The I/O gates
exercise [WriteFile](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-writefile)
and seven-argument [CreateFileA](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-createfilea)
with actual Windows file round trips.

#### Check source without writing artifacts

```sh
./build/sotlas-native --check input.sotlas
./build/sotlas-native --check-build /path/to/source-root /path/to/entry.sotlas
```

Both commands use the same lexer, parser, semantic checker, Target IR lowerer
and native object validator as compilation. The object is validated in memory;
no output file is opened. A successful check is silent and returns zero. Errors
use the existing stage-specific exit codes. `--check-build` discovers glob
imports and validates their dependency graph using the same rules as `--build`.

Checking targets the declared native object profile, so a library without an
executable entry can pass. It does not prove executable linking, resolve foreign
symbols, or claim parity with every feature of the canonical hosted frontend.
Use executable compilation to validate the entry and linker contract.

#### Explicit multi-file builds (SV8.21a)

The Linux native driver also accepts a bounded list of source files. The
compiler joins them in the supplied order with newline separators, runs the
same lexer/parser/sema/lowerer, and emits one object or linked ELF executable:

```sh
./build/sotlas-native --project build/app.elf math.sotlas app.sotlas
./build/sotlas-native --project-object build/app.o math.sotlas app.sotlas
./build/app.elf
```

Pass dependencies before users and keep symbol names unambiguous. This initial
flat-source profile **does not resolve imports**: source files containing
`import` still fail with exit code 12, even if a target appears in the
explicit file list. Only syntactically valid, import-free modules are joined;
the driver never silently drops or rewrites dependency declarations. A
`--project-compiler` variant selects the dedicated compiler entry ABI, but
does not automatically merge or resolve the compiler's own imports. This is
not yet native package/module loading or release bootstrap closure.

At least two input files and at most 64 are accepted. The combined source
(including separators) remains under the 2 MiB limit; each file must
be nonempty. The second MiB remains reserved for synthetic symbols.
Missing files, invalid options, oversized/invalid sources and unresolved
imports fail before opening the output path. Successful object output is
byte-for-byte equal to compiling the exact newline-joined input with the
existing hosted producer. Native Linux tests execute the linked project with
no external tools on PATH and verify that failure preserves an old output
artifact. The regular one-file invocation and the Stage 2/Stage 3 generation
path are unchanged.

The implementation keeps single-file reading, explicit multi-file reading, and
the common native frontend/object/link pipeline in separate Sotlas functions.
This isolates the ELF link call from nested project input loops and preserves
the identical compiler core and fail-before-output contract for both modes.
The Linux regression suite exercises all three project modes' argument bounds
and empty-source rejection without modifying an existing artifact.

#### Bounded native module resolution (SV8.21b1)

The opt-in Linux-only flags `--project-resolve`, `--project-resolve-object` and
`--project-resolve-compiler` accept the same output and 2–64 explicitly
supplied source files as the earlier project modes:

```sh
./build/sotlas-native --project-resolve build/app.elf app.sotlas math.sotlas
./build/sotlas-native --project-resolve-object build/app.o app.sotlas math.sotlas
./build/sotlas-native --project-resolve-compiler build/stage2 \
  bootstrap/sotlas/native_compiler/{token,ast,lexer,parser,sema}.sotlas \
  bootstrap/sotlas/native_compiler/backend/{target_ir,lower_scalar,x86_64_scalar}.sotlas \
  bootstrap/sotlas/native_driver/linux.sotlas
```

The opt-in resolved modes use a separate exact ASCII-byte decoder without
introducing additional CLI string literal relocations into the native image.
Legacy flat-project modes dispatch first through the previously certified
entry path; unknown calls with five or more argv entries reach the isolated
resolver helper, and invalid suffixes fail without opening the output file.

All inputs must begin with exactly one explicit `module path;` declaration.
Imports are currently restricted to contiguous `import path::*;` declarations.
The native lexer reads each original source and builds a bounded module-name
index and dependency graph. Missing module names, duplicate modules/imports,
self imports, cyclic graphs, unsupported aliases and nested imports fail with
exit code 12 before any output file is opened. A stable topological sort chooses
the earliest ready source from the caller's list and emits the ordered source
stream with *only verified import tokens* removed. No Python, C emitter, host
linker, host module resolver or build-time concatenation is invoked by either
native compiler generation.

Imports expose current flat compiler symbols: **this does not yet implement
qualified namespace isolation or visibility rules**. The original `--project`
commands retain their exact behavior and continue to reject every import.
The 2 MiB combined-input bound and synthetic-symbol reservation remain.
General native package resolution and separate per-module linking remain
outside this profile.

The resolver uses one-element static scratch slots for parsed token spans
and the emitted source length. This is an intentionally non-reentrant
single-compilation-per-process interface: the current native lowerer cannot
yet lower helper calls passing several independent address-taken local scalar
out-parameters. The import graph and input limits remain unchanged.

The Linux gates validate out-of-order imported project execution, native/hosted
object identity for an explicitly normalized reference source, error paths
preserving existing output, and Stage 1→2→3 fixed point from the nine original
production module files. This profile is certified by
[CI #1167](https://github.com/HPinho/sotlas_dev/actions/runs/38037420665) for
`3782ff133b4c9e952f7bcb8fa8f188feb6c39b29`. The new check commands require their
own CI certification.

#### Discover imported files

```sh
./build/sotlas-native --build output /path/to/source-root /path/to/entry.sotlas
./build/sotlas-native --build-obj output.o /path/to/source-root /path/to/entry.sotlas
./build/sotlas-native --build-cc stage2 /path/to/source-root /path/to/compiler-entry.sotlas
```

Glob imports are discovered by the production lexer. `foo::bar` resolves to
`SOURCE_ROOT/foo/bar.sotlas`; the existing graph verifier rejects duplicate
modules, missing imports, cycles, aliases and malformed paths before output is
opened. Comments and strings are never interpreted as imports. Discovery uses
a queue of at most 64 paths, each shorter than 4,096 bytes, and the existing
one-megabyte combined source limit. Module visibility and import aliases are
still outside the native profile.

#### Install a native seed bundle

```sh
python packaging/native_linux.py --output dist/sotlas-native-linux-x64
tar -xzf dist/sotlas-native-linux-x64.tar.gz
bash sotlas-native-linux-x64/install-native.sh sotlas-native-linux-x64 /path/to/install
```

The packager uses build-time Python and the initial producer. The extracted
bundle contains a static native compiler, its eight core Sotlas modules and
the Linux, Windows and Darwin driver sources in
namespace layout under `src/`, documentation and SHA-256 checksums. Installation
uses Bash and ordinary system utilities; Python, Clang and a C compiler are not
required. The installer verifies the payload before writing and refuses an
existing destination. The archive has deterministic order, timestamps and
permissions. CI builds, installs and uploads this Linux bundle independently of
the existing Python distribution.

The installed compiler can discover and rebuild its own source tree:

```sh
INSTALL/bin/sotlas-native --build-cc stage2 INSTALL/src INSTALL/src/sotlas/compiler/linux_driver.sotlas
./stage2 --build-cc stage3 INSTALL/src INSTALL/src/sotlas/compiler/linux_driver.sotlas
cmp stage2 stage3
```

#### Explicit native self-build

The self-build input concatenates these production sources in order:

1. `token`, `ast`, `lexer`, `parser`, `sema`
2. `backend/target_ir`, `backend/lower_scalar`, `backend/x86_64_scalar`
3. `native_driver/linux.sotlas`

Remove top-level import declarations after concatenation, since every dependency
is already included once. Single-file compilation rejects imports. Use `--build`
to discover dependencies directly from the original module files. The merged
source remains an alternative input for the same compiler implementation.

```sh
./build/sotlas-native compiler_merged.sotlas build/stage2 --compiler
./build/stage2 compiler_merged.sotlas build/stage3 --compiler
cmp build/stage2 build/stage3
```

`tests/test_sotlas_native_linux_driver.py` creates this merged input,
compares native and hosted-producer objects, requires Stage 2 and Stage 3 to be
byte-for-byte identical, and executes a program compiled by Stage 3. These
execution tests run with `PATH` pointing to an empty directory. Windows and
macOS compile and link the seed as a cross-target ELF artifact; Linux x86-64
executes the generation chain. WSL can execute the same local artifacts.

This closes a native self-build for the current compiler-source subset. Bounded
glob-module discovery and a Linux seed bundle are available. Broader module
visibility/package semantics, full language parity, general Windows ABI coverage
and the macOS native driver remain open.

#### Kernel interface

Reserved bodyless scalar declarations named `sotlas_linux_read`,
`sotlas_linux_write`, `sotlas_linux_open` and `sotlas_linux_close` lower to a
validated `SystemOp`. The existing C ABI syntax describes the scalar boundary;
these calls do not bind libc symbols. The backend emits Linux x86-64 syscalls
0, 1, 2 and 3 directly and preserves negative kernel error returns as `i64`.
Other declarations continue to use ordinary external-call linking. The Linux
process-entry ABI has a dedicated ELF note flag; it cannot be selected by
supplying arbitrary constant entry arguments or a freestanding target.

#### Experimental Intel macOS output

Native Linux and Windows drivers can discover a project and emit a static
Intel Mach-O image without a host compiler or external linker:

```sh
sotlas-native --build-mac app.macho SOURCE_ROOT SOURCE_ROOT/probe/main.sotlas
```

The supported entry contract is `pub fn main_entry() -> u32`. The writer
requires a recorded zero-argument ABI, resolves its internal ELF object, maps
strings and zero-filled BSS, and emits a kernel startup through `LC_UNIXTHREAD`.
The startup exits with the entry's low 32-bit scalar return value. Legacy object
ABI notes record arity rather than the full return-type schema; they do not
make arbitrary entry signatures interchangeable.

Reserved bodyless adapters lower directly to Darwin kernel operations:

```sotlas
@extern(C) fn sotlas_darwin_open(path: *const u8, flags: u64, mode: u64) -> i64;
@extern(C) fn sotlas_darwin_read(fd: u64, data: *mut u8, count: u64) -> i64;
@extern(C) fn sotlas_darwin_write(fd: u64, data: *const u8, count: u64) -> i64;
@extern(C) fn sotlas_darwin_close(fd: u64) -> i64;
```

Errors are normalized to negative `i64` errno values. Linux and Darwin use
different file flags; adapters do not translate flags across platforms.
The final writer rejects Linux operations, Windows imports, unresolved foreign
symbols and unsupported entry arity before opening the output file.

This profile is experimental: cross-build parity is tested locally on Linux
and Windows, and Intel macOS execution is a CI gate. Apple Silicon, Rosetta,
code signing, ASLR, dynamic libraries, separate payload permissions and a
general-purpose process-entry signatures remain outside its contract. The initial
payload segment is RWX; startup is RX. The hosted distribution remains
necessary for canonical features outside the native compiler-source subset.

#### Native Intel macOS compiler

`darwin.sotlas` is a native file driver for the same production lexer, parser,
semantic checks, Target IR, x86 writer and owned linker used by Linux and
Windows. It reads/writes files through the reserved Darwin kernel adapters,
uses Darwin output flags, and emits executable files with mode `0755` after
the complete artifact has passed validation. Failed compilation preserves an
existing output. The compiler-source and import limits match the other drivers.

Linux or Windows seeds can build the native macOS compiler from its original
module files in the installed namespace tree:

```sh
sotlas-native --build-mac-cc sotlas-native-mac INSTALL/src INSTALL/src/sotlas/compiler/darwin_driver.sotlas
```

The reserved entry `sotlas_darwin_main(argc: u64, argv: *const *const u8) -> u32`
has a dedicated ABI descriptor, distinct from Linux entry and Boolean parameter
flags. Startup captures the static XNU argument stack before aligning `rsp`.
Ordinary two-parameter functions cannot select this contract implicitly.

On Intel macOS, the resulting compiler can check a file, compile applications,
discover imports, and rebuild itself:

```sh
./sotlas-native-mac --check app.sotlas
./sotlas-native-mac app.sotlas app
./sotlas-native-mac --build-cc stage2 INSTALL/src INSTALL/src/sotlas/compiler/darwin_driver.sotlas
./stage2 --build-cc stage3 INSTALL/src INSTALL/src/sotlas/compiler/darwin_driver.sotlas
cmp stage2 stage3
```

Tests verify full native Linux/Windows cross-build byte parity locally. CI
executes file I/O, argument paths with spaces, failure preservation, original
module generation, Stage 2/3 byte identity and a Stage 3 application on Intel
macOS without host build tools on PATH. This candidate requires its CI result
before its native macOS runtime is certified. CI #1174 passed those gates for
`bb9a827559436bf7e703da2bd9d45f259b74c221`, certifying this bounded Intel macOS
compiler-generation profile.

#### Native signed 32-bit profile

The native frontend/backend now accepts `i32` in parameters, return values,
locals, four-byte fields, bounded arrays and typed pointers. It executes
signed comparisons, add/subtract/multiply, negation, bitwise operations,
division/remainder and arithmetic right shift. Calls use the existing bounded
internal ABI, including stack arguments. Casts widen signed `i32` with sign
extension and unsigned `u32` with zero extension.

Literal bounds are checked. Shift counts must be in `[0,31]`; known invalid
constants fail compilation and invalid dynamic counts trap before execution
of the shift. Signed indices and implicit mixed
signed/unsigned arithmetic remain rejected. Add/subtract/multiply and negation
wrap at 32 bits in this x86 profile. Division by zero and the `INT_MIN / -1`
or `% -1` overflow case raise a process-level arithmetic fault. These rules
do not define C11 signed overflow or the language-wide overflow contract.

The dedicated native signed tests compare defined arithmetic with C11,
validate memory/CFG behavior, and isolate arithmetic-fault execution in child
processes. The file-driver gates compile and run a signed example without
Python/C build tools on PATH. This extension requires its own CI validation.

#### Signed byte, word and wide integers

The native profile now accepts `i8` and `i16` across scalar calls, locals,
fields, bounded arrays and typed pointers. It also executes signed `i64`
division, remainder and arithmetic right shift. Values and parameter slots
are normalized with sign extension, while memory keeps the declared 1/2/4/8
byte width. Explicit casts preserve signed widening and destination-width
narrowing; implicit mixed-type arithmetic remains outside the profile.

Signed shifts accept constant and variable counts in `[0, width-1]`.
Known invalid constants fail compilation; invalid dynamic counts trap before
the shift. Add/subtract/multiply
and negation wrap at the declared machine width. Division by zero and each
type's `MIN / -1` or `% -1` case fault in the native process. These backend
rules do not define language-wide overflow or C11 signed-overflow equivalence.

The signed-family gates verify narrow memory layout, neighboring fields,
array stride, register/stack arguments, casts, defined C11 arithmetic parity
and exact arithmetic faults. The file-driver gates exercise a mixed-width
program. CI #1178 certified the signed-family implementation and fresh-build
SV2 gates after the stale compiler-cache regression was corrected.

#### Bit operations and variable shifts

The owned x86 profile accepts `~`, `&`, `|`, `^`, `<<` and `>>` on signed and
unsigned integers with widths of 8, 16, 32 and 64 bits, including `usize` and
`isize`. Operand types must match; casts remain explicit. Complement and left
shift retain the declared width. Right shift preserves the sign for signed
values and inserts zero bits for unsigned values.

Counts can come from parameters, calls, memory or expressions. Every executed
shift checks the complete count against the declared width before x86 can mask
CL. Negative signed counts and counts at or above the width fault with `ud2`
(`SIGILL` on Unix, `STATUS_ILLEGAL_INSTRUCTION` on Windows). A 64-bit count is
checked in RCX, so a value such as `4294967296` cannot pass as zero. Direct
invalid constant counts fail before object output. Boolean, pointer and float
operands are rejected. This is the owned-x86 contract; it does not define
invalid-shift behavior for C11 or another backend.

Short-circuit `&&` and `||` retain lazy evaluation when an operand contains a
shift. Calls used as an operand or count run once. There is no implicit rotation
or count masking; a rotation must normalize the count and handle zero explicitly.

[`native_bit_operations.sotlas`](../examples/native_bit_operations.sotlas)
combines CRC-32, rotation and byte unpacking. It exits with 42 when its checks
pass. Compile it with the matching native driver:

```sh
sotlas-native --check examples/native_bit_operations.sotlas
sotlas-native examples/native_bit_operations.sotlas bit_operations
./bit_operations
```

On Windows use `sotlas-native.exe` and `bit_operations.exe`. These commands need
the initial native seed, with no Python/C build tools on PATH. The dedicated
gates check valid execution, exact native faults, memory/stack counts, lazy
conditions and defined-input C11 parity. Linux, Windows and Intel macOS driver
gates execute the same workload; this extension awaits its candidate CI.

#### Floating scalars and profile discovery

```sh
sotlas-native --help
sotlas-native --capabilities
sotlas-native --check examples/native_float_profile.sotlas
sotlas-native examples/native_float_profile.sotlas float_profile
./float_profile
```

The owned hosted profile executes `f32`/`f64` arithmetic, sign-bit negation,
IEEE comparisons, calls, mutable control flow, typed buffers and fields, zero
static storage and casts between floating precisions. Literals use exact
rational rounding directly to the declared precision, with a coefficient below
`10^18` and at most 18 fractional digits. Scientific notation and broader
decimal forms are rejected. Arithmetic uses the process's FP environment;
the test contract uses default IEEE rounding and exception masks.

Float parameters/results use IEEE bits in the internal GPR/stack ABI. External
float declarations and float process entries are rejected.
Conversions between fixed-width signed/unsigned integers and floats are checked
in the native profile. Integer-to-float conversion follows the FP rounding mode;
float-to-integer conversion truncates toward zero. Finite values are accepted
only when the truncated result fits the destination, including negative
fractions that truncate to unsigned zero. NaN, infinity and out-of-range values
trap with `ud2` instead of publishing an indefinite integer. The full `u64`
range is supported in both directions; values rounded up to `2^64` cannot be
converted back. These are owned-profile rules; C11 equivalence covers defined
inputs only. Boolean/pointer numeric conversions remain rejected.
Initialized scalar storage and scalar module constants are described below.
Freestanding kernels must establish and preserve their FP environment before
using SSE2; this candidate does not certify kernel floating execution.

The profile report also exposes ownership runtime and Flow execution as
unsupported in this native driver. Their canonical hosted implementations are
separate paths. Native `--check` applies the same lowering/backend acceptance
rules as compilation and preserves outputs on failure.

Input is bounded to 2 MiB. Input plus generated names uses a checked 4 MiB
arena. Object emission supports 4,096 data relocations, with explicit failure
on exhausted tables; the function limit remains 512. Candidate CI is required
before these extensions are certified across all three platforms.

#### Initialized storage and expression values

The native scalar profile now supports initialized integer, float and Boolean
statics and repeated scalar arrays. The object writer emits these values in
writable `.data`, independently of zero-initialized `.bss`. Invalid initializers
are rejected rather than silently replaced with zero.

Scalar module constants support bounded arithmetic, bit operations, Boolean
logic and comparisons, with stored compile-time results. Signed overflow,
division by zero, invalid shifts and nonfinite floating constant results fail
before output. Forward scalar constant references are resolved after complete
declaration registration; dependency cycles fail before output. General
constant function calls remain outside the native profile.

Scientific literals accept `e` or `E` and an optional exponent sign. The
decimal exponent is at most 18 in magnitude, and the reduced rational must
fit the existing coefficient and denominator limits.

Local scalar arrays accept value lists and repeated runtime values, with exact
length/type validation. Large repetitions execute a native fill loop and
evaluate the initializer once. Scalar, floating and Boolean `if/else` values
use lazy native CFG arms in returns, calls and loops. Record conditional values
copy the selected arm into independent storage, including nested fields and
the accepted fixed-array fields. Exclusive POD conditional results preserve
ownership transfers. Non-POD ownership payloads remain outside this profile.

#### Native match statements

`match` selects on fixed integer types, Boolean values and the existing enums
with explicit scalar discriminants. The selector is evaluated once. Patterns
may be scalar literals, negative integer literals, typed module constants or
variants of the selector's enum. Duplicate values and incompatible patterns
are rejected. Integer matches require a final `_` arm. Boolean matches may
omit it when both values are covered; enum matches may omit it when every
declared discriminant is covered. Named enum constants retain their nominal
type and cannot act as patterns of a different enum or a plain integer.

```sotlas
fn select(value: u32) -> u32 {
    match value {
        0 => { return 42; }
        _ => { return 1; }
    }
}
```

Wildcard-free matches check the selector's representation before dispatch.
An invalid enum value produced through `unsafe` traps before any arm runs,
instead of selecting the final variant. This is a fail-fast check; trap unwind
and deferred cleanup on hardware faults remain outside the native profile.

Arms accept blocks or one statement, with optional commas between arms.
Arm-local bindings stay scoped. Nested matches, mutable state, record returns
and lexical defers execute through the native CFG. Exclusive states merge
across live arms, while returned arms do not invalidate the continuing path.
Break/continue work in loops when no qualified owner is visible at the match;
owned jump joins remain rejected until their edge analysis is available.

Matches accept at most 64 arms and retain the structured lowering depth bound.
Float/pointer/owned selectors, payload bindings, ranges, guards and match values
used as expressions remain unsupported. The subject and patterns retain their
source spans in `MatchStmt`/`MatchArm` nodes. Lowering emits existing comparison
and branch instructions, with no host runtime for dispatch.

#### Local record arrays

Local arrays of pointer-free records accept exact-length value lists and
repetition. Elements have independent value storage, including nested records
and the existing fixed scalar-array fields. Record strides need not be powers
of two: checked indexing scales by the declared layout size. Indexing supports field reads,
field writes, whole-element assignment, local copies, internal calls, record
returns and conditional values. Index/field chains such as `items[i].value`
are parsed directly.

Repeated initializers run once. Arrays larger than 16 elements copy that value
with a native loop. Record arrays accept at most 4,096 elements and 64 KiB of
element storage per declaration. Literal indices outside their declared range
are rejected; dynamic indices retain the checked native indexing operation.

```sotlas
struct Token { pub value: u32; }
pub fn main_entry() -> u32 {
    let mut items: [Token; 2] = [Token { value: 42 }; 2];
    let copy: Token = items[0];
    items[0].value = 7;
    return copy.value;
}
```

Pointer fields and ownership-qualified payloads remain unsupported. Owned
values cannot be copied into ordinary arrays. Record zero shorthand, aggregate
array parameters/returns and record arrays stored inside other records remain
outside this contract. Deferred ownership-free actions may read/write these
local elements; record return values are copied before deferred writes run.

The object writer supports up to 8,192 call patches and 4,096 data patches,
with a combined relocation table of 12,288 entries. Its scratch tables share
the compiler's existing module-global emission context; emission is sequential.
Capacity exhaustion still rejects the object. Large local scalar arrays retain
their existing 4,096-element bound.

#### Static scalar tables

Global scalar arrays accept explicit lists with exactly the declared number of
elements. Each element is checked and folded using the scalar constant rules,
including references to later constants and lazy conditional expressions.
Integer widths, signed values, float bits and Boolean elements retain their
declared representation. Global Boolean elements can be used directly in guards.

```sotlas
static mut table: [u32; 4] = [0, BASE, BASE + 2, 42];
const BASE: u32 = 20;

pub fn main_entry() -> u32 {
    unsafe { table[0] = table[1] + table[2]; }
    return unsafe { table[0] };
}
```

Nonzero lists become writable `.data`; all-zero lists remain in `.bss`. The
native linkers preserve the same storage when producing ELF, PE and Mach-O.
The explicit-list table holds at most 4,096 elements across the module; compact
repetitions and zero-storage declarations do not use that table. Wrong lengths,
out-of-range values, mixed types, runtime calls, pointer elements, record elements
and table exhaustion are rejected before publishing an object. This profile
does not yet support general aggregate or relocatable pointer initializers.

#### Lexical defer and cleanup

The native structured CFG executes direct deferred calls, assignments and
blocks in reverse registration order. Cleanup runs on normal block exit,
early return and loop break/continue/backedge. Loop jumps clean only scopes
inside that loop. Scalar and record return values are evaluated before deferred
writes run. Captured identifiers refer to bindings visible at registration;
later shadows do not change the capture, and mutable storage is read at cleanup.

Each function accepts at most 128 active lexical defers. Nested defers,
return/break/continue inside a deferred payload, deferred error propagation,
bare-name cleanup and qualified declarations in deferred payloads are rejected.
Read-only calls may capture qualified POD roots. The verifier reserves those
roots until lexical cleanup and rejects intervening moves or consuming calls.
Qualified POD roots can also be borrowed by a bounded deferred block
containing only direct, non-owning calls. Those calls execute in source order
during cleanup while defer registrations remain LIFO; moves remain prohibited
until the lexical scope exits. Deferred assignments, nested defers, owned-value
copies, arbitrary statements and general qualified captures remain rejected.
This contract does not provide ARC/drop integration or unwind.

#### Deferred owned-borrow argument effects (SV8.46)

When a `defer` captures a qualified POD owner through a read-only internal
`direct` or `whisper` call, native semantic analysis proves that its argument
expressions have no unmodeled effects at cleanup. Literals, field reads,
arithmetic and bounded, transitively checked local pure helper calls are allowed.
Unsafe expressions, pointer/address operations, mutations and unknown or
recursive helper calls fail closed. The analysis has a maximum call/AST depth
of 32; no host-language optimizer, C11-generated code or Python analysis is
used.

The **deferred observer itself is not required to be pure**: logging to
unrelated global storage inside an existing checked `direct` observer
remains legal. Ownership moves stay prohibited until lexical cleanup. Existing
ownership-free defers and the LIFO/source-order contract are unchanged.
This is not general effect inference, ARC, drop glue, or unwind handling.

##### SV8.47 regression clarification — field-array setup

The native projected-`defer` acceptance gate now constructs its
two-element array through a verified local array-list initializer, copies
that value independently into a POD record field, then transfers the
record to a mutable sole owner. Both steps have explicit native execution
coverage. The deferred indexed read and its reservation, before-cleanup
mutation, after-cleanup move and premature-move rejection are unchanged.

Embedding an array-list literal directly into the same record initializer is
tracked as a separate validation gap instead of silently treating a
type-error during test setup as a `defer`-ownership failure.

##### SV8.47 direct-borrow cleanup regression — corrected error position

In `NativeI32Tests.compile`, an extra `module probe;` line precedes the supplied source.
The recurring error at line 3, column 42 consequently pointed to the RHS
`v` in `unsafe{total=v;}`, not the record/array initializer. Storing
a `direct u32` alias into a global is correctly rejected by the native
ownership checker. To record the borrowed scalar's *value* during cleanup,
the checked positive test stores an independent computed scalar:
`unsafe{total=total+v;}`. A new negative gate preserves rejection of
the original direct alias storage. Indexed projection, lexical defer
registration, observation of the updated value, permitted post-scope move and
rejection of premature moves all remain in place.

#### SV8.47 regression note

Resolved internal scalar calls return independent values, not borrow aliases of
their argument owners. The checker must retain owner roots for direct indexed
and conditional references but must not carry those roots through the already
checked independent scalar return. The lexical pure-name verifier uses bounded,
shared local/parameter scanning to avoid unnecessary native codegen growth.
The deferred indexed-array test constructs a plain value before transferring
it into a mutable sole owner, preserving the scope-reservation contract.
The last certified CI remains the SV8.46 green run until all platforms pass.

#### SV8.47 — checked effect names and projected borrow roots

The native effect checker resolves a deferred helper's argument identifiers to
function parameters or earlier lexical declarations. Internal instance/static
callees are identified through their checked AST identities, not by treating
the method name as a variable. Unsupported global state dependencies, inline
assembly, mutation, `unsafe`, recursion and unbounded loops are not proven
effect-free. This conservative restriction applies to owned-borrow defer
arguments, not to the observer body's existing checked logging behavior.
Errors use the dedicated `deferred argument has unproven effects` cause in
the three native CLIs with their existing positions and preserved output files.

Direct/whisper borrow tracking also follows an indexed array field back to its
owner and includes conditional guard expressions when accumulating borrowed
roots. Such owners cannot be consumed by another argument to the same call.
A deferred projection holds its reservation through cleanup; a post-scope move
remains permitted. Unsupported owner-bearing expressions reject rather than
erasing identity. This is not general lifetimes, stored aliases or ARC/drop.

#### SV8.48a — native deferred helper capabilities

Helpers invoked as arguments of an owned-borrow deferred call must now satisfy
the checked typed call boundary as well as the existing transitive body proof.
Consuming `sole` parameters and unknown ownership domains cannot be certified
effect-free, even if the function body only reads a field. Ordinary POD input
values and read-only `direct`/`whisper` parameters remain supported.
Pointer parameters fail closed except a checked native `self:&Self` instance
receiver; pointer or ownership-qualified results are not independent
effect-free scalar outputs.

This check leaves the deferred observer's allowed independent logging intact.
It does not implement general effect inference, ARC/drop, region lifetimes,
global package capabilities or resource cleanup.

#### SV8.48b — typed native call capability metadata

Sotlas AST lowering now attaches two-bit ownership facts per argument to each
native `TargetOpcode::Call`. The existing instruction header carries this
semantic information in `flags` and `immediate_bits`: plain arguments are 0,
`sole` transfers are 1, `whisper` borrows are 2, and `direct` borrows are 3.
Up to 24 source parameters are retained in declared order; a hidden
aggregate-return destination is plain. The Target IR validator rejects
out-of-range or unrecognized tagged capability data; old manually constructed
Call entries with zero metadata remain compatible.

This is an in-memory typed call boundary and does not change ABI, machine
instructions, emitted object contents, ARC, resource cleanup or imported
signature resolution. The cross-platform native test suite remains the
certification gate before calling this advance green.

#### SV8.48b Windows bootstrap regression repair

The native call-capability encoder relies on the existing call-site arity check instead of scanning declarations a second time. It retains the strict 24-argument limit and fail-closed unknown domain handling, including the plain hidden aggregate-return pointer.

The Windows argv parser uses unsigned bitwise parity and shift for the slash count. For usize, (slashes & 1) == 1 is equivalent to slashes % 2 == 1, and slashes >> 1 equals slashes / 2. Both avoid expensive native division/modulo lowering inside nested control flow. Existing quoted path execution tests and IR invariants remain required.
#### SV8.48b native Stage1 IR headroom

The self-hosting Stage1 now allocates 131,072 TargetValue slots, 262,144
TargetInstruction slots, 524,288 TargetOperand slots, and 65,536 TargetBlock
slots, with the same bounds enforced by the native IR builder. This prepares
for large combined-module cross-builds such as the Windows file driver and
does not change the language, parser capacity, ABI, ownership validation or
emitted Target IR format. Capacity constants are required to match their
actual static backing arrays by a dedicated contract gate. The full matrix
must succeed before treating this as a certified fix.

#### SV8.48b Windows native Stage2 fixed-point CFG hardening

The Windows-native command-line parser is split into an outer argument/whitespace
loop and `windows_parse_one_argument`, which implements the same Windows
quote, doubled quote and backslash escape rules as the original. Repeated byte
append plus index increment and bounds failure are consolidated in
`windows_push_argument_byte`; it returns the reserved index 4096 on
failure and never exceeds the original 4095 payload-character rule.

The outer loop ensures that the consumed index strictly advances, limiting
progress and rejecting incomplete quotes exactly as before. The parser retains
the 67 argument / 32768 command bytes contracts and NUL-terminated global
argument pointers. The independent function boundaries reduce the deeply
nested native CFG in the Windows PE bootstrap without disabling any parser
checks. The existing Windows Stage2/Stage3 fixed-point and quoted-path runtime
tests remain unchanged and are required before certifying this repair.

#### SV8.48b Windows self-hosted Target IR arena parity

The Windows native driver owns a separate set of static Target IR arenas. Its
arrays and `ScalarLowering::new` arguments now match the compiler's certified
large combined-module capacities: 131072 values, 262144 instructions, 524288
operands, 65536 CFG blocks and 8192 function entries. The previously enlarged
`native_compiler/main.sotlas` buffers were not sufficient because the
Windows file driver does not use those globals when rebuilding Stage2/Stage3.

The driver retains its existing guarded allocations and diagnostics; all
actual Windows native PE fixed-point and quoted-path tests remain required.
A structural CI contract verifies capacity parity between the native compiler
and Windows driver to prevent another partial capacity update.
#### SV8.48b — installed native Linux seed and driver arena parity

All three independently compiled native file drivers now provide the same
Target IR arena headroom as `native_compiler/main.sotlas`:
131072 `TargetValue` entries, 262144 `TargetInstruction` entries, 524288
`TargetOperand` entries, 65536 `TargetBlock` entries and 8192
`TargetFunction` entries. Both the real static backing arrays
and the capacities passed to `ScalarLowering::new` are aligned for Linux,
Windows and Intel macOS; all existing validation and overflow rejection
remains enforced.

The distributed Linux-native seed is built from `linux_driver.sotlas`, not
`native_compiler/main.sotlas`. It must be able to rebuild the bundled
Windows driver and the Darwin driver without host compilers. A contract
test verifies all three drivers against the canonical capacity profile;
the installer and all real native smoke/Stage2/Stage3/PE/Mach-O gates remain
mandatory for certification.

#### SV8.48c — typed void calls and capability-signature agreement

Native void-returning calls now carry the same per-argument 2-bit ownership
profile as scalar and record-return calls. The existing `target_module_validate_calls`
checks tagged roles against callee SSA parameters' ownership-domain flags,
rejecting forged or contradictory metadata and unproved non-plain roles at
external declarations. It also retains type and arity equality checks.

The explicit signature validator is not yet a mandatory phase at every
native emission entry point; that separate end-to-end proof remains open.
No new FFI, lifetime, ARC/drop, ABI, source serialization or system capability
rights are enabled. All previous Windows Stage2/Stage3, installed Linux seed,
and macOS native selfhost tests remain mandatory.

#### SV8.48d — checked signatures at ELF object emission

The unified native ELF64 object writer now requires the typed
`target_module_validate_calls` proof before generating object bytes. This
verifies full CFG/Phi/branch targets and all direct call symbols, arity, scalar
ABI types and tagged ownership capabilities against declared callees. The
validator uses the real module Phi and target buffers instead of passing
null pointers. This retains valid loops/conditional blocks; there is no
second CFG pass on the same boundary.

This is bounded to `emit_elf64_module_object`. Other emitters, cross-object
linking, effects, ARC/drop and full FFI or cross-module capability proof
remain open. ABI, IR layout and existing binary fixed-point CI gates are
unchanged.

#### SV8.48d owned aggregate-return call validation

The unified ELF signature validator treats the final unnamed pointer
parameter of a void-ABI internal function as a synthetic return destination.
Its call role must be plain even when the destination SSA value preserves
sole ownership from a returned record. Named parameters still require exact
plain/sole/whisper/direct role equality; forged synthetic positions fail.
All native Stage2/Stage3 and platform matrix acceptance gates remain intact.

#### SV8.48e — specialized scalar CFG signature gates

Two specialized native emitters that already receive complete CFG/Phi and
target tables now use the full typed call-signature validator instead of a
CFG-only check: `emit_elf64_scalar_function_object` and
`emit_x86_64_scalar_cfg`. The verifier performs the CFG proof once and
checks direct-call symbols, parameter arity, scalar types, and any tagged
ownership roles before writing object or assembly bytes.

This does not change the machine ABI, IR layout, supported scalar instruction
subsets, legacy untagged calls, or the unified ELF object writer. Older
multi-function scalar assembly and object emitters have different IR
conventions and remain for a separate change, along with cross-object and
foreign capability guarantees. All Stage2/Stage3, PE, Mach-O and native seed
tests must remain green.

#### SV8.48f — legacy multi-function typed-call gates

The legacy ELF64 multi-function scalar object writer and x86-64 multi-function
assembly writer now invoke the shared CFG and typed direct-call verifier before
any output. Their one-block U32 profile carries no Phi or target arrays: the
validator rejects nonzero declared counts when those pointers are null.
Existing subsets and untagged IR compatibility stay intact; machine ABI and
emitted formats do not change.

Remaining specialized single-function U32 and three-block conditional assembly
emitters require a separate signature-parity pass (SV8.48g).
Cross-object/foreign capability guarantees and Python/C bootstrap removal
remain open. Acceptance requires the complete CI matrix.

#### SV8.48g — legacy single-function capability boundary

The legacy x86-64 U32 single-function assembly entry point has no TargetValue
domains or imported callee-signature table. Typed call metadata is therefore
accepted only for plain-role calls directly to the same function with an exact
U32 signature and parameter arity. Forged typed capabilities and external
typed calls fail before any output; existing untagged external assembly calls
remain explicitly uncertified legacy compatibility.

The restricted three-block conditional and constant assembly entry points
now reject unrepresentable Phi/target side tables before writing assembly.
No general cross-object ownership/effects, lifetime, ARC/drop or Python/C
bootstrap migration is claimed. Existing Stage2/3 and full CI matrix remain
required.

#### Project diagnostics

Project compiler diagnostics map resolved source positions back to the original
file, line, column and source excerpt after import removal and topological
ordering. Explicit source lists retain their original file positions too.
The source map holds at most 8,192 segments across 64 files and rejects
capacity exhaustion before output I/O. Paths remain bounded to 4,095 bytes.

#### Constant dependencies and control flow

Constant `if/else`, `&&` and `||` expressions evaluate only the selected path.
Inactive arms still undergo type and name validation, and cannot hide function
calls or cyclic dependencies. Static initializers may refer to later scalar
constants. Validation preserves real dependency cache values and restores all
temporary IR identities. Tables remain bounded to 64 declarations, nesting to
64 levels and each temporary expression to 128 instructions. Null pointer
initializers, identity casts and transparent unsafe scalar values retain their
existing behavior.

#### Owned records with scalar array fields

Exclusive POD records may contain inline arrays of 1 through 256 primitive
integer, Boolean or floating values. These fields use the existing native
record layout, including recursively nested plain records. Constructors accept
typed lists and repetition; the count and every element must match the declared
field type. Lists evaluate in source order, and repetition evaluates its value
once. Record copies retain independent field storage.

`sole` transfers and returns preserve move checking. Internal `direct` and
`whisper` parameters can read these fields without consuming the caller.
Borrowed mutation, whole-record escape and use after transfer are rejected.
Local scalar arrays and other scalar array fields can initialize or overwrite
these fields by value, with exact type/count checking and independent storage.
Pointers, qualified elements, nested array types and arrays of records remain
outside this field contract. Heap cleanup and ARC are not provided by POD moves.

Run the public example with an installed native file driver:

```sh
sotlas-native --check examples/native_owned_packet.sotlas
sotlas-native examples/native_owned_packet.sotlas owned-packet
./owned-packet
```

The executable returns 42 on success. On Windows, use `owned-packet.exe` as the
output name and run `.\owned-packet.exe`. The native seed performs these commands
without a Python interpreter, C compiler or external linker; producing that
initial seed still uses Stage 0.

#### Loop exits and POD ownership

Mixed if/else and direct match-arm break/continue exits keep separate owner
states. Continue paths must preserve the loop-entry state. Break paths may
consume a POD owner, but post-loop use is rejected when the break state differs
from the possible zero-iteration exit. Nested loops restore enclosing edge
summaries. Uniform match break/continue exits preserve the same checks.

Lexical defers execute on the actual jump path; an active deferred borrow still
prevents consuming its reserved owner. Fallthrough/jump mixtures, nested mixed
if exits inside match arms and general resource cleanup remain outside this
bounded profile. These gates do not implement ARC or non-POD drop.

#### Internal direct access

`direct T` supports internal function parameters for the same fixed scalars
and pointer-free POD records accepted by the ownership profile. It is a
read-only, non-consuming access domain. Direct calls and forwarding preserve
an exclusive caller's live state, including repeated read aliases. Forwarding
to an internal whisper parameter is also accepted. Scalar parameters use
immutable values; direct record parameters receive the existing record address
without creating the ordinary argument-copy storage.

```sotlas
struct Token { pub value: u32; }
fn read(value: direct Token) -> u32 { return value.value; }
fn forward(value: direct Token) -> u32 { return read(value); }
impl Token {
    fn inspect(self: direct Self) -> u32 { return self.value; }
}
```

Mutation, storing or returning a whole direct value, pointer/address escape,
foreign calls carrying that value and forwarding to a consuming parameter are
rejected. A call cannot borrow an owner while consuming it in another argument.
Fields, globals, direct returns and direct locals remain unsupported. Internal
POD instance receivers support `self: direct Self` and `self: whisper Self`;
an explicitly named receiver must match the enclosing record. Borrowed receivers
cannot overlap a consuming argument in the same call. Scalar field projections
can be converted to scalar values. Read-only deferred calls reserve their
qualified roots until lexical cleanup. Stored aliases, general alias lifetimes
and remaining qualified capture forms stay outside this profile. Static internal calls use the
same checked parameter contract. Domain tags remain in AST and TargetValue
metadata; this access requires no retain/release runtime.

#### Exclusive POD transfers and internal whisper parameters

Explicit `sole T` and `exclusive T` qualifiers support fixed scalars and
pointer-free POD records in locals, internal parameters and returns. Native
analysis tracks moves, use after move and conditional `MAYBE_MOVED` states.
Runtime `&&`/`||` operands merge skipped and evaluated ownership states; a move
on only one path becomes `MAYBE_MOVED`. A statically skipped Boolean literal
operand preserves the owner, while an evaluated consuming operand moves it.
Consuming an outer owner on a repeating loop path is rejected. Domain erasure
through ordinary bindings, assignments, whole-value returns, aggregate fields
or transparent unsafe expressions is rejected.

`whisper T` is limited to internal POD parameters. Record parameters use the
internal address ABI; scalar parameters use immutable values. Read-only calls
and forwarding leave the caller's exclusive owner live. Mutation, storage,
whole-value return, address escape and borrowing across foreign calls are rejected. Passing one
owner as both a borrowed and consuming argument in the same call is rejected.
The profile reports `ownership_analysis=exclusive-pod,whisper-internal,direct-internal`.

These contracts do not provide shared ARC, heap ownership, custom destructors,
weak storage/invalidation or a general borrowed-reference ABI. Their runtime
capability remains unsupported. Domains are retained in AST qualifiers and
TargetValue metadata for accepted bindings, parameters and aggregate return
destinations. See the [closure checklist](sotlas_native_frontend_ownership_checklist.md)
for the remaining migration requirements.


#### Native audit and reporting commands (SV8.50)

Linux, Windows and Intel macOS drivers expose the same bounded command contract:

| Command | Result |
|---|---|
| `--version` | Native driver and in-memory Target IR contract versions |
| `--limits` | Compiler/project bounds, including parameters, blocks and arrays |
| `--target` | Actual image format, architecture, pointer width and ABI limits |
| `--exit-codes` | Error-code mapping, including audit failures |
| `--compare LEFT RIGHT` | Streams both artifacts; returns 0 and `byte-identical` only for equal bytes; returns 14 on a content/length mismatch |
| `--fingerprint FILE` | Streams FNV-1a-64 and prints 16 lowercase hexadecimal digits; this is not a cryptographic hash |
| `--verify-seed FILE` | Checks the native platform/x86-64 executable envelope; returns 15 for unsupported/truncated headers; does not authenticate or execute the file |
| `--self-test` | Compiles an in-memory scalar program through frontend, typed IR and owned object emission; writes no artifact and does not execute the result |

Audit reads use fixed 4 KiB scratch buffers, retry interruptions and fill short
reads before comparing. File handles are closed on every handled result path.
Missing/unreadable files use the existing open/read error codes. Additional
arguments to report commands and missing/extra audit operands fail with usage
code 1. These commands start no Python, C compiler or external linker.

Generation gates exercise the audit commands using actual Stage 2/3 artifacts
with host tools absent. Complete canonical parity and authenticated seed
distribution remain open requirements.

## 14. Standard library API contracts

The following incorporates `stdlib/core/README.md` at the snapshot revision.
It describes library API obligations, not automatic native compiler ownership
integration for every module or allocation.

### Core standard library contracts

This page describes the public ownership and failure contracts in `alloc.sotlas`,
`result.sotlas`, and `string.sotlas`. All sizes and string indices count bytes.
`StringSlice` construction does not validate UTF-8 or prove that its pointer
covers `length` readable bytes. Callers must provide a live readable range for
every non-empty slice; call `string_is_valid_utf8` when text validity matters.

#### Strings

| API | Ownership and mutation | Failure behavior |
|---|---|---|
| `string_from_raw`, `string_as_bytes`, `string_slice`, `string_trim*` | Borrow the original storage; the caller keeps it alive. Slices do not copy or free bytes. | Invalid bounds return an empty slice. A non-empty pointer and its stated extent remain the caller's responsibility. |
| `string_len`, `string_is_empty`, `string_char_at`, `string_try_byte_at`, `string_equals`, `string_compare`, `string_starts_with`, `string_ends_with`, `string_find*`, `string_split_once` | Read borrowed inputs only; indices and results count bytes. | `string_char_at` returns `0` for a missing pointer or out-of-range index. `string_try_byte_at` returns `false` for invalid input and leaves its output unchanged, so embedded NUL bytes remain distinguishable. `string_find*` returns `-1` when absent or malformed; `string_compare` returns `-2` for a non-empty null slice. Empty needles are handled without dereferencing their pointer. |
| `string_is_valid_utf8` | Reads a borrowed byte slice and does not allocate. | Returns `true` for empty input, including a null-backed empty slice. Returns `false` for a non-empty null slice, malformed sequences, overlong encodings, surrogate code points, truncated sequences, and code points above U+10FFFF. It validates but does not change the byte-oriented behavior of other string APIs. |
| `string_new` | Wraps caller-owned mutable storage. The `String` does not own or free that buffer. | No allocation occurs. Mutating operations return `false` when capacity is insufficient. |
| `string_new_in_arena`, `string_reserve_in_arena` | Storage belongs to the supplied arena. The arena must outlive the string; resetting the arena invalidates all strings allocated from it. | Allocation failure returns an empty string or `false`. Failed reserve leaves the original string fields and contents unchanged. |
| `string_parse_u32` | Parses a borrowed slice without allocation; accepts ASCII decimal digits only and does not trim whitespace or accept a sign. | Returns `ResultU32::ok` for values through `4294967295`, `InvalidParam` for empty, null-backed, or non-decimal input, and `Overflow` above the `u32` limit. |
| `string_parse_i32` | Parses a borrowed slice without allocation; accepts ASCII decimal digits with one optional leading `+` or `-`. It does not trim whitespace. | Returns `ResultI32::ok` for values from `-2147483648` through `2147483647`, `InvalidParam` for empty, null-backed, sign-only, or non-decimal input, and `Overflow` outside the `i32` range. |
| `string_new_with_allocator`, `string_reserve`, `string_append*`, `string_concat_into` | Allocator-backed strings own their current buffer. Keep the allocator and its context alive until deinitialization. Slice inputs are borrowed and copied into the destination; appending an empty slice is a successful no-op, including a null-backed zero-length slice. Appending a slice of the destination itself is supported, including when growth relocates its buffer; overlapping fixed-buffer copies preserve the source bytes. | Allocation, capacity overflow, malformed non-empty input, and insufficient storage return `false` or an empty allocation result. Failed growth preserves the original data, length, capacity, and allocator. |
| `string_deinit` | Releases an allocator-owned buffer and clears the string. Call once for each live owned string; the allocator must outlive the call. Caller-owned and arena-owned buffers must not be passed as allocator-owned values. | Null input is a no-op. The function clears fields, making a second call a no-op. Automatic destruction is not provided by this API. |

Owned strings returned by value require the caller to preserve one live owner and
call `string_deinit` exactly once. The current language does not yet connect this
library contract to automatic move-aware destruction for every return path.

#### Allocators

`Allocator` is a borrowed callback table. Its `context` and callback functions
must remain valid while any allocation made through it is live. `allocator_alloc`
and `allocator_realloc` return null on failure; callers retain responsibility for
the old allocation if reallocation fails. `allocator_free` invokes the configured
callback and does not clear aliases held elsewhere.

`ArenaAllocator` and `BumpAllocator` use caller-provided backing memory and never
obtain storage from the operating system. An allocation returns null when the
buffer cannot satisfy the requested size/alignment. `arena_reset`,
`arena_restore`, and `bump_reset` invalidate allocations after the selected
point; every pointer into that storage must be treated as expired. A checkpoint
is only valid for the same arena and a position previously reached by that arena.
Arena allocation rejects offsets beyond capacity, address wraparound, and size or
alignment requests that exceed the remaining buffer. Capacity arithmetic is
validated before the offset is advanced.

#### Foundation string buffer

`foundation::string_buf::StringBuf` is a caller-owned, fixed-capacity,
null-terminated byte buffer. Its capacity includes the trailing NUL byte, so a
zero-capacity buffer cannot accept appends and a one-byte buffer can only hold
the terminator. `string_buf_append_str` and `string_buf_append_bytes` either
append the complete input or return `false` without changing the buffer. Byte
appends support input ranges that overlap the destination buffer. The caller
must provide readable source storage and writable backing storage for their
declared extents. The API is byte-oriented and does not validate UTF-8.

#### Ring buffer

`core::ring_buffer::RingBuffer` is a single-threaded FIFO over caller-owned
storage. The storage must remain writable and live for the entire initialized
lifetime. `ring_init` resets the struct before validating its inputs, so a null
storage pointer or zero capacity leaves a safe empty state. Push, pop, peek,
and batch operations reject zero capacity, out-of-range indices, and counts
larger than capacity before indexing storage or applying modulo. The fields are
public, so callers must not mutate them while using the API. The type uses no
atomics or locks; concurrent and interrupt access requires external
synchronization and is outside this contract.

#### Reference counting

`core::arc::ArcHeader` provides atomic `arc_retain`/`arc_release` operations for
shared references and explicitly single-threaded `arc_retain_local`/
`arc_release_local` helpers. Retain fails for a zero or saturated count. Release
returns `true` only for the transition from one reference to zero; a repeated
release at zero returns `false` and leaves the count unchanged. Local helpers
must not be used for references shared across threads or CPUs. Callers remain
responsible for freeing the allocation exactly once after the final release.
`SharedCounter.retain` returns whether the atomic retain succeeded.

#### Bounded vector and result values

`foundation::generic_vec::Vec<T>` is an experimental source declaration. The
current C11 backend does not specialize generic structs or methods. It accepts
the declaration for parsing and type checking, then fails closed with a Sotlas
diagnostic when asked to emit that generic module or to call a generic method;
no invalid C is emitted. Parsing and type checking the declaration do not make
the generic collection usable at runtime. Use `foundation::vec::VecU32` for native
programs in this preview. That bounded collection uses caller-provided storage,
reports zero capacity when constructed with a null backing pointer, and does
not allocate or destroy elements. Its `clear` operation only resets length;
element cleanup remains the caller's responsibility.

`foundation::vec::VecU32` is a fixed-capacity vector over caller-provided
mutable storage. The backing array must outlive the vector and have at least
`cap` writable elements. Constructing it with a null backing pointer yields an
empty vector with zero capacity. Query functions treat null vector pointers,
unavailable backing storage, and malformed lengths as empty; mutating functions
are no-ops or return failure. `vec_push`
returns `false` without changing length when the pointer is null or the vector
is full. `vec_get` and `vec_pop` return
`OptionU32` with `has_value == false` for missing elements; neither operation
allocates. `vec_clear` resets length but does not zero or destroy elements.
`vec_pop` returns the last value and decrements length; popping an empty vector
fails. Reads and pop also fail closed if the public `length` field exceeds
capacity.
This concrete `u32` collection does not provide generic element destruction.

`core::result::ResultBool`, `ResultU32`, `ResultI32`, and `ResultU64` carry a
`ResultCode` and a scalar value. `ok` sets `ResultCode::Ok`; `err` stores the
supplied code and clears the value (`false` for `ResultBool`). The code set includes `Overflow` for numeric conversion
outside a result type's range. `unwrap_or` returns the value only for `Ok`, while
`unwrap` uses zero as its fallback. `try_unwrap(out)` copies the value and
returns `true` only for `Ok`; it leaves `out` unchanged for an error or null
pointer. Use it when zero is a valid success value and the caller needs an
unambiguous success check. These result records own no heap memory. Native
coverage checks zero-valued success, signed and maximum-width values, and that
errors preserve both their code and the caller's output storage.

`foundation::hashmap::HashMapU64` uses caller-provided fixed-capacity storage.
Constructing it with a null entries pointer yields an empty table with zero
capacity.
`hashmap_get` returns `OptionU64` and preserves all 64 value bits. Updating an
existing key does not increase the count; removal repairs the affected probe
cluster so later colliding keys remain searchable. The table does not allocate
or grow. When storage is full, a new key is rejected while an existing key can
still be updated without changing the count. Lookup and removal reject zero
capacity before computing a probe index, including when public count fields have
been corrupted.

#### Verification scope

`tests/native/test_string_native.sotlas` exercises empty and malformed slices,
failed fixed-buffer and arena growth, allocator-backed growth, overlapping
fixed-buffer append, self-append across relocating reallocation, and explicit
cleanup through the checked C11 project pipeline. `test_arena_overflow_native.sotlas`
checks exhaustion and address wraparound; `test_string_buf_native.sotlas` checks
zero, one, and two-byte capacities in native execution. These tests do not
dereference arbitrary invalid non-null addresses, because that is undefined
behavior in the C11 runtime.

`tests/native/test_string_buf_native.sotlas` also checks atomic rejection when a
string does not fit, overlapping self-append, and source and destination address
wraparound. `tests/native/test_ring_buffer_native.sotlas` executes wraparound,
FIFO ordering, full and empty behavior, invalid reinitialization, and corrupted
public index and count rejection through the canonical C11 compiler.
The canonical shared-domain gate also exercises `VecU32` full/empty and bounds
behavior with `ResultU32` success and error construction through native C11.
The stdlib runtime test covers null handles, full/empty behavior, successful and
empty `pop`, `clear` preserving capacity and backing bytes, and a corrupted
`VecU32.length` above capacity; the malformed reads/pop fail without indexing
storage or decrementing length.
The hashmap native gate checks full-width values, updates while full, rejection
of a new key at capacity, stable counts, and lookup through a collision cluster
after removal. It also corrupts the public count while capacity is zero and
checks that lookup/removal fail without a divide-by-zero trap or count mutation.
When backing storage is unavailable or `count > capacity`, length reports zero
and insert, lookup, and removal fail closed. The test verifies that operations
leave the corrupted entry and count unchanged.

## 15. Documentation source inventory

Every tracked Markdown input is included in this provenance inventory. Source
paths and SHA-256 hashes of UTF-8 text with LF-normalized newlines identify
the snapshot used for this consolidation. Architecture,
release, historical, tutorial and tooling documents serve different purposes;
their claims must be interpreted through the current implementation contracts.

**Input documents: 64.**

| Source document | Consolidated coverage | SHA-256 |
|---|---|---|
| [CHANGELOG.md](../CHANGELOG.md) | Historical snapshot / change history | `59e11c24075334268572d66d1c386127f13b7a0de9483d63433e437d2e4bc324` |
| [README.md](../README.md) | Language, safety, usage or architecture reference | `51dac0dda2d7d5e8f6c26f0cf7b30a5582596d449fdfe03330d7e70456eedfab` |
| [README.pt-BR.md](../README.pt-BR.md) | Language, safety, usage or architecture reference | `01f6118e45200152a9cf93c49507c58a3c9aa93138b7287ba09ed7125022b364` |
| [bootstrap/sotlas/native_driver/README.md](../bootstrap/sotlas/native_driver/README.md) | Current native contracts; incorporated in full | `6fd92f10a66e117daef02e2717d3adda1b0522c4e9f13c4affcda391e1e4d96e` |
| [bootstrap/sotlas/native_examples/README.md](../bootstrap/sotlas/native_examples/README.md) | Example scope and reproduction instructions | `4c6c8e3e582db954a4c43584753c1e19d451f42fe0a349e19840b859344ef344` |
| [docs/QUICKSTART.md](QUICKSTART.md) | Language, safety, usage or architecture reference | `6c9cfef7030008db2cc4f8ae7a43715d659847e4cd6b7f205564ebfa168f122f` |
| [docs/README.md](README.md) | Language, safety, usage or architecture reference | `f6484916915718109cbb6779835a5db404d1b4fe1f4781ca96cbdfdaf09dc36d` |
| [docs/SAFETY_GUARANTEES.md](SAFETY_GUARANTEES.md) | Language, safety, usage or architecture reference | `ad4430b8d83041a8b18bc7af76f9444072c6f5e34dfa53201e5fee87e6a8d63f` |
| [docs/SPEC_SOTLAS_1.0.md](SPEC_SOTLAS_1.0.md) | Architectural design and language vocabulary | `0e86b394bc73d287f8a45421a4777127dd3ecc16774dc23f839f5a5c22ea9458` |
| [docs/archive/sotlas_implementation_status_2026-09-23.md](archive/sotlas_implementation_status_2026-09-23.md) | Historical snapshot / change history | `f111e11d759432807bb973f32b287a46d920d6442328687820263918110a2380` |
| [docs/bootstrap.md](bootstrap.md) | Native generation and dependency migration | `82978ee101f8f943e3af98d7a74b3ca4eb2adcdcd2c9dab8f317e81541bc563d` |
| [docs/compiler_architecture.md](compiler_architecture.md) | Language, safety, usage or architecture reference | `90e04131f88445b6c575a529d79672582ff46c91f259fd83b8609dd29992ba40` |
| [docs/current_implementation_progress.md](current_implementation_progress.md) | Dated implementation/evidence snapshot | `68c73c7fa7510c65f2d9c94b0e4066d85a87b3cc1aede46e893d861d6441a9cd` |
| [docs/ecosystem_and_registration_roadmap.md](ecosystem_and_registration_roadmap.md) | Website, ecosystem and integration metadata | `349581c06dde4e94cce543c932f89e91447d33bcc81d75e13852aeea88d2f4df` |
| [docs/flow_cpu_preview.md](flow_cpu_preview.md) | Language, safety, usage or architecture reference | `1699de951de4f8b8d93c89bbd9fc52eee4ab4fb4c22cc91a5bf17bc9ec1e4be0` |
| [docs/github_linguist_submission_guide.md](github_linguist_submission_guide.md) | Website, ecosystem and integration metadata | `c68ae1c30a541dd9e7e6516f01297d006c8969bb94157bf809c24bff70854368` |
| [docs/guided_tour.md](guided_tour.md) | Language, safety, usage or architecture reference | `1262e4d209479753add6837bb6f3d7bc243a0ae07a90041b3cb43a42d2e65941` |
| [docs/high_level_and_self_hosting_roadmap.md](high_level_and_self_hosting_roadmap.md) | Native generation and dependency migration | `db251a1364f53fd37effb69ea407773fb1703a9ca0071edf6837a615b5d0cae2` |
| [docs/interop_c_cpp_objc.md](interop_c_cpp_objc.md) | Language, safety, usage or architecture reference | `ba53b21a2fd4cb2b182c874f3b74e6054deec47dbcddc85fc1ddfbf2a1a33b0a` |
| [docs/language_reference_en.md](language_reference_en.md) | Language, safety, usage or architecture reference | `b7be6767cb526d0bf28a649a1b8ea9f7e3e510984ec56879cd92a8466a6ffc67` |
| [docs/language_spec.md](language_spec.md) | Language, safety, usage or architecture reference | `04b5022047277f49ab20ccbba83ceb63ebf502566b40a182c42257b8bdc1ab9d` |
| [docs/opencl_gpu_preview.md](opencl_gpu_preview.md) | Language, safety, usage or architecture reference | `11dda28cff683ff44086ccd2e4418e88c24cb5abf23abe21a513cfaf5c06ce89` |
| [docs/phase0_reality_audit.md](phase0_reality_audit.md) | Dated implementation/evidence snapshot | `e89f2fa304d38245abc7162229f175118d9c8c696d21d4a3ded977562ad4fd4b` |
| [docs/phase1-semantic-core-status.md](phase1-semantic-core-status.md) | Dated implementation/evidence snapshot | `1ef8cd3daba3d223d2f136e4e023cc81dada745c238d856feede1f88d3fa40c0` |
| [docs/phase_gate_matrix.md](phase_gate_matrix.md) | Bounded release/phase acceptance contracts | `c946f3e8e56184d1f1f7e812b3e241535c187d4dca16581c50fd4f0720bb9579` |
| [docs/preview_status_and_gaps.md](preview_status_and_gaps.md) | Dated implementation/evidence snapshot | `809e206e928316912b1f2554ed5b3f339f015232b87dab132a526d22a626d635` |
| [docs/safety_and_ffi.md](safety_and_ffi.md) | Language, safety, usage or architecture reference | `b3b0f4a19a4a37ac61a9d27aa790192569c3234d8c4e0b3cce4cd361de96197b` |
| [docs/self_hosting_migration.md](self_hosting_migration.md) | Native generation and dependency migration | `e6ed6536c320d1dfd627ce3c77ea423522215121ebc7b63f7ab6885f71f45b8d` |
| [docs/sir-status.md](sir-status.md) | Dated implementation/evidence snapshot | `973a43b7df03794c1c5f52a0b3a822f73968bee7b3599add0b43b1246de2ca77` |
| [docs/sotlas_1_0_phase10_guarantees_scope.md](sotlas_1_0_phase10_guarantees_scope.md) | Bounded release/phase acceptance contracts | `a889716aea84a99d258cd8d19aa50c6aba2fc87a3ee8bc1ed00f59481fb69b5d` |
| [docs/sotlas_1_0_phase3_authority_scope.md](sotlas_1_0_phase3_authority_scope.md) | Bounded release/phase acceptance contracts | `d4f5bdf3c5767bca094f0dd70b98de1f144ff2e5dc80948eb3b38bd467688af9` |
| [docs/sotlas_1_0_phase4_state_space_scope.md](sotlas_1_0_phase4_state_space_scope.md) | Bounded release/phase acceptance contracts | `93b3b86463875b67cc3aea39a0a843e072fb0203b3b8a8bc516cf6b530843401` |
| [docs/sotlas_1_0_phase5_effects_scope.md](sotlas_1_0_phase5_effects_scope.md) | Bounded release/phase acceptance contracts | `7bfd80894cd1e83e1d4fe3203d5fa63a10bb9fce53d6497924f0f7621d2e12b9` |
| [docs/sotlas_1_0_phase6_flow_scope.md](sotlas_1_0_phase6_flow_scope.md) | Bounded release/phase acceptance contracts | `e4c1dcc6bb1f811d746e9b9c6552fb376fe9042445691dd8fd58372e5fafcfba` |
| [docs/sotlas_1_0_phase7_execution_scope.md](sotlas_1_0_phase7_execution_scope.md) | Bounded release/phase acceptance contracts | `3c85730c8c3863b57abd25e73e8a7e515164b4c101fd69d9ab54515a56037f77` |
| [docs/sotlas_1_0_phase8_heterogeneous_compute_scope.md](sotlas_1_0_phase8_heterogeneous_compute_scope.md) | Bounded release/phase acceptance contracts | `39eb8ef24caf917801f9545d27a68a3a68f7f00e901e846a1697a91ff623e564` |
| [docs/sotlas_1_0_phase9_trust_domains_scope.md](sotlas_1_0_phase9_trust_domains_scope.md) | Bounded release/phase acceptance contracts | `44eab9c3dce75d3b699a85456405306a2b55a9abb0debd60f646dc27e055bba5` |
| [docs/sotlas_1_0_phases_11_12_scope.md](sotlas_1_0_phases_11_12_scope.md) | Bounded release/phase acceptance contracts | `bfc6ee295ff09b9ee3e2b6710c228b7cc3f49bf599d027fdca96cbc01c6be781` |
| [docs/sotlas_1_0_phases_13_17_scope.md](sotlas_1_0_phases_13_17_scope.md) | Bounded release/phase acceptance contracts | `5577e73688c0ae42fd92158fa7d4b941fa65db9ac166988607c92c5bb426a7bf` |
| [docs/sotlas_1_0_release_scope.md](sotlas_1_0_release_scope.md) | Bounded release/phase acceptance contracts | `5146a2f79ff84b4c040d56acc25112f7f00cca3b154a1be2d1842301e1b8bac5` |
| [docs/sotlas_development_blueprint.md](sotlas_development_blueprint.md) | Development dependencies, backlog and release policy | `8e88b2dcad368d44fd75df3e9346ede5db9ee203d6c4fa76a6a0692f07bf65a8` |
| [docs/sotlas_full_implementation_plan.md](sotlas_full_implementation_plan.md) | Development dependencies, backlog and release policy | `8ef3e41d6e26b5ea017d54c868bd3eff31ddf264b4e448ae233597192cc48eb3` |
| [docs/sotlas_implementation_status.md](sotlas_implementation_status.md) | Dated implementation/evidence snapshot | `654445b9d20be3d95ceb846d6f56b7351a24a0627210b9e5c3d3aea4f4530a29` |
| [docs/sotlas_m16_3_recursion_contract.md](sotlas_m16_3_recursion_contract.md) | Language, safety, usage or architecture reference | `c821ac00990678d0f775c67b9ba91f5cd16678f744be112e23405d9b3584cbf7` |
| [docs/sotlas_master_roadmap.md](sotlas_master_roadmap.md) | Architectural design and language vocabulary | `068cd228ffeb958e609c03de54892266a58fbd7dc07738887c6d63b6d7935a6a` |
| [docs/sotlas_native_frontend_ownership_checklist.md](sotlas_native_frontend_ownership_checklist.md) | Current native contracts; incorporated in full | `9cd1a1d483655f00bae133eba14e34d739c45a03fea8ad8af21499c66047da86` |
| [docs/sotlas_release_roadmap.md](sotlas_release_roadmap.md) | Development dependencies, backlog and release policy | `fa56feeee089333c67d97c98399ac1ed61c11c91a107d01af9bd404e409ad57c` |
| [docs/sotlas_sovereignty_roadmap.md](sotlas_sovereignty_roadmap.md) | Native generation and dependency migration | `b88870c209f040aa5e446a08260144d84d4984bf495fe90bba858c8235bce224` |
| [docs/sotlas_v1_audit_and_roadmap.md](sotlas_v1_audit_and_roadmap.md) | Development dependencies, backlog and release policy | `7fe9cacfc713e60540c910aec8c8f5767e2d0984b84b4b61324975a370bfc6eb` |
| [docs/target_ir_preview.md](target_ir_preview.md) | Language, safety, usage or architecture reference | `de11d5b90ca1f6cd7e55f6226f93e85eb1998efa506654ac59121790724b6c28` |
| [docs/the_sotlas_book.md](the_sotlas_book.md) | Language, safety, usage or architecture reference | `1c10647fee6cbadc7d0b58884f76e57f716b8054b2be0731191af14b72cca60a` |
| [editors/vscode/CHANGELOG.md](../editors/vscode/CHANGELOG.md) | Historical snapshot / change history | `a1fada6f9d5609cef306ef25d6ecfd7e725ccb91682a8cae6daa930c54826778` |
| [editors/vscode/README.md](../editors/vscode/README.md) | Editor installation, commands and compatibility | `e26a3bfed009a182f667a76dc01a40a6445c60d0e4ad5ccaeea7cf05da09b5d3` |
| [examples/01_hello_systems/README.md](../examples/01_hello_systems/README.md) | Example scope and reproduction instructions | `30a5b62850e309a3a2b72579e085ed12a04d2b5c83bcb267a32c22acaca73cc8` |
| [examples/05_c_cpp_objc_interop/README.md](../examples/05_c_cpp_objc_interop/README.md) | Example scope and reproduction instructions | `e4550fc69b127fba16e210dca374749f2584975f626679bef2e2944e2792494c` |
| [examples/07_cli_tool/README.md](../examples/07_cli_tool/README.md) | Example scope and reproduction instructions | `417ae476b2f4dd478d738453eb30ead51987309142aa69a60bdac959a6adb99f` |
| [examples/12_sotlas_by_example/README.md](../examples/12_sotlas_by_example/README.md) | Example scope and reproduction instructions | `da9fa772030b1660c1095d08aede4ac00191a01406575e8e1f72c4c0cb5c8d20` |
| [examples/13_opencl_vector_add/README.md](../examples/13_opencl_vector_add/README.md) | Example scope and reproduction instructions | `c54620aa7b2c67800515aeff5c80c438e9d3609013057dae7a8402bc2a8f2551` |
| [examples/STATUS.md](../examples/STATUS.md) | Example scope and reproduction instructions | `d3efe2a667f4d11e5fd026673f7a299d972481d7f0df182a3b14a3a24a37b48c` |
| [runtime/README.md](../runtime/README.md) | Language, safety, usage or architecture reference | `6fbe980e1a4a5790f78893769a9a607b93c28453b651d470768f550444070879` |
| [spec/linguist/README.md](../spec/linguist/README.md) | Website, ecosystem and integration metadata | `5f1226c0de92f224ac61e88bbf054f7ec2fdcc0455dcb8d2eb318c8b596ec6ff` |
| [spec/sotlas_semantics.md](../spec/sotlas_semantics.md) | Architectural design and language vocabulary | `ee4086af4abbdca5b799362e6c2d1b7666e4849022c14865b116fa6b6e9f7383` |
| [stdlib/core/README.md](../stdlib/core/README.md) | Library API contracts; incorporated in full | `574954d60b526dc10973ec56569c6482b2dc2412f39290acb9eb9389925059ed` |
| [web/README.md](../web/README.md) | Website, ecosystem and integration metadata | `27d5dcc3c8b2bf12efd0275765426a6f7769e048642d71dfd455b421ad5b9bb8` |

## 16. Standard library function inventory

Public function/method names below are extracted from tracked `.sotlas` sources
in `stdlib`. This is a declaration inventory. An individual name's presence
does not establish backend support or make its module safe to use without its
documented ownership/lifetime/failure contract. Methods may share names across types.

**Public declarations indexed: 516 in 44 modules.**

| Source module | Public function/method declarations |
|---|---|
| [stdlib/core/alloc.sotlas](../stdlib/core/alloc.sotlas) | `allocator_new`, `allocator_alloc`, `allocator_realloc`, `allocator_free`, `arena_as_allocator`, `arena_new`, `arena_used`, `arena_available`, `arena_alloc_aligned`, `arena_alloc`, `arena_reset`, `arena_save`, `arena_restore`, `bump_new`, `bump_alloc`, `bump_reset` |
| [stdlib/core/arc.sotlas](../stdlib/core/arc.sotlas) | `arc_init`, `arc_retain`, `arc_release`, `arc_count`, `arc_retain_local`, `arc_release_local`, `new`, `increment`, `get_value`, `retain`, `release` |
| [stdlib/core/bitfield.sotlas](../stdlib/core/bitfield.sotlas) | `bit_set_u32`, `bit_set_u64`, `bit_clear_u32`, `bit_clear_u64`, `bit_toggle_u32`, `bit_toggle_u64`, `bit_test_u32`, `bit_test_u64`, `bit_extract_u32`, `bit_extract_u64`, `bit_insert_u32`, `bit_insert_u64`, `popcount_u32`, `popcount_u64`, `clz_u32`, `clz_u64`, `ctz_u32`, `ctz_u64`, `log2_u32`, `log2_u64`, `is_power_of_two_u32`, `is_power_of_two_u64`, `next_power_of_two_u32`, `next_power_of_two_u64`, `make_mask_u32`, `make_mask_u64`, `align_up_u64`, `align_down_u64`, `is_aligned_u64` |
| [stdlib/core/collections.sotlas](../stdlib/core/collections.sotlas) | `new`, `with_capacity`, `len`, `is_empty`, `capacity`, `push`, `pop`, `get`, `free`, `new`, `len`, `is_empty`, `insert`, `get`, `contains`, `remove`, `free`, `new`, `len`, `is_empty`, `push_front`, `pop_front`, `front`, `free` |
| [stdlib/core/conv.sotlas](../stdlib/core/conv.sotlas) | `u64_to_str`, `i64_to_str`, `u64_to_hex`, `u64_to_hex_prefixed`, `u64_to_bin`, `str_to_u64`, `str_to_i64`, `hex_to_u64` |
| [stdlib/core/deque.sotlas](../stdlib/core/deque.sotlas) | `deque_u32_new`, `deque_u32_is_empty`, `deque_u32_is_full`, `deque_u32_len`, `deque_u32_push_back`, `deque_u32_push_front`, `deque_u32_pop_front`, `deque_u32_pop_back`, `deque_u32_peek_front`, `deque_u32_peek_back`, `deque_u32_clear`, `deque_u64_new`, `deque_u64_is_empty`, `deque_u64_is_full`, `deque_u64_len`, `deque_u64_push_back`, `deque_u64_push_front`, `deque_u64_pop_front`, `deque_u64_pop_back`, `deque_u64_peek_front`, `deque_u64_peek_back`, `deque_u64_clear` |
| [stdlib/core/fathom.sotlas](../stdlib/core/fathom.sotlas) | `from_raw`, `is_empty`, `count`, `at`, `sub` |
| [stdlib/core/fixed.sotlas](../stdlib/core/fixed.sotlas) | `fixed_from_int`, `fixed_to_int`, `fixed_to_int_round`, `fixed_from_parts`, `fixed_mul`, `fixed_div`, `fixed_abs`, `fixed_min`, `fixed_max`, `fixed_clamp`, `fixed_lerp`, `fixed_floor`, `fixed_ceil`, `fixed_frac`, `fixed_sin`, `fixed_cos` |
| [stdlib/core/fmt.sotlas](../stdlib/core/fmt.sotlas) | `formatter_new`, `formatter_clear`, `formatter_as_str`, `formatter_len`, `write_str`, `write_char`, `write_u64`, `write_i64`, `write_hex`, `write_bool` |
| [stdlib/core/hash.sotlas](../stdlib/core/hash.sotlas) | `fnv1a_32`, `fnv1a_32_cstr`, `fnv1a_64`, `fnv1a_64_cstr`, `hash_combine_32`, `hash_combine_64`, `hash_u32`, `hash_u64`, `hash_to_index`, `hash_to_index_mod` |
| [stdlib/core/io.sotlas](../stdlib/core/io.sotlas) | `buffer_reader_new`, `buffer_reader_read_byte`, `buffer_reader_read`, `buffer_writer_new`, `buffer_writer_write_byte`, `buffer_writer_write` |
| [stdlib/core/iter.sotlas](../stdlib/core/iter.sotlas) | `range`, `range_step`, `range_has_next`, `range_next`, `slice_contains_u32`, `slice_find_u32`, `slice_count_u32`, `slice_fold_u32` |
| [stdlib/core/json.sotlas](../stdlib/core/json.sotlas) | `new`, `parse`, `parse`, `stringify`, `stringify_pretty` |
| [stdlib/core/log.sotlas](../stdlib/core/log.sotlas) | `log_set_level`, `log_get_level`, `log_get_last_msg`, `log_get_last_len`, `log_get_last_level`, `log_get_total_emitted`, `log_reset_counters`, `log_trace`, `log_debug`, `log_info`, `log_warn`, `log_error`, `log_fatal`, `log_u64`, `log_i64`, `log_hex`, `log_bool` |
| [stdlib/core/math.sotlas](../stdlib/core/math.sotlas) | `abs`, `abs64`, `min`, `max`, `min_u32`, `max_u32`, `clamp`, `clamp_u32`, `pow`, `sqrt`, `sqrt_f32`, `sqrt_f64` |
| [stdlib/core/mem.sotlas](../stdlib/core/mem.sotlas) | `zero_memory`, `copy_memory`, `set_memory`, `compare_memory`, `get_default_page_size`, `remaining` |
| [stdlib/core/option.sotlas](../stdlib/core/option.sotlas) | `some`, `none`, `is_some`, `is_none`, `unwrap_or`, `some`, `none`, `is_some`, `is_none`, `unwrap_or`, `some`, `none`, `is_some`, `unwrap` |
| [stdlib/core/panic.sotlas](../stdlib/core/panic.sotlas) | `sotlas_panic` |
| [stdlib/core/primitives.sotlas](../stdlib/core/primitives.sotlas) | `min_u32`, `max_u32`, `clamp_u32`, `min_i32`, `max_i32`, `abs_i32` |
| [stdlib/core/priority_queue.sotlas](../stdlib/core/priority_queue.sotlas) | `pq_u32_new`, `pq_u32_is_empty`, `pq_u32_is_full`, `pq_u32_len`, `pq_u32_capacity`, `pq_u32_insert`, `pq_u32_extract_min`, `pq_u32_peek_min`, `pq_u32_clear`, `pq_u64_new`, `pq_u64_is_empty`, `pq_u64_is_full`, `pq_u64_len`, `pq_u64_capacity`, `pq_u64_insert`, `pq_u64_extract_min`, `pq_u64_peek_min`, `pq_u64_clear`, `pq_item_new`, `pq_item_is_empty`, `pq_item_is_full`, `pq_item_len`, `pq_item_insert`, `pq_item_extract_min`, `pq_item_clear` |
| [stdlib/core/result.sotlas](../stdlib/core/result.sotlas) | `ok`, `err`, `is_ok`, `is_err`, `unwrap_or`, `try_unwrap`, `unwrap`, `unwrap_err`, `ok`, `err`, `is_ok`, `is_err`, `unwrap_or`, `try_unwrap`, `unwrap`, `unwrap_err`, `ok`, `err`, `is_ok`, `is_err`, `unwrap_or`, `try_unwrap`, `unwrap`, `unwrap_err`, `ok`, `err`, `is_ok`, `is_err`, `unwrap_or`, `try_unwrap`, `unwrap`, `unwrap_err` |
| [stdlib/core/ring_buffer.sotlas](../stdlib/core/ring_buffer.sotlas) | `ring_init`, `ring_clear`, `ring_is_empty`, `ring_is_full`, `ring_available`, `ring_free_space`, `ring_push`, `ring_pop`, `ring_peek`, `ring_write`, `ring_read` |
| [stdlib/core/slice.sotlas](../stdlib/core/slice.sotlas) | `byte_slice_make`, `mut_byte_slice_make`, `byte_slice_is_empty`, `byte_slice_get`, `mut_byte_slice_set` |
| [stdlib/core/sort.sotlas](../stdlib/core/sort.sotlas) | `insertion_sort_u32`, `insertion_sort_u64`, `insertion_sort_i32`, `shell_sort_u32`, `shell_sort_u64`, `heap_sort_u32`, `heap_sort_u64`, `is_sorted_u32`, `is_sorted_u64`, `reverse_u32`, `reverse_u64`, `min_u32`, `max_u32`, `min_u64`, `max_u64`, `swap_u32`, `swap_u64` |
| [stdlib/core/string.sotlas](../stdlib/core/string.sotlas) | `string_from_raw`, `string_len`, `string_is_empty`, `string_is_valid_utf8`, `string_as_bytes`, `string_char_at`, `string_try_byte_at`, `string_equals`, `string_compare`, `string_slice`, `string_starts_with`, `string_ends_with`, `string_find_char`, `string_find`, `string_split_once`, `string_trim_start`, `string_trim_end`, `string_trim`, `string_parse_u32`, `string_parse_i32`, `string_new`, `string_new_with_allocator`, `string_reserve`, `string_deinit`, `string_new_in_arena`, `string_reserve_in_arena`, `string_append_char`, `string_append_slice`, `string_append_char_owned`, `string_append_slice_owned`, `string_append_char_in_arena`, `string_append_slice_in_arena`, `string_concat_into`, `string_as_slice` |
| [stdlib/foundation/alloc.sotlas](../stdlib/foundation/alloc.sotlas) | `arena_new`, `arena_alloc`, `arena_reset`, `arena_remaining`, `arena_used` |
| [stdlib/foundation/bitmap.sotlas](../stdlib/foundation/bitmap.sotlas) | `bitmap_init`, `bitmap_fill`, `bitmap_set`, `bitmap_clear`, `bitmap_test`, `bitmap_find_first_free`, `bitmap_alloc_first_free`, `bitmap_find_contiguous`, `bitmap_count_used` |
| [stdlib/foundation/engrave.sotlas](../stdlib/foundation/engrave.sotlas) | `engrave_u64_decimal`, `engrave_u64_hex`, `engrave_u64_bin` |
| [stdlib/foundation/fathom.sotlas](../stdlib/foundation/fathom.sotlas) | `new`, `empty`, `is_empty`, `count`, `at`, `subfathom`, `starts_with`, `equals` |
| [stdlib/foundation/file.sotlas](../stdlib/foundation/file.sotlas) | `file_new`, `file_from_raw_fd`, `file_is_open`, `file_raw_descriptor`, `file_close` |
| [stdlib/foundation/generic_vec.sotlas](../stdlib/foundation/generic_vec.sotlas) | `new`, `with_capacity`, `len`, `capacity`, `is_empty`, `push`, `clear` |
| [stdlib/foundation/hashmap.sotlas](../stdlib/foundation/hashmap.sotlas) | `hashmap_new`, `hashmap_len`, `hashmap_cap`, `hash_key`, `hash_str`, `hashmap_insert`, `hashmap_get`, `hashmap_contains_key`, `hashmap_remove`, `hashmap_clear` |
| [stdlib/foundation/parcel.sotlas](../stdlib/foundation/parcel.sotlas) | `new`, `is_inline`, `count`, `append`, `at`, `deinit` |
| [stdlib/foundation/string_buf.sotlas](../stdlib/foundation/string_buf.sotlas) | `string_buf_new`, `string_buf_len`, `string_buf_cap`, `string_buf_is_empty`, `string_buf_append_char`, `string_buf_append_str`, `string_buf_append_bytes`, `string_buf_as_str`, `string_buf_clear` |
| [stdlib/foundation/vec.sotlas](../stdlib/foundation/vec.sotlas) | `vec_new`, `vec_len`, `vec_capacity`, `vec_is_empty`, `vec_push`, `vec_pop`, `vec_get`, `vec_clear` |
| [stdlib/graphics/canvas.sotlas](../stdlib/graphics/canvas.sotlas) | `color_argb`, `color_rgb`, `color_get_a`, `color_get_r`, `color_get_g`, `color_get_b`, `color_blend`, `canvas_new`, `canvas_clear`, `canvas_set_pixel`, `canvas_get_pixel`, `canvas_draw_line`, `canvas_fill_rect`, `canvas_draw_rect`, `canvas_fill_circle`, `canvas_draw_circle`, `canvas_draw_char`, `canvas_draw_text` |
| [stdlib/system/intrinsics.sotlas](../stdlib/system/intrinsics.sotlas) | `inb`, `outb`, `inw`, `outw`, `inl`, `outl`, `cli`, `sti`, `hlt`, `memory_barrier`, `irq_save_disable`, `irq_restore`, `interrupts_enabled` |
| [stdlib/system/pulse.sotlas](../stdlib/system/pulse.sotlas) | `new`, `read`, `write`, `swap`, `pivot`, `fetch_add`, `fetch_sub`, `new`, `read`, `write`, `swap`, `pivot`, `fetch_add`, `fetch_sub`, `new`, `read`, `write`, `swap` |
| [stdlib/system/sync.sotlas](../stdlib/system/sync.sotlas) | `pulse`, `pulse_store`, `pulse_load`, `compiler_fence`, `cpu_pause`, `new`, `lock`, `try_lock`, `unlock`, `is_locked`, `new`, `deinit`, `new`, `clinch_shield`, `release_shield`, `new`, `deinit`, `new` |
| [stdlib/system/thread.sotlas](../stdlib/system/thread.sotlas) | `mutex_new`, `mutex_lock`, `mutex_try_lock`, `mutex_unlock`, `channel_new`, `channel_is_empty`, `channel_is_full`, `channel_send`, `channel_recv`, `condvar_new`, `condvar_notify_one`, `condvar_wait_change` |
| [stdlib/system/ticker.sotlas](../stdlib/system/ticker.sotlas) | `now`, `elapsed`, `monotonic_tick`, `tick_diff` |
| [stdlib/system/time.sotlas](../stdlib/system/time.sotlas) | `duration_from_secs`, `duration_from_millis`, `duration_as_millis`, `duration_as_secs`, `now`, `instant_elapsed_ticks` |
| [stdlib/system/topology.sotlas](../stdlib/system/topology.sotlas) | `phys_region_new`, `phys_region_contains`, `dma_zone_new`, `dma_barrier` |
| [stdlib/system/wire.sotlas](../stdlib/system/wire.sotlas) | `from_raw`, `read`, `write` |
