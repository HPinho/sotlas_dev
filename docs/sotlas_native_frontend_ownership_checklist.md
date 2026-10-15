# Native frontend and ownership closure

Repository: [HPinho/sotlas_dev](https://github.com/HPinho/sotlas_dev).

This checklist tracks migration of the contracted canonical language into the
Sotlas-written compiler. A working bootstrap profile does not establish full
language parity. Parent items stay open until every contracted form has native
positive, negative and execution coverage. Subitems record smaller validated
contracts. Local validation must pass CI before being called certified.

## Frontend parity

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
