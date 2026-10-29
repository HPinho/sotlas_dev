# Native frontend and ownership closure

Current compiler candidate: [interior addresses](native_projected_addresses.md)
add selected field/element pointers with parsed `&mut`, exact types and bounded
array access. General borrow lifetimes and arbitrary receiver expressions remain open.

Current compiler candidate: [typed local record-array storage](native_record_storage.md)
supports exact POD element pointers and typed pool metadata. General field
addresses, non-POD arrays and lifetime/alias analysis remain outside this block.

Current runtime candidate: [bounded native text map](native_text_map.md), with
owned key/value slots, checked-source copying, iteration and explicit cleanup.
This evidence does not complete generic collections or automatic ownership.

Detailed inventory and checkpoint reference. Use the shorter
[active plan](sotlas_sovereignty_roadmap.md) for current priorities;
[implementation history](sotlas_sovereignty_history.md) preserves past deliveries.
The reusable allocator/text delivery is documented in [native pools](native_pool.md).

Repository: [HPinho/sotlas_dev](https://github.com/HPinho/sotlas_dev).

## SV8.103 — persistent Unicode text composition and checked fields (2026-10-28)

Starting green baseline: `d02fe88b`,
[CI success](https://github.com/HPinho/sotlas_dev/actions/runs/40690756562),
19/19 jobs across Linux, Windows and Intel macOS.

- [x] Extend the reusable Sotlas pool text profile with scalar append,
  insert, remove, pop and reset/recovery without a host allocator.
- [x] Add self and cross-slot text composition, scalar-range append/replace,
  and independent scalar-range cloning with explicit allocation identity.
- [x] Add checked UTF-8 split-once returning revision-bound views; parse strict
  decimal fields from those views without unsafe, untracked pointer escapes.
- [x] Extend the native application to parse a persistent key/value record,
  reuse slots, exercise Unicode edits, reject stale views and release all owners.
- [x] Add source-to-machine regression cases for stale handles, clone
  exhaustion, revision saturation, byte/UTF-8 boundaries and failure atomicity.
- [ ] Certify this candidate through its own full CI matrix and native fixed
  point before adopting it as the new baseline.
- [ ] General borrow checking, language-level ARC/drop, resource-bearing
  aggregates, OS heap and complete frontend parity remain open.

[SV8.103 contract](native_pool_text_composition.md). This is executable native
runtime functionality; it does not claim that hosted Stage 1 or CI stopped
using Python, nor that the C11 interoperability backend is removed.

**Next package:** connect a bounded resource ownership/escape and cleanup
contract to compiler source acceptance, negative gates and original-source
native Stage 2/3 fixed points. No partial feature receives `SUPPORTED`.

## SV8.102 - pointer projections, snapshots and CI repair (2026-10-27)

Starting point: main c3e08c4 (SV8.101 candidate), with the reproduced
[CI #1314 failure](https://github.com/HPinho/sotlas_dev/actions/runs/40561453211).
The last inspected green baseline is b3ea906 / [CI #1313](https://github.com/HPinho/sotlas_dev/actions/runs/40533008504).

- [x] Correct the exhaustion fixture: 16 bytes plus a 3-byte scalar do fit in
  20 bytes. Use an 18-byte failing arena and separately prove exact 19-byte success.
- [x] Lower mixed inline-record/raw-record-pointer field chains through loaded
  pointer values, retaining field offsets, widths and bounded array access.
- [x] Keep pointer receiver identity separate from record value identity; pointer
  locals preserve addresses and explicit plain-record dereferences take snapshots.
- [x] Evaluate pointer-returning assignment receivers once before the right-hand
  side; check newly crossed unsafe/const boundaries in the native frontend.
- [x] Exercise recursive pointer graphs, retargeting, floating-point fields,
  copied records/arrays, alias-sensitive snapshots and positive/negative gates.
- [x] Use chained access in the arena runtime generation check and publish a
  native graph example in the shared rebuilt-driver gate.
- [ ] General inference/CFG, automatic resource management, pointer provenance,
  pointer-bearing record array values and foreign aggregate ABI parity.

[Pointer projections](native_pointer_projections.md) documents the contract and
seed transition caused by corrected snapshot semantics. Fixed-point checks stay
strict: unequal intermediate generations are never certified as equal.

Local validation: 505 native match, array/ABI, ownership, managed runtime,
numeric/result, UTF-8/arena and pointer-projection tests pass per Windows/Linux
host, plus 93 shared rebuilt-driver cases per host. A 310-test focused run passed
during implementation; the final frontend/runtime guard passed a separate
234-test focused run, including the reproduced CI failure and exact-fit success.
Native Stage 2/3 images are identical within each host after the documented seed
transition. Final pointer-graph check/build/object/link/run gates pass without
host tools on PATH, with byte-identical object and ELF/PE/Mach-O output across
hosts. New GitHub CI and actual Intel macOS execution remain pending.

## SV8.101 - Unicode scalar operations for arena text (2026-10-27)

Starting certified baseline: `b3ea906a` /
[green CI](https://github.com/HPinho/sotlas_dev/actions/runs/40533008504) (19 jobs).

- [x] Add codepoint-to-byte indexing, scalar reads and borrowed scalar slices
  after full UTF-8 and generation validation.
- [x] Insert, replace, remove and pop Unicode scalars, preserving the native
  result contract and existing transactional editing semantics.
- [x] Append whole texts and scalar ranges between arena descriptors, including
  same-descriptor self append across allocation relocation.
- [x] Cover 1/2/3/4-byte encodings, invalid indices/scalars, aliases, stale
  generations, malformed backing and allocation failure in native execution tests.
- [x] Extend the imported arena-report example without changing its expected
  exit status or cleanup discipline.
- [ ] Confirm the new block against the full GitHub Linux/Windows/Intel macOS
  matrix before treating this commit as a new green baseline.
- [ ] Automatic ARC/drop, checked borrow lifetimes, general heap allocation and
  grapheme-aware string operations remain unimplemented.

[Scalar-indexed arena text](native_arena_unicode.md) specifies contracts and
limitations. This is an additional native runtime capability, **not** removal
of Python from the hosted seed, CI harness or canonical C11 backend.

**Next item: SV8.102** — investigate native persistent string ownership and
lifetime/alias invariants, with a new fail-closed executable contract.

## SV8.100 - arena-allocated growing UTF-8 text (2026-10-27)

Green starting baseline: cefbd7a, as confirmed by the user.

- [x] Allocate and grow UTF-8 text within the existing Sotlas arena, starting
  lazily or with explicit capacity, without a C allocator or hidden OS calls.
- [x] Grow the last allocation in place, relocate/copy non-last allocations and
  fall back to exact capacity when geometric growth cannot fit.
- [x] Preserve cursor, descriptor and existing bytes on exhaustion; preflight
  malformed input, boundaries and source aliases before allocating.
- [x] Support append, numeric/scalar encoding, replacement, truncate, reset,
  borrowed views, explicit close and descriptor detach.
- [x] Check generation/range before text backing access after arena invalidation;
  compose result propagation, return snapshots and deferred close on both paths.
- [x] Execute an imported report with interleaved allocation, relocation,
  in-place growth, neighboring storage checks and cleanup before arena rewind.
- [ ] OS-heap strings, automatic ARC/drop, allocation identity/alias tracking,
  compiler-proven slice lifetimes and unrestricted string-language parity.

[Arena text](native_arena_text.md) defines this runtime API. Relocated blocks
remain in the arena until rewind; close does not individually reclaim them or
revoke raw borrowed views. Compiler sources are unchanged in this block.

Local validation: 112 focused arena, managed-runtime, numeric, result, inline
UTF-8 and caller-backed buffer tests pass on each Windows/Linux native driver.
All 16 new arena-text tests pass through the hosted seed route, plus 21 manifest/
documentation gates. The imported report passes direct build/run and object/link
paths with host tools absent from PATH; objects and ELF/PE/Mach-O bytes match
across hosts. The report is integrated into all three Stage 3 platform gates.
New GitHub CI and actual Intel macOS execution of this report remain pending.

## SV8.99 - caller-backed UTF-8 report buffers (2026-10-27)

Verified starting baseline: 3ec0990, [CI #1311](https://github.com/HPinho/sotlas_dev/actions/runs/40468078041),
all jobs successful, including Linux/Windows/Intel macOS matrix and C11 gate.

- [x] Build UTF-8 text beyond the inline 256-byte value limit using explicit
  caller-provided capacity and borrowed views, without allocation or C glue.
- [x] Validate descriptor shape, byte ranges and full UTF-8 before publishing
  edits; reject capacity, malformed input and split-scalar failures atomically.
- [x] Append byte ranges, borrowed slices, checked decimal values and scalars;
  support self append and overlapping sources with memmove order.
- [x] Replace scalar-aligned ranges, shift suffixes, reject replacement aliases,
  truncate, reset and optionally clear used storage.
- [x] Compose native result propagation with LIFO cleanup and deferred wipe on
  success/error; preserve return values before cleanup changes backing storage.
- [x] Build an imported 551-byte report with edits, Unicode and self append.
- [ ] Allocated/growing strings, compiler-proven backing lifetimes, alias
  revocation, concurrent access and automatic ARC-backed text storage.

[UTF-8 buffers](native_utf8_buffer.md) specifies the raw-storage contract.
The existing byte-slice and inline UTF-8 APIs remain available. Compiler sources
are unchanged in this block; it exercises the current native compiler/runtime ABI.

Local validation: 82 focused numeric/result/UTF-8/buffer tests pass on each
Windows/Linux native driver from the certified compiler sources. All 15 new
buffer tests pass through the hosted seed route, plus 21 manifest/documentation
gates. The imported report builds and executes with host tools absent from PATH;
object and ELF/PE/Mach-O bytes are identical across hosts. The report gate is
integrated into Linux, Windows and Intel macOS Stage 3 tests. New GitHub CI and
actual Intel macOS execution of this new report remain pending.

## SV8.98 - bounded native UTF-8 text and result choices (2026-10-26)

Starting point: main commit 37f36a4 (native results and checked numeric runtime).

- [x] Add pointer-free 256-byte UTF-8 value text with independent aggregate copies.
- [x] Validate lengths and UTF-8 before indexing, rejecting malformed sequences,
  overlong encodings, surrogates, truncated input and invalid scalar values.
- [x] Provide capacity-checked concat/repeat, scalar-boundary slices, ASCII trim/
  case, equality/order, search, first-separator extraction and replacement.
- [x] Integrate checked numeric parsing/formatting and transactional byte writes.
- [x] Apply native `?` directly to compatible conditional/match results, value
  blocks and inferred locals; preserve selected-path cleanup and nominal types.
- [x] Execute a configuration-to-report text example through native imports.
- [ ] Dynamic strings, general borrowed slices, Unicode normalization/graphemes,
  generic error conversion and automatic resource-backed string storage.

[Native text](native_text.md) defines the fixed-capacity profile. This is inline
value storage, with no allocator or C glue. Complete canonical language parity
and unrestricted string/slice support remain open.

Local validation: 449 native match, aggregate/array ABI, ownership, runtime,
result and UTF-8 tests pass on each rebuilt Windows/Linux compiler, plus 90 shared
Stage 3 driver cases per host. The 30 new tests also pass through the hosted seed
route; another 269 focused regression tests pass. Native Stage 2/3 images are
identical within each host. The Windows original-module reconstruction gate
passes with calculator, GUI and UI-model checks. The final UTF-8 import/demo gate
passes separately on both hosts with build tools absent from PATH; object and
ELF/PE/Mach-O output bytes match across hosts. Actual Intel macOS execution and
new GitHub CI remain pending.

## SV8.97 - native error propagation and numeric results (2026-10-25)

Starting point: main commit c56954c (composed native data models).

- [x] Propagate concrete POD status/value results with postfix `?`; evaluate once,
  preserve the entire error record and return before later expressions execute.
- [x] Run active lexical defers in LIFO order after capturing the error return;
  preserve lazy expressions, nested loop/match paths and existing move checks.
- [x] Extract scalar, record, payload-enum and bounded-array success values;
  index plain array temporaries returned by calls or successful propagation.
- [x] Reject invalid shapes, nominal mismatches, deferred propagation and borrowed,
  owned or resource-bearing result storage, including dead source branches.
- [x] Provide a Sotlas numeric result library: checked u32 arithmetic, narrowing,
  strict decimal parsing, bounded parsing, parse/sum and transactional formatting.
- [x] Exercise the APIs together in an import-based native numeric pipeline.
- [ ] General generic Result/error conversion, resource-bearing result payloads,
  automatic ARC/drop, broader lifetimes and foreign semantic aggregate signatures.

[Native results and numeric operations](native_result_propagation.md) define the
bounded contract. This adds structured error returns, not an exception/unwind ABI.
Python/C remain outside the post-seed native path; full language parity is open.

Local validation: 419 native match, aggregate/array ABI, ownership, runtime and
result tests pass on each rebuilt Windows/Linux compiler, plus 88 shared Stage 3
driver cases per host. All 37 new result/numeric tests also pass through the hosted
seed route; another 269 focused regression tests pass. Native Stage 2/3 images are
identical within each host. The imported numeric example passes with host build
tools absent from PATH; its object and ELF/PE/Mach-O images are byte-identical
across Windows/Linux builds. The Windows original-module CI gate also passes,
including calculator, GUI, UI model and the imported numeric pipeline. Actual
Intel macOS execution and new GitHub CI remain pending.

## SV8.96 - composed native data models (2026-10-25)

Green starting baseline: bc02a76, as confirmed by the user.

- [x] Resolve finite record/payload-enum/array layout dependencies before code
  generation, including forward declarations and interleaved dependency chains.
- [x] Reject by-value cycles, unresolved types, duplicate names and exhausted
  layout/variant/field budgets before publishing an artifact.
- [x] Store payload enums inside records and use those enums as bounded array
  elements; preserve nested copies, assignments, indexing and nominal types.
- [x] Destructure composed values with nested named/array/variant patterns and
  preserve guard snapshots, internal value ABI and exclusive/borrow contracts.
- [x] Serialize direct and nested static payload constructors into native data,
  including scalar widths, zero padding/inactive slots and zero-valued BSS.
- [x] Execute a public event pipeline with static settings, heterogeneous input,
  success/error results, report data, ownership transfer and input replacement.
- [ ] Resource-bearing payload graphs, automatic ARC/drop, general strings/slices,
  error propagation and foreign/cross-object semantic aggregate signatures.

[Composed native values](native_composed_values.md) define this package. Explicit
error enums in the example are ordinary values, not a new exception/unwind ABI.
The native post-seed compiler remains distinct from full canonical language parity.

Local validation: 382 native match, array/ABI, ownership, runtime and composed-
value tests pass on each Windows/Linux host, plus 83 shared rebuilt Stage 3 driver
cases per host. All 31 new composed-value tests also pass through the hosted seed
route; another 269 focused parser, semantic, numeric, storage, frontend, bootstrap
and documentation tests pass. Native Stage 2/3 images are identical within each
host. The exact Windows original-module CI gate passes with calculator, GUI and
UI-model checks. Both public examples produce byte-identical objects and ELF/PE/
Mach-O images across hosts; Windows/Linux images run with exit 42 with host tools
absent from PATH. New GitHub CI and actual Intel macOS execution remain pending.

## SV8.95 - staged whole-array updates (2026-10-25)

Starting point: main commit 5f0f5a4 (SV8.94 owned array ABI and resource batches).

- [x] Replace bounded POD arrays in mutable locals, value parameters, inline
  fields and existing mutable globals under native access rules.
- [x] Evaluate the destination once before staging the complete right-hand array;
  preserve self-reordering, independent copies, list order and one-shot repetition.
- [x] Accept stored/call/match/conditional values, capture value-block tails before
  LIFO cleanup and avoid publishing assignments on enclosing return paths.
- [x] Reinitialize definitely moved sole/exclusive arrays, consuming incoming
  owners; reject live and MAYBE_MOVED owner replacement or borrowed destinations.
- [x] Check shape and nominal element types before lowering, including dead code;
  reject Boolean-to-numeric literal substitution in contextual arrays.
- [ ] Resource-element destruction/replacement, slices, broader inferred arrays
  and foreign/separate-object array signatures.

[Whole-array assignment](native_array_assignment.md) specifies this block.
Staging preserves source evaluation order; it is not rollback of program side
effects, a concurrent transaction or automatic resource drop glue.

Local validation: 351 native match, ABI, resource and whole-array assignment
tests pass on each Windows/Linux host, plus 76 shared rebuilt Stage 3 driver
cases per host. All 21 new assignment tests also pass through the hosted seed
route, alongside 58 existing array-result/record-storage tests. Another 231
focused parser, semantic, numeric, frontend, bootstrap and documentation tests
pass. Native Stage 2/3 images are identical within each host. The exact Windows
original-module CI gate passes, including calculator, GUI and UI-model checks.
Public-example objects and ELF/PE/Mach-O images match across hosts; Windows/Linux
images execute with exit 42. The new GitHub matrix and actual Intel macOS
execution remain pending.

## SV8.94 - owned array ABI and transactional resource batches (2026-10-25)

Starting point: main commit f3e3cab (SV8.93 internal value arrays).

- [x] Transfer bounded scalar/POD record arrays through sole/exclusive parameters,
  locals and returns; retain owner domains in Target IR storage and signatures.
- [x] Forward no-escape whisper/direct array parameters; preserve immutable
  snapshots vs direct storage, deferred reservations and move/merge rejections.
- [x] Resolve fields through typed pointer locals, loading reassigned addresses;
  reject field/index writes through const pointers despite mutable bindings.
- [x] Validate collective resource claims and payload agreement before checked
  rewind/drain, preventing partial destruction of overclaimed control blocks.
- [x] Transfer resource-scope suffixes after preflighting both complete scopes,
  combined counts, disjoint tables and capacity; preserve order and refcounts.
- [ ] Automatic ARC/drop for resource-bearing arrays/aggregates, general lifetime
  proofs and foreign/separate-object ownership-aware array signatures.

[Owned arrays and resource batches](native_owned_arrays_and_resources.md) specify
this block. Resource enrollment and cleanup remain explicit Sotlas runtime APIs.

Local validation: 330 native match, array-ABI and resource tests pass on each
Windows/Linux host, plus 72 shared rebuilt Stage 3 driver cases per host. The
29 new tests also pass through the hosted seed route. Another 269 focused
frontend, parser, semantic, numeric, record-storage, bootstrap and documentation
tests pass. Native Stage 2/3 fixed points hold within each host. The exact Windows
original-module CI gate passes with calculator, GUI and UI-model checks. Example
objects and ELF/PE/Mach-O images are identical across hosts, and the Windows/Linux
images execute with exit 42. The new GitHub matrix and actual Intel macOS
execution remain pending.

## SV8.93 - internal by-value array parameters and returns (2026-10-24)

The preceding contextual-array block 51ac7bd passed CI, as confirmed by the user.

- [x] Accept bounded scalar/POD record arrays in internal function parameters and
  returns; preserve exact shape and nominal element identity.
- [x] Copy arguments independently in evaluation order and use caller-owned hidden
  return storage, including recursion, forwarding, void calls and stack arguments.
- [x] Capture array returns before LIFO cleanup and preserve mutable-parameter
  isolation, including deferred calls.
- [x] Initialize locals/fields/payloads from array-returning calls, infer local
  array types from call signatures and match returned arrays directly.
- [x] Reject incompatible calls/returns during semantic analysis even in dead
  code; retain explicit foreign, resource and qualified-array rejection gates.
- [ ] Foreign/separate-object array signatures, general array inference and
  reassignment, slices, resource arrays, integrated ARC/drop and full parity.

[Internal value arrays](native_value_array_abi.md) define this completed block.
It uses the private aggregate ABI within a compilation unit; it does not export
an interoperable array ABI or certify the remaining sovereignty checklist.

Local validation: 256 native match/array-ABI tests and 67 shared rebuilt Stage 3
cases pass on each Windows/Linux host. All 15 new ABI tests also pass through
the hosted bootstrap route. Another 231 focused parser, semantic, frontend,
bootstrap and documentation tests pass. Native Stage 2/3 images are identical
within each host. The exact Windows original-module CI gate passes, including
calculator, GUI and UI-model gates. Public-example objects and ELF/PE/Mach-O
images match across hosts; Windows/Linux images execute with exit 42. New GitHub
CI and actual Intel macOS execution remain pending.

## SV8.92 - contextual array match and conditional results (2026-10-24)

The preceding stored-array subject block ea8df2d passed CI, as confirmed by the user.

- [x] Select bounded POD arrays into explicitly typed local initializers and
  declared inline record fields/enum array arguments with match/conditionals.
- [x] Propagate destination element types/counts through arms, conditional branches
  and value-block tails; reject incompatible unselected branches too.
- [x] Copy results independently, evaluate only the selected initializer and
  capture value-block tails before LIFO deferred cleanup.
- [x] Preserve local scopes, enclosing early returns, guard/alternative ordering
  and branch-sensitive ownership of element computations.
- [x] Reuse the existing private storage layout and aggregate container ABI;
  preserve general array-parameter/return and resource-array rejection gates.
- [ ] General array value ABI/inference/reassignment, slices, resource ARC/drop.

[Contextual array results](native_match_array_results.md) specify the completed
bounded block.

Local validation: 241 native match tests and 61 shared rebuilt Stage 3 driver
cases pass on each Windows/Linux host. All 20 new array-result tests also pass
against the rebuilt native seeds, including payload/array subjects and copied
results. Another 233 focused frontend, parser, semantic, bootstrap and docs tests
pass through the hosted bootstrap route. Native Stage 2/3 images are identical
within each host. The exact Windows original-module CI gate passes, including
calculator, GUI and UI-model gates. Public-example object and ELF/PE/Mach-O outputs
match across hosts; Windows/Linux images execute with exit 42. New GitHub CI and
actual Intel macOS execution remain pending.

## SV8.91 - stored arrays as native match subjects (2026-10-24)

The preceding array-pattern block a37c4c5 passed CI, as confirmed by the user.

- [x] Match typed local arrays, existing global array storage and array-valued
  record fields directly in statement/expression forms.
- [x] Snapshot the complete array independently of sparse pattern views; copy
  whole-subject bindings before guards and preserve checked element indexing.
- [x] Preserve element types through root bindings, nested matches, original
  alternative trees and normalized decision rows.
- [x] Resolve array-valued fields of supported internal record-returning calls,
  nested fields and captured records; evaluate receivers exactly once.
- [x] Preserve guards, OR ordering, coverage, lexical cleanup and owner checks;
  explicitly reject scalar patterns on array subjects and unsupported array ABI.
- [x] Check all 512 Boolean rectangle unions for direct array subjects against an
  independent oracle; execute original/capture mutation and runtime bounds cases.
- [ ] General array parameters/returns, slices, resource payloads and ARC/drop.

[Native array subjects](native_match_array_subjects.md) define this completed
bounded block.

Local validation: 221 match tests and 57 shared rebuilt Stage 3 driver cases
pass on each Windows/Linux host. Another 235 focused frontend, parser, semantic,
bootstrap and documentation tests passed during this block; the final 22 new
subject tests also pass through the hosted bootstrap route. Final native Stage
2/3 images are identical within each host. The exact Windows original-module
CI gate passes with the final sources and fixtures, including calculator, GUI
and UI-model gates. Public-example object and ELF/PE/Mach-O outputs match across
hosts; Windows/Linux images execute with exit 42. New GitHub CI and actual Intel
macOS execution remain pending.

## SV8.90 - inline array element patterns (2026-10-24)

The local main was fast-forwarded from 88bfa5c to bdd605d, preserving the online
module/file-identity and Linux/Darwin atomic-publication work.

- [x] Parse exact arrays and one unbound prefix/middle/suffix rest marker inside
  supported enum payloads and named POD record fields.
- [x] Preserve scalar/record element types for immutable captures, calls, guards
  and nested named field access.
- [x] Lower element tests and independent captures through shared typed array
  layout views; preserve value ABI, subject snapshots and guard ordering.
- [x] Integrate exact product coverage, alternative expansion, owned reads and
  lexical cleanup with these array patterns.
- [x] Check all 512 Boolean rectangle unions with an independent set oracle;
  execute suffix-offset, 256-element sparse view and IEEE NaN cases.
- [ ] Resource-bearing payloads, ARC/drop, slice/rest bindings and general array ABI.

[Inline array patterns](native_match_array_patterns.md) define the completed
bounded block. This adds a native feature; it does not certify broader resource
management or full canonical frontend parity.

Local validation: 199 native match tests and 52 shared rebuilt Stage 3 driver
cases pass on each Windows/Linux host. The 20 new array-pattern tests also pass
through the hosted bootstrap route. Another 212 frontend/parser/bootstrap/docs
tests pass, as does the exact Windows original-module CI gate with calculator,
GUI and UI-model checks. Final native Stage 2/3 images are byte-identical within
each host; reconstruction runs without host tools after obtaining a refreshed
seed for the OS adapters added online. The final sources also pass canonical
bootstrap validation. The public example object and ELF/PE/Mach-O images match
across hosts, and the Windows/Linux images execute with exit 42. GitHub CI and
actual Intel macOS execution remain pending.

## SV8.89c3b1 - Intel macOS atomic source-list publication (2026-10-23)

**Green starting baseline:** `5fafd77`, [CI #1297](https://github.com/HPinho/sotlas_dev/actions/runs/39978252120), including Linux SV8.89c3a.

- [x] Extend the owned XNU x86-64 kernel adapter with typed
  `sotlas_darwin_rename(old:*const u8,new:*const u8)->i64`
  (BSD syscall 128) and `sotlas_darwin_unlink(path:*const u8)->i64`
  (BSD syscall 10); check signatures in lowering and Target IR.
- [x] Emit the exact BSD syscall numbers in native machine code,
  retaining Darwin negative-errno normalization and without host C or Python.
- [x] Add four opt-in `--build-*-atomic` source-list commands to
  the Intel macOS driver. Existing replace and exclusive `-new`
  commands remain unchanged across every host.
- [x] Compile/link in memory, write complete content via an exclusively
  created same-directory `.sotlas-stage` file, close, then publish via
  XNU `rename`. Preserve the previously published output until rename.
- [x] Refuse occupied staging names with status 10, preserving foreign
  staging bytes. On partial write or failed rename, return status 11
  and attempt native unlink of the stage created by this process.
- [x] Add Darwin integration tests covering successful library/ELF/PE/Mach-O
  replacements, occupied stages, failed publish cleanup and compile
  failures. Add a direct Mach-O execution/ABI gate for both syscalls and
  invalid declarations.
- [ ] Certify the new full CI matrix, especially Intel macOS native
  execution. Linux #1297 remains the known green baseline.
- [ ] Implement the Win32 counterpart with typed move/delete imports.
  Do not claim cross-platform atomic replace until that is certified.
- [ ] Certify crash durability, independent concurrent writers,
  file/directory sync, metadata preservation and handle-backed race defense.

This is an opt-in **single-writer atomic namespace replacement** on macOS,
not a durable transaction. Full details and limitations:
[native module builds](native_module_builds.md).

**Next SV8.89c3b2:** native Win32 staged atomic publication via
signature-checked move/delete APIs, complete artifact rollback gates and
Windows CI. Then assess stronger crash durability and race resistance.

## SV8.89c3a - Linux atomic source-list publication (2026-10-23)

**Verified green baseline:** commit `29a60f34`, [workflow #1296](https://github.com/HPinho/sotlas_dev/actions/runs/39962262074).

- [x] Expose typed native Linux `rename(old:*const u8,new:*const u8)->i64`
  and `unlink(path:*const u8)->i64` adapters (syscalls 82 and 87).
  Extend scalar lowering, Target IR verification and x86-64 machine emission
  without invoking libc, an external compiler or host Python.
- [x] Implement opt-in Linux `--build-library-atomic` and
  `--build-{elf,pe,macho}-modules-atomic` for native source-list builds.
  Existing replace and strict `-new` modes remain unchanged.
- [x] Compile and link fully in memory, write the complete result to a
  bounded same-directory `.sotlas-stage` name using exclusive create,
  close it, then publish with the kernel's atomic `rename`.
- [x] Refuse to overwrite a pre-existing staging name (status 10).
  Return status 11 for failed write/publish, with best-effort removal of
  a stage created by this process; never truncate the previous published
  output before the rename.
- [x] Add Linux integration gates for the four artifact types: full
  replacement and execution, occupied stage preservation, rename failure
  rollback, compile failure preservation, and direct typed syscall behavior.
- [x] Certified Linux staged publication and all existing platform gates
  on [workflow #1297](https://github.com/HPinho/sotlas_dev/actions/runs/39978252120) (commit `5fafd77`).
- [ ] Linux atomic mode does **not** ensure fsync durability, cleanup after
  process crash, robust parallel writers, permission/ACL retention, or
  handle-backed defense against directory/path races.
- [ ] Implement platform-specific atomic publication for Darwin and Win32
  before claiming this mode on macOS/Windows.

This block is a bounded **opt-in Linux native atomic name replacement**,
not general cross-platform atomic transactions or complete removal of
hosted Python/C bootstrap components. The executable contract and limits
are recorded in [native module builds](native_module_builds.md).

**Next SV8.89c3b:** certify staged atomic source-list publication using
native Darwin rename/unlink syscalls and typed Win32 move/delete imports,
with failure rollback, destination protection and matrix tests.

### SV8.89c2b — Darwin regression repair after CI #1294/#1295 (2026-10-23)

- [x] Identify the false-positive file collisions on Intel macOS. The
  previous adapter used XNU's legacy `fstat` syscall 189 while reading
  bytes as the newer 64-bit inode layout. Independent files could
  incorrectly compare equal and reject valid source-list builds.
- [x] Preserve the legacy adapter, but introduce a distinct typed
  `sotlas_darwin_fstat64` entry bound to XNU syscall 339
  (`0x02000153`). Extend lowering, Target IR verification and x86-64
  machine emission without changing Linux or Windows implementations.
- [x] Use the `user64_stat64` layout for bounded Darwin file identity
  checks and reject unusable zero inodes conservatively.
- [x] Strengthen Mach-O integration to prove that hard links compare
  equal, two independently created same-content files have distinct
  inodes, invalid signatures reject, and the native object contains
  the exact fstat64 machine syscall; keep all original tests active.
- [x] Certified the Darwin fstat64 regression repair on full
  [workflow #1296](https://github.com/HPinho/sotlas_dev/actions/runs/39962262074)
  (commit `29a60f34`). Failed runs #1294/#1295 remain unsafe baselines.

**Next item after green:** SV8.89c3 — handle-backed atomic artifact
publication and rollback on late I/O failures, across native platforms.

## SV8.89c2b - Intel macOS native file identity via XNU fstat (2026-10-22)

**Verified green baseline:** `c3f697ce`, [workflow #1293](https://github.com/HPinho/sotlas_dev/actions/runs/39857829346).

- [x] Extend the reserved Darwin kernel-adapter family with the typed
  `sotlas_darwin_fstat64(fd:u64, data:*mut u8)->i64` syscall (BSD 339),
  retaining legacy fstat(189), Linux fstat(5) and Windows PE ABI.
- [x] Enforce the new Darwin opcode and argument types in Target IR, native
  scalar lowering and x86-64 machine emission. Restore the x86-64 errno
  normalization already used by the Darwin driver. No libc or C linking.
- [x] Compare kernel device (32-bit at byte 0) and inode (64-bit at byte 8)
  in a fixed 256-byte Intel Darwin user64_stat64 buffer, using native
  `open(O_RDONLY)`, `fstat64`, and `close`.
- [x] Reject duplicate source/library inputs and protected output collisions
  through hard links, symlinks and symlinked parent paths, preserving
  source-list exit status 1 and strict-output status 10.
- [x] Preserve five Intel macOS-hosted regression tests and upgrade the
  Mach-O gate to fstat64 execution, negative errno and signature rejection.
  Separately created equal-content files must have different inode IDs.
- [ ] Certify this new commit on Ubuntu, Windows and Intel macOS CI before
  calling SV8.89c2b green. Other platforms' adapters remain unchanged.
- [ ] Protect all platforms against filesystem races between the identity
  preflight and output publication, plus partial artifacts on write failure.
  These require handle-backed output/atomic publication certification.

**Scope:** the Intel macOS x86-64 native source-list profile, not full
filesystem identity across every mount type or general Python/C removal.
Darwin O_RDONLY permission failures reject conservatively. See
[native source-list build contract](native_module_builds.md).

**Next SV8.89c3:** safe native output publication and rollback of partial
artifacts, with no-clobber and replace-mode race tests on all three OSes.

## SV8.89c2a - Windows native file identity with Win32 file handles (2026-10-22)

**Verified green baseline:** `68dce798` / [CI #1292](https://github.com/HPinho/sotlas_dev/actions/runs/39835602797).

- [x] Reserve a signature-checked Win32 `GetFileInformationByHandle` import
  in the owned x86-64 PE backend, preserving the existing ID 11 internal
  scalar bridge and a contiguous Kernel32 import address/name table.
- [x] Extend the Windows native driver with metadata-only `CreateFileA`,
  Win32 handle information and guaranteed close to read bounded
  `BY_HANDLE_FILE_INFORMATION` volume serial and 64-bit file index.
- [x] Compare OS-reported identity for source/library duplicates and
  destination/manifest collisions through hard links, symlinks or linked
  directories, preserving distinct status 1 for invalid/duplicate input
  and status 10 for blocked `-new` output collisions.
- [x] Retain the Linux SV8.89c1 inode identity implementation unchanged.
  Keep the Windows create-new kernel/API operation authoritative against
  output replacement races; the identity query is still a preflight.
- [x] Add Windows-host integration tests and an executable PE import probe,
  including fail-closed invalid Win32 declarations; no native Python/C
  compilation or external linker is added.
- [ ] Certify Windows integration on the new CI matrix, and cover ReFS's
  potential 128-bit file identity, network filesystems, Unicode and
  concurrent path swaps separately.
- [ ] Implement and certify the Intel macOS native file identity adapter.

**Scope:** preflight path identity for the Windows x64 native source-list
profile, not a claim of arbitrary filesystem security or full hosted
Python/C removal. API layout and import contract are tracked in
[native module builds](native_module_builds.md).

**Next SV8.89c2b:** Intel macOS file identity via verified native XNU API,
with hard-link/symlink regression tests and stable Linux/Windows baselines;
then SV8.89c3 for handle-backed atomic output publication.

### SV8.89c1 — repair of CI #1291 preflight exit contract (2026-10-22)

- [x] The Linux inode/device preflight remains active. It did not overwrite
  hardlinked or symlinked files, but rejected two protected `-new` destinations
  with usage status `1` instead of the documented create status `10`.
- [x] Return distinct typed statuses from the native manifest preflight:
  `10` for a detected output collision under `-new`; `1` for repeated
  sources/libraries or invalid manifest input, and for replace-mode conflicts.
  Keep OS-level exclusive create as the final no-clobber enforcement.
- [x] Preserve the same separation in Linux, Windows and Intel macOS drivers,
  and add negative tests for source, manifest and library collisions across
  all output formats, without weakening the existing regression tests.
- [ ] Confirm the repair's new Ubuntu/Windows/macOS CI matrix before declaring
  the post-fix baseline green. Next feature item remains SV8.89c2.

## SV8.89c1 - Linux native inode/device identity for source-list builds (2026-10-22)

**Green baseline:** commit `42c4d7f`, [workflow #1290](https://github.com/HPinho/sotlas_dev/actions/runs/39781689384).

- [x] Extend the Linux x86-64 kernel adapter with the typed `fstat(fd, *mut u8)`
  syscall (number 5), including Target IR validation, native lowering and
  machine emission. Use no libc layout, C object code or Python driver.
- [x] Read `st_dev` and `st_ino` from the first 16 bytes of the Linux x86-64
  kernel `struct stat` into bounded Sotlas scratch storage using `O_PATH`
  file descriptors. Close descriptors on every opened path.
- [x] Before output creation, compare actual identities for source/library
  duplicates and collisions with manifests or the intended output; reject
  hard links, symbolic-file aliases and linked-parent directory aliases.
- [x] Preserve existing missing-input diagnostics and reject unexpected
  metadata failures conservatively without truncating previously existing
  inputs or destinations.
- [x] Add Linux execution tests for source hard links and symlinks, manifest
  aliasing, destination hard links, linked-parent paths and equal-content
  independent files.
- [ ] Extend file identity through certified Darwin and Win32 native file APIs.
- [ ] Add handles/atomic output replacement to close filesystem race windows,
  including dangling links and symlinked parent swaps; existing `-new`
  remains the OS-level no-clobber option on all three systems.
- [ ] Confirm Stage 2/3 and GitHub OS matrix for this commit.

**Scope:** The Linux native post-seed source-list build path, not the
reference compiler, general package resolver, or complete Python/C removal.
The Windows/macOS lexical SV8.89a and strict output SV8.89b paths stay
unchanged and documented. See [native module builds](native_module_builds.md).
**Next SV8.89c2:** certify native file-ID adapters on Intel macOS and Windows
before integrating their preflight with replace-capable output commands.

## SV8.89b - OS-enforced no-clobber source-list builds (2026-10-22)

**Green baseline:** `ec00297a`, [GitHub CI #1289](https://github.com/HPinho/sotlas_dev/actions/runs/39740061235).

- [x] Add explicit native `--build-library-new`, `--build-elf-modules-new`,
  `--build-pe-modules-new` and `--build-macho-modules-new` commands.
- [x] Keep the existing source-list compilation and linker profile, with
  backwards-compatible default commands that may replace an output.
- [x] Route `-new` output creation to OS-native exclusive create: O_EXCL
  (Linux/Darwin) or CREATE_NEW (Windows), after all parsing, object and link
  gates, with no prior time-of-check / time-of-use existence probe.
- [x] Preserve existing destination bytes (including hard links and symbolic
  links) and reject an existing name with status 10; do not truncate or replace.
- [x] Add tests for first creation, second-creation rejection, hard-link
  preservation, symbolic-link protection and POSIX dangling links.
- [ ] Complete OS metadata-based file-identity comparisons (source and library
  duplicates via inode/file ID), path aliases through linked parent directories,
  atomic replacement for ordinary builds and artifact rollback on late I/O
  errors. These require separate certification.

This is **real kernel-backed protection against overwriting an existing final
path in opt-in `-new` mode**, not complete path/file identity, and it adds no
host Python or C compiler to the native runtime. The ordinary replace commands
remain unchanged. Details: [native module builds](native_module_builds.md).
Evidence: `tests/test_sotlas_native_module_builds.py`; post-commit CI must
pass before declaring the new gate green.

**Next SV8.89c:** use native OS file handles and metadata to compare resolved
identity of existing source, library and destination files; verify alias,
hard-link, symlink-parent, privilege and race boundaries before enabling
general replacement safety.

## SV8.89a - lexical path identity for native module builds (2026-10-21)

**Green starting point:** commit `617ba47d` / [CI #1287](https://github.com/HPinho/sotlas_dev/actions/runs/39685586187).

- [x] Normalize bounded source, library, manifest and output paths inside
  the Sotlas-written Linux, Windows and Darwin native drivers before comparing
  them for duplicated roots or unsafe output collisions.
- [x] Eliminate repeated separators, `.` and safely reducible `..` segments.
  Retain leading `..` for relative inputs and distinguish absolute roots,
  Windows drive-relative paths and UNC prefixes.
- [x] Compare Windows ASCII case-insensitively with slash/backslash equivalence;
  retain POSIX case-sensitive naming and double-leading-slash distinction.
- [x] Keep all comparisons bounded to 4095 input bytes, using fixed native
  scratch buffers and no Python interpreter, generated C or host linker.
- [x] Add integration tests for aliased source roots, aliased output/source and
  output/manifest collisions, duplicate libraries and Windows ASCII variants.
- [ ] Prove filesystem-level identity for hard/symbolic links, Windows
  junctions, absolute/relative aliases, Unicode case rules and existing
  destination file handles; lexical checks are not sufficient for these cases.
- [ ] Certify the new post-commit Ubuntu/Windows/Intel macOS CI matrix.

**Scope:** the C-free post-seed source-list build path; no whole-program
ownership, ARC/drop, package manager or Python/C bootstrap removal is claimed.
See [independent module-build contract](native_module_builds.md).

**Next SV8.89b:** native OS-backed input/output file-identity checks and
output creation policy for symlinks/hard links, then a matrix of actual
filesystem-alias preservation tests.

## SV8.88 - native source-list input and artifact safety (2026-10-21)

**Starting green baseline:** `88bfa5c` / [CI #1286](https://github.com/HPinho/sotlas_dev/actions/runs/39632022114).

- [x] Reject repeated byte-exact source paths in the native library/ELF/PE/Mach-O
  source-list drivers before invoking the native compiler for any input unit.
- [x] Reject repeated archive paths in an optional native library list before
  loading them, rather than allowing duplicate linker candidates.
- [x] Reject destinations identical to source inputs, library inputs, source
  manifests or library manifests, preserving the original bytes on failure.
- [x] Apply the same bounded, allocation-free preflight across Linux, Windows
  and Intel macOS native drivers. Do not introduce Python, C compilation,
  subprocess linkers or extra host build tools in the native build path.
- [x] Add cross-target failure/preservation tests for all four collision types,
  including existing output files and invalid library bytes.
- [ ] Prove canonical path identity across aliases, symbolic links and
  case-insensitive filesystems; lexical equivalence is the current bound.

**Executable contract:** [Native independent module builds](native_module_builds.md).
**Regression coverage:** `tests/test_sotlas_native_module_builds.py`.
This block protects an existing sovereign build path; it does not certify
general package resolution or remove the remaining hosted Python/C producers.
The new CI matrix is the post-commit acceptance gate, not yet a green claim.

**Next SV8.89:** platform-aware canonical path and file-identity checks in native
artifact preflight, with symlink/alias preservation tests and no dependency on
Python or C within the execution path.

## SV8.87 - inline array payloads and owned subject reads (2026-10-21)

The previous pattern block (commit 1c6763c) passed CI, as confirmed by the user.

- [x] Store bounded scalar and pointer-free POD record arrays directly in enum
  payloads, with checked element counts/types and the existing 4096-byte layout.
- [x] Construct arrays from lists, one-evaluation repetition, local arrays and
  record fields; preserve source order and independent storage.
- [x] Carry array payloads through native aggregate calls, returns and match
  results; retain independent captures, guards and compatible alternatives.
- [x] Read named exclusive/whisper/direct POD subjects in statement/expression
  matches without consuming them; preserve moves, guard fallthrough and cleanup.
- [ ] Integrate resource-bearing payload fields with generated destruction,
  shared ARC, weak invalidation and general resource lifetime/escape analysis.

[Inline arrays and owned subjects](native_match_array_payloads.md) specify the
executable scope. This closes the inline POD array payload block; it does not
certify automatic resource management.

Local evidence: 179 match tests pass on each Windows/Linux host, along with
48 shared rebuilt Stage 3 driver cases per host. The exact Windows original-module
Stage 2/3 CI gate and all 19 new array-payload tests pass through the hosted seed
route; calculator and GUI gates pass too. Another 155 frontend/documentation
tests pass. Native Stage 2/3 fixed points hold within each host. The public example
executes with exit 42 on Windows/Linux, and its object plus ELF/PE/Mach-O outputs
are byte-identical across hosts. The new GitHub CI and Intel macOS execution gates
remain pending.

## SV8.86 - named fields and IEEE float patterns (2026-10-21)

- [x] Match bounded POD records directly and inside positional enum payloads.
- [x] Resolve fields by name, accept reordering, renaming, shorthand and final
  rest markers, and reject unknown/duplicate/missing fields.
- [x] Preserve nested typed bindings, alternative groups, guard ordering, array
  capture copies, record results, exclusive POD rules and lexical cleanup.
- [x] Execute F32/F64 equality and open/closed/half-open numeric intervals.
- [x] Normalize signed-zero boundaries, compare rounded values and preserve a
  path for NaNs; numeric ranges alone never prove exhaustive float coverage.
- [x] Check named-field product coverage against 512 independent rectangle unions.
- [x] Raise the hosted/native lexer buffer to 524288 tokens for the larger
  compiler sources; preserve separate AST/IR and source-byte bounds.
- [ ] Resource-bearing payloads, ARC/drop and their general cleanup integration.

The pattern forms in the current native release profile are implemented.
[Named fields and float patterns](native_match_named_float.md) define the syntax,
semantics, 4096-byte record bound and evidence. Resource payloads are next.
Local validation: 160 match tests and 45 shared Stage 3 cases pass on each
Windows/Linux host, alongside 335 focused frontend, numeric, docs and hosted
bootstrap checks. The exact Windows original-module Stage 2/3 CI test also passes,
including calculator, GUI and UI-model gates. Native Stage 2/3 images are identical
within each host. The example object and ELF/PE/Mach-O outputs match across hosts;
Windows/Linux images execute with exit 42. GitHub CI and Intel macOS execution
remain pending certification gates.


## SV8.85 - value-block loop and mutable-local parity (2026-10-20)

- [x] Accept native mutable `var` and bare `loop` statements inside value-producing
  `match` arms, while retaining the established tail-value requirement.
- [x] Keep break/continue scoped to their actual loop and reject a missing arm
  result or an unscoped break without emitting an executable artifact.
- [x] Teach the transitional hosted Stage 1 C11 emitter to lower the existing
  `WhileStmt` bare-loop marker as `while (true)`, without attempting to read
  synthetic integer literals with no source span.
- [x] Add native executable tests, a shared Stage 3 driver fixture, and a
  Stage 1/2/3 C-emission parity gate for bare loops.

This fixes a frontend dialect gap and hardens the hosted bootstrap compatibility
path. Native objects and executables still use Sotlas machine emission; the
separate hosted C11 emitter is not being claimed as C-free. Evidence:
`tests/test_sotlas_native_match_values.py`,
`tests/native/match_profile/block_loop.sotlas`, and
`tests/test_sotlas_sovereignty_sv8.py`. The OS matrix remains a post-commit
acceptance gate; this entry does not assert an unobserved green result.

**Delivered in SV8.86:** named-field/record destructuring in native `match`, with
nominal identity, field completeness, ownership and coverage tests.
Resource-bearing payloads and ARC/drop remain separate certification blocks.

## SV8.84 - native alternative patterns (2026-10-20)

- [x] Parse root/nested | alternatives and grouped positional patterns.
- [x] Require identical binding names and declared types across alternatives,
  including unused captures and nominal enum/record identity.
- [x] Select bindings from the first matching alternative and evaluate the
  source guard once; false skips the entire source-arm group.
- [x] Preserve unguarded union coverage, overlapping alternatives, subject
  snapshots, exclusive moves, record results, defer and loop exits.
- [x] Bound distribution to 64 rows per match and reject capacity/syntax errors.
- [x] Preserve parenthesized arithmetic and bitwise integer range bounds.
- [x] Snapshot AST sibling links before native parser rewiring and exercise the
  feature through rebuilt Stage 3 drivers.
- [x] Named-field/record destructuring patterns (SV8.86).
- [x] Float equality and interval patterns; NaN guards retain a fallback (SV8.86).
- [ ] Resource-bearing payloads and general ARC/drop cleanup.

Implementation: native Sotlas parser, semantic checker and Target IR lowering.
The 25-test alternative suite includes a Boolean-union set oracle, binding
permutations, nested body cloning, exact row boundaries and compatibility cases.
See [the executable contract](native_match_alternatives.md).
Local validation: 139 match tests and 40 shared Stage 3 driver cases pass on
each Windows/Linux host. Another 329 focused frontend, compatibility, docs and
bootstrap checks pass, including the hosted C11 Stage 1/2/3 fixed point. Native
Stage 2/3 images match within each host; the example object and ELF/PE/Mach-O
outputs match across hosts. Windows/Linux examples execute with exit 42.
GitHub CI and actual Intel macOS execution remain separate certification gates.

## SV8.83 - complete combinations for current match patterns (2026-10-20)

- [x] Prove the union of positional field patterns across full Boolean,
  signed/unsigned integer and declared enum domains.
- [x] Combine nested variant sums and independent field products without a
  mandatory capture-only fallback.
- [x] Partition integer axes at pattern boundaries, including U64/I64 extrema.
- [x] Reject Cartesian holes, even when individual fields have full marginal
  coverage, and exclude guarded rows from the proof.
- [x] Preserve ordered runtime tests for the last refutable arm; unmatched raw
  representations trap instead of selecting that arm implicitly.
- [x] Keep proof storage and traversal native, with caller-local scratch buffers
  and explicit frames under existing layout/arm bounds.

Evidence: 	ests/test_sotlas_native_match_combinations.py, including all 512
Boolean rectangle unions and 64 deterministic interval-union oracle cases.
Windows and Linux native Stage 2/3 rebuilds have identical successive images;
114 match tests and 37 shared Stage 3 driver fixtures pass on each host.
ELF/PE/Mach-O generation is checked; Windows/Linux images execute locally.
The GitHub matrix and Intel macOS execution remain CI gates.

This closes the combination block for existing patterns and declared domains.
Pattern syntax extensions and resource-bearing payloads remain separate blocks.
See [the precise coverage contract](native_match_payloads.md#combination-coverage).

## SV8.82 - nested variant and field patterns (2026-10-20)

- [x] Parse nested positional variant patterns with a depth bound of 32.
- [x] Test integer/Boolean literals, module constants, ranges and nominal scalar enum fields.
- [x] Resolve nested immutable bindings with declared field types and arm-local scope.
- [x] Reject duplicate bindings across nested siblings, bad arity, wrong types and invalid ranges.
- [x] Test each nested tag before its payload, and every field before the guard.
- [x] Preserve ordered fallback, record results, early return and LIFO defer cleanup.
- [x] Snapshot aggregate subjects once before the decision chain.
- [x] Keep the initial total-variant fallback rule (superseded by SV8.83).

The [payload contract](native_match_payloads.md) records supported forms. Complete
product coverage, named-field/or-patterns and resource/ARC payload cleanup remain
separate open items; these checks do not mark general match parity complete.

## SV8.81 - payload matching and exclusive expression joins (2026-10-19)

- [x] Construct tagged payload enums in Sotlas without C emission.
- [x] Preserve scalar/POD payloads across internal calls, returns and match results.
- [x] Unpack positional immutable bindings and ignored fields after tag selection.
- [x] Validate guards, nominal identity, arity, coverage, bounds and binding scope.
- [x] Copy record payloads independently and zero inactive storage.
- [x] Merge exclusive POD moves across expression arms, including value blocks.
- [x] Reject moved/maybe-moved reads, consuming guards and deferred-owner transfers.
- [x] Execute nested matches, early returns and LIFO arm cleanup.

See the [payload contract](native_match_payloads.md). General resource fields,
ARC/drop synthesis and recursive/refutable field patterns remain open; these
checks do not mark complete canonical language parity.

## SV8.80 - native POD match release profile (2026-10-19)

- [x] Add scoped immutable subject bindings in guards and arm bodies.
- [x] Preserve module constants as value patterns and lexical shadowing.
- [x] Cover open integer intervals, including signed extrema and complete domains.
- [x] Return independent POD records, including nested records/array fields.
- [x] Return nominal payload-free enums and reject destination/arm mismatches.
- [x] Execute arm blocks with locals, tail values and enclosing function returns.
- [x] Capture scalar/record results before LIFO defer cleanup and deferred mutation.
- [x] Preserve nested match result contexts and existing ownership exclusions.
- [x] Check arm/local/table capacities and keep malformed/value-less blocks closed.
- [x] Extend shared Stage 3 fixtures, documentation and the original-source example.

The [release profile](native_match_release_profile.md) fixes this executable
surface. Payload enums/patterns and ownership-bearing match values remain open
foundation/integration work; the master match item is not marked complete.

## SV8.79 - scalar match expressions (2026-10-19)

- [x] Parse match values in expression positions with comma-separated scalar arms.
- [x] Reuse statement-match coverage, range, enum-subject and guard validation.
- [x] Evaluate the subject once; evaluate only eligible guards and the chosen arm.
- [x] Materialize typed results at a CFG join for lets, returns, arguments and calculations.
- [x] Execute nested matches, Boolean conditions, loops and deferred call arguments.
- [x] Check every result arm, including unselected arms, with explicit capacity limits.
- [x] Reject aggregate/pointer/enum results and owned captures/call results explicitly.
- [x] Add a native classification example and positive/negative execution gates.

Payload matching, statement-valued arm blocks, general ownership merges and
aggregate results remain open. See the [match-value contract](native_match_values.md).

## SV8.78 - initialized global record tables (2026-10-19)

- [x] Serialize typed global record array lists and repetitions into native data/BSS.
- [x] Preserve padded element stride, zero padding and nested record/array values.
- [x] Read/write indexed entries and independently copy/return supported elements.
- [x] Enforce literal bounds, dynamic traps, immutable writes and lexical shadowing.
- [x] Reject runtime/resource/pointer initializers, mismatches and pool exhaustion.
- [x] Preserve the compiler's existing large zero-storage table shorthand.
- [x] Add an immutable command-table example with native execution gates.

See the [table contract](native_static_tables.md). General slices, whole-array
assignment and resource/aggregate array ABI remain open.

## SV8.77 - native static record configurations (2026-10-18)

- [x] Fold pointer-free static record literals with typed constant scalar fields.
- [x] Serialize nested records and scalar/record arrays using native padded layout.
- [x] Zero padding deterministically and keep all-zero records in BSS.
- [x] Read/mutate mutable static fields and replace complete record values.
- [x] Copy static containers into independent locals and supported return/borrow paths.
- [x] Preserve lexical shadowing, nominal types and immutable-global rejection.
- [x] Reject runtime/pointer/resource initializers and bounded pool exhaustion.
- [x] Ship a source-to-native configuration example with execution gates.

The parent initializer item remains open for strings, pointer relocations,
resource-bearing values and other aggregate forms. See the
[static record contract](native_static_records.md).

## SV8.76 — native inline record-array fields (2026-10-18)

- [x] Lay out pointer-free record arrays inline with correct element size/alignment.
- [x] Initialize them from lists, one-evaluation repetition and compatible storage.
- [x] Read/write nested fields and replace whole elements or array fields.
- [x] Snapshot list/repeat RHS values before replacing an existing field.
- [x] Copy/return containers with independent element storage and supported borrows.
- [x] Preserve exclusive POD container transfers, mutation rules and checked indexing.
- [x] Reject pointer/resource payloads, nominal/count mismatches and capacity exhaustion.
- [x] Add an inventory example and native positive/negative execution gates.

General slices, standalone aggregate array parameters/returns, non-POD payloads
and automatic destruction remain open. See [the contract](native_record_array_fields.md)
and [current roadmap checkpoint](native_roadmap_checkpoint.md).

## SV8.75 — complete builds from independent source lists (2026-10-18)

- [x] Compile each listed source through the native frontend independently.
- [x] Retain compiled objects in bounded native storage without intermediate files.
- [x] Build reusable static libraries directly from source lists.
- [x] Build ELF/PE/Mach-O applications from source roots and optional library lists.
- [x] Reuse lazy selection, embedded ABI validation and target/startup checks.
- [x] Preserve original diagnostics and destination bytes on late build rejection.
- [x] Verify unit symbol/type/data isolation and individually compiled archive parity.
- [x] Publish checked-in example lists and validate both rebuilt native compilers.

General import/package resolution, private symbol linking and ownership/effect
signatures remain separate work. See [commands and bounds](native_module_builds.md).

## SV8.74 — shared native libraries, three executable formats (2026-10-18)

- [x] Link the existing integer libraries into Windows PE32+ executables.
- [x] Link them into static Intel macOS Mach-O executables.
- [x] Register explicit target commands in all native host drivers.
- [x] Preserve archive selection and embedded ABI checks for every target.
- [x] Resolve the typed U32 entry beyond the first object and in selected members.
- [x] Enforce platform requirements and selected-object bounds before output I/O.
- [x] Retain the single-object backend APIs and their established startup paths.
- [x] Validate native self-builds, PE execution and cross-host artifact identity.

Actual Intel macOS execution requires CI. General ownership/effects, pointer
interfaces, COFF/Mach-O object archives and foreign linking remain open.
See the [executable-target contract](native_library_targets.md).

## SV8.73 — native ELF static-library block (2026-10-18)

- [x] Create deterministic regular ar libraries directly in Sotlas.
- [x] Validate every stored ELF member and its compiler ABI manifest.
- [x] Link mixed direct objects and libraries without a host archiver/linker.
- [x] Select members lazily and resolve transitive/cyclic function imports.
- [x] Preserve exact integer ABI checks across every selected boundary.
- [x] Reject malformed storage, capacity failures and incompatible selected
  providers before opening the output artifact.
- [x] Expose the commands in all three native host drivers and document the
  reusable three-module example with positive/negative execution gates.

This completes the regular short-name ELF library subset. The parent items for
general archives/libraries, ownership/effect signatures, PE/Mach-O and dynamic
linking remain open. See [format, bounds and tests](native_static_libraries.md).

## SV8.72 — embedded integer ABI for independent modules (2026-10-17)

- [x] Emit versioned signatures automatically in production ELF objects,
  covering every function definition and external declaration.
- [x] Add `--link-elf-abi-objects` to all three native host drivers.
- [x] Validate multiple symbols and providers across 1–16 independent objects,
  including transitive and unused imports, without hand-authored sidecars.
- [x] Compare integer width/signedness, Boolean identity, arity and return tags.
- [x] Reject malformed/incomplete manifests and mismatches before output writes.
- [x] Include an executable three-module example and native regression gates.

These checks close the integer machine ABI delivery. They do not close the
parent items for general separate compilation or semantic signatures: pointer
lifetimes, ownership, effects, visibility, aggregates and typed PE/Mach-O
linking remain pending. See the [contract](native_embedded_abi.md).
Local validation and remote certification are reported separately in the
[sovereignty roadmap](sotlas_sovereignty_roadmap.md).

## SV8.71 — verify complete ELF imports and compiler-sourced ABI subset (2026-10-17)

**Certified baseline:** `684e674ca15c31441f88293757dfe69eac855f67` /
[CI #1259](https://github.com/HPinho/sotlas_dev/actions/runs/39065215635).
Candidate until its own complete matrix passes.

- [x] Reject every undefined global ELF symbol not named in the one
  SOTI importer record; cannot silently link a second unverified import.
- [x] Cross-check the real defined export against the compiler's
  `.note.sotlas.abi` function descriptor for arity, boolean mask and
  float-return classification before emitting an executable.
- [x] Fail closed on missing/corrupted notes and on unproven non-plain
  (sole/direct/whisper) parameter claims; retain plain ABI successes.
- [x] Derive a portable SOTI v1 record from compiler-owned Target IR
  function and parameter ABI types, including validated ranges and
  source symbol bounds, with no hosted encoder.
- [x] Preserve old output bytes and written-length markers on rejected
  Target IR encoding; validate all parameters before the first write.
- [x] Add 19 native successful and negative gates split between real ELF
  two-object linking (11) and Sotlas-machine-code Target IR ABI encoding
  (8). Keep all old CI/matrix/ownership tests enabled.

**Explicit boundaries:** the current compiler IR lacks a validated
parameter ownership-role field, and lacks inferred effect/capability
claims in this record. The new serializer therefore emits only plain
roles, with caller-supplied rights bits. The ELF note proves only
arity/boolean parameter positions/float-return class, not complete
ABI provenance. Production CLI/ELF section automatic SOTI generation,
all-object coverage, Windows PE/Mach-O typed linking and zero-hosted
Python/C bootstrap are still unverified.
See [SV8.71 typed ELF gates](native_typed_elf_pair.md).

## SV8.70.1 — cross-host opt-in typed ELF linker regression repair (2026-10-17)

**Last fully green baseline:** `6593c521966ab1fa8c1531312bb4214948502fdf` /
[CI #1257](https://github.com/HPinho/sotlas_dev/actions/runs/39042389972).
[CI #1258](https://github.com/HPinho/sotlas_dev/actions/runs/39048032064)
failed on the SV8.70 candidate. The complete next matrix must certify
this repair before SV8.71 begins.

The log evidence isolates **three independent causes**:

1. The new `--link-elf-typed-pair` command had only been registered in
   `linux.sotlas`. The separately compiled `darwin.sotlas` and
   `windows.sotlas` drivers still returned usage exit 1 for every
   new command. Both now get the identical native, bound-checked
   ELF/SOTI typed-pair handler, static name/record storage and explicit
   dispatcher registration; no Python/C execution fallback is added.
2. A backend source comment literally contained the forbidden marker
   `@extern(C)`, violating the preexisting sovereignty contract
   `test_x86_scalar_emitter_is_fail_closed_and_target_ir_native`.
   The comment now says "foreign-call declarations". The compiler's
   actual ABI handling and the test itself are unchanged.
3. All 15 new test cases shared the same image path. Negative tests
   first wrote a mode-0644 sentinel; a subsequent positive link
   truncated the existing file without restoring executable mode.
   Linux therefore returned `PermissionError: [Errno 13]` on
   an otherwise successfully linked ELF. Each case now owns a
   unique output path derived from its test method while still
   protecting the previous image byte-for-byte **within that case**.

**Nothing weakened:** all fifteen native positive/rejection tests, all
pre-existing per-platform tests, SOTI ABI/effect/ownership security
checks, legacy multi-object ELF linking, and Stage2/Stage3 fixed-point
gates are preserved. This candidate awaits its own full Linux,
Windows and Intel macOS workflow with installer/package jobs.

## SV8.70 — typed ABI gates on actual two-object ELF linking (2026-10-17)

**Baseline:** green `6593c521966ab1fa8c1531312bb4214948502fdf`,
[CI #1257](https://github.com/HPinho/sotlas_dev/actions/runs/39042389972).
New CI is required before certification.

- [x] Add opted-in `--link-elf-typed-pair` directly to the Sotlas-native
  Linux driver, accepting two separate object inputs and SOTI v1 sidecars.
- [x] Enforce full wire/ABI/role/effect/capability compatibility *before*
  asking the production native multi-object linker to publish an image.
- [x] Check both supplied names against actual ELF symbol table entries,
  distinguishing undefined import from exported defined function,
  rejecting duplicate matching symbols.
- [x] Keep all error paths before artifact writing; preserve previous
  executable bytes on invalid ABI, authority, ELF symbols, input
  files, wire formats and entry points.
- [x] Keep the original `--link-elf-objects` untouched, the fixed-point
  compiler tests and Linux/Windows/Intel macOS matrix intact.
- [x] Add 15 real two-object CLI tests in
  `tests/test_sotlas_native_typed_elf_pair.py`, including machine-code
  ELF execution and negative gates.

**Open:** metadata is caller-supplied, not synthesized from frontend
or embedded in objects; the command checks one import/export pair,
not every unresolved symbol. No automatic ARC/drop, all-object/PE/Mach-O
typed linking, authenticated authority or zero-hosted-tool first seed
is claimed. See [typed ELF pair contract](native_typed_elf_pair.md).

## SV8.69.1 — native u64 wire-shift regression repair (2026-10-17)

[CI #1256](https://github.com/HPinho/sotlas_dev/actions/runs/39038976982)
failed the native compiler smoke gates on Linux, Windows and Intel macOS.
Many previously green tests also failed because every assembled Target IR
driver included the newly introduced wire helpers. The first consistent
native compile rejection occurs at the `u64` serializer shift, around
Target IR line 2096 (driver assembly reports approximately 9255).
The SV8.69 implementation cast its right-side shift count to `u32`,
although the 64-bit left operand requires a matching `u64` count in
this native lowering profile.

The correction makes **both** 64-bit store/load helpers use
`(index as u64)*8`, following the already certified
`runtime/native/binary.sotlas` pattern. The 32-bit helpers continue
using 32-bit shift counts. This preserves all wire ABI, encoding,
capability, role, malformed-input and transactional-write rules.
No tests are removed, weakened or skipped. One additional native
compile/link/execute case checks distinct high/low bytes of two
nonuniform 64-bit effect/capability values and decodes them back,
bringing the SV8.69 suite to **16 tests**.

**Last certified green baseline:** `43bb572e23c724c06ea99a2b694ad38f27756d2d` /
[CI #1255](https://github.com/HPinho/sotlas_dev/actions/runs/39011203750),
also green #1254. The repair is a candidate until its own complete
Linux/Windows/Intel-macOS, native fixed-point and packaging workflow
passes. Do not advance to SV8.70 before this gate is green.

## SV8.69 — versioned native serialized interface contract (2026-10-17)

**Baseline:** green [CI #1254](https://github.com/HPinho/sotlas_dev/actions/runs/38992580949)
and [#1255](https://github.com/HPinho/sotlas_dev/actions/runs/39011203750),
both at `43bb572e23c724c06ea99a2b694ad38f27756d2d`.
SV8.69 awaits full CI.

- [x] Encode fixed-width import/export records (v1 little endian):
  magic, version, kind, scalar/pointer return ABI, symbol name offsets,
  parameter count, effects and required capabilities.
- [x] Encode a bounded table of exact parameter ABI and plain/sole/direct/
  whisper roles, maximum 24 per interface, without C or host endian.
- [x] Validate magic/version/reserved bytes, full exact record lengths,
  name bounds, parameter type/role and unsupported aggregate shapes.
- [x] Decode valid records into typed Target IR records, preserving
  the existing output and parameter slots on rejection.
- [x] Reject too-small encoding buffers and malformed source signatures
  without modifying previously emitted bytes or output length.
- [x] Compare two fully serialized import/export signatures directly,
  including exact ABI and ownership and non-escalating capabilities/effects.
- [x] Add 15 native compile/link/execute and fail-closed tests, preserving
  all previously certified SV8.66–SV8.68 gates.

The underlying native interface contract is now serializable and
executable without Python/C in the generated test images.
**Unfinished parent:** integrating these records with the real native
object writers and linkers, initial native distribution seed and
compiler-generated ARC/drop. See [SV8.69 wire format](native_typed_interfaces.md).

## SV8.68 — native typed pre-link interface and manifest verification (2026-10-16)

**Baseline:** `e3abf81191a1a928d6a981b9d29eb00c0d6155ff`,
[CI #1253](https://github.com/HPinho/sotlas_dev/actions/runs/38980061670).
Candidate until this commit's complete CI passes.

- [x] Represent typed Sotlas module symbols with name slices, parameter
  ABI tags, ownership roles, return ABI, effect bitmask and capability set.
- [x] Validate source-name/parameter bounds, export/import record flags,
  supported scalar/pointer shapes and exact role/type/return matches.
- [x] Reject ambiguous duplicates, missing symbols and unsupported
  aggregate ABIs without a hosted semantic fallback.
- [x] Enforce effect/capability subset checking at the pre-link boundary.
- [x] Resolve individual symbols with output preservation on failures.
- [x] Bind whole manifests with a two-pass validate-then-publish policy;
  reject the second failed import without partially writing earlier mappings.
- [x] Add 19 native positive/negative gates:
  `tests/test_sotlas_native_migration_sv868.py`.

The `Target IR` pre-link API is native Sotlas code. General separate
compilation, serialized object interfaces, actual cross-object linking
enforcement, canonical effects/ownership and Python/C-independent initial
seed remain open. See [typed interface contract](native_typed_interfaces.md).

## SV8.67 — bounded native scoped ownership transactions (2026-10-16)

**Baseline certified:** [CI #1251](https://github.com/HPinho/sotlas_dev/actions/runs/38957013245),
commit `94823c443e741184f3c148e0435e06c72d4cb081`. The SV8.67
candidate requires its own complete matrix.

- [x] Acquire and register a cloned independent strong claim in the same
  native scope operation, with rollback on unexpected registration failure.
- [x] Upgrade a matching current weak generation and publish a tracked
  strong handle without accepting stale, foreign or mismatched tokens.
- [x] Transfer one caller-owned strong claim into a scope via a fresh
  destination handle, poisoning the previous handle and preserving refcount.
- [x] Reject full tables, already-registered sources and nonempty target
  handles before changing claim state.
- [x] Detect duplicate slot pointers (including corrupted unsafe writes)
  before checked rewind can cause partial cleanup.
- [x] Reject aliasing/overlapping backing buffers during scope-to-scope
  transfer, permitting adjacent nonoverlapping tables.
- [x] Execute combined clone/take/weak cleanup via compiler-lowered lexical
  `defer`; retain all 15 earlier SV8.66 gates.
- [x] Add 16 native execute/rejection tests:
  `tests/test_sotlas_native_migration_sv867.py`.

Still open: compiler-synthesized ARC/drop, general borrow/lifetime checks,
unforgeable ownership under arbitrary raw pointer writes, typed
independently compiled modules and wholly Python/C-independent
bootstrap/package creation. See
[native scope contract](native_scoped_resources.md).

### SV8.66.1 — CI #1250 portable address-slot repair (2026-10-16)

The Linux/Windows/Intel-macOS jobs of
[CI #1250](https://github.com/HPinho/sotlas_dev/actions/runs/38949008917)
failed the same 14 new positive native test compilations, all at the
first pointer-to-pointer local cast from a scalar address array.
The previous SV8.65 [CI #1249](https://github.com/HPinho/sotlas_dev/actions/runs/38940935785)
is green. The native profile supports machine-pointer addresses but its
nested pointer-to-pointer array cast is not certified.

Keep the same complete 15-test ownership suite and its check/build/execute
contracts. Store registered stable handle addresses in caller-owned
`usize` entries (`*mut usize`) and cast each loaded scalar address
explicitly back to the native handle pointer. This retains every LIFO,
transactional preflight, detach/transfer and weak/strong lifetime guard.
No test removal, test skip, previous code rollback or Python/C fallback.
The repair is a **candidate** until its full cross-platform CI is green.

## SV8.66 — scoped native resource lifecycle: larger complete bounded block (2026-10-16)

**Verified baseline:** `768b6d1d2bd17a46ad2be227d464cdc276717602` /
[CI #1249](https://github.com/HPinho/sotlas_dev/actions/runs/38940935785).
The work below is a candidate until its new full matrix passes.

- [x] Initialize bounded (1–64), caller-backed native scope tables with pointer-extent and capacity guards; no Python/C allocator.
- [x] Register independent strong-claim slots while rejecting duplicate, stale, null and over-capacity registration.
- [x] Query registration/depth and explicitly detach a slot without releasing its strong claim.
- [x] Release live claims in reverse registration order, poison closed handles, clear table rows, and preserve other claims during non-final release.
- [x] Support nested scope-depth marks, checked rewinds, and full preflight so stale entries or out-of-range marks cannot partially release other live resources.
- [x] Transfer an active ownership claim between disjoint scope tables without incrementing or decrementing reference counts.
- [x] Integrate a `void` scope-close function with the existing Sotlas-native lexical `defer` backend, including early returns, loop break and continue.
- [x] Exercise strong/weak generations, clone/close boundaries, table exhaustion, recovery from stale entries and negative native ownership diagnostics.

**Gate:** `tests/test_sotlas_native_migration_sv866.py` contains 15
cross-platform native compile/link/execute/rejection tests. The existing
SV8.51–SV8.65 suites, Linux/Windows/Darwin matrix and Stage2/Stage3 selfhost
gates remain intact. No prior tests have been removed or weakened.

**Boundaries:** this is explicit source-registered cleanup of stable,
caller-owned buffers, headers and handles. It does not yet provide
compiler-synthesized ARC/drop glue, general lifetime proofs, multithreaded
reference counting, resource heap allocation, non-POD destructors, typed
separate-object module interfaces or full Python/C bootstrap removal.
See [the scoped resource contract](native_scoped_resources.md).

## SV8.63 — native match guards (2026-10-16)

Owner-reported baseline: `899fce1` is green. This cut closes the native guard
subset described in [the contract](native_match_guards.md), including execution,
coverage and ownership analysis; it does not close general match expressions.

- [x] Parse and execute Boolean guards on scalar, Boolean, scalar-enum,
  bounded-range and wildcard patterns, with single selector evaluation.
- [x] Evaluate guards only on pattern hits, try the next arm on false, preserve
  lazy Boolean operators and exclude guarded cases from coverage proofs.
- [x] Permit guarded overlap/fallback; reject explicit overlap after an
  unguarded case, a guarded final arm and incomplete unguarded coverage.
- [x] Permit supported live POD owner borrows, reject consuming guards and
  preserve selected-body moves, scope checks and LIFO cleanup on returns/jumps.
- [x] Run the combined 24 native fixture cases on Windows and Linux/WSL, verify
  Stage 2/3 identity and execute the guarded command dispatcher with result 42.
- [x] Register the new documentation snippet and pass the 16 reality gates.

The implementation is Sotlas code; no Python implementation was added. Existing
Stage 3 CI gates consume the expanded fixture manifest without another seed
build. The Intel macOS compiler was cross-generated; full suites and Intel macOS
execution were not run locally. The candidate CI remains pending.

## SV8.62 — integer match ranges, complete native cut (2026-10-15)

- [x] Parse inclusive/exclusive bounded integer range patterns into native AST.
- [x] Fold typed bounds and reject dynamic, nominal-enum and out-of-range values.
- [x] Reject empty/reversed and overlapping scalar/range patterns.
- [x] Prove full integer-domain coverage without expanding values or overflowing
  at signed minima and unsigned maxima; otherwise require a final wildcard.
- [x] Lower directly to typed comparisons and structured CFG; evaluate the
  subject once and preserve existing return/jump/defer/POD ownership semantics.
- [x] Report located causes through Linux, Windows and Intel macOS native drivers.
- [x] Execute 13 fixture cases on Windows and Linux through WSL, including
  positive execution, negative check/compile parity and artifact preservation.
- [x] Rebuild the changed compiler from native seeds on Windows/Linux and
  require Stage 2/3 identity; run the byte classifier example with exit 42.

The implementation is Sotlas code. The Python changes only invoke the shared
fixture checks from the existing platform Stage 3 gates; they implement no
language behavior and add no separate compiler bootstrap. Intel macOS execution
and remote CI remain unverified locally. Full suites were not rerun for this
cut. [Contract and commands](native_match_ranges.md).

## Native build entry points (2026-10-15)

- [x] Remove mandatory C-compiler discovery and Python fallback from
  `scripts/build_native.bat` and `scripts/build_native.sh`.
- [x] Rebuild both compiler generations from Sotlas modules using a compatible
  native seed, then require identity before exercising the rebuilt compiler.
- [x] Run a Sotlas text-parser example and reject use-after-move from both check
  and compilation with host build tools absent from PATH.
- [x] Preserve existing output directories and the previous executable when a
  compilation is rejected.

The complete scripts passed on Windows x64 and Linux x86-64 through WSL.
The shell syntax check also passed. Intel macOS execution was not run for this
change. Initial seed production used the existing hosted producer; neither a
Python process nor a C compiler was invoked during these native rebuilds.
This replaces the build entry points, not the remaining hosted packager or
whole-language frontend/ownership analysis. See the
[native seed workflow, commands and limits](native_seed_workflow.md).

This checklist tracks migration of the contracted canonical language into the
Sotlas-written compiler. A working bootstrap profile does not establish full
language parity. Parent items stay open until every contracted form has native
positive, negative and execution coverage. Subitems record smaller validated
contracts. Local validation must pass CI before being called certified.

### SV8.61 — new loop/range/enum syntax and text values (2026-10-15)

Starting from `7a36a3e`, this package delivers 36 new source/runtime contracts
across four capability families. The allocation follows new language surface
and a new text module; it does not repeat the previous nine-topic allocation.

#### SV8.61 Unconditional loop syntax

- [x] Execute loop statements with explicit break.
- [x] Execute continue against an unconditional loop header.
- [x] Nest loop statements with innermost jump targets.
- [x] Prove returning loop bodies without an artificial trailing return.
- [x] Run lexical defers in LIFO order on loop continue and break.
- [x] Preserve owner borrows through loop statements and reject reads after transfer.

Gate: `test_sotlas_native_language_sv861`.

#### SV8.61 Integer range for syntax

- [x] Execute exclusive integer ranges with a lexical iteration binding.
- [x] Use matching integer variables as range endpoints.
- [x] Evaluate start and end calls once in source order.
- [x] Execute ranges over matching signed integer endpoints.
- [x] Nest ranges with independent hygienic internal cursors.
- [x] Shadow an outer iteration name and restore its lexical scope.
- [x] Keep the default index immutable and support an explicit mutable iteration copy.
- [x] Advance the hidden cursor on continue.
- [x] Run deferred cleanup before a range break.
- [x] Skip empty and descending ranges while rejecting noninteger endpoints.

Gate: `test_sotlas_native_language_sv861`.

#### SV8.61 Implicit enum values

- [x] Start an implicit scalar enum at zero.
- [x] Assign distinct successive implicit discriminants.
- [x] Reset the implicit successor after an explicit discriminant.
- [x] Compute implicit successors after radix integer discriminants.
- [x] Carry implicit enum values through record fields and native calls/returns.
- [x] Reject implicit U32 overflow while permitting a following explicit reset.

Gate: `test_sotlas_native_language_sv861`.

#### SV8.61 Borrowed byte-slice text module

- [x] Construct length-delimited byte slices that retain embedded zero bytes.
- [x] Produce checked borrowed substrings.
- [x] Read a byte through checked slice indexing.
- [x] Compare slice values lexicographically by unsigned bytes and length.
- [x] Compare complete slice values for equality beyond embedded zeros.
- [x] Match a borrowed prefix, including an empty prefix.
- [x] Match a borrowed suffix at the slice end.
- [x] Search for a byte substring with an unchanged output on failure.
- [x] Split a record once into borrowed key/value slices.
- [x] Trim ASCII edge whitespace while retaining interior bytes.
- [x] Parse complete unsigned decimal values with U64 overflow checks.
- [x] Materialize a slice into caller storage with overlap-safe copying.
- [x] Iterate separated fields while retaining empty and trailing fields.
- [x] Iterate LF/CRLF lines and a final unterminated line.

Gate: `test_sotlas_native_text_sv861`.

Loop and range statements pass through the Sotlas lexer/parser, existing
native semantic/ownership checks, Target IR, owned object writer and native
linker. They use structured CFG and existing defer cleanup. A returning loop
body is proven only when its body returns on all represented paths and contains
no jump targeting that loop. Other value-returning functions still need a
return after a potentially exiting loop. General divergence proofs remain open.

For ranges use exclusive bounds and matching integer types. Unsuffixed literals
retain the existing U32 default. Start is evaluated before end; both are
captured once. The public index is a per-iteration value. An explicit mut/var
index changes that copy; it does not steer the hidden cursor. The cursor advances
before the body, so continue advances correctly. Empty/descending ranges have
no iterations; increments cannot exceed the captured exclusive bound. Hidden
bindings use reserved keyword spellings inaccessible as source identifiers,
and nested scopes restore the outer bindings. Arrays/iterators, steps and
inclusive ranges are not implemented by this syntax.

- [ ] Align the reference C11 range emitter with this native contract before
  claiming backend equivalence. Its current size_t counter and repeated end
  expression can differ for signed bounds, effectful ends and a mutable index.

Internal generated increment/loop-condition integers carry a zero-length source
spelling and a bounded numeric AST payload. They retain the source span of the
originating keyword. No host string pool or Python AST synthesis is required.

Native scalar enums now allow implicit and mixed discriminants in the existing
U32 layout. Values start at zero and advance from the preceding value. A value
above U32 is rejected; an explicit reset after U32 maximum is allowed. Payload
variants, signed/backing-type declarations and general discriminant expressions
remain open. The old implicit-variant rejection fixtures now check unsupported
payload variants at their actual locations; positive implicit variants execute in
the new native gate.

The new runtime/native/text.sotlas defines NativeByteSlice, NativeTextSplit and
NativeTextCursor as ordinary records. Text operations are byte based; ASCII
trimming and decimal parsing have explicit rules. They do not add built-in str
or slice syntax, UTF-8 scalar indexing, allocation or inferred lifetimes.
Embedded zeros are ordinary bytes. A slice's valid flag records checked shape,
not a proof that memory exists. Backing storage and metadata/output disjointness
remain caller obligations. Copy writes exactly the slice length, with no NUL
terminator. Split cursors retain empty/trailing fields; line cursors normalize
CRLF and omit a trailing empty record after a final newline. No foreign runtime
calls are used. A native integration test parses and sums key=value lines.

Automatic resource cleanup synthesis, typed separate modules, payload enums,
native generic resolution and whole-language Python/C independence remain open.

SV8.61 local validation:

- Full Windows suite: **3242 tests run, no failures/errors, 79 existing
  platform/toolchain skips, 1192.567 seconds**.
- The 36 new gates passed with Windows Python 3.10 (30.375 seconds) and actual
  Linux x86-64 execution through WSL (33.013 seconds), including the composed
  key=value text program. Native images execute with external tools off PATH.
- The signed-range gate was strengthened to assert all five iterations, then
  rerun successfully on Windows and Linux after the full suite.
- Linux original-source Stage 2/3 byte identity and full Darwin compiler
  cross-generation passed: two gates in 131.258 seconds. The full Windows suite
  also passed its native Windows Stage 2/3 fixed-point gate.
- Additional Sotlas machine-code compiler seeds each compiled and executed three
  integration programs on Windows and Linux: loop/range/enum composition, the
  text record reader and a directly returning loop. All six runs returned 42;
  compilation and execution used PATH without external tools after seed setup.
- Two historical implicit-enum rejection fixtures now reject unsupported
  payload variants at column 7; positive implicit enums have native coverage.
- Local Darwin evidence is cross-generation; native macOS execution awaits CI.
- Documentation validation passed 147 links, 196 heading anchors and normalized
  source hashes. Candidate CI remains pending; no workflow was monitored.


### SV8.60 — 36 native contracts (2026-10-15)

Starting from online revision `88c80e2`, this package builds on SV8.57–SV8.59.
It adds four bounded deliveries in each of nine open migration topics.
Whole-topic completion and candidate CI certification remain open.

#### SV8.60 Frontend

- [x] Accept digit-separated positive exponents in native F32 literals.
- [x] Accept digit-separated negative exponents in native F64 literals.
- [x] Evaluate scientific float module constants with exponent separators.
- [x] Reject malformed exponent separators and values outside the existing bounded literal profile.

Gate: `test_sotlas_native_migration_sv860`.

#### SV8.60 Native ownership

- [x] Join a preserving first match break arm with ordinary fallthrough.
- [x] Join a preserving trailing match break arm with a live preceding arm.
- [x] Join a preserving first match continue arm with ordinary fallthrough.
- [x] Join a preserving trailing match continue arm with a live preceding arm.

Gate: `test_sotlas_native_migration_sv860`.

#### SV8.60 Sotlas memory runtime

- [x] Clone a managed byte claim into an empty independent strong slot.
- [x] Upgrade a matching weak token into an empty strong slot.
- [x] Transfer a managed claim into an empty slot while poisoning its source.
- [x] Swap valid managed slots without changing strong reference counts.

Gate: `test_sotlas_native_migration_sv860`.

#### SV8.60 States, effects, authority and contracts

- [x] Check U64-to-U8 narrowing before publishing an output.
- [x] Check U64-to-U16 narrowing before publishing an output.
- [x] Check U64-to-U32 narrowing before publishing an output.
- [x] Check I64-to-I32 narrowing before publishing an output.

Gate: `test_sotlas_native_migration_sv860`.

#### SV8.60 Native IR and lowering

- [x] Reject shared parameter-table rows between independent functions.
- [x] Reject shared block-table rows between independent functions.
- [x] Reject duplicate function spellings at the source-aware IR boundary.
- [x] Reject duplicate nonempty parameter spellings within one IR function.

Gate: `test_sotlas_native_migration_sv860`.

#### SV8.60 Owned backend execution and binary API

- [x] Load unaligned little-endian integers with checked extents.
- [x] Load unaligned big-endian integers without host byte-order dependence.
- [x] Store little-endian integers while rejecting truncation before writes.
- [x] Store big-endian integers with full-width roundtrip coverage.

Gate: `test_sotlas_native_migration_sv860`.

#### SV8.60 Owned objects and linking

- [x] Reject overlapping file-backed ELF section payloads.
- [x] Reject uncontracted string-table link, info and entry-size metadata.
- [x] Reject ELF relocation targets that name metadata sections.
- [x] Require zero section virtual addresses in the accepted relocatable ELF profile.

Gate: `test_sotlas_native_tool_operations_sv860`.

#### SV8.60 Native CLI

- [x] Report validated object counts through --object-info-json.
- [x] Report executable fingerprints and sizes through --seed-info-json.
- [x] Report ordered artifact-set identity through --artifact-set-info-json.
- [x] Check project semantics before --project-set-info-json reports source identity.

Gate: `test_sotlas_native_tool_operations_sv860`.

#### SV8.60 Bootstrap and self-hosting

- [x] Rebuild project objects natively before --verify-project-object compares bytes.
- [x] Compile both project manifests before --compare-project-objects compares object bytes.
- [x] Rebuild a project before --stamp-project-object records SOTOBJ01 object identity.
- [x] Rebuild a project before --verify-project-object-stamp verifies object identity and stamp metadata.

Gate: `test_sotlas_native_tool_operations_sv860`.

Numeric separators are permitted only between decimal exponent digits. The
existing coefficient/denominator and exponent limits remain in force; this
does not add arbitrary-precision parsing or the complete IEEE literal range.

Match arms with ordinary fallthrough may coexist with simple break/continue
edges when those edges preserve every owner visible at the surrounding loop
entry. Moving an owner before such a match still fails. Closed-edge summaries
retain their previous behavior. Arms with nested mixed break/continue summaries
cannot join ordinary fallthrough yet; arbitrary CFG and automatic resource
cleanup remain open. One old
rejection fixture now consumes the owner on its break arm; preserving matches
are covered by new native execution tests.

Managed clone/upgrade/take/swap operate on explicit caller-backed strong slots.
Destinations for clone/upgrade/take must have all four fields empty. Successful
clone/upgrade adds one claim; take empties its source without retaining; swap
changes neither count. Slots, headers and payloads must stay valid, stable and
disjoint; raw struct copies remain forgeable. Close is still explicitly
registered with defer. Synthesized cleanup and a typed separate-module ABI,
identified as priorities after SV8.59, are not completed by these APIs.

Narrowing APIs leave outputs unchanged on rejection and do not change the
language's ordinary cast rules or migrate canonical contract/effect syntax.
Binary APIs support widths 1, 2, 4 and 8; check the full extent and reject stores
that would truncate. Backing storage and disjoint writable outputs remain
caller obligations. These software routines use the existing owned scalar IR;
they add neither volatile/atomic/MMIO semantics nor dedicated instruction
selection. No foreign runtime calls are used.

IR uniqueness checks compare actual source spellings and allow empty parameter
debug names in manually built IR. Parameter/block partitions must not overlap
across independent functions. ELF checks narrow the existing relocatable-object
contract; they do not expand relocation types or the external object ABI.

JSON report fields are fixed-width lowercase hexadecimal strings, explicitly
named *_hex. Existing text commands remain available. Reports are emitted only
after validation. Project commands retain bounded manifest input, source
concatenation and explicit import resolution, not typed separate compilation.

Object audits actually invoke the native project checker/emitter. Byte comparison
uses the rebuilt ELF object, not source fingerprints. SOTOBJ01 records magic,
FNV-1a object fingerprint, object length, version 1, kind 3 and zero reserved
bytes in 32 bytes. It is a reproducibility aid, not authentication. Creation is
exclusive; invalid projects preserve existing outputs and failed new writes may
leave partial files. Inputs must remain stable during reads. Object equality
does not establish full compiler fixed points; the separate Stage 2/3 gates
remain required. Python/C still provide Stage 0 and have not been removed.

SV8.60 local validation:

- Full Windows suite: **3206 tests run, no failures/errors, 79 existing
  platform/toolchain skips, 941.781 seconds**.
- The 36 new gates passed with Windows Python 3.10 (25.582 seconds) and with
  actual Linux x86-64 execution through WSL (27.523 seconds), with native test
  images running while external tools were absent from PATH.
- Linux original-source Stage 2/3 byte identity and full Darwin compiler
  cross-generation passed: two gates in 95.105 seconds. The full Windows suite
  also passed the native Windows Stage 2/3 fixed-point gate.
- Darwin evidence here is cross-generation; native macOS execution awaits CI.
- Documentation validation passed 147 links, 190 heading anchors and normalized
  source hashes. Candidate CI remains pending; no workflow was monitored.


### SV8.59 — native defer-driven managed resource close (2026-10-15)

**Verified baseline:** `fd6dd7d89cff9b38fa6fbe58bb34551b30806f37` /
[CI #1234](https://github.com/HPinho/sotlas_dev/actions/runs/38790093635).

- [x] Add Sotlas-native `native_managed_bytes_close` for a mutable resource slot, releasing one live strong claim and poisoning the handle before another cleanup can reuse it.
- [x] Execute this cleanup through compiler-lowered lexical `defer` on block exit and early return, without C runtime glue.
- [x] Verify duplicate deferred close is harmless and strong reference counts/weak invalidation track the final release.
- [x] Verify non-final closing preserves bytes and that stale/forged resource handles cannot change reference state.

Gate: `tests/test_sotlas_native_migration_sv859.py` (native compile, owned
link and execution; positive and negative state checks). The source programmer
must explicitly register `defer`; this **does not** synthesize drop glue,
prove caller-owned backing storage lifetime, make aliases unforgeable or
provide general automatic ARC. Control/payload/handle storage must remain
stable and disjoint. This candidate still requires full CI certification.

### SV8.58 — native managed byte-resource final release (2026-10-15)

**Last green baseline:** `0df0bb95bfc3ae9300d49be8063703d722d32d87` /
[CI #1233](https://github.com/HPinho/sotlas_dev/actions/runs/38781346034).

- [x] Bind a unique live reference header to a checked caller-backed byte payload without C allocation.
- [x] Retain and upgrade generation-matched weak tokens only for their original managed payload.
- [x] Keep payload bytes intact on nonfinal release; clear exactly the declared range upon final release and invalidate weak upgrades.
- [x] Reject null/empty, stale/recycled, shared-at-bind and mismatched-resource states without changing the reference count.

**Execution and rejection gate:** `tests/test_sotlas_native_migration_sv858.py`.
The Sotlas-owned API is single-threaded and caller-driven: stable/disjoint
header, handle and payload storage are preconditions. This is **not**
automatic compiler-emitted ARC, heap allocation, destructor dispatch or
general owned payload lifetime/escape validation. Those parent items stay open.
No compiler C/Python fallback or weakened CI gate is introduced. Candidate
awaits its own complete cross-platform and self-host fixed-point matrix.

### SV8.57 — compound integer assignments in the Sotlas-written frontend (2026-10-15)

Baseline: `08b0cc4b3009291dfea8fbdba229e5ca9202dbef` / [green CI #1231](https://github.com/HPinho/sotlas_dev/actions/runs/38762917787).
This candidate expands the existing identifier-only compound assignment contract:

- [x] Recognize and lower `%=` with existing typed integer remainder rules.
- [x] Recognize and lower `&=`, `|=` and `^=` using the existing native bitwise operators.
- [x] Recognize and lower `<<=` and `>>=` using the existing native integer shifts.
- [x] Preserve single RHS evaluation, immutable-binding rejection and fail-closed indexed/owned aggregate destinations.

Gate: `tests/test_sotlas_native_migration_sv857.py`. Compounds use the typed AST's existing binary/assign path; unsupported general lvalues, resource ownership and complete canonical operator parity remain open. No hosted Python/C compiler fallback is introduced. Candidate CI pending.

## Frontend parity

### SV8.56 — 36 native contracts (2026-10-15)

Starting from `bba4c7a`, this candidate adds four bounded contracts in each
of nine still-open migration areas. Whole-topic completion and CI certification
remain open. Every delivery below has an execution or rejection gate.

#### SV8.56 Frontend

- [x] Execute local-name += with mutability checks and exactly one RHS evaluation.
- [x] Execute local-name -= while rejecting immutable bindings.
- [x] Execute local-name *= while preserving existing operand type checks.
- [x] Execute local-name /= and reject unsupported compound assignment places.

Gate: `test_sotlas_native_migration_sv856`.

#### SV8.56 Native ownership

- [x] Accept preserving conditional then-break edges with implicit fallthrough.
- [x] Accept preserving else-break edges with a live then arm.
- [x] Accept preserving conditional then-continue edges using the surrounding loop entry.
- [x] Restore nested loop entry snapshots for preserving else-continue edges.

Gate: `test_sotlas_native_migration_sv856`.

#### SV8.56 Sotlas memory runtime

- [x] Initialize a caller-backed byte buffer with bounded empty/null state.
- [x] Append bytes with overlap-safe movement and checked capacity.
- [x] Truncate a byte buffer while clearing its discarded suffix.
- [x] Consume a byte prefix while compacting contents and clearing the old tail.

Gate: `test_sotlas_native_migration_sv856`.

#### SV8.56 States, effects, authority and contracts

- [x] Guard signed I64 addition before publishing a result.
- [x] Guard signed I64 subtraction before publishing a result.
- [x] Guard signed I64 multiplication across sign combinations and the minimum value.
- [x] Guard signed I64 division against zero and minimum divided by minus one.

Gate: `test_sotlas_native_migration_sv856`.

#### SV8.56 Native IR and lowering

- [x] Reject unrelated flags and edge metadata on stack allocations.
- [x] Reject reserved flags and edge metadata on direct calls.
- [x] Reject unrelated symbol, flag and edge metadata on system operations.
- [x] Validate block labels and instruction source ranges before object emission.

Gate: `test_sotlas_native_migration_sv856`.

#### SV8.56 Owned backend execution and word API

- [x] Execute U64 leading-zero counts with a defined zero result of 64.
- [x] Execute U64 trailing-zero counts with a defined zero result of 64.
- [x] Execute full-width U64 bit reversal.
- [x] Execute checked U64 bit extraction, including zero and full widths.

Gate: `test_sotlas_native_migration_sv856`.

#### SV8.56 Owned objects and linking

- [x] Require a zero program-header entry size when ELF has no program headers.
- [x] Require aligned section-header geometry outside the ELF header.
- [x] Reject file-backed section payloads overlapping the ELF header.
- [x] Reject file-backed section payloads overlapping the section-header table.

Gate: `test_sotlas_native_tool_operations_sv856`.

#### SV8.56 Native CLI

- [x] Emit resolved project objects from --project-list-resolve-object manifests.
- [x] Select the host compiler entry with --project-list-compiler.
- [x] Resolve compiler manifests with --project-list-resolve-compiler.
- [x] Cross-emit a Mach-O application from --project-list-macho manifests.

Gate: `test_sotlas_native_tool_operations_sv856`.

#### SV8.56 Bootstrap and self-hosting

- [x] Validate project semantics before --project-set-info reports source fingerprints.
- [x] Validate project semantics before --stamp-project creates an exclusive stamp.
- [x] Check semantics and source identity with --verify-project-stamp.
- [x] Validate both projects before --compare-projects compares corresponding source bytes.

Gate: `test_sotlas_native_tool_operations_sv856`.

Compound assignment currently accepts identifier places only. The parser
desugars a copied identifier and one RHS into the existing typed binary/assign
pipeline; fields, indices and dereferences fail closed. Existing numeric and
division behavior applies; compound syntax does not add checked arithmetic.

An early conditional break/continue may coexist with fallthrough only when all
visible owners on that edge preserve the surrounding loop-entry state. Moving
an owner before the conditional remains an error. Nested loop entry snapshots
are restored on return to the outer loop. General mixed CFG and automatic
resource cleanup beyond the existing POD ownership profile remain open.

NativeByteBuffer stores a caller-owned pointer, capacity and used length. Append
allows overlapping source bytes; truncate/consume clear discarded storage.
Callers must provide valid backing memory, writable outputs and metadata
disjoint from backing/source storage. These functions neither allocate nor
prove lifetimes, ownership or thread safety. Signed guards leave outputs
unchanged on rejection. They are explicit APIs, not migrated canonical effects
or contract syntax. Word functions use existing scalar IR rather than dedicated
LZCNT/TZCNT or bit-reversal instruction selection.

IR checks validate metadata/source ranges; ELF checks validate file geometry.
They do not expand the accepted relocation ABI or establish that arbitrary
external objects are safe to execute. Empty/NOBITS payloads keep their existing
contracts.

New compiler-manifest commands reuse the existing compiler entry signatures
and ordered/resolved source concatenation. Mach-O output is x86-64 application
cross-generation; local validation does not claim native macOS execution.
Shared limits remain 16 paths, 65,535 manifest bytes and 4,095-byte paths;
emission requires at least two modules. Typed module interfaces and package
resolution remain open.

Project audits first run the resolved native check pipeline, then reuse SOTART01
ordered FNV/size records or byte comparison. Dependency graphs are reset between
checks in the same process. These commands validate source sets, not compiler
fixed points; stamps are not cryptographic authentication. Files must remain
stable during reads. Existing stamp outputs are preserved; failed new-file
writes may leave partial artifacts.

Local validation for this candidate:

- Full Windows regression suite: **3154 tests passed, 79 platform/toolchain
  skips, 943.042 seconds**. Existing skips were retained.
- The 36 new gates passed with Windows Python 3.10 (33.976 seconds) and through
  actual Linux x86-64 execution in WSL (40.880 seconds).
- Linux original-source Stage 2/3 byte identity and complete Darwin compiler
  cross-generation passed: two gates, 113.420 seconds. The full Windows suite
  also includes the native Windows Stage 2/3 fixed-point gate.
- Local Darwin evidence is cross-generation, not native macOS execution.
- Candidate CI remains pending; no GitHub workflow was monitored for this package.



### SV8.55 — 36 native contracts (2026-10-15)

Starting from `d9abed4`, this candidate adds four bounded contracts in each
of nine still-open migration areas. Every check below has an execution or
rejection gate. Full migration parents and candidate CI remain open.

#### SV8.55 Frontend

- [x] Encode one-byte Unicode scalar escapes in native strings.
- [x] Encode two-byte Unicode scalar escapes as UTF-8.
- [x] Encode three-byte Unicode scalar escapes while rejecting surrogate code points.
- [x] Encode four-byte Unicode scalar escapes while enforcing the Unicode scalar ceiling.

Gate: `test_sotlas_native_migration_sv855`.

#### SV8.55 Native ownership

- [x] Join a returning arm with a closed break edge without keeping dead owner state.
- [x] Join a returning arm with a preserving continue edge and reject consumed backedges.
- [x] Preserve nested mixed break/continue summaries when the other arm returns.
- [x] Accept nested return/loop-edge joins inside match arms.

Gate: `test_sotlas_native_migration_sv855`.

#### SV8.55 Sotlas memory runtime

- [x] Find the first matching byte while publishing an index only on success.
- [x] Reverse a checked byte range in place, including odd and empty lengths.
- [x] Swap disjoint byte ranges while rejecting partial overlap before writes.
- [x] Copy a byte range into checked arena storage without host allocation.

Gate: `test_sotlas_native_migration_sv855`.

#### SV8.55 States, effects, authority and contracts

- [x] Guard unsigned division against zero without publishing a failed result.
- [x] Guard left shifts against invalid counts and value overflow.
- [x] Guard index-to-byte-offset conversion against bounds and stride overflow.
- [x] Guard a complete offset/count/stride extent against capacity and overflow.

Gate: `test_sotlas_native_migration_sv855`.

#### SV8.55 Native IR and lowering

- [x] Reject unrelated metadata on arithmetic, bitwise and logical instructions.
- [x] Reject unrelated symbol, flag and edge metadata on comparisons.
- [x] Reject unrelated symbol, flag and edge metadata on indexed addresses.
- [x] Reject unrelated symbol, flag and edge metadata on pointer offsets.

Gate: `test_sotlas_native_migration_sv855`.

#### SV8.55 Owned backend execution and word API

- [x] Execute a native Sotlas U64 rotate-left operation with counts modulo 64.
- [x] Execute a native Sotlas U64 rotate-right operation with counts modulo 64.
- [x] Execute a native Sotlas U64 byte swap with a checked involution example.
- [x] Execute a native Sotlas U64 population count for empty, sparse and full words.

Gate: `test_sotlas_native_migration_sv855`.

#### SV8.55 Owned objects and linking

- [x] Accept only the contracted System V/Linux ELF OSABI identities.
- [x] Reject uncontracted nonzero ELF ABI versions.
- [x] Reject nonzero reserved ELF identification padding.
- [x] Require file-backed section offsets to satisfy declared alignment.

Gate: `test_sotlas_native_tool_operations_sv855`.

#### SV8.55 Native CLI

- [x] Check an ordered project from a manifest with --check-project-list.
- [x] Check dependency-resolved manifest projects with --check-project-list-resolve.
- [x] Emit an ordered project object from a manifest with --project-list-object.
- [x] Build and execute a dependency-resolved manifest project with --build-project-list.

Gate: `test_sotlas_native_tool_operations_sv855`.

#### SV8.55 Bootstrap and self-hosting

- [x] Report ordered fingerprints, total size and count for arbitrary artifacts with --artifact-set-info.
- [x] Create an exclusive SOTART01 artifact stamp with --stamp-artifact-set.
- [x] Verify bytes, ordering and format metadata with --verify-artifact-set.
- [x] Compare corresponding artifact bytes and counts across manifests with --compare-sets.

Gate: `test_sotlas_native_tool_operations_sv855`.

Unicode string escapes use `\u{HEX}` with 1–6 hexadecimal digits. Scalars
above U+10FFFF and surrogates are rejected. The four frontend checks distinguish
the four UTF-8 encoding widths; they do not establish a general Unicode library,
normalization or non-byte character values. Strings keep their existing raw
pointer/terminator representation and rodata capacity. An embedded zero scalar
is a zero byte, not a length-aware string API.

Ownership joins now discard a returning arm when the surviving arm contains
closed loop exits. Only surviving continue edges must preserve entry owners;
consumed break edges still make owners maybe-moved after a possibly empty loop.
Return plus ordinary fallthrough retains its previous behavior. Arbitrary CFG,
open fallthrough/jump mixtures and automatic resource-domain runtime remain open.

Memory APIs require valid caller-backed ranges. Find leaves its output unchanged
on failure; reverse and swap reject invalid arithmetic before writes. Swap
allows exact identity but rejects partial overlap. Arena copy uses overlap-safe
movement after checked allocation and does not implement a heap or lifetime proof.
Arithmetic guards publish only after validation; they are explicit runtime
contracts rather than canonical contract/effect migration.

The new `runtime/native/word.sotlas` implements rotate-left/right, byte swap and
population count with existing native scalar IR. This is an executable low-level
API, not instruction selection for dedicated ROL/ROR/BSWAP/POPCNT instructions,
CPU feature detection or a promise about emitted instruction counts. It has no
foreign calls. Other IR metadata and ELF identity/alignment checks reject
unsupported inputs without expanding the external object ABI.

Project manifest commands share the existing ordered/resolved project pipeline
and source concatenation. Check accepts 1–16 paths; object/image emission keeps
the existing minimum of two modules and accepts at most 16 listed paths. They
retain 65,535 manifest bytes, 4,095-byte paths and cwd-relative interpretation.
Typed separate module interfaces, package resolution and incremental builds
remain open.

SOTART01 stamps use the same ordered FNV/size records as seed sets, without
requiring executable envelopes. Artifact-set-info reports aggregate fingerprint,
total byte size and file count as three U64 hexadecimal lines. Compare-sets
checks corresponding files byte-for-byte and rejects different counts before
reporting success. Paths are not artifact identity. Source files, objects or
images may be included; files must remain stable during operations. Stamps are
not cryptographic authentication. Creation is exclusive and a failed new-file
write may leave a partial artifact. Existing SOTSET01 seed semantics are retained.

Final local validation: 3,118 Windows regression tests passed with 79
platform/toolchain skips in 1,052.646 seconds. All 36 new gates passed on Linux
through WSL (44.083 seconds) and Windows Python 3.10.11 (37.889 seconds).
The 137 existing native frontend closure gates passed. Original-source Stage
2/3 identity passed on Windows in the full suite and Linux in a separate gate;
complete Darwin compiler cross-generation passed on both hosts. The two Linux
generation gates took 134.872 seconds. Native Intel macOS execution and the
candidate's CI result remain pending.


### SV8.54 — 36 native contracts across nine open areas (2026-10-15)

No whole migration topic is complete, so this package retains four advances
in each of all nine topics. It starts from `74881ce`; its CI result is pending.
The checks below represent implemented bounded contracts, not whole-area closure.

#### SV8.54 Frontend

- [x] Decode backspace escapes consistently in native byte characters and strings.
- [x] Decode form-feed escapes consistently in native byte characters and strings.
- [x] Decode vertical-tab escapes consistently in native byte characters and strings.
- [x] Reject unknown string escapes instead of silently removing their backslash.

Gate: `test_sotlas_native_migration_sv854`.

#### SV8.54 Native ownership

- [x] Join a nested mixed then-branch with another closed loop exit using separate edge states.
- [x] Join a nested mixed else-branch without losing the continuing owner snapshot.
- [x] Accept closed nested break/continue paths inside match arms while checking moves.
- [x] Preserve sibling break summaries across nested match evaluation.

Gate: `test_sotlas_native_migration_sv854`.

#### SV8.54 Sotlas memory runtime

- [x] Allocate cleared arena arrays after checking count/stride multiplication.
- [x] Query whether a range lies within the allocated arena cursor.
- [x] Grow a known last allocation in place while checking capacity and address wrap.
- [x] Shrink a known last allocation and invalidate outstanding arena marks.

Gate: `test_sotlas_native_migration_sv854`.

#### SV8.54 States, effects, authority and contracts

- [x] Execute a checked U64 addition contract without publishing overflowed output.
- [x] Execute a checked U64 subtraction contract without publishing underflowed output.
- [x] Execute a checked U64 multiplication contract with zero/division guards.
- [x] Execute checked power-of-two alignment without wraparound or partial output.

Gate: `test_sotlas_native_migration_sv854`.

#### SV8.54 Native IR and lowering

- [x] Reject unrelated symbol, immediate, flag and branch metadata on phi instructions.
- [x] Reject unrelated symbol, flag and edge metadata on loads.
- [x] Reject unrelated symbol, flag and edge metadata on stores.
- [x] Reject unrelated metadata on integer/float/numeric casts and float negation.

Gate: `test_sotlas_native_migration_sv854`.

#### SV8.54 Owned backend and ABI

- [x] Reject U8 immediates containing bits above the declared byte width.
- [x] Require an eight-bit two-complement immediate representation for I8.
- [x] Reject U16 immediates containing bits above the declared halfword width.
- [x] Require a sixteen-bit two-complement immediate representation for I16.

Gate: `test_sotlas_native_migration_sv854`.

#### SV8.54 Owned objects and linking

- [x] Reject nonzero entry addresses in ELF relocatable headers.
- [x] Reject reserved object flags while preserving the internal Linux/Darwin operation bits.
- [x] Validate every section name inside the section-name string table.
- [x] Bound the symbol local/nonlocal boundary field to its symbol table.

Gate: `test_sotlas_native_tool_operations_sv854`.

#### SV8.54 Native CLI

- [x] Check independent source paths from a bounded manifest with --check-list.
- [x] Validate objects from a manifest with --verify-object-list.
- [x] Resolve the requested entry in every listed object without images using --check-entry-list.
- [x] Link listed objects through the owned ELF linker using --link-elf-list.

Gate: `test_sotlas_native_tool_operations_sv854`.

#### SV8.54 Bootstrap and self-hosting

- [x] Compare listed artifacts using --compare-list without premature success output.
- [x] Validate all listed seed envelopes using --verify-seed-list.
- [x] Create an exclusive stamp of an ordered seed set using --stamp-seed-set.
- [x] Reject changed content, ordering, count or stamp metadata using --verify-seed-set.

Gate: `test_sotlas_native_tool_operations_sv854`.

Nested ownership joins represent closed break/continue exits, including
mixed exits in nested if/match branches. Continue edges preserve the incoming
exclusive POD owner; break edges are merged separately and can make owners
maybe-moved after a loop. Return/jump/fallthrough mixtures and arbitrary CFG
ownership remain open. The earlier mixed-match rejection fixture now consumes
the owner on its break edge; a separate positive gate covers the newly accepted
live-owner case. Move safety remains checked in both fixtures.

Arena contains is a range/cursor query, not a lifetime or allocation identity
proof. Grow/shrink require the caller to supply the actual last allocation and
its true old size. Grow preserves existing bytes but does not clear new bytes;
shrink invalidates marks and requires disuse of its truncated suffix. These
remain explicit single-threaded primitives. Arithmetic guards are explicit
runtime contracts, not migration of full canonical contract/effect syntax.

IR load/store immediates retain their existing storage semantics; unrelated
symbol/flag/edge fields are rejected. Narrow machine immediates use low-width
two-complement patterns. ELF preflight preserves internal OS flag bits 0/1.
The symbol boundary is checked for range; the legacy internal function/data
ordering is retained. Standard external ELF local-symbol ordering remains open.

Manifest commands share a 65,535-byte text budget, 16 paths and a 4,095-byte
path limit. Empty lines and whole-line # comments are ignored, horizontal
whitespace at path edges is trimmed, and LF/CRLF are accepted. Embedded NUL,
empty lists, oversize input and excess paths are rejected. Paths are relative
to the process working directory. There is no shell expansion or quote syntax.
Independent check inputs are not merged. ELF list linking retains the existing
8 MiB object and 16 MiB image limits. Entry-list checking uses the host image
linker in memory, with success reported after every object passes.

Seed-set stamps are 32-byte SOTSET01 records. They hold FNV-1a over fixed-size
records of each seed's content fingerprint and byte size in list order, total
bytes, count, version and zero reserved bytes. Each seed must pass the host
platform envelope gate. Stamps are reproducibility evidence, not authentication
or proof of full compiler parity; identical bytes at different paths are the
same artifact for this purpose. Files must remain stable while a command runs.
Existing stamp files cannot be overwritten. A failed new-file write can leave
a partial file. General package manifests, typed interfaces and distribution
remain separate requirements.

Final local validation: 3,082 Windows regression tests passed with 79
platform/toolchain skips in 855.727 seconds. All 36 new gates passed on Linux
through WSL (35.147 seconds) and Windows Python 3.10.11 (29.201 seconds).
The strengthened seed-order check also passed separately on Windows and Linux.
All 137 existing native frontend closure gates passed. Original-source Stage
2/3 identity passed on Windows in the full suite and Linux in a separate gate;
complete Darwin compiler cross-generation passed on both hosts. The two Linux
generation gates took 89.806 seconds. Native Intel macOS execution and the
candidate's CI result remain pending.


### SV8.53 — 36 native migration contracts (2026-10-14)

Based on `7c42ad7`, this package implements four bounded contracts in each of
the nine migration areas. These checks record implementation and local gates;
the candidate still requires its own CI result. Full parent areas remain open.

#### SV8.53 Frontend

- [x] Decode exactly two hexadecimal digits in byte character escapes, including values above ASCII.
- [x] Decode checked hexadecimal, binary and octal dimensions for local scalar arrays.
- [x] Compare array repeat lengths numerically across radices and separators.
- [x] Preserve scalar record-array layout and exclusive POD checks with radix dimensions.

Gate: `test_sotlas_native_migration_sv853`.

#### SV8.53 Native ownership primitives

- [x] Retain multiple local strong references with an overflow check before mutation.
- [x] Release multiple references with distinct invalid, retained and final-destruction statuses.
- [x] Observe whether a weak token is current without acquiring a strong reference.
- [x] Observe whether a live local control block has exactly one strong reference.

Gate: `test_sotlas_native_migration_sv853`.

#### SV8.53 Sotlas memory runtime

- [x] Fill a byte range after checking null and address wraparound.
- [x] Compare byte ranges with explicit empty, null and wraparound behavior.
- [x] Query remaining arena capacity while rejecting invalid cursor state.
- [x] Reset an arena by clearing used bytes and invalidating old marks.

Gate: `test_sotlas_native_migration_sv853`.

#### SV8.53 Authority and state guards

- [x] Capture an authority token bound to its owner, generation and required rights.
- [x] Check a captured token against current owner state after revocation.
- [x] Delegate a narrower token while rejecting widening and stale grants.
- [x] Guard a state transition with a current token and destination mask.

Gate: `test_sotlas_native_migration_sv853`.

#### SV8.53 Native IR and lowering

- [x] Reject hidden symbol and unrelated edge metadata on integer constants.
- [x] Reject reserved flags and unrelated edge metadata on floating constants.
- [x] Reject hidden immediate, symbol, flag and phi metadata on return instructions.
- [x] Reject unrelated flag, immediate, symbol and phi metadata on branch instructions.

Gate: `test_sotlas_native_migration_sv853`.

#### SV8.53 Owned backend and ABI

- [x] Sign-extend i8 pointer offsets to machine width before scaling.
- [x] Sign-extend i16 pointer offsets to machine width before scaling.
- [x] Zero-extend u8 pointer offsets before scaling and subtraction.
- [x] Zero-extend u16 pointer offsets before scaling and subtraction.

Gate: `test_sotlas_native_migration_sv853`.

#### SV8.53 Owned objects and linking

- [x] Reject relocation kinds outside the owned ELF relocation contract during preflight.
- [x] Reject relocation symbol indices outside the linked symbol table.
- [x] Check the complete relocation patch width against the destination section.
- [x] Reject relocation destinations that are not program or zero-fill sections.

Gate: `test_sotlas_native_tool_operations_sv853`.

#### SV8.53 Native CLI

- [x] Validate up to 16 ELF inputs with --verify-objects and defer batch success output.
- [x] Check up to 16 independent sources with --check-many without merging or output files.
- [x] Report validated section, symbol and relocation counts with --object-info.
- [x] Resolve a single object entry in memory with --check-object-entry without writing an image.

Gate: `test_sotlas_native_tool_operations_sv853`.

#### SV8.53 Bootstrap and self-hosting tools

- [x] Compare 2–16 artifacts with --compare-many and reject late mismatches without success output.
- [x] Validate 1–16 native seed envelopes with --verify-seeds before reporting success.
- [x] Validate 1–16 seed/stamp pairs with --verify-stamps before reporting success.
- [x] Copy a bounded native seed byte-for-byte into a new exclusive executable file with --copy-seed.

Gate: `test_sotlas_native_tool_operations_sv853`.

The frontend uses checked numeric decoding for bounded array shapes. It does
not evaluate general constant expressions in type dimensions. Local limits
remain 4,096 scalar elements; scalar record fields remain at most 256 elements.
Character hex escapes encode one byte, not Unicode. Raw non-ASCII characters
remain rejected. The shared numeric decoder also corrects radix count/index
interpretation in lowering.

The runtime APIs remain explicit, local and non-atomic. Reference observation
does not establish a borrow lifetime or acquire ownership. Final batch release
authorizes one caller-managed destruction. Control blocks, authority owners
and backing memory must stay alive; public record fields are not unforgeable
security capabilities. Memory equality is not constant-time. Arena reset
requires proof by the caller that discarded pointers are no longer used.

IR preflight now rejects unrelated metadata on constants and control transfers.
ELF preflight checks relocation types 1/2/4/10/11, symbol indices, destination
kinds and patch extents. It does not resolve foreign symbols, prove addend
representability in a final layout or support every external ELF producer.

Batch commands fail at the first invalid input and emit one success report only
after all inputs pass. Check-many validates independent files; imports do not
become separately compiled typed interfaces. Object-info prints three U64 hex
lines: section count, symbol count (including the null symbol), relocation count.
Check-object-entry uses the host image linker in memory. Copy-seed accepts an
input of at most 8 MiB, validates its platform envelope and refuses existing
outputs, including the input itself. It does not authenticate the seed. Files
must remain stable during validation and copying. Write failures can leave a
partial newly created file.

Final local validation: 3,046 Windows regression tests passed with 79
platform/toolchain skips in 815.285 seconds. All 36 new gates also passed on
Linux through WSL (31.734 seconds) and Windows Python 3.10.11 (26.873 seconds).
Original-source Stage 2/3 identity passed on Windows in the full suite and on
Linux in a separate generation gate. Complete Darwin compiler cross-generation
also passed; the two Linux generation gates took 87.997 seconds. Native Intel
macOS execution and the candidate's CI result remain pending.


### SV8.52 — independently compiled ELF objects (2026-10-14)

The native Linux, Windows and Darwin drivers now provide
`--link-elf-objects OUTPUT ENTRY INPUT.o...`. It always produces an x86-64 Linux
ELF executable, including when invoked on Windows or Darwin. It accepts 1–16
ELF relocatable inputs, with an 8 MiB combined input budget and a 16 MiB image
buffer. All inputs are loaded and structurally validated before output I/O.
The existing owned linker resolves calls across objects and rejects duplicate
definitions, unresolved calls and missing entry points.

- [x] Load and link bounded, independently compiled objects through a native CLI.
- [x] Resolve cross-object calls with either input ordering.
- [x] Reject malformed/missing inputs, duplicate symbols and unresolved calls
  before replacing an existing output.
- [x] Enforce object count, entry and combined input capacity bounds.
- [x] Emit reproducible images for a fixed input order, including a single input.
- [ ] Complete separate module compilation, typed interface metadata and package
  dependency resolution without source concatenation.
- [ ] Extend multi-object CLI linking to owned PE and Mach-O images.

Gate: `test_sotlas_native_multi_object_cli`. This bounded operation does not
establish general ELF compatibility or whole-language ABI parity. The output
uses the existing hosted Linux entry contract; it is not a barecore kernel image.
Local validation: all seven new gates passed on Windows (Python 3.10.11)
and Linux through WSL. The previous 17 CLI/bootstrap gates also passed.
The final Target IR and native CLI regression run passed 40 tests.
Original-source Stage 2/3 identity passed on Windows and Linux; complete Darwin
compiler cross-generation passed on Linux. Native Intel macOS execution and
the new candidate's CI result remain pending.



### SV8.51 — the next 36 native migration contracts (2026-10-14)

Starting from `3e4320e`, this package adds four bounded contracts in each of the
nine migration areas. These are executable native advances, not closure of the
parent migration requirements. The runtime remains explicit and single-threaded.

| Area | Four new contracts | Gate |
|---|---|---|
| Frontend | Hexadecimal integer values lower natively; binary integer values; octal integer values; ASCII byte character values with supported escapes | `test_sotlas_native_migration_sv851` |
| Native ownership primitives | Capture a weak token bound to its control block; upgrade through that token; recycle a released header with generation advancement; distinguish invalid, retained and final releases | `test_sotlas_native_migration_sv851` |
| Sotlas memory runtime | Allocate cleared arena storage; copy non-overlapping memory with checked arithmetic; move overlapping memory in either direction; clear discarded bytes during checked rewind | `test_sotlas_native_migration_sv851` |
| Authority/state/effect guards | Initialize an authority mask/generation; revoke bits with generation advancement; reject stale authority observations; guard a destination state mask with current authority | `test_sotlas_native_migration_sv851` |
| Native IR | Reject unknown opcode IDs; reject reserved function flag bits; reject reserved value flag bits while preserving domains; reject noncanonical PointerCast metadata | `test_sotlas_native_migration_sv851` |
| Owned backend/ABI | Sign-extend i32 pointer offsets before scaling; handle i64 pointer offsets; handle the native isize source alias; lower unsigned 64-bit literal addresses only under unsafe | `test_sotlas_native_migration_sv851` |
| Owned objects/linking | Bound symbol names to their own string table; reject unsupported bindings; reject indirect-function/TLS types and reserved visibility bits; bound defined symbol extents to their section | `test_sotlas_native_migration_sv851` |
| Native CLI | Check explicit projects without output; check dependency-resolved explicit projects without output; validate ELF object structure/symbols; link an existing object with the owned platform linker | `test_sotlas_native_tool_operations_sv851` |
| Bootstrap tools | Compare three artifacts without premature success output; create an exclusive seed stamp; verify stamp content/size/platform/version; report seed fingerprint and exact size | `test_sotlas_native_tool_operations_sv851` |

Radix values use checked U64 decoding and contextual signed/unsigned limits.
Hex values execute in scalar constants, array values and match patterns as well
as ordinary expressions. Binary/octal prefixes accept upper/lowercase forms and
digit separators; missing digits, invalid digits and overflow are rejected.
Character values are ASCII bytes, including \0, \n, \r, \t, escaped quote,
double quote and backslash. Unicode scalars, extended escapes, numeric suffixes
and radix expressions in array type dimensions remain separate requirements.

Weak tokens carry a stable control-block pointer and generation. Released
headers may be recycled through the new API while old tokens remain, provided
their storage remains valid. Recycling advances the generation and rejects
live, zero-generation and saturated headers. Direct reinitialization or forgery
of public token/header fields is outside the API contract. No keyword-level
stored `whisper`, atomic ARC or automatic destruction is introduced here.

Memory callers provide valid backing ranges. Copy rejects overlap; move handles
overlap. Checked arithmetic never proves that physical addresses are mapped.
Clearing rewind validates the mark before writes; it is not a DMA/security
erasure guarantee. Authority generations invalidate old observations after
revocation, including observations for other remaining bits. State masks are
bounded to 64 destinations. These remain explicit guards rather than complete
canonical state/effect/authority syntax migration.

Object validation checks ELF structure and symbols; it does not resolve foreign
symbols, certify every relocation or guarantee linking. `--link-object` resolves
with the platform's owned linker and preserves an existing output when input,
entry or linking is rejected before output I/O.

Seed stamps contain a 32-byte SOTSEED1 record with FNV-1a-64, size, platform and
format version. Creation requires a new file, so existing artifacts and seed
aliases cannot be overwritten. Verification rejects changed content, sizes,
platforms, versions, reserved bytes and truncation. FNV does not authenticate a
seed or replace a cryptographic signature. Three-artifact comparison proves byte
identity of supplied artifacts, not full-language bootstrap parity.

Final local validation passed 3,003 Windows regression tests with 79
platform/toolchain skips in 969.761 seconds. All 36 new gates passed on Windows,
Linux through WSL and Windows Python 3.10.11. The combined frontend/CLI/migration
run passed 182 tests. Linux original-source Stage 2/3 identity and complete Darwin
compiler cross-generation passed in 125.815 seconds; Windows Stage 2/3 passed in
the full suite. Native Intel macOS execution remains a CI gate. CI certification
was reported green by the repository owner for `24d5627`. The run number was
not independently inspected in this update; full migration parents stay open.


### Implemented contracts from the green SV8.51 baseline

The following checks refer to the bounded contracts in `24d5627`, not to
completion of their parent migration areas. Gates are listed above.

#### Frontend

- [x] Hexadecimal integer values lower natively.
- [x] binary integer values.
- [x] octal integer values.
- [x] ASCII byte character values with supported escapes.

#### Native ownership primitives

- [x] Capture a weak token bound to its control block.
- [x] upgrade through that token.
- [x] recycle a released header with generation advancement.
- [x] distinguish invalid, retained and final releases.

#### Sotlas memory runtime

- [x] Allocate cleared arena storage.
- [x] copy non-overlapping memory with checked arithmetic.
- [x] move overlapping memory in either direction.
- [x] clear discarded bytes during checked rewind.

#### Authority/state/effect guards

- [x] Initialize an authority mask/generation.
- [x] revoke bits with generation advancement.
- [x] reject stale authority observations.
- [x] guard a destination state mask with current authority.

#### Native IR

- [x] Reject unknown opcode IDs.
- [x] reject reserved function flag bits.
- [x] reject reserved value flag bits while preserving domains.
- [x] reject noncanonical PointerCast metadata.

#### Owned backend/ABI

- [x] Sign-extend i32 pointer offsets before scaling.
- [x] handle i64 pointer offsets.
- [x] handle the native isize source alias.
- [x] lower unsigned 64-bit literal addresses only under unsafe.

#### Owned objects/linking

- [x] Bound symbol names to their own string table.
- [x] reject unsupported bindings.
- [x] reject indirect-function/TLS types and reserved visibility bits.
- [x] bound defined symbol extents to their section.

#### Native CLI

- [x] Check explicit projects without output.
- [x] check dependency-resolved explicit projects without output.
- [x] validate ELF object structure/symbols.
- [x] link an existing object with the owned platform linker.

#### Bootstrap tools

- [x] Compare three artifacts without premature success output.
- [x] create an exclusive seed stamp.
- [x] verify stamp content/size/platform/version.
- [x] report seed fingerprint and exact size.

### SV8.50 — four advances in each migration area (2026-10-14)

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

### Implemented SV8.50 contracts retained in the current baseline

#### SV8.50 Frontend

- [x] Nested block comments.
- [x] numeric separator/radix-prefix validation.
- [x] string line-break rejection, including escaped breaks.
- [x] source NUL rejection inside code/comments/literals.

#### SV8.50 Native ownership primitives

- [x] Initialize a local strong control block.
- [x] checked retain.
- [x] final release authorizes one destruction.
- [x] generation-checked weak upgrade acquires a strong reference.

#### SV8.50 Sotlas memory runtime

- [x] Initialize a caller-backed arena.
- [x] allocate with actual-address alignment and checked capacity.
- [x] capture an arena-specific mark.
- [x] rewind with epoch invalidation and unchanged state on failure.

#### SV8.50 State/effect/authority/contract guards

- [x] Check all required authority bits.
- [x] delegate only a subset.
- [x] guard a state transition with expected state and authority.
- [x] validate a range without overflow.

#### SV8.50 Native IR/lowering

- [x] Reject invalid/void SSA value types.
- [x] reject unrecognized ownership IDs.
- [x] distinguish parameter/value and return type sets.
- [x] validate function/parameter/value source spans before call-aware emission.

#### SV8.50 Owned backend/ABI

- [x] Pointer/U64 roundtrip.
- [x] pointer/usize roundtrip and usize pointer offsets.
- [x] require unsafe for address conversions.
- [x] reject narrowing/signed/float address conversions.

#### SV8.50 Owned objects/linking

- [x] Validate ELF version/header envelope.
- [x] reject a nonempty undefined section.
- [x] validate the section-name table.
- [x] reject a forged undefined symbol.

#### SV8.50 Native CLI

- [x] `--version` reports contract versions.
- [x] `--limits` reports bounds.
- [x] `--target` reports the platform and ABI limits.
- [x] `--exit-codes` reports the error contract.

#### SV8.50 Bootstrap tooling

- [x] Stream byte comparison.
- [x] stream FNV-1a fingerprints.
- [x] check the native seed platform/architecture envelope.
- [x] self-test frontend, typed IR and owned object emission.

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
  - [x] Execute native scalar/Boolean/scalar-enum match statements with single evaluation, typed patterns and a mandatory final wildcard.
  - [x] Reject duplicate patterns, incompatible enum variants, missing coverage, scope leaks and exhausted arm tables.
  - [x] Integrate nested selection, record returns, lexical defer and exclusive live-path state merges into the structured CFG.
  - [x] Prove wildcard-free Boolean and scalar-enum coverage, preserve nominal enum constant patterns and reject missing discriminants.
  - [x] Trap invalid raw selector representations before dispatch in wildcard-free matches.
  - [x] Execute bounded inclusive/exclusive integer ranges with overlap rejection and complete integer-domain coverage proofs; validate signed/unsigned extrema, cleanup and supported ownership paths.
  - [x] Execute native Boolean match guards with pattern-hit-only evaluation, lazy conditions, false fallthrough, unguarded coverage proofs and supported POD ownership preservation.
  - [x] Execute exhaustive scalar match expressions with ordered guards/ranges, single subject evaluation and lazy selected arm values.
  - [x] Execute open integer ranges, scoped subject bindings, nominal enum results, POD record copies and arm value blocks with LIFO/early-return cleanup.
  - [ ] Complete payload-enum patterns/bindings, resource-bearing results and ownership-bearing match expressions.
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
  - [x] Execute pointer-free record array fields with nominal element typing, independent copies, nested indexing and supported internal container transfers.
  - [ ] Complete slices, aggregate array parameters/returns, non-POD record array fields and remaining array forms.
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
  - [x] Serialize static pointer-free records, nested records and scalar/record array fields with deterministic padding and bounded typed constant evaluation.
  - [x] Initialize global pointer-free record arrays from exact typed lists/repetition and execute checked element operations.
  - [ ] Complete remaining aggregate forms, strings, pointer relocations and resource initializers.
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


### SV8.47 — four bounded frontend cuts (2026-10-13)

- [x] **Symbols/scope:** identify parameter and preceding lexical-local bindings while checking effects of transitive native AST helper calls; unproven global/out-of-scope references fail closed.
- [x] **Methods/calls:** resolve internal instance/static helper call targets using the typed native call AST, evaluating receiver and argument nodes rather than mistaking callee names for local bindings.
- [x] **Expression acceptance:** reject unsafe, mutable assignment, assembly, trap, unknown call, nonterminating loop and unsupported effect-bearing forms in owned deferred argument evaluation.
- [x] **Diagnostics:** emit a source-positioned dedicated deferred-argument-effect cause consistently in the three Sotlas-native file drivers, preserving existing output artifacts.

These items are partial refinements of open parent migration contracts, not complete symbol parity, general expression typing or canonical diagnostic parity.

## Ownership, states, effects and cleanup

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


### SV8.47 — four bounded ownership cuts (2026-10-13)

- [x] Trace **indexed array projections** to the owner for direct/whisper borrow masks, rather than treating indexed values as independent storage.
- [x] Trace **conditional guard operands**, in addition to selected arms, to their owner before deciding whether a call borrows an owner.
- [x] Reject **borrow/consume overlap in the same native call**, including borrowed array-field indexes and conditionally computed scalar arguments; fail closed for unknown owner-bearing expression forms.
- [x] Preserve **projected defer owner reservations** through lexical cleanup and allow ownership transfer after the enclosing scope exits, without ARC/drop or stored weak references.

The complete alias graph, retained borrows, general lifetimes and resource cleanup remain open.

## New acceptance evidence

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

## Remaining limits

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
