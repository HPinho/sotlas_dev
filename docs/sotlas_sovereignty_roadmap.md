# Sotlas Sovereignty Roadmap

**Status:** active implementation track  
**Started:** 2026-10-03 (America/Fortaleza)  
**Green baseline at track start:** `7162167dec6fd5fa0a216121b147335d222e43f1` / CI #1063  
**Latest inspected green baseline:** `013f8e5faf1d0986ff23f77c4bab4f9c0644bd55` / [CI #1261](https://github.com/HPinho/sotlas_dev/actions/runs/39085692941).



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

## SV8.82 - nested variants and refutable payload fields (2026-10-20)

**Starting baseline:** `44e5958` on main.
The native parser now parses positional patterns recursively with a depth bound
of 32. Field patterns accept bindings, wildcards, integer/Boolean literals,
module constants, integer ranges, scalar enum variants and nested variants.
Semantic lookup preserves each binding's declared field type and rejects scope
leaks, duplicate names across nested siblings, wrong variants/arity and invalid
field patterns. Lowering tests each nested tag before its fields, then runs the
guard only if every field matched. Failed fields/guards continue in source order.
Aggregate subjects are snapshotted once before dispatch; returned POD records,
exclusive captures, early returns and LIFO cleanup retain their existing rules.

At SV8.82, coverage was conservative (superseded by SV8.83): refutable fields did not prove coverage of an entire
variant. A total variant fallback or final wildcard is required. General product
coverage, named-field/or-patterns and resource ARC/drop integration remain open;
this is not a claim of complete master match parity.

**Local evidence:** 298 focused compatibility/frontend/IR/documentation tests
passed, including all earlier C11 diagnostic regression gates. Native Windows
and Linux/WSL rebuilt the compiler from original sources without host build tools
on PATH and proved Stage 2/3 byte identity. Each rebuilt compiler passed 96 match
tests and all 35 shared Stage 3 cases, including located diagnostics and output
preservation on rejection. The expanded example ran with exit 42 on both hosts;
its object, ELF, PE and Mach-O bytes matched across hosts. Intel macOS execution
and the new CI run remain unverified locally. See [the payload contract](native_match_payloads.md).

## SV8.81 - native payload matching and exclusive expression joins (2026-10-19)

### Compatibility repair after CI #1275

The matrix exposed four failures, reproduced locally before repair. The native
C11 emitter now locates its unsupported-payload error at the payload delimiter,
and the diagnostic API copies that position into its caller-provided outputs.
Scalar enum paths retain the pre-existing U32 discriminant contract; only payload
enum paths request aggregate inference. The obsolete native scalar-payload
rejection test now requires execution and retains a pointer-payload rejection.
A combined scalar/payload inference case protects the compatibility boundary.

The formerly failing cases pass. The broader frontend/Target IR/SV2 run passed
199 tests. Final native Windows and Linux rebuilds proved Stage 2/3 byte identity;
each rebuilt compiler passed 80 match tests and all 33 shared Stage 3 cases.
This is local validation; certification by the replacement CI run remains pending.

CI #1276 reduced the matrix failure set to one stale diagnostic expectation:
the nonzero-array C11 refusal test still required an unlocated error after the
API began returning emitter positions. The gate now requires zero output and
the exact declaration position, line 3 column 5. The failure was reproduced
locally; all 58 tests in the struct semantic, aggregate parser and compiler
self-host diagnostic modules then passed. The replacement CI remains pending.

**Starting baseline:** `9926e37`, reported green by the repository owner.
The native parser accepts positional payload declarations and variant patterns.
Sotlas lowering constructs a tagged aggregate, zeroes inactive storage and copies
POD payload values independently. Internal calls/returns and match results retain
the aggregate ABI. Bindings are immutable and scoped to the selected arm/guard;
coverage checks ignore guarded variants and reject nominal or arity mismatches.

Expression match ownership now analyzes arms independently, merges live exclusive
POD move states and retains deferred-borrow reservations. Value blocks support
owned yields, early returns and cleanup; consuming guards and maybe-moved reads
remain errors. POD checks include nominal enums, and native inference preserves
the enum identity of constructor locals. The expanded public example combines
these paths without C emission.

**Local evidence:** the 247-test focused match/frontend/IR/documentation run
passed; the final inference case and two ownership edge cases also passed.
The latest frontend/Target IR run passed 153 tests. Windows and Linux/WSL native
seeds rebuilt the final compiler sources with host build tools absent from PATH
and proved Stage 2/3 byte identity. Each rebuilt compiler passed 79 match tests
and all 33 shared Stage 3 cases, including located diagnostics and preservation
of an existing executable on rejection. A parser regression involving dynamic
range endpoints was caught and corrected by this shared gate before the commit.
The example executed with exit 42 on Windows and Linux. Its object, ELF, PE and
Mach-O bytes matched across both hosts; Intel macOS execution still requires CI.

The [payload contract](native_match_payloads.md) records executable boundaries.
Resource fields, integrated ARC/drop generation, recursive/refutable field
patterns and complete canonical frontend parity remain open. This package does
not label the entire master language or sovereignty track complete.

## SV8.80 - native POD match release profile (2026-10-19)

**Starting baseline:** `8bdfdc4`, reported green by the repository owner.
This package closes the documented [POD match release profile](native_match_release_profile.md):
scoped immutable subject bindings, closed/open integer ranges, nominal
payload-free enum and independent POD record results, and arm value blocks.
Blocks support locals, ordinary structured statements, tail values and enclosing
function returns. A tail is captured/copied before LIFO defer cleanup; early
return executes enclosing cleanup. Pattern constants retain their existing
meaning and bindings cannot escape an arm. Scalar/POD results remain lazy.

Enum arm/destination identity is checked across typed lets, returns, assignments
and internal calls. Record results retain nominal layout and independent nested
field/array storage. Missing values, mismatched types, invalid intervals, overlap,
immutable writes and capacity exhaustion fail closed. Lexical ownership lookup
distinguishes an arm binding from a shadowed outer owner. Owned captures/call
results, pointer/resource record values and payload enums remain explicit
exclusions rather than being erased during lowering.

**Local evidence:** 196 focused match/frontend/Target IR tests passed before the
final local-capacity guard; the final 25 closure tests also passed. Windows and
Linux/WSL rebuilt original compiler sources from native seeds with host build
tools absent from PATH and proved Stage 2/3 byte identity. Each final compiler
passed 44 match-value/closure tests and all 30 shared native Stage 3 cases.
The shared cases verify diagnostics/status and preserve an existing executable
on rejection, including local-capacity exhaustion returning lowering error 7.
They are wired into the existing Stage 3 CI scripts. Test sets overlap.

Both hosts emitted identical object/ELF/PE/Mach-O bytes for the expanded example;
ELF executed on Linux and PE on Windows with status 42. The 18 reality/phase-audit
tests passed locally. Actual Intel macOS execution and new remote CI certification
remain pending. The master match item is still open for payload enums/patterns
and ownership-bearing values; this release profile does not mark those complete.

## SV8.79 - scalar match expressions (2026-10-19)

**Starting baseline:** `cccadd7`, reported green by the repository owner.
The Sotlas-written AST/parser now represents match values explicitly. Native
lowering reuses the existing statement-match decision chain, ordered guards,
ranges, enum/Boolean validity guards and exhaustive coverage checks. The subject
is evaluated once; only eligible guards and the selected value execute. Every
arm is typed/lowered before emission. Selected scalar results store into shared
storage before the join load, using existing Target IR and backend operations.

Integer, Boolean and float results work in lets, returns, call arguments,
assignments, calculations, Boolean conditions, loops and deferred call arguments.
Match values can nest. The first known arm type/Boolean literal provides bounded
inference; explicit context types select signed/narrow/float literal results.
Arms are comma-separated expressions with the existing 64-arm limit. Aggregate,
pointer and enum results, statement blocks, owned captures and owned call results
are rejected. General ownership-bearing/payload matching remains separate work.
See the [contract](native_match_values.md) and
[classification example](../examples/native_match_values/README.md).

**Local evidence:** 19 focused feature tests and 171 existing frontend/Target IR/
reality/phase-audit tests passed; the example manifest also passed. Windows and
Linux/WSL rebuilt the original compiler sources from native seeds with host tools
absent from PATH and proved Stage 2/3 byte identity. Each final rebuilt compiler
passed 39 match-value/static-record tests, including the owned-call rejection.
The example produced identical object/ELF/PE/Mach-O bytes across the two hosts;
ELF executed on Linux and PE on Windows with status 42. Test sets overlap. Intel
macOS execution and new remote CI certification remain pending.

## SV8.78 - initialized global record tables (2026-10-19)

**Starting baseline:** `8d8f0b5`, reported green by the repository owner.
The Sotlas-written compiler now accepts global pointer-free record arrays with
constant element lists/repetition. Serialization reuses native padded layout and
the existing bounded initializer pool. Nested records, scalar/record array fields
and typed scalar constants produce data/BSS directly, without C initializers or
runtime constructors. Explicit initialized tables accept 1-256 entries and share
the 4,096-entry pool, one entry per serialized byte including padding.

The native CFG now resolves these table elements through checked addresses with
actual element stride. It supports field reads/mutation, whole-element writes,
independent element copies/returns and supported internal borrows. Literal bounds,
dynamic traps, immutability, lexical shadowing and nominal types remain checked.
Pointer/resource-bearing tables and runtime initializers remain excluded from
this new direct-access/initialized profile. The compiler's existing larger `=0`
storage arrays are preserved. See the [table contract](native_static_tables.md)
and [command dispatch example](../examples/static_dispatch/README.md).

**Local evidence:** Windows and Linux/WSL rebuilt the original compiler sources
from native seeds, with host tools absent from PATH, and proved Stage 2/3 byte
identity. The focused frontend/Target IR/static suites passed 192 tests; the
18 reality/phase-audit tests and example manifest also passed locally. Test sets
overlap. Each rebuilt compiler passed 39 static-table/static-record tests,
including original-source execution, raw object padding/BSS checks, exact byte
and element limits, independent copies and a dynamic bounds trap. Both compilers
emitted identical object/ELF/PE/Mach-O bytes for the dispatch example; ELF ran on
Linux and PE on Windows with status 42. Intel macOS execution and new remote CI
certification remain pending.

The old negative single-record initializer is now positively executed; its
negative slot tests a pointer-bearing record. Remaining slices, resource storage,
whole-array assignment and aggregate array ABI are still open parent work.

## SV8.77 - native static record configurations (2026-10-18)

**Starting baseline:** `da05329`, reported green by the repository owner.
The Sotlas-written lowerer now folds static record literals into initialized
object data. Pointer-free nested records and scalar/record array fields retain
their actual padded layout. Scalar constants reuse the existing typed evaluator;
named fields can appear in any order. Padding is zero and all-zero records use
BSS. No runtime constructor or C initializer is introduced.

Native expressions resolve global record layouts through lexical bindings,
preserving scalar/record name shadowing. Supported code reads, copies, returns,
borrows and mutates explicitly mutable static configurations, including nested
arrays and whole-record replacement. Immutable mutation, runtime calls in
initializers, pointer/resource payloads, invalid field/type/count combinations
and initializer-pool exhaustion are rejected. Serialization uses the existing
4,096-entry pool, one entry per record byte, with depth 32. See the
[contract](native_static_records.md) and
[configuration example](../examples/static_config/README.md).

**Local evidence:** the frontend/Target IR/array/static suites passed 184 tests
before six additional static-data/example gates were added. Both Windows and
Linux/WSL then rebuilt the original compiler sources using native seeds with
host tools absent from PATH and proved Stage 2/3 byte identity. Each rebuilt
compiler passed the final 38 static-record/record-array gates. These include
exact pool capacity, raw object padding/data/BSS checks and source execution.
The configuration example emitted all three executable formats on both hosts;
PE ran on Windows and ELF on Linux with status 42. Actual Intel macOS execution
and new remote CI certification remain pending. Test sets overlap.

The initializer parent item remains open for other aggregates, string/pointer
relocations and resource-bearing storage. This delivery changes native Sotlas
implementation and tests; it does not remove the hosted Stage-0 reference.

## SV8.76.1 - public snippet inventory repair (2026-10-18)

[CI #1268](https://github.com/HPinho/sotlas_dev/actions/runs/39177099085/job/117821904507)
passed the C11 example compilation step, then failed the documentation reality
gate: `native_record_array_fields.md` contained a Sotlas fence without an entry
in `public_snippets.json`. The new entry links the checked-in inventory source
and native execution tests. It follows the existing EXPERIMENTAL classification
for native-only examples; RUNNABLE specifically promises canonical Stage-0/C11
coverage. No test or acceptance rule is relaxed.

The 18 Windows reality/phase-audit tests and generated phase matrix check passed
locally. The full WSL reality suite could not complete because its hosted
bootstrap requires Clang, absent from that environment. New remote CI remains
pending. Compiler sources and the native array implementation are unchanged.

## SV8.76 - inline record array fields (2026-10-18)

**Starting baseline:** `be555e0`, reported green by the repository owner.
The Sotlas-written semantic checker and native lowering now accept fixed inline
arrays of pointer-free records inside structs. Lists, evaluate-once repetition,
compatible local/field copies, nested indexing/mutation, whole-element/field
replacement and supported enclosing-record returns/borrows produce native code.
Array list assignment stages its complete RHS before overwriting the field,
including element swaps. Record padding/alignment determines element stride.

Nominal type/count checks, runtime dynamic bounds and existing move/borrow
checks remain active. Pointer/resource-bearing elements, invalid literal indices,
oversized fields and overflowing record layouts are rejected. Fields are bounded
to 1-256 elements and 65,536 bytes; existing nesting/frame/IR limits also apply.
This does not add general slices, standalone array ABI, resource drop glue or
cross-module aggregate signatures. See the [contract](native_record_array_fields.md)
and executable [inventory example](../examples/record_table/README.md).

**Local evidence:** 18 focused new tests passed. The existing frontend-closure
and Target IR suites passed 153 tests before the final layout-overflow guard.
After that guard, both Windows and Linux/WSL rebuilt the compiler using native
seeds with host tools absent from PATH and proved Stage 2/3 byte identity. Each
final rebuilt compiler passed 25 positive, negative, native execution and bounds
trap tests, including the new oversized/overflowing layout regression. The
example manifest also passed. Test sets overlap. Intel macOS execution and new
remote CI certification remain pending; no workflow polling was done.

**Roadmap checkpoint:** [native delivery and preview status](native_roadmap_checkpoint.md).
The general arrays/slices parent item remains open. Python/C are not removed
from the reference/bootstrap/test environment by this delivery.

**Public preview delivery:** [six-block launch roadmap](preview_launch_roadmap.md),
including an initial Sotlas declarative UI and independently gated installation.

**P1 application candidate (2026-10-16):** a terminal calculator now exercises
native recursive expression parsing, `f64` arithmetic, bounded text formatting,
recoverable errors and OS I/O. Its Sotlas model regression and 12 CLI scenarios
passed on Windows and Linux/WSL with host tools absent from PATH. The existing
Stage 3 gates now include these application checks. Intel macOS execution and
remote CI are pending. See the [calculator contract](../examples/calculator/README.md).

**P2 Windows platform candidate (2026-10-16):** the native backend now resolves
loader imports and emits a Win64 scalar call bridge. The Sotlas window probe
passed local lifecycle, drawing, resize, posted input and GDI/USER resource
checks. A visible window rendered text and accepted updates. Both native
compiler fixed points passed; Linux/Windows emitted identical GUI PE bytes.
Four PE regression gates and the calculator gate passed. Full P2/P3 scope and
remote CI remain pending. See the [window contract](../examples/native_window/README.md).

**P3 first application (2026-10-16):** the graphical calculator now declares
23 components through a Sotlas UI model and renders with the native Windows
adapter. Model/layout gates passed on Windows and Linux/WSL; Windows drawing,
clip cleanup and a visible `7+8 = 15` interaction passed. The initial delivery
used ASCII labels, fixed layout and caller-owned storage. Native language parity,
complete P2/P3 coverage and remote CI remain open. See the
[application contract](../examples/graphical_calculator/README.md).

**P3 UTF-8 label candidate (2026-10-16):** a Sotlas runtime codec now validates
UTF-8 and preflights UTF-16 conversion. UI labels accept validated UTF-8 within
their byte limit, including supplementary scalars; calculator input remains
ASCII. Native tests passed on Windows and Linux/WSL; Windows mixed-script
drawing and cleanup passed. Encoding, layout/shaping and editing scopes remain
distinct; remote CI is pending. See the [text contract](native_unicode_text.md).

## SV8.75 — native source-list application and library builds (2026-10-18)

**Starting baseline:** `95183be`, reported green by the repository owner.
The native drivers now build complete applications and static libraries from
explicit source lists. `--build-library` compiles independent sources into an
archive; `--build-elf-modules`, `--build-pe-modules` and
`--build-macho-modules` compile roots, optionally load listed libraries,
resolve selected modules, check integer ABI and emit the chosen executable.

Every unit passes the native lexer, parser, semantic checker, lowering and
object writer independently. Sources are not concatenated and sibling symbols
are not imported implicitly. Compiled objects are retained in a bounded
8 MiB arena while the compiler's per-unit state is reset. Source errors retain
their original path/line/column, and late failures preserve the old destination.
No temporary object files, generated C, host linker or subprocess compiler are
introduced. The additional storage and existing target bounds are explicit in
the [build contract](native_module_builds.md).

The [three-module example](../examples/separate_modules/README.md) now includes
checked-in application, provider and library lists. It demonstrates both one
command application builds and reusable source-built libraries. All three
native host drivers register the same explicit commands.

**Local evidence:** 54 focused Windows source-build, target, manifest and
reality tests passed. Windows and Linux/WSL then rebuilt the compiler from
native seeds and proved Stage 2/3 byte identity. Each final compiler passed
106 source-build, target, manifest, archive and typed/untyped linker gates.
Tests include no intermediate artifacts, byte equality with individually
compiled archives, symbol/type/data isolation, late source failures, missing
and invalid lists/libraries, transitive dependencies and target limits. PE ran
on Windows and ELF on Linux. Test sets overlap. Actual Intel macOS execution
and new remote CI certification remain pending; no workflow polling was done.

**Still open:** automatic module/package resolution for this separate-unit
path, visibility/mangling and semantic ownership/effect signatures, generic
library boundaries, dynamic/foreign linking and independent first-seed
distribution. This closes the documented source-list build workflow for the
bounded native profile; it does not certify a complete native package manager.

## SV8.74 — libraries producing Windows and Intel macOS executables (2026-10-18)

**Starting baseline:** `1ea4e12`, reported green by the repository owner.
This delivery adds `--link-pe-libraries` and `--link-macho-libraries` to all
three native host drivers. The commands reuse archive member selection and
embedded integer ABI checks, then generate PE32+ or static Intel Mach-O
executables directly in Sotlas. The existing ELF output remains available.

The PE and Mach-O backends now accept multiple selected native objects. Their
previous single-object APIs delegate to these implementations and preserve
existing OS-import/process-entry paths. Typed library startup explicitly
requires an embedded zero-argument U32 signature. Entry lookup works beyond
the first object and inside a selected library member. Target-operation flags,
ABI mismatches, duplicate definitions and unsupported signatures fail before
opening the output file.

This is one shared internal object/library representation with three native
executable formats. It does not claim COFF/Mach-O object archives or general
foreign library support. PE reserves a resolver slot for its startup bridge:
15 selected Sotlas objects versus 16 for ELF/Mach-O. The complete
[target contract](native_library_targets.md) documents these boundaries, and
the [example](../examples/separate_modules/README.md) includes all three commands.

**Local evidence:** 13 new target tests passed on Windows, including actual PE
execution, entry placement, Boolean/signed and stack arguments, initialized
data, deterministic images, capacity and negative cases. A further 33 existing
Target IR, Mach-O cross-compilation and reality checks passed. Both Windows
and Linux/WSL rebuilt from native seeds and proved Stage 2/3 byte identity;
each final compiler passed 93 target, manifest, archive and ABI/linker gates.
Linux and Windows produced byte-identical example objects, archive, ELF, PE
and Mach-O images. The Linux-produced PE executed on Windows with result 42.
Test sets overlap. Actual Intel macOS execution and new remote CI certification
remain pending; no workflow polling was performed.

**Still open:** semantic ownership/effect library signatures, pointer and
aggregate boundaries, general system imports in library mode, dynamic libraries,
foreign object formats, package visibility, ARM64/signing and the independent
initial distribution. This closes the documented executable-target block for
the integer library profile, not general native language parity.

## SV8.73.1 — repair manifest-based ELF linking (2026-10-18)

[CI #1264](https://github.com/HPinho/sotlas_dev/actions/runs/39132698403)
failed in all nine matrix jobs on the same existing regression gate:
`test_cli_link_elf_list_uses_the_owned_linker_and_preserves_rejected_output`.
Windows reported an access violation; Linux and Intel macOS reported SIGSEGV.
The preceding SV8.72 workflow attempts also failed. The latest inspected
successful workflow is #1261, not the later user-reported green candidate.

The SV8.72 ABI-mode selection read `argv[1]` inside the shared linker handler.
The manifest command synthesizes payload arguments only and leaves that slot
null, so comparing it to the ABI command name dereferenced a null pointer.
The handler now takes an explicit Boolean mode. CLI dispatch passes its selected
mode; the existing manifest path passes plain mode. This repairs all three
native host drivers without changing archive selection, ABI checks or tests.

The old compiler reproduced the crash locally on Linux/WSL. The unchanged
manifest, embedded ABI and static-library suites then passed 47 focused Windows
tests after the repair. Both Windows and Linux/WSL then rebuilt the compiler
from native seeds and proved Stage 2/3 byte identity. Each final compiler passed
80 manifest, archive and typed/untyped ELF linker gates, including real Linux
execution and the original crashing test. The new remote workflow must
independently certify this correction; actual Intel macOS execution is pending.

## SV8.73 — native static libraries and lazy dependency closure (2026-10-18)

**Starting baseline:** `e8fa57a`, reported green by the repository owner on
2026-10-18. No workflow polling was performed for this delivery. Subsequent
inspection found its CI attempts #1262/#1263 failed; see the SV8.73.1 repair.

The complete static-library path is now implemented in Sotlas:

- `--archive-elf OUTPUT INPUT.o...` creates deterministic regular ar libraries
  from independently emitted native ELF objects and their embedded ABI records.
- `--link-elf-libraries OUTPUT ENTRY INPUT...` accepts direct objects and
  libraries, selects only needed archive members, resolves transitive and
  cyclic imports to closure, checks integer ABI compatibility and invokes the
  existing native linker before publishing the executable.
- Direct objects are roots. Selected definitions take precedence; remaining
  imports select the first matching archive member in input order. Unused
  members do not introduce duplicate definitions or unresolved dependencies.
- All stored members are validated. Malformed containers/ELF, unsupported
  archive extensions, missing providers, incompatible ABI and bounded-table
  failures preserve previous output bytes before artifact writing.
- The commands are registered in Linux, Windows and Intel macOS drivers.
  Production archive parsing, writing, member selection and linking do not
  invoke Python, C, a host archiver or a host linker.

The [static library contract](native_static_libraries.md) records the container
subset, selection rules, I/O limitations and explicit capacities: 16 input
files, 8 MiB total, 256 candidates and 16 selected objects. The existing
[three-module example](../examples/separate_modules/README.md) now documents
both direct object linking and distribution of providers through a library.

**Local validation:** 57 focused Windows tests passed for archives, existing
embedded ABI, untyped multi-object linking and reality checks. Both native
compilers were then rebuilt from seeds with host tools absent from PATH and
proved Stage 2/3 byte identity. Each final rebuilt compiler passed 68 archive,
embedded ABI and older typed/untyped linker gates, including the additional
256/257 candidate boundary. Linux executed the resulting ELF programs,
including transitive/cyclic cases. Test sets overlap. Remote CI and actual
Intel macOS execution remain pending.

**Still open:** ownership/effect/visibility signatures, pointer and aggregate
library interfaces, typed PE/Mach-O libraries, dynamic linking, general foreign
archive compatibility, package-level separate compilation and a fully
independent initial distribution. This closes the documented native ELF
static-library block; it does not certify all archive or language functionality.

## SV8.72 — embedded ABI and independent multi-module linking (2026-10-17)

This delivery connects the production native object writer to multi-module
ABI validation and executable linking. The Sotlas implementation now writes
versioned records for all function definitions and external declarations into
the ELF note section. Each record names the actual symbol-table index and
preserves the native return and parameter type tags.

The native Linux, Windows and Intel macOS drivers expose
`--link-elf-abi-objects OUTPUT ENTRY INPUT.o...`. It checks all function imports
across 1–16 independent objects against exactly one provider, with exact
integer width/signedness, Bool identity, arity and return type agreement.
Transitive imports, multiple exports and stack arguments work without
handwritten SOTI sidecars. Unsupported cross-module signatures, incomplete or
malformed records and duplicate providers fail before executable publication.
Existing untyped and SOTI-pair commands retain their contracts.

The [three-module example](../examples/separate_modules/README.md) is compiled
from separate source files and returns 42 on Linux. Its files are exercised
by the regression suite. The [format and command contract](native_embedded_abi.md)
documents the exact boundary and distinguishes ABI metadata from ownership,
effect or cryptographic provenance guarantees.

**Local evidence:** 73 focused Windows regression cases passed, covering the
new delivery, existing typed/untyped ELF linking, IR serialization and reality
gates. Both Windows and Linux/WSL then rebuilt from native seeds with host
tools absent from PATH and proved Stage 2/3 byte identity. The final native
compilers each passed 50 ABI/linking gates, including the additional incomplete
manifest test and actual ELF execution on Linux. A further 17 Target IR and
Mach-O cross-compilation checks passed on Windows. These sets overlap and are
not a claim of complete CI coverage. Intel macOS execution and remote matrix
certification remain pending; no new workflow was monitored.

**Remaining work:** complete semantic signatures for ownership/effects and
visibility; pointer/aggregate/float inter-module boundaries; typed PE/Mach-O
linking; archives/dynamic libraries; general package compilation; and initial
distribution without hosted bootstrap dependencies. The next block should
connect frontend domain/effect metadata to separate-module contracts rather
than infer those guarantees from integer ABI compatibility.

## SV8.71.1 — restore bootstrap and ABI regression gates (2026-10-17)

CI #1260 failed while building Stage 1: literal-first wire offset arithmetic
inferred `i64` for an argument requiring `usize`. The ELF ABI checker now
computes the parameter offset from an explicitly typed `usize` index and
reuses that offset for both the type and ownership-role fields. Wire layout
and ABI rejection rules are unchanged.

The focused rerun also exposed two test fixture errors: an adopted static
wire serializer was being bound as an instance method, and byte fields were
compared directly with `u32` interface constants. The helper retains its
static binding, and those comparisons explicitly widen the byte to `u32`.
All existing acceptance, rejection and output-preservation assertions remain.

Local Windows validation passed all 50 ABI, typed ELF pair and reality gates.
Linux/WSL independently rebuilt the compiler from a native seed with host
tools absent from PATH, proved Stage 2/3 byte identity, and passed 34 ABI
and typed ELF pair gates using that rebuilt driver, including ELF execution.
The latest inspected certified baseline remains CI #1259; this correction
requires its own remote CI result.

## SV8.71 — complete plain-import coverage and compiler ABI provenance (2026-10-17)

**Certified green baseline:** `684e674ca15c31441f88293757dfe69eac855f67` /
[CI #1259](https://github.com/HPinho/sotlas_dev/actions/runs/39065215635).
19/19 jobs green: Linux, Windows, Intel macOS, native seed and stage
fixed point, PE/Mach-O, distribution, snapshots and preview. The
SV8.71 candidate needs its **own** complete multi-platform CI.

This larger block strengthens the Sotlas-owned ELF typed pair linking
pipeline without removing untyped linking or any existing test.

- **Exhaustive import coverage in the bounded pair:** a validated
  importer ELF may have exactly one undefined global function symbol
  matching the SOTI contract. Every other undefined global, including
  an unused external declaration, fails before linker output.
- **Compiler-emitted ABI-note cross-check:** for the actual defined
  exporter ELF function, the new checker finds the Sotlas-owned
  `.note.sotlas.abi` descriptor and demands the SOTI record match
  function arity, boolean-parameter bitmask and float/nonfloat
  return class. Missing/corrupted/contradictory ABI notes fail closed.
  This does not pretend the legacy note proves every scalar width,
  pointer lifetime, effects or capabilities.
- **Plain-only boundary:** the legacy ELF ABI note does not encode
  sole/direct/whisper. These non-plain parameter roles fail closed
  on the new typed link path until the compiler embeds verified,
  complete ownership metadata. Ordinary plain parameters remain
  accepted with a matching compiler-owned note.
- **Compiler-owned Target IR serialization:** a new
  `target_interface_wire_encode_from_function_abi` API derives
  name, import/export identity, scalar/pointer return and parameter
  ABI from genuine `TargetFunction`/`TargetParameter` records,
  emitting canonical SOTI v1 bytes with a normalized name offset.
  Effects and capabilities are explicit caller assertions, **not**
  claimed as compiler-inferred/validated. General aggregate or
  non-plain signatures remain unsupported by this encoder.

**Test evidence:** 11 new cross-host CLI cases in
`tests/test_sotlas_native_typed_elf_sv871.py` cover real
independently compiled objects, one valid imported symbol,
additional used/unused imported symbols, forged but agreeing sidecars,
real U32/Bool signatures, false arity/bool/float claims, missing or
tampered notes, role rejection and unchanged executable output.
Eight Sotlas-native machine-code compile/link/execute tests in
`tests/test_sotlas_native_migration_sv871_abi.py` certify Target IR
ABI-derived serialization, successful comparison, scalar and void
shapes, malformed ranges, forbidden ABI, flags and artifact integrity.
All previous SV8.70 positive/negative tests and the old linker remain.

**Still open:** automatic sidecar emission by the production compile
CLI and embedded ELF/PE/Mach-O SOTI sections; attested compiler-owned
sole/direct/whisper roles and effect/capability derivation; complete
multi-symbol and multi-object typed linking; ARC/drop generation;
first-seed packaging with zero mandatory Python/C. These require
separate complete CI proofs, not a percentage inferred from this cut.

**Next substantial SV8.72:** integrate compiler-derived manifests
into the object writer and actual ELF metadata sections, extend
coverage beyond one pair and add fail-closed authenticity checks for
typed ownership/effects when the frontend metadata is available.

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

## SV8.70 — opt-in typed ELF linking of independently compiled object pairs (2026-10-17)

**Last certified green baseline:** `6593c521966ab1fa8c1531312bb4214948502fdf` /
[CI #1257](https://github.com/HPinho/sotlas_dev/actions/runs/39042389972).
All 19 platform, native seed, fixed-point, installer, PE/Mach-O execution
and packaging jobs passed. This new cut is a candidate until its own CI.

A new owned Linux-native driver command `--link-elf-typed-pair` accepts
an existing output path, entry point, immutable name buffer, independently
compiled importer/exporter ELF64 objects, and their SOTI v1 wire records.
It reuses the existing native ELF64 object loader/linker but requires a
typed *preflight* before publishing the executable:

- Both inputs must pass the production ELF64 structural validator.
- Both untrusted wire sidecars must pass full SOTI version/extent,
  parameter, type, ownership role, name and flag verification.
- Import/export names, return types, parameter count/types/roles, effect
  and capability subset rules must match, with no privilege escalation.
- The declared imported name must be present as a genuine undefined
  global ELF function reference in the importing object; the exported
  name must exist as a real defined global ELF function in the provider.
  The native symbol scanner recognizes the owned writer's STT_NOTYPE
  undefined extern declarations and STT_FUNC definitions, rejecting
  duplicate matches.
- The existing 2-object linker then resolves relocations and builds
  the executable. Preflight failures leave a previously written output
  byte-for-byte intact. The historical untyped linking command is unchanged.

Fifteen new `tests/test_sotlas_native_typed_elf_pair.py` gates use the
real Sotlas-native CLI to compile two separate ELF objects, execute the
successful linked image on Linux and reject bad/missing/tampered metadata,
ABI/role mismatch, effect/capability escalation, absent or reversed ELF
symbol identities, invalid ELF, bad entry, argument errors and missing
files without overwriting an existing image. They supplement all 16 SV8.69
wire tests, 19 SV8.68 manifest tests and the existing multi-object CLI suite.

**Security boundary:** this first integration is *opt-in*, ELF64-x86_64
only and deliberately limited to one import and one export interface
across two objects. Metadata is passed as separately created sidecars;
the compiler does **not yet** synthesize those contracts from canonical
frontend ownership/effects or embed them in the object file. Therefore
the verifier proves consistency of supplied signed-looking declarations
and presence/definition of ELF names, **not** authenticity of ABI/effect
claims against machine instructions. No trust or signature cryptography
is provided. General per-symbol metadata, true internal object sections,
automatic ARC/drop and Python/C-free first bootstrap remain open.

**Next large SV8.71 block:** generate SOTI records from compiler-owned
typed symbols and embed them in ELF relocatables, require coverage for
all imported functions at the native linker and extend independent
object and metadata checks to PE/Mach-O without weakening green CI.

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

## SV8.69 — portable versioned typed interface wire records (2026-10-17)

**Full green baseline:** `43bb572e23c724c06ea99a2b694ad38f27756d2d`.
[CI #1254](https://github.com/HPinho/sotlas_dev/actions/runs/38992580949)
and independently [CI #1255](https://github.com/HPinho/sotlas_dev/actions/runs/39011203750)
passed the same head on Linux, Windows and Intel macOS, plus native seed,
nightly snapshot, PE/Mach-O execution and Python distribution gates.
SV8.69 is an unverified candidate until its own complete CI passes.

This substantial Sotlas-native object-format preparation block
extends `backend/target_ir.sotlas` with a deterministic, little-endian
version-one interface record. A record has a 48-byte fixed header,
eight bytes for each parameter and a maximum size of 240 bytes.
It stores exact import/export kind, scalar/pointer return ABI,
name offset/length, parameter ABI tags and ownership domains,
effect mask and required capability mask. Names remain slices into
a supplied immutable source buffer, not host pointers.

The wire implementation uses per-byte shifts, avoiding C structs,
host endian/alignment, compiler ABI padding and foreign serializers.
Its API includes checked size calculation, fail-closed encoding,
full-record validation, transactional decode and direct *serialized*
import/export compatibility checking. Unsupported aggregates, invalid
roles/type tags, malformed lengths, magic/version/reserved flags and
effect/capability escalation are rejected before any output publication.
Encoding capacity errors preserve old bytes; decoded interface and
parameter destinations remain unmodified after invalid input.

**Gate:** 15 additional native compiled-and-executed tests in
`tests/test_sotlas_native_migration_sv869.py` cover wire size limits,
roundtrip, exact little endian bytes, unaligned input, version/magic
and extent corruption, no partial encoding/decoding, all 4 ownership
roles, ABI changes, privilege escalation, zero-param void return
and full 64-bit capability/effect bit preservation. Prior 19 SV8.68
and all previous SV/CI tests remain unchanged.

**Boundary:** the typed *wire contract* is executable Sotlas code,
but actual ELF/PE/Mach-O writers and the multi-object linker do not yet
embed/read those records or check them before final image creation.
These are still required before certifying full cross-object ownership,
effects or authority. Python/C-free initial seed and automatic ARC/drop
remain pending.

**Next large SV8.70:** attach these stable records to emitted native
objects and require verification in real multi-object ELF linking,
then extend PE/Mach-O; check tampering and preserve executable bytes
on failed binding, including Stage2/Stage3 and cross-platform matrix.

## SV8.68 — typed native pre-link interfaces, roles and capability bounds (2026-10-16)

**Certified baseline:** `e3abf81191a1a928d6a981b9d29eb00c0d6155ff` /
[CI #1253](https://github.com/HPinho/sotlas_dev/actions/runs/38980061670).
All Linux/Windows/Intel macOS, native seed, installer, snapshot and
native PE/Mach-O execution jobs were green. This cut awaits its own CI.

The Sotlas-written `Target IR` now exposes caller-owned
`TargetInterface` and `TargetInterfaceParameter` records and five
bounded native verification functions. They validate symbol-name slices,
parameter intervals (maximum 24), scalar/pointer return and parameter ABI,
ownership roles (plain/sole/direct/whisper), duplicated and missing
declarations, and import/export signatures. Export effects and required
capability bits must be subsets of the importing declaration; no
privilege or effect escalation is admitted.

`target_interface_bind_manifest` checks the entire import/export
manifest before publishing any output mapping, so a later missing or
incompatible import cannot partially overwrite prior mappings.
Nineteen native compile/link/execute/rejection tests demonstrate those
properties using the production Sotlas backend and no C glue.
Previous SV8.66/8.67 gates remain enabled and unchanged.

**Critical boundary:** this is *pre-link typed metadata checking*,
not yet emitted ELF/PE/Mach-O interface metadata or true native
separate-object linking. Source-name, record, and output buffers must
remain immutable/disjoint during verification; this profile is
single-threaded, fail-closed on aggregate ABI and does not prove general
automatic ARC, capabilities propagation or Python/C-free first seed.
[Contract](native_typed_interfaces.md).

**Next large SV8.69 block:** emit/serialize typed module interfaces
through the native object format, check external references against
them in the real linker, and preserve existing executable bytes upon
failed linkage. Certify full fixed-point matrix before completion claims.

### SV8.67.1 — regression repair: lexical fixture collisions (2026-10-16)

[CI #1252](https://github.com/HPinho/sotlas_dev/actions/runs/38969506696)
failed exactly two of the 16 new SV8.67 tests on Linux, Windows and
Intel macOS. In both cases the generated source redeclared an identifier
already in the shared SV8.66 fixture: `table` in the adjacent-buffer
test and `cp` in the combined weak/take/defer cleanup test. The native
compiler correctly rejected both programs, before any runtime execution.
There was no evidence in the CI output of a runtime ownership failure.

Keep all 16 SV8.67 cases, all 15 SV8.66 cases, and the entire Sotlas
runtime implementation unchanged; rename only the two new fixture
locals to `adjacent_storage` and `cloned_handle`, updating their uses.
No tests are skipped, removed or relaxed; the positive gates must still
compile, link and execute native code. The last certified green baseline
remains [CI #1251](https://github.com/HPinho/sotlas_dev/actions/runs/38957013245)
(`94823c4`). The repair needs its own complete matrix before certification.

## SV8.67 — native scoped ownership transaction and alias-hardening block (2026-10-16)

**Baseline verde:** `94823c443e741184f3c148e0435e06c72d4cb081` /
[CI #1251](https://github.com/HPinho/sotlas_dev/actions/runs/38957013245).
All platform, packaging, native rebuild and fixed-point jobs passed.
The new work remains uncertified until its own full CI finishes green.

The Sotlas runtime now supports three coordinated resource operations:
scope-bound clone of a new strong claim, scope-bound weak upgrade with
generation proof, and scope-bound take/move of an existing claim. Each
checks its table/destination before mutation and includes recovery on
unexpected registration failure, preserving exactly-once close semantics.
Two further native validators reject duplicate handle identities
(including unsafe table corruption) and overlapping scope-table backing
storage; LIFO rewind and ownership transfer now fail closed on these
conditions. The public scope contract, native driver guidance and
unified roadmap are updated in this same commit.

**Gate:** 16 new `test_sotlas_native_migration_sv867` native
execution/rejection cases, on top of unchanged SV8.66's 15 gates.
No C helper, Python semantic fallback, test removal or new Git branch.
This addresses bounded manually enrolled ownership; it is not general
compiler-emitted automatic ARC/drop or global lifetime verification.

**Next large SV8.68 block:** typed module/object exports/imports with
ownership/effect/capability signature validation, and compiler-emitted
drop/cleanup for a proven bounded native resource shape. Maintain
green CI #1251 as rollback comparison, keep macOS green and measure
Python/C reduction only after complete dependency audits.

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

## SV8.66 — scoped resource lifecycle: full native acceptance block (2026-10-16)

**Green baseline:** `768b6d1d2bd17a46ad2be227d464cdc276717602` /
[CI #1249](https://github.com/HPinho/sotlas_dev/actions/runs/38940935785).
Candidate until its own full Linux/Windows/Intel-macOS matrix, packaging
and Stage2/Stage3 native fixed-point gates finish green.

This single commit adds a coherent, bounded resource-lifecycle contract in
Sotlas-written `runtime/native/managed.sotlas`: 64-entry checked scope
tables, live owner registration, duplicate/capacity rejection, LIFO release,
nested mark and transactional rewind, detach, full drain, scope-to-scope
ownership promotion, and a `void` lexical `defer` close operation.
All bytes and headers remain caller-backed; no C helper or Python runtime
path executes in the generated program. Fifteen new positive/negative
native program gates exercise code generation, weak generation invalidation,
exactly-once slot cleanup, early exits and fail-closed invalid ownership.
See [detailed API/verification contract](native_scoped_resources.md) and
[ownership checklist](sotlas_native_frontend_ownership_checklist.md).

This is a complete **bounded explicit-ownership feature**, not the full
canonical ownership implementation. The compiler still needs to *synthesize*
destructors/ARC, validate general lifetimes and aliases, and support typed
independently compiled modules with cross-object ownership/effect/capability
signatures. The initial native seed and some distribution paths still rely
on hosted tools; 0% mandatory Python/C has not been established.

**Next large block SV8.67+:** combine typed native separate-object module
interfaces, cross-object signature/authority validation and a certified
compiler-generated cleanup subset before attempting any full-migration
completion claim.

## SV8.65 — full-capacity regression closure and strengthened Linux gates (2026-10-16)

**Last certified main baseline:** `2e93a8d78b720545943e85cccea6bb44c3420854` /
[CI #1242](https://github.com/HPinho/sotlas_dev/actions/runs/38901099982).
Commits #1243–#1248 added native capacity and preview application work, but
their Linux matrix consistently failed an obsolete test expecting the 513th
string literal to be rejected. The owned compiler now allows 2,048 literal
symbols. The Windows and macOS suites passing on the latest run do not
override that Linux failure.

Restore the intended safety invariant **without weakening a test**: extend
the Linux native file-driver integration test to run 512, 513 and all 2,048
literal symbols, reject 2,049, independently prove the 65,536-byte decoded
pool, query the compiler's `--limits` profile, and verify that failing check
and compile operations preserve a previously generated image byte-for-byte.
Run these programs using the native Sotlas toolchain with Python/C/external
tools absent from its PATH. The existing cross-platform large-module
scripts and Windows GUI/calculator release gates remain unchanged.

No new semantic fallback, compiler source change, new branch or test skip.
This cut remains a **candidate** until its own complete Linux/Windows/
Intel macOS, Stage2/Stage3, packaging and runtime matrix passes.

**Next larger implementation block, after green:** SV8.66+ should group
fully typed separate-module interfaces, cross-object effect/ownership ABI
proofs, and explicit resource-cleanup migration into a single tested
sovereignty milestone rather than accumulating tiny standalone patches.

## SV8.64 — larger native programs (2026-10-16)

The unified Sotlas object backend now accepts 1,024 functions; native literal
tables accept 2,048 symbols while retaining the 65,536-byte decoded pool.
All function symbol/offset/size and string symbol tables use the new bounds.
Native check/build gates execute the exact boundaries and reject one-over
inputs without replacing an existing executable.

Windows and Linux/WSL passed six capacity cases each and rebuilt the original
compiler modules with Stage 2/3 byte identity. Two focused object regressions
passed, including all 2,048 literal relocations. Existing platform Stage 3 gates
reuse their compiler for these cases. Intel macOS execution and remote CI
remain pending. This removes a compiler-growth barrier; full frontend and
ownership parity remain open. See the [capacity contract](native_large_modules.md).

## SV8.63 — native match guards (2026-10-16)

Starting from owner-reported green `899fce1`, this cut closes Boolean guards on
native match statements. Parser, ownership checking and CFG lowering are Sotlas
code. Guards run only after a pattern hit, false guards continue dispatch and
only unguarded cases contribute to coverage. Supported POD borrows are allowed;
guards that may consume owners are rejected.

The combined 24 range/guard cases passed on Windows and Linux/WSL. Both native
compilers rebuilt with Stage 2/3 byte identity; a guarded command dispatcher
returned 42 on both. The 16 reality gates passed with the documentation snippet
registered. No full suite or Intel macOS execution was run locally, and the
candidate CI is pending. See the [native guard contract](native_match_guards.md).

## SV8.62 — native integer match ranges (2026-10-15)

This cut implements `first..last` and `first..=last` from native AST through
typed constant checking, overlap/coverage validation, Target IR and machine
execution. It supports exhaustive fixed-width integer domains without
enumerating values or overflowing at MAX. Source-located errors distinguish
invalid bounds, reversed/empty intervals, overlaps and incomplete coverage.

Windows and Linux/WSL native seeds rebuilt the changed compiler with Stage 2/3
byte identity. Thirteen focused fixture cases passed on both platforms, and the
byte-classifier example returned 42. Existing platform Stage 3 gates now run
these fixtures without creating another bootstrap. Intel macOS execution and
remote CI are pending. This closes integer match ranges, not payload patterns,
guards or match expressions. See the [contract](native_match_ranges.md).

## SV8.61 — native loop/range syntax, implicit enums and borrowed text (2026-10-15)

Starting from `7a36a3e`, this package adds new source capabilities: unconditional
loops, exclusive integer for ranges and implicit/mixed scalar enum values.
The parser builds native AST nodes and structured CFG; generated constants and
hidden range bindings do not depend on Python or a host string allocator.

A new Sotlas text module provides length-delimited borrowed values, substring
operations, field/line iteration and decimal parsing. A native program composes
these APIs to parse key=value records. [The checklist](sotlas_native_frontend_ownership_checklist.md)
records 36 contracts across these four new capability families, plus execution
and rejection gates. Built-in slices/str, generics, payload enums, automatic ARC
and typed separate modules remain open. Candidate CI is pending.

## SV8.60 — managed strong slots and native object rebuild audits (2026-10-15)

Starting from online `88c80e2`, this package adds 36 bounded contracts across
nine open migration topics. It extends separated scientific literals and match
ownership fallthrough, provides explicit managed strong-slot operations and
checked narrowing, and adds unaligned endian I/O written in Sotlas.

IR function identities/table partitions and ELF section contracts are checked
before machine artifacts are consumed. JSON reports support tools; rebuilt
project objects can be compared or recorded in SOTOBJ01 stamps without invoking
external compilers. [The checklist](sotlas_native_frontend_ownership_checklist.md)
records all 36 deliveries, gates and limits. Automatic cleanup synthesis, typed
separate-module ABI, whole-language native parity and independent distribution
remain open. Candidate CI is pending; source stamps/object audits do not replace
the existing full compiler fixed-point gates.

## SV8.59 — compiler-lowered lexical cleanup of native managed resources (2026-10-15)

**Green baseline:** `fd6dd7d89cff9b38fa6fbe58bb34551b30806f37` /
[CI #1234](https://github.com/HPinho/sotlas_dev/actions/runs/38790093635)
(Linux, Windows and Intel macOS).

The Sotlas-written `runtime/native/managed.sotlas` now provides
`native_managed_bytes_close(*mut NativeManagedBytes) -> void`: it verifies
the original generation, releases one strong claim, zeros its registered
payload on final release and poisons the mutable resource slot on success.
When explicitly registered by source code as `defer native_managed_bytes_close(ptr);`,
the already-native compiler emits the call on lexical block exit, early
function return or supported loop jumps. Repeated cleanup through the same
slot has no second release. Non-final release preserves the payload; stale
handles, mismatched generation and invalid states remain fail-closed.

The `test_sotlas_native_migration_sv859` suite adds native compile/link/
execute and rejection gates for lexical cleanup, duplicate defers, return,
non-final and final releases. The caller still provides stable disjoint
backing/control/handle memory and accounts for any separate strong claims.
The compiler does not infer destructors, inject automatic ARC/drop glue or
prove non-POD lifetimes. The candidate remains uncertified until its
complete platform and fixed-point workflow passes.

**Next SV8.60:** make ownership-bearing values eligible for synthesized,
exactly-once cleanup in a certified bounded native profile, or complete a
typed separately compiled module ABI/capability interface. Keep unsupported
resource shapes fail-closed and maintain zero Python/C fallback in native
runtime code.

## SV8.58 — explicit managed byte resources in native Sotlas runtime (2026-10-15)

**Certified baseline:** `0df0bb95bfc3ae9300d49be8063703d722d32d87` /
[CI #1233](https://github.com/HPinho/sotlas_dev/actions/runs/38781346034).

The Sotlas-written `runtime/native/managed.sotlas` now binds one uniquely
owned reference-control block to caller-backed bytes. It keeps a generation
snapshot in the managed resource, allows strong retains and matching weak
upgrades, and clears the payload exactly when the final strong release occurs.
Subsequent release/upgrade and old resource bindings fail closed even if the
reference header is recycled. A final-release status authorizes exactly one
caller-managed cleanup, without C object glue or a Python semantic fallback.

`test_sotlas_native_migration_sv858` contains native execute/reject gates for
retained payload, final zeroing, weak invalidation, stale generations, invalid
binding and foreign weak tokens. Stable, disjoint buffer/control storage remains
a caller precondition, with no hidden heap allocation, atomic reference counts,
language-integrated ARC/drop, guaranteed lifetime proof or thread safety.
This candidate is not certified until its own complete matrix passes.

**Next SV8.59:** make the resource lifecycle callable from compiler-generated
ownership cleanup or construct a typed cross-module interface boundary with
positive and negative ABI/capability signatures; retain strict fail-closed
unsupported paths and preserve native fixed-point CI.

### SV8.57 regression repair — native execution fixture (2026-10-15)

CI [#1232](https://github.com/HPinho/sotlas_dev/actions/runs/38775167195)
reported seven `AttributeError: 'NativeMigrationSV857Tests' object has no
attribute 'link_image'` errors in the new SV8.57 execution tests on Linux,
Windows and Intel macOS. The root cause was a missing Python *test harness*
method binding, not a reason to remove native compile/link/execute gates.
Restore the same `link_image` delegation already used by SV8.56 so all eight
SV8.57 tests retain their positive execution and negative rejection checks.
No Sotlas compiler/lexer/parser, ABI, assertions or previous tests are changed.
Last certified baseline remains `08b0cc4` / green CI #1231; the repair is
a candidate until its own full matrix passes. Next native implementation
remains SV8.58 after regression closure.

## SV8.57 — six native compound operators and bounded owner safety (2026-10-15)

**Last verified green baseline:** `08b0cc4b3009291dfea8fbdba229e5ca9202dbef` /
[CI #1231](https://github.com/HPinho/sotlas_dev/actions/runs/38762917787) (Linux, Windows and Intel macOS matrix).

The Sotlas-written token, lexer and parser now accept `%=`, `&=`,
`|=`, `^=`, `<<=` and `>>=` for mutable identifier places, reusing
existing type-checked expression/assign lowering. The RHS is evaluated
once. Immutable bindings, indexed/field/pointer places and owned aggregates
without an admitted operator fail before native output. Native positive,
negative and side-effect tests are in `test_sotlas_native_migration_sv857`.
This does not implement automatic ARC, generics, package modules or an
independent Python-free bootstrap. This candidate must still pass its full CI.

**Next SV8.58:** progress a fully typed separate-module interface or a
resource ownership runtime gate, prioritizing replacement of Python/C
semantics and preserving the green fixed-point matrix.

## SV8.56 — compound assignments and compiler manifests (2026-10-15)

Starting from `bba4c7a`, this candidate adds 36 bounded contracts across nine
open areas: local compound assignments, preserving conditional loop exits,
mutable byte buffers, signed arithmetic guards, IR/ELF validation, scalar bit
operations, compiler manifests and checked project source audits.

[The checklist](sotlas_native_frontend_ownership_checklist.md) records each
delivery, gate and limit. Whole-topic frontend/ownership/runtime migration,
typed separate modules and independent distribution remain open. Project
source stamps complement the existing fixed-point gates; they do not replace
Stage 2/3 identity evidence. Candidate CI remains pending.

## SV8.55 — returning ownership edges and project manifests (2026-10-15)

Starting from `d9abed4`, this candidate delivers 36 bounded contracts across
nine open areas. Unicode scalar escapes cover all four UTF-8 widths; closed
loop ownership edges can join returning arms. Explicit memory/arithmetic APIs
and a Sotlas word-operations module execute through the owned scalar backend.

IR metadata and ELF identity/alignment checks reject unsupported input. Native
project manifest commands reuse ordered/resolved compilation; general artifact
sets gain ordered stamps, reports and byte comparison. [The checklist](sotlas_native_frontend_ownership_checklist.md)
records each delivery and gate. Dedicated word instruction selection, Unicode
library breadth, typed modules and automatic ownership runtime remain open.

Local validation passed 3,118 Windows regression tests with 79 skips in
1,052.646 seconds. All 36 new gates passed on Linux through WSL and Windows
Python 3.10.11; the 137 existing frontend closure gates passed. Windows/Linux
Stage 2/3 identity and complete Darwin compiler cross-generation passed.
Candidate CI remains pending.

## SV8.54 — nested ownership joins and native manifests (2026-10-15)

Starting from `74881ce`, this candidate implements 36 bounded contracts across
all nine still-open migration areas. Closed nested if/match loop edges retain
independent break and continue owner states. Arenas gain checked array allocation
and last-allocation reuse. Explicit arithmetic guards, scalar metadata preflight
and narrow immediate validation extend the native runtime/backend contract.

Object preflight checks entry/reserved flags, section names and symbol boundary
ranges while preserving the internal ABI. All drivers gain file manifests for
source/object checking, entry resolution, ELF linking, comparison and seed-set
stamps. [The checklist](sotlas_native_frontend_ownership_checklist.md) records all
36 delivered contracts, exact limits and gates. Whole-language ownership,
effects/contracts, modules and toolchain independence remain open.

Local validation passed 3,082 Windows tests with 79 skips in 855.727 seconds.
All 36 new gates passed on Linux through WSL and Windows Python 3.10.11;
the additional seed-order check passed on both native hosts. The existing
137 frontend closure gates, Windows/Linux Stage 2/3 identity and complete
Darwin compiler cross-generation passed. Candidate CI remains pending.

## SV8.53 — array shapes, runtime batches and artifact preflight (2026-10-14)

Starting from `7c42ad7`, this candidate adds 36 bounded contracts, four in each
migration area. The [checklist](sotlas_native_frontend_ownership_checklist.md)
marks every implemented contract and names its gate.

Native features include byte hex escapes, radix array dimensions/repeats,
narrow signed/unsigned pointer offsets, batched local reference operations,
memory fill/equality and arena reset, revocable authority tokens, stricter
constant/control metadata and ELF relocation preflight. All platform drivers
gain eight native commands for independent source/object checks, artifact
comparison, seed/stamp validation and exclusive seed copying.

Automatic ownership, canonical effects/state migration, typed separate module
interfaces and full toolchain independence remain open. This candidate does
not authorize deletion of the Stage-0 Python/C oracle.

Local validation passed 3,046 Windows regression tests with 79 skips in
815.285 seconds. All 36 new gates passed on Linux through WSL and Windows
Python 3.10.11. Original-source Stage 2/3 identity passed on Windows/Linux;
complete Darwin compiler cross-generation passed. Candidate CI remains pending.

## SV8.52 — native linking of separate ELF objects (2026-10-14)

Based on the owner-reported green `24d5627`, all native drivers now accept
`--link-elf-objects OUTPUT ENTRY INPUT.o...` and emit a hosted Linux x86-64 image
through the owned linker. Up to 16 independently compiled objects share an
8 MiB input budget. Structural validation and symbol resolution finish before
output is opened. Native gates cover input ordering, cross-object calls,
duplicate and unresolved symbols, malformed inputs and output preservation.

The [checklist](sotlas_native_frontend_ownership_checklist.md) now marks all 72
bounded SV8.50/SV8.51 contracts individually. Full typed module interfaces,
package compilation and multi-object PE/Mach-O output remain open.

Local gates passed: seven new cases on Windows Python 3.10.11 and Linux through
WSL, 40 final Target IR/CLI regressions, Windows/Linux Stage 2/3 identity and
complete Darwin compiler cross-generation. Candidate CI remains pending.

## SV8.51 — literals, reusable runtime and native artifact operations (2026-10-14)

The candidate based on `3e4320e` delivers another four bounded contracts in
each of nine migration areas. The [native checklist](sotlas_native_frontend_ownership_checklist.md)
records the complete 36-item inventory, gates and remaining limitations.

Native decoding now covers hexadecimal, binary, octal and ASCII character
values. Checked weak tokens support header recycling without resurrecting old
generations. The explicit Sotlas runtime gains cleared allocations, memory
copy/move, clearing rewind and revocable authority/state guards. Signed pointer
offsets and unsigned literal addresses lower through the owned x86-64 backend.

IR preflight rejects unknown schema/flag metadata. ELF preflight validates
symbol names, bindings, types/visibility and extents. Native drivers can check
explicit projects without output, validate objects, link existing objects and
create/verify reproducibility stamps. Stamps are exclusive new files and use
FNV for content comparison, not authentication.

Original-source compiler generation, existing reference contracts and full
regression remain required gates. This package does not establish complete
canonical parity or authorize removal of the Python/C bootstrap.

Final local validation: 3,003 Windows tests passed with 79 platform/toolchain
skips in 969.761 seconds. All 36 new gates passed on Windows, Linux through WSL
and Windows Python 3.10.11; the combined targeted run passed 182 tests. Linux
Stage 2/3 identity and complete Darwin compiler cross-generation passed in
125.815 seconds. Windows Stage 2/3 passed in the full suite. The owner reported
the workflow green for `24d5627`; the run number was not independently inspected.


## SV8.50 — native runtime and migration boundaries (2026-10-14)

Starting from `b40a8fa`, this candidate implements four bounded contracts in
each of nine migration areas. The complete 36-item inventory and evidence are
in [the native migration checklist](sotlas_native_frontend_ownership_checklist.md).

The new `runtime/native/managed.sotlas` provides caller-backed arenas, local
reference headers, generation-checked weak upgrades and explicit runtime
authority/state/range guards. It compiles through the owned x86-64 object/link
path. A native project gate uses the actual library source with host tools
absent. Automatic ARC/drop, stored language borrows and canonical state/effect
syntax remain separate migration requirements.

Native address conversions use `PointerCast`, preserve 64 bits and require
unsafe; narrowing, signed and floating address conversions are rejected.
Branch assignments select structured CFG lowering. IR preflight and ELF input
checks are strengthened before machine emission/linking.

All three native platform drivers gain four report commands and four bootstrap
audit commands. Generation gates use those native commands on actual Stage 2/3
artifacts while retaining the existing byte identity assertions. Fingerprints
and executable envelope checks do not authenticate a seed or prove full parity.

Final local validation passed 2,967 Windows tests with 79 platform/toolchain
skips in 897.171 seconds. All 40 added gates passed on Windows, Linux through
WSL and Windows Python 3.10.11. Linux original-source Stage 2/3 identity and
complete Darwin compiler cross-generation passed in 104.232 seconds; Windows
Stage 2/3 passed in the full suite. Native Intel macOS execution still requires
CI. CI certification remains pending. Python/C bootstrap removal is not
established by these bounded advances.


## SV8.49c — per-edge POD ownership and matrix regression repair (2026-10-14)

The local main was synchronized to `3f2fa08`. CI #1222 failed on Linux,
Windows and Intel macOS at the same SV8.49a negative case: its unchanged owner
break/continue program contradicted the new SV8.49b acceptance contract.
That exact source is now a permanent execution case. The negative slot tests
consumption in the condition before a continue backedge; moved-owner and
opaque-fallthrough rejection coverage is retained.

The native ownership verifier keeps a separate break-edge state table for
mixed loop exits. A consuming break arm is accepted when the continue arm
preserves its owners. The enclosing while validates the continue backedge and
joins break states with the zero-iteration exit, marking differences
MAYBE_MOVED. Post-loop use remains rejected. Nested loops save and restore
their parent's break summaries.

Direct match-arm break/continue exits now propagate the same outcomes, with
separate break-state merging and unchanged continue-state checks. Uniform
break and continue matches are accepted. Normal fallthrough mixed with loop
jumps, nested mixed if exits inside match arms, and general resource cleanup
remain outside this contract. This is POD ownership analysis, not ARC/drop.

Five frontend gates cover both branch orders, match cleanup, uniform match
exits, nested loop summaries and unsafe edge rejection. Three native platform
CLI gates validate check/compile/run and output preservation on a rejected
post-loop read. Final local validation passed 2,927 Windows tests with 79
platform/toolchain skips in 843.420 seconds. All 137 frontend gates passed on
Windows, Linux (WSL) and Windows Python 3.10.11. Linux native CLI execution,
original-source Stage 2/3 identity and Darwin compiler cross-build passed
three gates; the Windows native generation chain passed in the full suite.
The temporary hosted C-emission fixed-point oracle also exposed unsupported
conditional-value syntax in two new verifier locals. Equivalent structured
if/assign statements preserve that rebuild gate without adding a fallback or
changing the per-edge semantics; all six SV8 gates passed after the adjustment.
The last certified baseline remains `ce93fa9` / CI #1221 until new CI passes.

## SV8.49b — native mixed break/continue ownership gates (2026-10-14)

**Last verified green baseline:** `ce93fa901716671a85437e8be1d047540afa7d4c` /
[CI #1221](https://github.com/HPinho/sotlas_dev/actions/runs/38621972769).

The Sotlas-written `NativeOwnershipCheck.sequence_inner` now supports bounded
mixed `break`/`continue` paths when a full `if/else` transfers control on
both arms. It proves separate branch snapshots match the entry owner states,
propagates an explicit mixed-edge outcome and rechecks the enclosing while
backedge. Lexical cleanup is exercised with read-only deferred captures.
Any outer sole owner moved/rebound in either arm, mixed match-arm transfers,
and opaque/joined loop paths still fail closed.

**Verification:** native positive execution and negative rejection gates in
`test_sv849b_native_mixed_loop_edges_preserve_sole_owner`,
`test_sv849b_native_mixed_edges_preserve_owned_defer_cleanup` and
`test_sv849b_native_mixed_edges_reject_owner_moves_and_opaque_joins`.
The candidate remains uncertified until its own full Linux/Windows/Intel-macOS
and Stage2/3 CI matrix is green. No Python/C semantic fallback or relaxation
of existing CI tests was introduced.

**Next frontend/ownership item: SV8.49c.** Explicit per-edge owner states
for paths that legitimately consume an owner only on a terminating break path,
with certified cleanup and use-after-maybe-move diagnostics. Cross-object
capability signature work SV8.48h remains open separately.

## SV8.49a — native frontend/ownership uniform loop exits (2026-10-14)

**Baseline:** `82f7f2b3c47aacdea2680a4c327e39d24c26585f` / [CI #1220](https://github.com/HPinho/sotlas_dev/actions/runs/38614802316), green on Linux, Windows and Intel macOS. This is the last confirmed full matrix, not a claim that this patch has passed.

The Sotlas-written `NativeOwnershipCheck.sequence_inner` now propagates a
proven identical `break`/`break` or `continue`/`continue` from both
branches of an `if/else`. It conservatively joins `sole` owner states:
disagreement becomes `MAYBE_MOVED`; the existing while analyzer rejects
an owner moved on a `continue` backedge and refuses use after a possibly
consuming `break`. Mixed jumps, implicit fallthrough and general loop-edge
joins remain fail-closed. Positive native execution and negative diagnostic
gates are `test_sv849a_native_owned_uniform_loop_jumps_execute` and
`test_sv849a_native_owned_loop_jump_states_fail_closed`. No Python/C
compiler semantic fallback is added, and no hosted files are removed.

**Next frontend/ownership cut: SV8.49b.** Prove distinct break/continue
ownership joins using explicit per-edge snapshots in Sotlas-native semantics,
while guarding cleanup/defer and early-return interactions. Separately,
SV8.48h (cross-object capability signatures) stays open until complete
native module and FFI boundaries have matching ABI/effect evidence.

## Goal

The long-term goal is for the normal Sotlas development and execution path to no
longer require C or Python. Sotlas should be able to compile applications,
kernels, runtimes, libraries and eventually its own compiler through
Sotlas-owned frontend, IR, machine backend, object writer and linker stages.

This does **not** mean deleting the current C11 and Python Stage-0 paths before
parity. They remain bootstrap and differential-oracle implementations until the
native route proves the same or stronger contracts. No test may be weakened,
skipped or bypassed to accelerate this transition.

The intended end state is:

```text
Sotlas source
    -> Sotlas-written lexer/parser/sema
    -> Sotlas-owned canonical IR
    -> Sotlas-owned Target IR
    -> Sotlas-owned machine backend
    -> Sotlas-owned object writer
    -> Sotlas-owned linker / image builder
    -> apps / libraries / kernels / firmware
```

Python and C may remain optional development/reference tools after the normal
path stops depending on them, but they are not part of the sovereignty target.

## Migration rules

1. Stage 0 remains trusted only as a bootstrap and parity oracle while Stage 1
   is incomplete.
2. New native stages must consume explicit data contracts rather than Python
   dictionaries, C structs used only as glue, or product-specific shortcuts.
3. C11 remains a portability/reference backend until native output has execution
   parity for the same subset.
4. The machine backend must fail closed on unsupported instructions, ABIs,
   layouts and object features.
5. Kernel and application work share the same language/backend primitives; the
   compiler must not gain Baken- or application-specific bypasses.
6. A milestone is promoted only with positive, negative, end-to-end and CI
   evidence appropriate to its scope.
7. The final removal of Python/C from the normal installed path happens only
   after Stage 1 -> Stage 2 fixed-point evidence and clean-install native tests.
8. Commit implementation in substantive, validated blocks. Moving a diagnostic
   to a later line is investigation evidence, not a completed milestone. Keep
   incomplete implementation local until its agreed behavioral gate and the
   existing regression checks pass. Do not rewrite or skip real validator logic
   just to satisfy a source-line threshold.

## Sovereignty milestones

| Milestone | Objective | State |
|---|---|---|
| **SV0** | Recover a green cross-platform baseline before sovereignty work | ✅ CERTIFIED (`7162167d`, CI #1063) |
| **SV1** | Define backend-neutral Target IR in Sotlas, independent of C/Python containers | ✅ CERTIFIED |
| **SV2** | Lower the Sotlas-written native frontend AST/sema subset into native Target IR | 🟡 IN PROGRESS (scalar/struct memory, scalar enums, string literals, constrained static/receiver methods, wide calls/comparisons and integer module constants are certified; general arrays/slices, payload enums/match and richer compiler expressions remain open) |
| **SV3** | Feed native Target IR into the Sotlas-owned x86-64 backend for scalar functions | ✅ CERTIFIED (single-block U32 subset) |
| **SV4** | Native CFG, calls, aggregates, ownership/effects and ABI parity required by real apps | 🟡 IN PROGRESS (x86 backend emits validated scalar CFGs with backedges; source lowering covers return branches and a constrained `while`/`break`/`continue` subset; same-module direct `u32` calls execute on host ABI; aggregates and ownership/effects remain open) |
| **SV5** | Sotlas-owned object emission and freestanding/native linking for supported targets | 🟡 IN PROGRESS (ELF64 multi-object linking and bounded Windows PE images validated; Intel Mach-O images experimental; COFF/Mach-O relocatable objects and archives pending) |
| **SV6** | Compile a real application and the minimal kernel without the C11 backend | ✅ CERTIFIED (`tests/test_sotlas_sovereignty_sv6.py`) |
| **SV7** | Build the Sotlas compiler Stage 1 from Sotlas sources using Stage 0 | ✅ CERTIFIED (`tests/test_sotlas_sovereignty_sv7.py`) |
| **SV8** | Stage 1 builds Stage 2 with deterministic fixed-point/equivalence gates | 🟡 IN PROGRESS (hosted Stage1/2/3 determinism is certified, but the compiler executables are still built through emitted C + Clang + C driver; native module-by-module self-compilation is the active frontier) |
| **SV9** | Make the native compiler/backend the normal installed path; Python/C become optional legacy/reference tooling | 🟡 IN PROGRESS (the CLI defaults to the bounded native backend and fails closed, but packaging/bootstrap still depend on Python, Clang and the C host driver) |

The Stage 1/2 path now starts at `native_compiler/main.sotlas`; its C host
driver recursively loads the imported module tree before invoking the native
frontend. This is a real compiler-source generation chain, but it still
flattens modules into one source buffer and uses Clang plus a C host driver to
produce each executable. The separate C `selfhost` command still targets the
`sotlas_lite` tree and is not the SV8 pipeline.

## Sotlas 1.0 development strategy

Native self-hosting is a structural release requirement. Development also needs
a feature track that gives Sotlas its own systems-language identity; bootstrap
progress alone is not a complete 1.0 release. The tracks share typed frontend,
IR and backend contracts rather than introducing application-specific shortcuts.

The feature priorities are explicit `@system`/`unsafe` boundaries, ownership and
region lifetime guarantees, authority and device access, typed state transitions,
and deterministic execution for systems programs. Existing frontend tests are
evidence for their covered paths, not proof that all of these constructs already
have native backend parity. Each proposed 1.0 feature needs a stated supported
subset, positive execution examples, negative diagnostics and native lowering
evidence before it is advertised as a release guarantee. Relevant regression
oracles include `test_sotlas_unsafe_ffi.py`, `test_sotlas_ownership_soundness.py`,
the region release gates, the authority gates and the state/flow suites.

### Explicit bidirectional interoperability

The interoperability target is an explicit, bidirectional C ABI: external
programs can call exported Sotlas functions, and Sotlas can call explicitly
declared external functions. Using that binary calling convention does not make
a C compiler part of the normal Sotlas compilation path. Toolchains required to
build an application's foreign library are dependencies of that integration,
not evidence that Sotlas's compiler bootstrap is sovereign.

| Integration priority | Planned boundary | Evidence required before certification |
|---|---|---|
| C and Assembly | Explicit exported/external symbols and target calling conventions | Real callers and callees in both directions; parameter/result, layout, relocation and symbol tests |
| C++ | C-linkage bridge functions; C++ classes, templates and exceptions remain behind the bridge | Bidirectional bridge execution and explicit ownership/error handling; no unwinding across the boundary |
| Rust | C-linkage functions and explicitly compatible data layout | Bidirectional execution, layout checks and documented ownership/allocation/freeing |
| Objective-C | C ABI wrappers around Objective-C APIs and objects | macOS execution, object-lifetime contracts and platform symbol verification |
| Java, hosted only | JNI or Foreign Function & Memory integration with a Sotlas library | JVM-hosted examples and explicit lifetime/error contracts; no JVM requirement in the compiler or kernel path |

The ABI work must specify fixed-width scalars, Bool representation, aggregates,
pointer validity, callback lifetimes, ownership transfer, allocator/freeing
pairs and error propagation for each certified target. These are certification
requirements, not a declaration that the ABI is currently frozen or general.
The current FFI remains limited, as described in the READMEs and
`docs/safety_and_ffi.md`; the stability language in
`docs/interop_c_cpp_objc.md` describes the intended end state.

Release work proceeds in substantive blocks: close the structural CFG gate,
extend native module compilation, prove native Stage1 -> Stage2 -> Stage3,
validate clean native installation, and certify the agreed 1.0 feature and ABI
contracts. Reference Python/C paths may remain optional after native closure.

## SV1 contract

The first native Target IR representation lives under
`bootstrap/sotlas/native_compiler/backend/target_ir.sotlas`.

Its design deliberately avoids host-language maps and strings for SSA identity.
Values and blocks use stable numeric identifiers. Variable-sized instruction
inputs are represented as ranges into flat operand/phi/target tables. Functions
and blocks similarly reference flat instruction ranges. Source-facing names are
represented as source slices, which keeps the representation usable in hosted
and barecore environments without requiring a string runtime.

The initial opcode vocabulary mirrors the existing checked Target IR boundary:
stack allocation, load/store, integer constants, arithmetic, compare, phi,
calls, system operations, branches, returns and semantic-only ownership/state
operations. This is a representation contract, not yet a claim that the
Sotlas-written frontend lowers all of those operations.

### SV1 exit criteria

- [x] Target IR types and opcodes are represented in Sotlas source.
- [x] SSA values and block references do not depend on host-language objects.
- [x] variadic operands/phi inputs/targets have flat-table contracts.
- [x] semantic-only operations remain explicit instead of disappearing before backend selection.
- [x] the contract has no dependency on the legacy C emitter.
- [x] native AST/sema lowering creates this IR for the initial scalar subset.
- [x] differential tests compare the initial native constant/return stream with canonical Stage-0 Target IR.
- [x] the Sotlas-owned machine backend consumes the native representation for the declared single-block U32 subset.

### SV3 certified subset

`x86_64_scalar.sotlas` accepts one-block U32 functions with up to six SysV or
four Windows x64 parameters, constants, `add/sub/mul`, direct calls to another
function in the same module, and a direct return. It also accepts the declared
three-block choice CFG, with unsigned integer
comparisons (`==`, `!=`, `<`, `<=`, `>` and `>=`), scalar arithmetic and a
return in each arm. It uses stack slots and emits GNU/LLVM assembler text.
Tests assemble, link, and run both branch outcomes and a same-module call on
the host ABI. Calls are currently limited to direct `u32` calls with at most
six SysV or four Windows x64 arguments in one-block functions. Checked overflow
semantics, aggregates, indirect/external calls, wider integer types and general
CFG lowering remain outside these subsets.

The module emitter resolves each direct call against a function in the same
Target IR module and checks its `u32` result and parameter signature before
writing assembler. It also checks each parameter, arithmetic operand/result,
call operand/result, and returned value against the typed Target IR value table.
Negative native backend tests corrupt a call target and a call argument type;
both are rejected. Host integration tests execute the four-argument Windows
x64 path and the six-argument SysV path on their respective CI hosts.

## SV4 CFG foundation

`target_module_validate_cfg` checks flat table ranges, block-local unique IDs,
terminator placement, branch target membership, operand IDs, scalar parameter,
result, arithmetic, phi and return types, duplicate SSA definitions, and a
complete, duplicate-free phi entry for every predecessor. Native tests accept
branch and phi graphs and reject absent targets, incomplete/duplicate/non-edge
phi inputs and type mismatches. `target_module_validate_ssa_dominance` adds use
availability and reachable-block dominator checks for branches, merges and
loops. It uses caller-owned scratch storage and rejects functions above its
explicit 4,096-block bound. Tests exercise a diamond with `phi`, a loop
backedge and an invalid use from a branch that does not dominate the merge.
This remains partial frontend support, not arbitrary source control flow. It
lowers conditional-return functions and a constrained loop form with a bool or
unsigned comparison condition, with either one `break`/`continue` statement or
one nested `if` whose arms each contain `break` or `continue`, followed by a
return. The x86 emitter accepts ordered single-function scalar CFGs containing
constants, arithmetic, unsigned comparisons, `Branch`, `CondBranch` and
`Return`. It supports U32/Bool `Phi` values when each incoming edge comes from
an unconditional single-successor `Branch`; edge copies use temporary stack
slots so loop-carried values and parallel copies remain safe. Native tests
assemble and execute source-lowered backedge/exit paths, a Phi diamond and a
loop-carried Phi graph; invalid predecessor inputs are rejected. The emitter
requires callers to validate CFG and SSA dominance first and rejects Phi blocks
targeted directly by conditional edges. The frontend does not yet lower Phi.
Other loop bodies, general statement sequences, aggregate values,
ownership/effect runtime behavior and broader ABI parity remain open.

## SV5 object-writer foundation

`emit_elf64_scalar_function_object` writes an ELF64 little-endian x86-64
relocatable object directly from Target IR for a single `u32` function using
integer constants, `add/sub/mul`, unsigned comparisons, ordered basic blocks,
`Branch`, `CondBranch`, `Return`, and `u32`/`bool` `Phi` values fed by
unconditional predecessor branches (incoming values must be parameters or be
defined in that predecessor block), plus direct self-recursive `u32` calls
with up to six `u32` arguments under the System V ABI. Phi edge copies use temporary stack slots to preserve
parallel-copy semantics. Local branch displacements are patched after block layout; the
object has one function symbol and no relocations. Sotlas writes machine bytes,
symbol/string tables and section headers without C emission or an assembler.
Before encoding, it checks block/instruction ranges, terminator placement,
branch target membership, value types, and operation shapes. Tests compile both
outcomes of a conditional through the Sotlas ELF writer and its own executable
linker and run them natively; a hand-built phi diamond also emits an ELF object
and is exercised through a native caller on Linux. Corrupted branch targets
and non-predecessor phi inputs are rejected. A recursive countdown function is
emitted for the native caller test. Existing
tests inspect the ELF header, executable text section, exported symbol and
argument spill instructions. The object includes a `.note.sotlas.abi`
descriptor recording parameter count and the Bool-parameter bit mask. The
linker validates Bool arguments as zero or one. The SysV integration test
exercises all six integer argument registers (`edi`, `esi`, `edx`, `ecx`,
`r8d`, `r9d`) with a native C caller and checks the computed result. On Linux, a C caller
links and runs both zero-argument and parameterized objects as an independent
ABI comparison. Cross-object relocations, Windows COFF, Mach-O and general
freestanding image construction are not yet supported, so SV5 is not complete.

The `emit_elf64_scalar_module_object` path writes multiple single-block `u32`
functions into one Sotlas-authored ELF object. It supports up to six `u32`
parameters per function, integer constants, `add/sub/mul`, and direct calls to
any function in the same module when its signature has up to six `u32`
parameters. Calls are resolved to same-object `.text` offsets after function
layout is known, including calls to later declarations. Each function receives
a global symbol with its own offset and size during emission.
The symbol and string tables are generated directly. Tests inspect the second
symbol offset, link and execute the first function through Sotlas's tiny
linker, and call the symbols through a native C caller. Tests execute a call
from the third function to a six-argument helper and a forward call through the
Sotlas linker. Modules with more than six parameters, incompatible call
signatures, branches, or other unsupported operations fail closed; tests cover
forward-call execution and arity rejection. A separate CFG-object test now
emits a recursive countdown function. Cross-object relocations and general CFG
object emission remain open.

`link_elf64_scalar_executable` consumes the fixed-layout ELF object and emits a
minimal static Linux x86-64 executable. Its `_start` shim can load up to six
explicit `u32` arguments into the SysV integer argument registers, call the
first function, and exit with its `u32` result. The linker requires argument
count and Bool mask to match the `.note.sotlas.abi` descriptor and rejects
missing, excess or invalid Bool arguments. Tests link a six-argument sum and
check the result on Linux, and reject parameterized entries with missing
arguments or a Bool value outside 0/1. It
validates the ELF header, section-name indices, flags and alignments, symbol and
string tables, and fails closed on unsupported sections. Multiple input
objects, relocations, general symbol resolution, data sections, other operating
systems and linker scripts remain unsupported.

## SV2a implementation status

`bootstrap/sotlas/native_compiler/backend/lower_scalar.sotlas` now contains a
Sotlas-written AST-to-Target-IR lowering pass for integer scalar parameters,
decimal constants, `add/sub/mul` expressions, direct returns and one basic
block, plus a conditional whose two blocks return scalar expressions and whose
condition can compare `u32` parameters. Comparisons use the Target IR `Compare`
opcode with a validated predicate and boolean result. It writes deterministic
value IDs and flat parameter, operand,
target, instruction, block and function tables into caller-owned buffers. Unsupported
declarations, statement shapes, expression forms, types and buffer exhaustion
fail closed and clear the published module counts.

The Stage-0 contract gate type-checks the Target IR contract and lowering module
without calling the C emitter. A separate bootstrap integration test builds the
native frontend with Stage 0, calls the source-to-IR entry point, and checks the
flat table counts for positive arithmetic and a rejected division. It also
compares a parameter-return stream emitted by the native frontend with
canonical Stage-0 Target IR. This does not prove self-hosting and does not
execute the Target IR directly. The next Sotlas-written backend module,
`bootstrap/sotlas/native_compiler/backend/x86_64_scalar.sotlas`, consumes the
same flat tables for one-block `u32` functions with up to six SysV or four
Windows x64 parameters, constants, `add/sub/mul`, and a direct return. It also
executes the tested three-block bool choice CFG with arithmetic in each arm. Values
spill into stack slots, so this subset does not depend on a register allocator.
The integration test assembles and links both a constant-return function and a
parameterized arithmetic function with the available Clang toolchain, then runs
the resulting executables.

---

## SV2 Status: Frontend AST/Sema to Target IR Lowering (Scalar & Struct Subsets Certified)

Milestone **SV2** establishes native lowering from the Sotlas AST/sema frontend into the flat Target IR representation.

### Certified Subset (SV2a — Scalar & Struct Memory Operations):
1. **Types & Signatures:** Scalar integer types (`u8`, `u16`, `u32`, `u64`, `usize`, `i8`, `i16`, `i32`, `i64`, `isize`) and `bool`. Function parameter tables, external prototypes (`@extern(C)`), and typed returns.
2. **Statements & Bindings:** Local bindings (`let`), mutability, and assignment expressions (`=`).
3. **Expressions & Arithmetic:** Binary expressions (`+`, `-`, `*`), integer constants with range checks, and intra-module direct calls.
4. **Control Flow:**
   - Conditional branches (`if`/`else`) lowered to `CondBranch` and `Branch` blocks.
   - Constrained loop constructs (`while` with `break`/`continue` and nested conditional jumps).
5. **Aggregates & Memory Operations (NEW):**
   - **Struct Declarations (`StructDecl`):** Layout computation with field byte offsets and types.
   - **Struct Literals (`ExprStructLiteral`):** Lowers to stack allocation (`TargetOpcode::AllocStack`) and field initializations (`TargetOpcode::Store`).
   - **Field Access (`ExprFieldAccess`):** Lowers to typed memory loads (`TargetOpcode::Load`) via base pointer + field displacement.
   - **Field Mutation:** Lowers field assignment (`pt.x = val`) to memory store (`TargetOpcode::Store`).
6. **Target IR Invariants:** Deterministic numeric SSA value IDs, block IDs, and flat tables (`TargetInstruction`, `TargetOperand`, `TargetPhiInput`, `TargetBlock`), validated by `target_module_validate_cfg` and `target_module_validate_ssa_dominance`.
7. **Fail-Closed Guards:** Undeclared variables, type mismatches, unsupported operations, and buffer overflows strictly fail closed.
- **Validation Suite:** `tests/test_sotlas_sovereignty_sv2.py`; current certified behavior is anchored to the green CI baseline recorded at the top of this roadmap.

### Open Gaps for Full Self-Hosting (SV2b):
- **Enums:** enum declarations, scalar variants and path expressions are certified; payload variants and `match` remain open.
- **Arrays & Slices:** fixed arrays exist in constrained bootstrap forms; general indexing/slicing and dynamic slice values remain open.
- **Strings:** string literals and native `.rodata` symbols are certified; general string/slice manipulation remains open.
- **Impl & Methods:** constrained static and receiver method calls are certified, including typed `usize` calls; broader receiver/value forms remain open.
- **Module constants:** typed scalar integer `const` declarations now lower as immediates; non-integer/general constant evaluation remains open.
*Nota de Soberania:* SV2b is no longer blocked by the basic existence of enums/strings/methods. The active blockers are the richer expression/control-flow and memory forms used by the compiler itself.

---

## SV5 Status: Object Emission & Freestanding/Native Linking (ELF64 Certified, Multi-Platform Open)

Milestone **SV5** establishes autonomous object emission and static executable linking.

### Certified Subset (ELF64 Linux / Freestanding):
1. **Direct ELF64 Relocatable Writer (`emit_elf64_module_object`):**
   - Emits valid `ELFCLASS64`, `ELFDATA2LSB`, `EM_X86_64`, `ET_REL` objects.
   - Generates `.text`, symbol tables (`.symtab`), string tables (`.strtab`), section header tables, and `.note.sotlas.abi`.
   - Generates `.rela.text` with `R_X86_64_PLT32` and `PC32` relocations for external calls.
2. **Sotlas Static Linker (`link_elf64_executable` and `sotlas_native_link_objects`):**
   - **Single-Object Hosted:** Resolves local entry points (`main_entry`, `main`) at standard virtual address base `0x400000`.
   - **Freestanding Kernels:** Links freestanding binaries loaded at `0x100000` (1 MiB) with entry point `_start` without external linkers or runtime dependencies.
   - **Multi-Object Linking (`--link-objs`):** Concatenates `.text` segments across independently compiled modules, performs cross-object global/weak symbol resolution, and patches `R_X86_64_PLT32` / `PC32` displacements.
   - **Order Invariance:** Verification proves that linking order (e.g., `[A, B]` vs. `[B, A]`) yields identical symbol resolution and correct call displacements.
3. **Fail-Closed Guards:** Missing input objects, undefined external symbols, duplicate strong symbols, and non-existent entry points fail closed.
- **Validation Suites:**
  - `tests/test_sotlas_sovereignty_sv5.py` (9/9 tests passing).
  - `tests/test_sotlas_sv5a_multi_object_link.py` (multi-object ELF64 cross-relocation verification).

### Open Gaps for Full Multi-Platform Sovereignty:
- **Windows PE/COFF:** Emissão de arquivos `.obj` no formato COFF e linker para `.exe` (PE32+) com diretório de importações e tabela IAT.
- **macOS Mach-O:** Emissão de `.o` no formato Mach-O 64-bit e comandos `LC_SEGMENT_64`.
- **Arquivos e Bibliotecas Estáticas:** Suporte a arquivos de biblioteca estática (`.a` / `.lib`).
- **Limites de Capacidade Fixa:** Escalar buffers fixos (atualmente 16 objetos, tamanhos estáticos de tabelas).

---

## SV6 Certification: Real App and Minimal Kernel Native Compilation

Milestone **SV6** establishes the complete sovereign native pipeline without the C11 backend:
```text
Sotlas Source
  -> Sotlas Frontend / AST Lowering
  -> Sotlas Target IR (SSA flat tables)
  -> Sotlas x86-64 Machine Backend
  -> Sotlas ELF64 Object Writer (ELFCLASS64, ELFDATA2LSB, EM_X86_64, ET_REL)
  -> Sotlas ELF64 Static Linker / Freestanding Image Builder (ET_EXEC)
```

### SV6 Audit Evidence
- **Real Multi-Function Application (`app::calculator`):**
  - Compiles multiple interdependent functions (`multiply_offset`, `compute_metric`, `main_entry`).
  - Emits valid ELF64 relocatable object without invoking GCC/Clang or C11 backend.
  - Links directly to a static ELF64 executable (`ET_EXEC`) via Sotlas native linker.
- **Freestanding Minimal Kernel (`kernel::minimal`):**
  - Compiles freestanding kernel source containing `@system pub fn _start() -> u32` and helper functions.
  - Emits valid freestanding ELF64 relocatable object.
  - Links to a freestanding binary image with base address `0x100000` (1 MiB) without external linkers.
- **Fail-Closed Contract Guards:**
  - Non-existent symbols, invalid headers, and malformed inputs are strictly rejected.
- **Validation Suite:** `tests/test_sotlas_sovereignty_sv6.py` (3/3 tests passing).

---

## SV7 Certification: Stage 1 Native Compiler Build from Sotlas Sources

Milestone **SV7** proves that the Stage 0 compiler builds the Sotlas Stage 1 compiler binary directly from Sotlas source code files under `bootstrap/sotlas/native_compiler`:

### Source Manifest:
1. `lexer.sotlas`: Lexical analyzer and scanner.
2. `token.sotlas`: Token representation and constructors.
3. `parser.sotlas`: Recursive-descent parser.
4. `sema.sotlas`: Semantic analyzer and type checker.
5. `backend/target_ir.sotlas`: Native SSA Target IR flat contracts.
6. `backend/lower_scalar.sotlas`: AST-to-Target-IR lowering.
7. `backend/x86_64_scalar.sotlas`: Machine code emission.
8. `main.sotlas`: Compiler driver and entry points (`sotlas_native_compile`, `sotlas_native_compile_object`, `sotlas_native_link_executable`).

### SV7 Audit Evidence
- **Stage 1 Executable Build:**
  - `build_stage1_native_compiler` in `tools/sotlas/bootstrap_pipeline.py` builds `build/sotlas_stage1.exe`.
  - Binary size > 50 KB, executes standalone.
  - Invocations with `--version` report `Sotlas 1.0.0 (Native Stage 1)`.
- **Stage 1 Native Compilation:**
  - Compiles real application to `.o` and links to static executable `.bin`.
  - Compiles freestanding kernel to `.o` and links to freestanding `.bin`.
- **Verification Routine:**
  - `verify_stage1_compiler` executes clean build and self-test verification cycle.
- **Validation Suite:** `tests/test_sotlas_sovereignty_sv7.py` (5/5 tests passing).

---

## SV8 Status: Hosted Fixed-Point Certified; Native Build-Chain Closure In Progress

Milestone **SV8** currently certifies deterministic Stage1/Stage2/Stage3 frontend and native-output equivalence, but **does not yet certify a C/Python-free compiler build chain**. Stage2 and Stage3 executables are still produced from emitted C with Clang plus the C host driver.

### Active implementation queue
- **Current item — SV8.7b2:** CI #1119 confirmed monotonic progress: the real `target_ir.sotlas` blocker moved from the enclosing function at 289 to the actual guard clause at `295:5`. This cut adds leading guard-return CFG lowering plus contextual pointer-null equality/inequality; `null` is represented only as a zero Pointer constant, without enabling integer-to-pointer casts. CI #1120 showed the guard still stopped at 295 because `return false;` was incorrectly sent through decimal-integer literal lowering. The repair adds only certified Bool constants (`false=0`, `true=1`).
- **Current item — SV8.7b3:** CI #1121 advanced the real-module blocker from 295 to `target_ir.sotlas:314:5` in `target_cfg_block_has_edge`. The condition reads `block.instruction_count` from a `block: &TargetBlock` parameter. CI #1122 showed the struct metadata fix was necessary but not sufficient: boolean OR lowering also classified `ExprFieldAccess` as impure, so the compound guard was rejected before expression lowering. This repair is deliberately narrow: a field read is considered pure only when its base expression is pure.
- **Current item — SV8.7b4:** CI #1123 advanced the real-module blocker to `target_ir.sotlas:318:5`: `let terminator: TargetInstruction = unsafe { *(instructions + terminator_index) };`. Instead of opening general struct-by-value SSA/ABI, this cut keeps the bootstrap pattern as a certified typed pointer alias: the local records the pointee struct identity and subsequent field reads remain typed Load operations from that address.
- **Completed locally — SV8.7b5:** the real-module blocker moved from `target_ir.sotlas:324:5` to `357:5`. The native CFG subset now lowers a search loop whose counter starts as a local, whose body first loads one `u32` through an explicit unsafe pointer expression, and whose match branch returns early. The loop counter remains a Phi value; the body binding is removed from the exit scope. A native ELF gate covers this shape. CI certification is pending.
- **Completed locally — SV8.7b6:** the real `target_ir.sotlas` native probe advanced from `357:5` to `452:5`. The value-definition scan now uses separate parameter and block searches, so each loop fits the certified native CFG subset. A typed Bool local from a helper call is accepted as the loop's early-return guard, and the dominator bit test widens loaded bytes to `u32` before applying the already supported bitwise operation. The next blocker is the nested definition search in `target_value_dominates_point`. This remains a bounded compiler-bootstrap subset; CI certification is pending.
- **Completed locally — SV8.7b7:** definition lookup and the initial value-table scan are now separate Sotlas functions. The real-module probe reaches `target_module_validate_cfg` at its function-table loop. That validator, followed by call validation and SSA dominance, contains nested loops and mutable state beyond the current native CFG subset. Full native compilation of `target_ir.sotlas` is still open; this change does not claim Stage1 self-compilation.
- **Completed locally — SV8.7b8:** the certified native search-loop body now accepts a `u64` or `usize` scalar local as well as the earlier `u32`, `bool`, and typed struct aliases. A `u64` payload search emits a native ELF object, with a host execution gate on Linux. The real `target_ir.sotlas` probe remains at the CFG function-table loop; general nested CFG lowering is still required for full-module compilation.
- **Completed locally — SV8.7b9:** the native scalar path now lowers unary Boolean negation through a typed equality comparison and permits pure nested negations in `&&`/`||`. Search-loop payloads and comparisons also cover `u8` and `u16`, needed for dominator byte-buffer work. Positive native ELF and Linux execution gates plus a negative integer-negation gate cover these capabilities. The complete `target_ir.sotlas` native object still stops at the CFG function-table loop; nested CFG lowering remains the blocking work.
- **Completed locally — SV8.7 call ABI (2026-10-07):** the native lowerer retains up to 16 scalar or pointer call operands in source order, including nested argument expressions and void calls. The ELF x86-64 backend reads incoming SysV stack arguments, reserves an aligned outgoing area, writes arguments seven onward, and restores the stack after each call. The nine-argument `target_module_validate_cfg` call now lowers; the real `target_ir.sotlas` probe traverses call validation and stops in SSA dominance at the byte-buffer reachability check. Native emission of the full module and a native Stage 2 build remain open. The added test compiles a nine-argument nested call on Windows and runs it on Linux.
- **Completed locally — SV8.7 structural CFG block (2026-10-07):** the real native object probe now traverses all of `target_module_validate_cfg`, including the nested instruction scan and its duplicate/range/terminator/Phi/operand checks. It next rejects the nine-argument call to that validator from `target_module_validate_calls` at `1149:13`; the bounded call ABI still accepts at most six arguments. This is a structural lowering milestone, not native emission of the complete module or a native Stage 2 build. The new recursive CFG path supplies short-circuit branch edges, typed stack storage for mutable scalars, lexical loop scopes and innermost break/continue targets. Nested field metadata includes natural alignment and inline aggregate fields, and the x86 emitter gives each local allocation a distinct function-wide stack range. Ten new gates cover native execution and rejection boundaries in `tests/test_sotlas_native_structured_cfg.py`, including explicit and implicit void returns and byte-sized Bool accesses that preserve adjacent fields. These ten gates and all six SV8 gates pass locally. The real-module regression gate now requires progress beyond the entire CFG validator, and SV8 checks identical nested-CFG objects across all three hosted stages. General aggregate return ABI and stable cross-language ABI are not certified by these tests. CI certification is pending.
- **Certified green baseline (2026-10-07):** CI #1134 on `f3ed10ec7e6b846e36b4c7b23e2ef9975058bc6a` passed the complete Linux/Windows/macOS matrix. The real `target_ir.sotlas` Stage 1 probe reaches `target_module_validate_ssa_dominance` at `1313:68`, where a short-circuit compares a dereferenced `u8` reachability flag to zero. Stage 1 still has not emitted the complete real module or built Stage 2 by itself.
- **Current item — SV8.7 SSA typed-memory guards:** resolve the exact scalar pointee type through an explicit `unsafe` expression when lowering a comparison. The new isolated native object+execution gate covers `u8` and `u16` pointer reads and verifies that `||`/`&&` skip a null pointer on the unused branch. Keep the complete real SSA-dominance verifier, including nested loops and byte-buffer operations, as the next substantive object gate; do not claim closure on the strength of one condition.
- **SV8.7 CI regression correction (2026-10-07):** CI #1135 failed the newly added single-while `u8`/`u16` guard test on Linux, Windows and macOS at the loop statement, while the previously certified tests remained green. This was not an SSA gate regression: `cfg_required` selected the legacy eager search-loop lowerer because it counted only one `while`, despite `&&`/`||` containing a potentially trapping `unsafe` read. The repair selects structured CFG for a one-loop function when its Boolean guard is not pure, preserving branch-based short-circuit semantics. The original single-loop fixture and its native execution requirements remain; the test description is clarified, not relaxed. Keep CI #1134 / `f3ed10ec7e6b846e36b4c7b23e2ef9975058bc6a` as the certified green baseline until the repair's complete matrix succeeds.
- **Completed locally — SV8.7 real Target IR object:** Stage 1 now emits one ELF object for the complete `target_ir.sotlas` source, including CFG, call and SSA validators and its BSS globals. Global-array-to-pointer casts are limited to matching element types. The ELF emitter handles up to 1,024 blocks and 2,048 branch patches per function; the real validator uses 428 blocks. Tests require the complete object and cover a valid global array cast and a mismatched-pointee rejection. This certifies object emission locally, not linking the compiler as native Stage 2 or a fixed point. CI certification is pending.
- **Completed locally — SV8.8 structured control in library methods:** a condition with a potentially unsafe `&&`/`||` now selects structured CFG even without a loop, so its unused branch is not evaluated. Field stores nested under `if` use the same typed store lowering as straight-line methods. Native object gates cover both forms, with Linux execution checks for the null-pointer short circuit and branch-local field mutation. The next compiler-wide gate must resolve imported type declarations across modules; compiling `sema.sotlas` alone stops at its imported `AstKind` parameter and does not measure complete-project self-hosting. CI certification is pending.
- **Completed locally — SV8.9 native import entry path:** Stage 1 `--compile-obj` now loads the entry source and its transitive imports through the existing module resolver before invoking the Sotlas frontend and Target IR lowerer. Gates compile a two-file function call and an entry that imports the complete real `target_ir.sotlas` into one ELF object; a missing import fails without writing an object. This uses the current C host loader, so it resolves a source-visibility blocker but does not close native Stage 2 bootstrap or remove the hosted driver. With imports active, native probes of `ast.sotlas` and `sema.sotlas` both reach `token.sotlas:135:9`, where the `Token::new` aggregate return needs lowering. The remaining compiler modules still need native lowering and a fully native build/link gate. CI certification is pending.
- **Completed locally — SV8.10 native aggregate return ABI (2026-10-08):** internal Sotlas functions return declared structures through a final hidden Pointer parameter backed by caller-owned stack storage. Return paths copy typed fields, nested structures and inline zero-initialized `u8` arrays of 1–256 elements into that destination. Calls preserve source argument order; the destination can use the SysV stack-argument path. Structure parameters passed by value receive separate copies. Foreign aggregate signatures are rejected because this internal convention does not implement the C aggregate ABI. Gates execute forwarding, branch returns, nested fields, independent return buffers, value-parameter mutation, a seventh hidden argument, and a 128-byte array with surrounding sentinels. Stage 1 now emits complete native ELF objects for the real `token.sotlas` and `ast.sotlas` modules, and their `Token::new` and `AstNode::new` constructors execute natively through imported source modules. Subsequent probes reach `lexer.sotlas` Boolean-return lowering and a loop in `sema.sotlas`; compiler-wide native Stage 2 remains open. The Windows execution harness resolves `main_entry` from the ELF symbol table so it also tests objects whose helper functions precede the entry. CI certification is pending.
- **Completed locally — SV8.11 native Lexer and expression CFG (2026-10-08):** built on the user-confirmed green `f25c20b` baseline, Stage 1 now emits the complete real `lexer.sotlas` module as an ELF object. Native execution checks `next_token` on one punctuation byte followed by EOF, including token kind and source span. Every represented `while` uses structured CFG; `&&` and `||` also produce Boolean values for returns, locals, assignments and call arguments through branch stores and a typed join load. Tests verify skipped side effects and skipped null-pointer reads. Additional lowering covers nested field reads/stores, aggregate replacement, precise scalar method-result types, void instance/static calls, same-pointee casts of addresses of stack-backed locals, and bounded negative decimal `i64` literals including the minimum value. Direct aggregate call returns forward caller-owned output storage instead of creating and copying another aggregate at each return site. A production-source prefix of `sema.sotlas`, including `same_declaration_name`, executes natively; the full Sema probe now reaches its ordered signed comparison at `digit < 0`, which remains rejected. Complete native Sema/Parser/driver compilation and native Stage 2 bootstrap remain separate open gates. CI certification is pending.
- **Sovereignty metric:** application/kernel native gates are C/Python-free; compiler bootstrap gates remain hosted. Current tracked reduction is 40% eliminated / 60% remaining for both Python and C until a native Stage1→Stage2 build gate closes.

### SV8.12 — Native Parser/Sema and executable frontend (2026-10-08)

Stage 1 emits complete ELF objects for both production `parser.sotlas` and
`sema.sotlas`. Signed `i64` ordering uses x86 signed condition codes, including
comparisons between the minimum and maximum values; unsigned ordering keeps its
unsigned condition codes. Mixed signed/unsigned comparisons and ordered pointer
comparisons remain rejected.

Aggregate lowering now handles a returned pointer dereference, stores through
typed aggregate pointers, fields of returned structures, and discarded aggregate
call results. Struct-valued field bindings receive independent copies. Global
zero-initialized struct arrays retain their exact element identity and stride;
casts to another struct, nonzero initializers and overflowing sizes are rejected.
The Parser needs larger bounded flat tables: 32,768 instructions, 65,536 operands
and 2,048 call patches. Other existing resource limits remain active.

`bootstrap/sotlas/native_examples/frontend_native.sotlas` compiles and
links with the Sotlas-owned backend into an executable containing the real
Lexer, Parser and Sema. It validates an embedded Sotlas program using native
machine code. Local Ubuntu/WSL execution returned zero for valid source and four
for a `u32` return overflow, without Python or a C runtime participating in that
execution. The checked-in gates run these paths on Linux and compile/link them
on the other CI hosts.

Six of the ten modules in the current bootstrap source manifest now emit full
native objects: Token, AST, Lexer, Parser, Sema and Target IR. This is a module
emission count, not an effort percentage or native Stage 2 certification. The
lowerer, machine/object/linker backend and driver still need native compilation
and integration before Stage 1 can produce a compiler executable without the
hosted bootstrap. The optional C emitter remains in the existing source manifest.
CI certification for this change is pending.

### SV8.13 — Inline integer-array fields (2026-10-08)

The native subset now lowers inline fields containing 1–256 elements of `u8`,
`u16`, `u32`, `u64` or `usize`. Zero-repeat initialization, natural alignment,
typed copies and nested field addresses preserve each element's width and
stride. Field-array reads and writes use checked `IndexAddr`; native execution
gates require an illegal-instruction trap for both reads and writes past the
bound, including an index larger than 32 bits. Method-based updates and copying
the containing struct are execution gates as well.

Boolean expressions inside `unsafe` wrappers use the same lazy CFG as other
conditions, with gates covering comparison of raw byte loads and a skipped null
dereference. Scalar global-array stores remain covered when structured CFG is
selected. Floating-point fields, oversized inline arrays and general local
array storage are still outside this native contract.

This advances prerequisites for porting ScalarLowering's table fields. Full
native emission of `lower_scalar.sotlas` is still blocked by pointer
requalification in its source-writing helper; `x86_64_scalar.sotlas` reaches
its narrow integer-shift helper. Neither module is counted as complete, and
the native Stage 2 compiler gate remains open. CI certification is pending.

SV8.11 also preserves the textual assembly contract for its scalar subset: the emitter validates CFG ranges, follows each block's instruction slice instead of assuming physical block order, and accepts the canonical no-result conditional-branch marker while still requiring a Bool condition operand. Assembly gates retain native execution and verify the new loop-header backedges. The previous eager-only rejection fixtures now execute call-bearing and divide/modulo-bearing short-circuit expressions; signed division, incompatible pointer casts and unsupported narrow arithmetic remain rejection gates.

### SV8.14 — Pointer qualifiers, scalar references and narrow shifts (2026-10-08)

The native lowerer preserves addresses when changing pointer qualifiers with
the same scalar pointee or exact struct identity. Cross-type reinterpretation,
integer-to-pointer conversion and nested-pointer casts remain rejected. Native
execution covers scalar and aggregate updates through the converted pointers;
raw dereferences retain their unsafe requirement.

Scalar reference types such as `&mut usize` now supply the correct pointee type
for loads, stores, comparisons and pointer offsets. This closes the writer's
cursor helpers without treating a reference-valued offset as an integer.
Unsigned `u8` and `u16` shifts accept constant counts below their bit width.
The object emitter independently checks the constant definition and normalizes
both the input and output width. Dynamic counts and counts at or above the
width fail closed; narrow addition and other unsupported arithmetic remain
outside this contract.

The native execution gate compiles the actual byte/storage helper definitions
from `x86_64_scalar.sotlas`, exercising cursor updates and capacity failures.
Its unused Target IR import is removed only in the isolated test fixture to
avoid importing unrelated large validator frames. The complete helper slice
with Target IR also linked and executed successfully on local Linux via WSL.
Windows execution of that larger imported slice still needs stack-frame work:
the backend currently reserves module-wide value storage in each function.

The full writer probe now reaches the local `block_offsets` array in
`emit_elf64_scalar_function_object` (source line 510). The full lowerer reaches
its local digit array in `append_synthetic_str_symbol` (source line 115).
General local-array storage and the digit helper's narrow addition remain
connected blockers. Neither module
is counted as complete: six of the ten manifest modules emit native objects,
and the fully native Stage 1 -> Stage 2 build remains open. These are local
results; certification of this commit belongs to the subsequent CI run.

Local regression evidence: the full Windows suite ran 2,628 tests with no
failures and 33 skips. Pointer qualifier, scalar reference and narrow-shift
fixtures also executed as Sotlas-linked ELF binaries on Linux via WSL. This is
not a claim that the full Linux or macOS workflow matrix ran locally.

### SV8.15 — Bounded native local scalar arrays (2026-10-08)

**Certified baseline:** CI #1148 on `c0e99af8d9776c759260ffacbe0d060a25f228e4` completed successfully on Linux, macOS and Windows, including Python 3.10–3.12, native gates, package builds and the nightly toolchain snapshot. The module-emission gate covers **six of ten** bootstrap manifest modules: Token, AST, Lexer, Parser, Sema and Target IR. This is **not** six of ten native bootstrap stages.

**Current implementation cut:** bounded zero-initialized local arrays of scalar elements (`u8`, `u16`, `u32`, `u64` and `usize`, represented by the native U64 slot). They use a distinct `AllocStack` region and typed `IndexAddr` for both reads and writes; the object backend traps on out-of-range indices, including dynamic indices. Every element is explicitly initialized through typed native stores, so no uninitialized bytes are exposed as zero. Array metadata follows lexical local bindings, not global names. This initial contract accepts 1–256 elements initialized with `= 0`, and rejects nonzero fills, oversized arrays and unsupported element types without emitting an object. Existing struct inline arrays and global arrays retain their previous contracts.

**Regression evidence for this cut:** `tests/test_sotlas_native_structured_cfg.py` now covers mutable `u8`/`u16` arrays in a structured loop, zeroed untouched elements, native execution on supported hosts, out-of-bounds read/write traps on Linux, and fail-closed initializers/counts. CI certification of this commit is pending; do not promote it until the whole matrix is green.

**Next source closure:** native `lower_scalar.sotlas` still requires its `u8` digit arithmetic and any additional unsupported constructs exposed by the full-module object gate; native `x86_64_scalar.sotlas` still requires its writer's larger local tables, deterministic frame sizing and all remaining machine emission constructs. The current initial 256-element array limit is not a claim that those complete modules now compile. Keep the **Stage1→Stage2 native executable build and Stage2→Stage3 fixed-point** as subsequent distinct gates. Python/C elimination remains the roadmap estimate **40% completed / 60% remaining** pending actual native compiler bootstrap.

**SV8.15 matrix repair (2026-10-08):** CI #1149 (`b61d87d41c021f8491d3e814ad8ceee134dbbf53`) failed three new local-array checks across Linux, macOS and Windows; previously certified tests remained green. The two out-of-bounds subcases compiled native ELF objects but their test asserted an incorrectly escaped ELF magic byte literal. The positive `u8`/`u16` case reached its return expression and was rejected because the native cast type resolver did not yet recognize `ExprIndex` on local arrays. The repair preserves all native execution, bound-check and fail-closed gates, corrects the ELF signature assertion, and derives indexed-element type from the existing scoped local-array metadata. **Do not promote baseline #1148** until the complete repair matrix succeeds; native emission of `lower_scalar.sotlas` and `x86_64_scalar.sotlas` remains open.

### SV8.16 — Native narrow unsigned arithmetic for the self-hosting digit writer (2026-10-08)

**Certified baseline:** [CI #1150](https://github.com/HPinho/sotlas_dev/actions/runs/37863329452) on `0aa387bfb9992d37b8372a9b593cca684227d719` passed the full Linux, Windows and macOS workflow matrix after the local-array repair. This supersedes #1148 as the regression baseline. The six complete real-module ELF object gates (Token, AST, Lexer, Parser, Sema and Target IR) remain the last verified module count.

**Current cut — SV8.16:** lower native unsigned `u8` and `u16` `+`, `-` and `*` through typed Target IR. The x86-64 object emitter uses the existing 32-bit arithmetic encoding and explicitly masks the result with `0xff`/`0xffff` before writing the SSA value slot, certifying modulo-`2^8`/`2^16` results instead of retaining overflow bits. Signed `i8`/`i16` arithmetic is still rejected. Existing narrow bitwise and constant-shift contracts remain unchanged. Positive Linux/Windows native-execution tests exercise add/sub/mul at both width boundaries; an additional fixture combines bounded stack-local `u8` arrays, the real `((value % 10) as u8) + 48` decimal-digit expression, and a structured loop. Negative tests retain signed narrow arithmetic rejection.

**Actual self-hosting blocker:** `append_synthetic_str_symbol` in `lower_scalar.sotlas` uses exactly this narrow digit arithmetic. This cut resolves that arithmetic capability, **but does not claim the complete real lowerer emits an ELF**. The next native module gate must compile the entire imported `lower_scalar.sotlas` and the actual `x86_64_scalar.sotlas`, surfacing any remaining unsupported forms and stack-frame/table capacity limits. No extra modules are counted until a complete real-module object is verified in CI.

**Stage closure:** the native Stage 1 → Stage 2 compiler executable and Stage 2 → Stage 3 native fixed point remain separate, open gates. The roadmap-wide Python/C dependency reduction estimate remains **40% eliminated / 60% outstanding**, not a per-module or per-stage percentage. CI certification for SV8.16 is pending; promote the baseline only once every matrix job is green.

### SV8.17 — Full-width synthetic symbols and real backend module probes (2026-10-08)

**New certified regression baseline:** [CI #1151](https://github.com/HPinho/sotlas_dev/actions/runs/37867363283) on `a501e1ea474ef97fc430cfa18be7862cb9a3e0d8` passed the complete Linux, macOS and Windows workflow matrix. It certifies SV8.16's native unsigned narrow arithmetic, including the digit-expression fixture, and supersedes #1150.

**Production correctness fix:** `ScalarLowering::append_synthetic_str_symbol` previously buffered decimal digits in `[u8; 16]`. On 64-bit targets, a `usize` can have 20 decimal digits; IDs with more than 16 digits would overflow that buffer. The implementation now writes digits directly to their destination range in reverse order and reverses that range in place. This removes one temporary array, retains `_str_<decimal-id>` encoding and supports the full `u64` value range (provided the caller's existing destination buffer has sufficient capacity). The method still uses the existing source-extension allocation contract; this patch does **not** add or certify a new output-buffer-capacity parameter.

**Production-source execution gate:** `test_real_lowerer_symbol_writer_supports_all_usize_digits` extracts the *unchanged production method body*, supplies only the source field it uses, compiles it through Stage 1 into ELF and verifies `0`, `12345` and `18446744073709551615` (20 digits) without changing how the compiler formats symbols. Linux additionally links and executes the object; other hosts check native object emission. This is a real method gate, **not** full-module compilation.

**Complete-module observability:** the new non-promoting `test_real_backend_modules_report_next_native_gate` runs Stage 1 against complete `lower_scalar.sotlas` and `x86_64_scalar.sotlas` directly. It records the next diagnostic if native lowering still rejects a module, verifies no partial ELF was published, and verifies ELF magic if the module succeeds. A diagnostic probe must never be counted as a completed module. The full native object and execution/link gates remain required before adding either module to the current **6 of 10** count. This cut's CI certification is pending.

**Next item — SV8.18:** use the new whole-module diagnostics to eliminate connected lowering and stack-frame blockers, certify complete native ELF objects for the actual lowerer and x86 writer, and integrate them into a Stage 1 → Stage 2 native compiler executable. Then prove Stage 2 → Stage 3 with a true native fixed-point check. Estimated mandatory Python/C dependency reduction stays at **40% eliminated / 60% remaining** until those native bootstrap gates close.

**SV8.17 matrix regression repair (2026-10-08):** CI #1152 (`27150278ac6915fff72f6889d02641b5abfd0176`) failed **one new test** on each Linux, Windows and macOS lane; other tests remained green. The unchanged production symbol writer's isolated native fixture failed at merged-source `1598:33`, corresponding to the assignment `g_extended_len = g_extended_len + name_len` within its unsafe block. Stage 1 already supports loading scalar BSS globals but its structured CFG assignment path only recognized mutable local bindings. The repair creates a relocatable symbol-backed pointer for a **module-level mutable scalar**, uses the BSS declaration's exact scalar type for the RHS and store, and requires the module declaration's `mut` flag in the AST. Array/global-aggregate stores and immutable scalar globals remain outside this path. The type inference path now recognizes existing scalar BSS declarations in conditions/casts. New gates compile the real production method (including 20-digit `usize` IDs), link and execute a scalar-global increment on Linux, check portable ELF output, and reject an immutable scalar-global assignment without creating an object. This does not weaken any prior native tests or claim full-module compilation.

The non-promoting #1152 probes also recorded the full-module next blockers: `lower_scalar.sotlas:5282:33` and `x86_64_scalar.sotlas:2369:9`. The current certified regression baseline remains **CI #1151 / `a501e1ea474ef97fc430cfa18be7862cb9a3e0d8`** until the repair matrix completes successfully. Next item remains **SV8.18 native complete backend objects**, followed by native Stage 1 → Stage 2 and Stage 2 → Stage 3 fixed point. Mandatory Python/C dependency elimination stays estimated at **40% completed / 60% remaining**.

### SV8.18 — Complete native lowerer and x86 writer (2026-10-09)

Local Stage 1 now emits complete ELF64 objects for the actual
`lower_scalar.sotlas` and `x86_64_scalar.sotlas` sources. The previous diagnostic
probe is a mandatory regression gate: either failure rejects the change.
Representative lowerer, object-writer and linker entry symbols must be present.
This raises the locally verified manifest count from **6 to 8 of 10 modules**;
CI certification of this advance is pending.

The connected compiler changes are:

- Aggregate metadata tracks 256 fields with explicit rejection on exhausted
  field or struct budgets. Initialization tracking uses the same field budget;
  fields are no longer silently omitted after the old limit of 128.
- Declared pointer types are retained in field metadata. Stores through
  dereferenced aggregate pointer fields and by-value aggregate arguments use
  exact struct identity. Indexed scalar widths propagate through arithmetic,
  casts and global-array reads; enum paths retain their U32 discriminant.
- The native SysV contract accepts 24 machine parameters, including a hidden
  aggregate result pointer. Register arguments, stack arguments, 16-byte call
  alignment and ELF Boolean signature masks use the same bound. More than 24
  parameters remain rejected.
- Zero-initialized local scalar arrays accept up to 4,096 elements. Arrays
  larger than 16 elements initialize through a bounded CFG loop instead of
  unrolled element stores. Checked indexing and exact-pointee pointer casts
  remain enforced. Inline struct arrays still have their separate 256-element
  limit; general aggregate local arrays are not part of this contract.
- Production machine frames use each function's value range rather than every
  value in the module. Parameters, arithmetic, memory accesses, call results,
  return values and Phi edge copies use the same relative slot mapping.
  Large frames touch each stack page without a C runtime helper, preserving
  SysV argument registers. Execution gates cover 512 recursive calls with many
  unrelated functions and repeated initialization of 32 KiB local arrays.
- IR buffer capacities and their physical storage grow together for the real
  compiler workload. Production ELF tables accept 256 functions, 2,048 blocks
  per function and 4,096 branch/call patches, with explicit capacity checks.
- Nested branches select structured CFG. The existing scalar Boolean assembly
  profile and hosted Stage 1/2/3 equivalence remain regression contracts.

Execution fixtures compile the complete lowerer and invoke its actual
20-parameter constructor, verifying late fields and zeroed metadata arrays.
The complete writer fixture executes byte/word helpers and writes and reads
an ELF section header. Both fixtures, large-array initialization and an
aggregate-pointer update execute on Windows and as Sotlas-linked Linux ELF
programs via WSL. macOS remains an object-emission gate for these fixtures.

This closes native object emission for these two production modules, not the
fully native compiler generation chain. The installed driver, the remaining
manifest sources and a native Stage 1 -> Stage 2 executable still require
closure. Stage 2 -> Stage 3 must then prove a native fixed point. The previous
mandatory Python/C dependency reduction estimate remains unchanged until those
build-chain gates pass; the hosted bootstrap is still required today.

Local regression evidence: the final Windows suite ran **2,647 tests with no
failures and 33 skips**. The four Linux ELF execution fixtures described above
also passed via WSL. The full Linux/macOS CI matrix was not run locally.

### SV8.19 — Integrated native compiler execution (2026-10-09)

`bootstrap/sotlas/native_examples/pipeline_native.sotlas` links all eight core
compiler modules into one native image. During execution it tokenizes and
parses embedded Sotlas source, checks types, lowers to Target IR, emits an
ELF64 object and links an executable using the production implementations.
The workload includes a scalar parameter, multiplication and an internal call.
No Python parser, C emitter or C runtime participates in that execution.

The generated ELF is 248 bytes and has FNV-1a fingerprint
`14630699014357374998`. Regression tests regenerate the reference through the
Stage 1 producer and run its `answer` entry, which returns 42. The native image
requires the complete generated ELF to match the reference length and
fingerprint. Changing the embedded call argument rejects the old fingerprint;
invalid syntax fails at the parser boundary. Linux executes these gates;
Windows and macOS compile and link the same artifacts. Local WSL execution
also validates the integrated pipeline. This checksum is a deterministic
regression oracle, not cryptographic proof or general compiler equivalence.

Combining the production modules exceeds the previous single-module budgets.
The native ELF writer now accepts 512 functions, and both checked capacities
and physical buffers grow together to 65,536 values and 131,072 instructions.
Other capacity and acceptance checks remain in force. The execution fixture
supplies smaller caller-owned buffers for its embedded workload and fails
closed at each pipeline boundary.

This advances native compiler integration without declaring self-host closure.
Input is embedded and output stays in memory: argument handling, file I/O,
imports and an installed native driver remain separate work. The complete
compatibility `main.sotlas` probe still fails, and Stage 1 -> Stage 2 native
self-build and Stage 2 -> Stage 3 fixed point remain open. The hosted bootstrap
continues to produce the initial compiler. CI certification is pending.

Local verification: the final Windows suite ran **2,649 tests without failures,
with 33 skips**. WSL execution returned 0 for the integrated pipeline, 10 for
changed input, 3 for invalid syntax and 42 for the reference program. Windows
native fault fixtures suppress error-reporting dialogs in their child process
while retaining the exact expected NTSTATUS assertions.

### SV8.20 — Native Linux file driver and self-build fixed point (2026-10-09)

`bootstrap/sotlas/native_driver/linux.sotlas` compiles real files to ELF objects
or executables. Its process startup receives Linux argc/argv through a checked
ELF ABI flag. The production lowerer and writer implement typed kernel read,
write, open and close operations directly, including signed error results.
No libc, Python process, C emission or external linker participates in this
driver's compilation or self-build execution.

Native self-compilation exposed two production defects: hexadecimal binary
string escapes were not decoded, and data relocation indices could be shifted
as if they were external-call indices. Both are repaired, with positive and
negative gates. The complete compiler core plus driver now self-compiles to
the same ELF object as the hosted producer. The native seed builds Stage 2;
Stage 2 builds Stage 3; both executable images are identical. This is a native
Linux generation chain, distinct from the older hosted C-emission fixed point.

Local WSL evidence for the final source snapshot:

- Self-compiled object equals the hosted-producer object; SHA-256:
  `2bd41e8f8410ef616ff1e35230bbea296c9cbcb3866c8310cc598f10259fd6e4`.
- Stage 2 and Stage 3 ELF images match; SHA-256:
  `093e4f4c83b02f0b403d119e5ea6e3c96287a92eb3614ec2c03efab9f9431e9c`.
- A file compiled by the native driver executes and returns 42.

The new Linux CI gate repeats self-object equivalence, the native generation
chain and Stage 3 application execution with PATH pointing to an empty
directory. Windows/macOS build the seed ELF and validate malformed signatures;
they do not execute Linux syscalls. Cross-platform CI certification is pending.

Final local regression evidence: the Windows suite ran 2,654 tests with no
failures and 36 skips; the additional binary-escape regression gate also
passed. WSL repeated the final native generation chain. Stage 3 compiled and
executed an application returning 42 with PATH pointing to no tools, rejected
missing/invalid inputs and unresolved imports, and preserved an existing
artifact when frontend validation failed. The three new skipped execution
gates are enabled on Linux x86-64 in CI.

This closure uses a merged input assembled from the eight production core
modules and the new driver. Imports are rejected explicitly, source input and
tables are bounded, and the driver supports the current native compiler-source
subset. Full module/project loading, full language parity, release packaging
and native Windows/macOS drivers remain open. The compatibility `main.sotlas`
and optional C emitter are not part of this native generation chain.

### SV8.21a — Native Linux explicit multi-file project compilation (2026-10-09)

**Certified reference:** [CI #1157](https://github.com/HPinho/sotlas_dev/actions/runs/37946890838) on `cce33b5c1abd3925db524dfbb24660db582ec689` passed the entire Linux, Windows and macOS matrix. Linux executed the native compiler self-build: the Stage 1 native seed produces Stage 2, Stage 2 produces an identical Stage 3 ELF image, and Stage 3 compiles a runnable program without tools on PATH. The current native sovereignty checkpoint remains **6/10, or 60% of the explicit milestones**, not 60% removed host dependency lines.

**Current implementation:** extend the Sotlas-written Linux driver to accept `--project` / `--project-object` / `--project-compiler` followed by an output path and two to 64 explicitly named input files. It reads files in argument order, appends a deterministic newline separator after each source, preserves the existing combined 1 MiB source cap and reserves the second MiB for compiler-owned synthetic symbols. The same production Lexer, Parser, Sema, Target IR and native x86-64 writer compile the resulting stream. Single-file calls and the existing Stage 1→2→3 fixed point are unmodified. Negative paths (missing/empty files, invalid options, excessive size, invalid syntax, unresolved `import` declarations) fail before the output file is opened.

**Scope / safety boundary:** this is a *flat explicit-source project subset*, not module lookup or import resolution. `import` remains a hard error, including when an imported module happens to appear in the list. No import is silently removed or trusted without validation. The test suite runs a two-file native project executable returning 42 without host tools on PATH and requires exact object-byte identity against the hosted producer compiling the exact concatenated source. It also preserves a previously existing artifact across failures. Windows/macOS continue certifying the seed object path; the new native project runtime tests execute on Linux x86-64. CI certification of this cut is pending.

**Next — SV8.21b:** implement a bounded native module-name index and safe import resolution, with duplicate/missing/cyclic import rejection, deterministic dependency ordering and complete self-build from the nine original module files without host-side premerging. Then extend the certified native generation chain to those input modules. Other open milestones remain full frontend parity, Windows/macOS native targets and installed seed/distribution closure. Do **not** credit another sovereignty checkpoint until the corresponding acceptance gate closes.

### SV8.21a regression hardening — separate native source I/O from ELF linkage (2026-10-09)

The first SV8.21a CI attempt, [run #1158](https://github.com/HPinho/sotlas_dev/actions/runs/37966039648) on `8ee6689200957fd192815475d13b535f08ec657e`, regressed on Linux Python 3.10/3.11/3.12. Three native execution gates returned exit 9 (ELF link failure): single-file compilation, explicit multi-file compilation, and the Stage 2/3 self-build link. Windows/macOS gates succeeded, but they do not execute the Linux driver. The last certified green baseline remains [run #1157](https://github.com/HPinho/sotlas_dev/actions/runs/37946890838), commit `cce33b5c1abd3925db524dfbb24660db582ec689`.

Repair candidate: split the Sotlas-written Linux driver into independent single-file and bounded project input readers and a single downstream `driver_compile_loaded` frontend/lowering/object/link path. This removes nested project-file loops and their mutable control variables from the function responsible for the native ELF link. Preserve the existing single-file options and source bytes, ordered per-file newline separators, 1 MiB combined bound, import rejection, object equivalence, output preservation on validation errors and the Stage 2/3 fixed-point test. Add negative gates for every project mode with missing input, empty input, and 65 input paths.

**Verification status:** this is a proposed source-level repair, not a new certified green baseline. The Linux execution and full cross-platform matrix must pass before SV8.21a is promoted. **Next: SV8.21b** — bounded native module identity/dependency graph, fail-closed duplicate/missing/cyclic import handling, and self-build from original modules without host premerging. No new sovereignty milestone or Python/C elimination percentage is credited by this repair.

### SV8.21b1 — Linux native bounded import resolution and original-module self-build (2026-10-09)

**Green reference:** [CI run #1159](https://github.com/HPinho/sotlas_dev/actions/runs/37969940811), commit `29df97e6c0bc9ce82ce672202f831822262062c2`, passed the Linux/Windows/macOS matrix after the SV8.21a linker regression repair. Do not move this certified baseline until the new native-resolution gate passes.

**Implementation cut:** opt-in `--project-resolve` (plus object and compiler variants) reads two to 64 real files into bounded Sotlas-owned memory. Production lexer tokens, not text matching, identify each canonical module declaration and `import path::*;` edge; reject duplicate module names/imports, missing/self imports, unsupported import forms and nested imports. The native graph uses 64×64 bounded edges, stable topological order and deterministic source emission with only validated import declarations removed. The existing flat compilation/ELF-writing path then compiles and links the result. Existing single-file and `--project` commands remain unchanged.

**Acceptance gate:** Linux native run with inputs deliberately reversed, linked program returns 42, exact ELF object parity against hosted reference of the deterministic import-free stream; fail-before-output fixtures for missing/duplicate/cyclic/unsupported dependencies; Stage 1 produces Stage 2 and Stage 2 produces identical Stage 3 **directly from the nine original files**, with PATH excluding host build tools. Windows/macOS continue verifying the native seed object path. These are new gates, not claims of verified success before CI.

**Limits and next step — SV8.21b2:** this closes only a bounded *explicit-source glob-import* profile: native package discovery, import aliases, namespace visibility and independent-object linking are still open. Finish the safe module resolver API and explicit namespace semantics before declaring full native imports closed. Milestone score remains **6/10 (60% of milestones)** until all acceptance criteria pass; it does not quantify Python or C code elimination.

### SV8.21b1 compilation regression repair (2026-10-09)

[CI run #1160](https://github.com/HPinho/sotlas_dev/actions/runs/37976045347) on `44213183c03374e274be4e0278cafbbdeb3abd0b` failed in the same native-driver Stage 1 compilation setup across Linux, Windows and macOS: exit 10, expanded-source diagnostic line **18916**, column **60**. The location maps to the first `&mut off` argument passed along with other address-taken scalar locals to `driver_read_module_path`. The existing native lowering profile does not yet support this helper-call form. It is *not* a platform-specific failure and none of the new runtime resolver tests were reached.

**Repair:** keep the SV8.21b1 bounded graph, lexer-based identity validation, fail-closed imports, stable ordering and original-module self-build gates. Replace multi-scalar out-parameter references with four one-element, Sotlas-owned static scratch buffers for parsed module span and resolved source length. Their writers/readers remain bounds-checked, with no allocations or dependence on Python or C; the driver executes one compile per process, so scratch state is deliberately non-reentrant. Preserve all existing tests and the prior CI-green baseline `29df97e6c0bc9ce82ce672202f831822262062c2`.

**Acceptance:** Stage 1 must compile and link the driver on all three OSes; Linux must then execute the full positive, negative, equivalence and Stage 2→3 fixed-point gates, with the whole test matrix passing before this commit becomes the new baseline. CI success is **pending**, not implied by the commit. **Next SV item remains SV8.21b2**; no sovereignty milestone or Python/C percentage is advanced by this repair.

### SV8.21b1 Ubuntu CLI-dispatch regression (2026-10-09)

[CI run #1161](https://github.com/HPinho/sotlas_dev/actions/runs/37979287139) on `89a8185b42c89d96e6ceb701db613e833cf4c11e`: Linux x86-64 tests compile and self-build the legacy native compiler (including the Stage 2/3 fixed point), but all new `--project-resolve*` runtime commands returned **exit 1**, even when the broken module dependency graph should return exit 12. The shared failure occurs *before* resolver semantics: the driver falls back to its legacy single-file CLI. Windows and completed macOS jobs passed their seed/object gates; those platforms do not execute the Linux driver.

**Repair candidate:** replace monolithic 17/24/26-byte CLI option comparisons with an explicit exact matcher assembled from shorter literals (`--project` + `-resolve` + optional `-object`/`-compiler`), checking the NUL terminator. No names or modes are removed, no resolver or backend tests are weakened; add negative CLI suffix gates. Keep the last certified full-matrix green baseline [#1159](https://github.com/HPinho/sotlas_dev/actions/runs/37969940811) at `29df97e6c0bc9ce82ce672202f831822262062c2`. New commit must pass Linux runtime resolution, original-module Stage2/3 identity, and the unchanged Windows/macOS matrix before green certification. **Next planned SV: SV8.21b2**; sovereignty checkpoints remain 6/10 until acceptance.

### SV8.21b1 — Ubuntu regression #1162: isolate native CLI dispatch (2026-10-09)

[GitHub Actions #1162](https://github.com/HPinho/sotlas_dev/actions/runs/37982034639) on `8f0c2b6f9879d32791569c879f8a63e631cffd47` showed seven failures on each Ubuntu Python version, including previously certified `--project` and Stage2→3 `--compiler` paths. Windows/macOS passed non-Linux-execution gates and one-file Linux application compilation still passed. The extra resolved-option helper in the entry CFG correlates with legacy dispatch corruption; the exact generated machine-code defect remains to be independently reproduced.

The corrective cut restores the three certified flat-project checks at the start of the entry routine, dispatches unknown five-or-more-argument calls to an isolated resolver helper and matches the new opt-in commands using an exact ASCII-byte decoder rather than new CLI string-literal relocations. All existing import graph/negative, native object equivalence and Stage 2/3 fixed-point checks are retained; a separate Linux regression gate rechecks old project executable/object semantics and missing-file preservation.

**Status:** not certified until the new Linux CI and full Windows/macOS matrix complete successfully. The last green reference is [#1159](https://github.com/HPinho/sotlas_dev/actions/runs/37969940811) at `29df97e6c0bc9ce82ce672202f831822262062c2`. No SV milestone or Python/C dependency percentage is promoted. **Next: SV8.21b2 only after green.**

### Ubuntu resolver regression repair — CI #1163

The Ubuntu Python 3.10/3.11/3.12 lanes on `bfb5fb6` failed the same resolved
project execution gate with exit 12. The production lexer classifies `gate`
as `KwGate`, while the new module-path reader accepted only `Ident`. Valid
namespaces such as `gate::app` therefore failed before graph ordering.

The reader now validates ASCII identifier spelling in module-path context,
including keyword namespace segments. Contiguous `::`, explicit glob imports,
graph validation and output-preservation requirements remain unchanged.
Numeric-leading segments remain rejected. A Linux execution gate covers
`system::gate` and `gate::system`, comments and strings containing import text,
and malformed names. The original failing test retains its exact native-object
comparison and all dependency-graph rejection gates remain enabled.

Local verification: 2,664 Windows-suite tests completed without failures
(45 skips). The original Ubuntu failure, contextual keyword namespaces,
invalid dependency graphs, option rejection and legacy CLI compilation passed
through native Linux execution under WSL. The original-module native self-build
gate also passed, including identical regenerated compiler images and execution
of its Stage 3 sample. New CI certification remains pending.

### Native discovery and Linux seed distribution

The file driver adds `--build`, `--build-obj` and `--build-cc`. It starts with
one entry file, resolves explicit glob namespaces beneath a supplied source
root, reads dependencies into a bounded queue and applies the existing graph
verification/topological order. Missing files, cycles, duplicate declarations,
unsupported imports and malformed identifiers fail before output creation.
The source-root layout maps `foo::bar` to `foo/bar.sotlas`; no Python source
merger participates in native discovery.

`packaging/native_linux.py` creates a reproducible Linux x86-64 seed archive
with a static compiler, namespace-layout source tree and checksums. The packager
is a release-time tool, not an installed compiler dependency.
`packaging/install-native.sh` validates the payload and installs it with system
utilities without Python or C build tools. The new CI artifact job installs
and executes this native bundle while retaining the existing distributions.

The declared native glob-import/project profile and the Linux installed-seed
profile close two further checkpoints locally. Global progress is **80%, not
90%**: broader canonical frontend parity and actual native Windows/macOS
toolchains remain open. Namespace visibility, aliases and package management
remain part of the broader parity work; they are not claimed by discovery.

Local evidence: the complete Windows regression run passed 2,667 tests with
47 skips. Five native Linux discovery/legacy/graph gates passed through WSL.
The installed compiler rebuilt its namespace-layout sources with PATH excluding
host tools; its Stage 2 and Stage 3 images matched with SHA-256
`7d8540a72243798e90ffd697652deb72b01965a82c73e0cf46b47eb271646e93`.
Reproducible archive and existing installer/release contracts passed separately.
Installation also passed with PATH containing only the eight required system
utilities. Linux CI executes the installer tamper and no-host-tools gates;
new CI certification remains pending.

### SV8.22a — native string relocation capacity repair

CI [#1165](https://github.com/HPinho/sotlas_dev/actions/runs/38009068884)
failed on all three Ubuntu Python versions at the malformed-arity gate for
`--project-compiler`. Windows, macOS and the C11 contract passed. The driver
had grown beyond 256 string literals: the lowerer emitted the 257th string's
bytes but omitted its symbol, leaving its address instruction unrelocated.
This is a compiler capacity defect, not a platform timing issue.

The native Target IR now reserves 512 string symbols. The lowerer rejects
symbol exhaustion and decoded payload exhaustion instead of silently emitting
unpatched addresses or truncated strings. The byte pool remains 65,536 bytes,
including every literal's terminating NUL. Boundary gates verify all 512
symbols have relocations, reject a 513th literal without output, accept a
65,535-byte payload and reject a 65,536-byte payload. Linux execution also
checks late string addresses and preserves an existing artifact on rejection.

The existing CLI arity and self-build gates remain unchanged. The checkpoint
score stays 8/10 locally; certification requires a new green CI run.

Local validation passed the complete Windows run (2,669 tests, 47 skips),
six Linux execution gates through WSL, and verified installation of a newly
built seed with only system utilities on PATH. Native Stage 2 and Stage 3
rebuilt directly from the original modules and matched byte for byte; Stage 3
compiled and executed a program returning 42. The extra Linux string-capacity
gate ran separately after the Windows suite had already collected its tests.

### SV8.22b — certified Linux profile and native check commands

The baseline `3782ff133b4c9e952f7bcb8fa8f188feb6c39b29` passed
[CI #1166](https://github.com/HPinho/sotlas_dev/actions/runs/38013959975)
and [CI #1167](https://github.com/HPinho/sotlas_dev/actions/runs/38037420665).
The eight closed checkpoints below are now CI-certified for their declared
profiles, including native Linux source discovery, generation identity and
installed seed execution. The score is **80%**. Full canonical frontend parity
and native Windows/macOS toolchains remain open; a tooling improvement does
not, by itself, close either checkpoint or justify an 85% score.

The next candidate adds native `--check INPUT` and `--check-build ROOT ENTRY`.
Both share compilation's frontend, Target IR lowering and object validation,
with the object held in memory and no output file opened. Discovery and graph
validation are shared with native builds. Libraries need no executable entry
for checking; foreign symbol resolution and executable linking are separate.
The check profile remains the declared native subset, not full language parity.

Acceptance gates cover valid libraries, parser/semantic/lowering failures,
matching object-compilation exit codes, unchanged files, imported modules,
cycles, missing inputs and malformed arguments. The installed seed CI job
also runs both checks with no host build tools on PATH. Candidate certification
requires its own green CI run.

Local Linux validation passed both new CLI gates, legacy dispatch, argument
bounds and source discovery. The original-module generation gate also passed:
Stage 2 and Stage 3 matched byte for byte, and Stage 3 successfully executed
both check commands before compiling a runnable program. A newly built bundle
was installed with only system utilities and checked/compiled source with no
Python or C build tools on PATH.

The complete Windows regression run passed 2,672 tests with 50 platform/tool
skips. The six selected Linux execution gates passed separately through WSL.

### SV8.23 — first owned Windows executable path

Baseline `fe435430e803085eee97cb83b327db2dbbdd4f2d` passed
[CI #1168](https://github.com/HPinho/sotlas_dev/actions/runs/38057222821).
Native checks are now part of that certified Linux profile.

The new candidate adds a PE32+ writer and linker in
`bootstrap/sotlas/native_compiler/backend/x86_64_scalar.sotlas`.
The existing ELF object resolver supplies internal symbol resolution; the PE
writer maps the resolved payload, zero-initialized memory and a Win64 startup
bridge. `ExitProcess` from KERNEL32 is the only generated Windows import. The
internal calling convention stays SysV, with a zero-argument process entry.
The low 32 return bits are passed as the Windows exit code.

The Linux native driver exposes `--windows` and `--build-win` directly. The
hosted producer also exposes `--link-pe` through a temporary Stage-0 bridge;
that bridge performs file I/O while the Sotlas writer produces the image.
Native Linux/Stage-3 gates compare PE bytes with the hosted oracle without
tools on PATH. Windows gates execute calls, strings, global storage and a
260 exit code. Negative gates reject unresolved foreign symbols, Linux
syscalls, nonzero entry arity, missing ABI notes and malformed input while
preserving existing output.

The CI distribution job generates a PE using the installed native Linux seed;
a Windows job downloads and executes it without Python or C build tools.
This is a first Windows executable path, not a Windows compiler self-build.
Windows native file APIs/driver, general Win64 FFI, COFF inputs, unwind data,
ASLR and separate memory protections remain open, as does macOS. The current
PE gate rejects syscall byte patterns conservatively, including immediates.
These limits prevent closing the platform checkpoint or claiming 95%.
The certified checkpoint score remains 80%; new candidate CI is pending.

Local validation passed the PE contract and rejection suite on Windows,
including execution without host tools. Five Linux gates passed through WSL,
including native PE equivalence and original-module Stage 2/3 identity.
Stage 3 generated a PE matching the hosted oracle. The installed Linux bundle
also produced a PE that executed on Windows with exit code 42; this rehearses
the new cross-platform CI artifact gate.

The Windows regression suite covered all 2,677 cases in two blocks (51 skips).
The first run exposed a missing PE symbol in the shared legacy driver bridge;
the compatibility compiler now provides its explicit unsupported-backend
response. Its 12 compatibility gates passed, and all 984 remaining cases
passed after the repair. The 1,693 earlier cases had already passed. No legacy
test was removed or weakened, and both bootstrap mirrors remain identical.

### SV8.23a — public frontend clean-build repair

[CI #1169](https://github.com/HPinho/sotlas_dev/actions/runs/38061042685)
failed in the C11 job's reality gate while building the native Stage 1 compiler.
The numbered C11 examples had already passed. The new PE writer passed
`4096 + memory_size` to a `usize` parameter, but the public `compiler/` frontend
inferred the literal-led expression as `i64`. A subsequent check also exposed
a comparison between a `u64` address and a `usize` length.

Size arithmetic now starts with the typed size operand, and the address-bound
comparison explicitly converts the length to `u64`. Type checks remain strict.
The PE suite now builds Stage 1 in a fresh subprocess with only `compiler/`
on PYTHONPATH. A new public CLI test uses an empty temporary cache, so a stale
Stage 1 binary cannot hide source-build failures. The existing `tools/`
validation remains available, but does not replace the public frontend gate.

Local validation passed source checking through the public frontend on Windows
and Linux, the four PE/clean-cache tests, and all 707 tests in the exact failing
CI step. Candidate CI certification remains pending.

### SV8.23b — strict compatibility C11 matrix repair

[CI #1170](https://github.com/HPinho/sotlas_dev/actions/runs/38062373265)
passed the C11 contract job but failed every Python/OS matrix job at the same
Sotlas-lite test. The compatibility PE rejection bridge did not reference six
of its parameters; GCC and Clang rejected the generated C under
`-Wall -Wextra -Werror`.

The bridge now checks its input pointers and sizes before returning its
unsupported-backend result. It still returns false and clears the output length;
the compatibility compiler does not gain PE support. Warning flags remain
unchanged. The C11 test also discovers the project's configured LLVM installation
when neither GCC nor Clang is on PATH, preventing an avoidable local skip.

The original failure was reproduced locally with strict Clang diagnostics.
After repair, all 15 Sotlas-lite and compatibility self-hosting tests passed
without skips, including strict C11 compilation, execution, output preservation
and the legacy Stage 2 fixed point. New CI certification remains pending.

### SV8.24 — native Windows file compiler and generation chain

The candidate adds `bootstrap/sotlas/native_driver/windows.sotlas`. It shares
the production Lexer, Parser, Sema, Target IR, object writer and linker with
Linux. Win32 adapters supply file input/output and command-line arguments.
The PE backend bridges the internal SysV convention to eight frozen scalar
KERNEL32 imports, including five-argument I/O and seven-argument CreateFileA.
These calls use native machine code and require no C runtime or external linker.

The object writer validates import machine signatures and records their ABI ID
in the undefined symbol's size field (`0x57000000 + import ID`) of the internal
ELF container. The PE resolver accepts only recognized, validated imports.
ELF object platform flag bit 0 records actual Linux SystemOps; PE rejects that
requirement instead of scanning instruction-shaped bytes in immediates.

Frontend work also closes concrete compiler-source gaps: calls in `if`
conditions select structured CFG; casts can parse nested pointers without
consuming scalar multiplication; zero-initialized global pointer arrays use
eight-byte elements and preserve complete element identity in pointer views.
Changed pointees and inner qualifiers remain rejected. Input/output, console,
buffer counts, pointer-array round trips and malformed import signatures have
positive/negative execution gates.

Local Windows validation produced Stage 2 and Stage 3 directly from the nine
original source modules with no tools on PATH. Their PE images matched byte
for byte; Stage 3 checked, compiled and executed an application returning 42.
The first generation proof recorded SHA-256
`4fa15fd8684d528fecb8150901b046e9fc85930b944a8e263052662bdedab563`;
subsequent code revisions use the generation equality gate rather than that
historical digest. The installed Linux seed also produced a Windows compiler
which compiled and ran its own application. The CI artifact now carries that
compiler and the source tree to the Windows runner for native self-build.

The Windows profile uses ANSI paths and bounded command-line storage, and
retains the existing native language subset. Full Unicode paths, COFF inputs,
general Win64 FFI/unwind, ASLR, separate memory protections and macOS remain
open. Full canonical frontend parity also remains open. This is a Windows
profile closure candidate, not a claim of 100% global sovereignty. The certified
checkpoint score remains 80% pending further checkpoint acceptance.

Baseline [CI #1171](https://github.com/HPinho/sotlas_dev/actions/runs/38066449971)
passed C11 and eight matrix jobs, but its final macOS/Python 3.12 job timed out
at two compiler-sized pipeline fixtures. CFG selection now examines each
parser-allocated function subtree instead of rescanning the complete module
for every function. The 120-second fixture watchdog remains unchanged; local
pipeline and recursive-call gates passed after the optimization. Final CI
certification of this candidate remains pending.

Final local validation passed the complete Windows suite (2,685 cases, 49
platform/tool skips), all 89 Windows-driver/structured-CFG gates after the
subtree optimization, and three native Linux gates including original-module
Stage 2/3 identity. The 89-gate run completed in 68 seconds and the three Linux
gates in 35 seconds on this host; these are validation timings, not a portable
benchmark claim. The installed Linux-to-Windows compiler/application chain
also passed locally. The recursive legacy object path remains supported;
the new CFG selector applies calls-in-condition rules without redirecting
ordinary calls in branch bodies.

### SV8.25 — owned Intel Mach-O images and Darwin I/O

**Green reference:** [CI #1172](https://github.com/HPinho/sotlas_dev/actions/runs/38073734160)
on `668cfab144ab83cad56b03ab48032ca253668f77` passed the complete matrix,
including the native Linux-to-Windows compiler build and Windows Stage 2/3
fixed point. Windows generation is now certified for the declared source
profile. This does not close the combined Windows/macOS checkpoint.

The next candidate adds `link_macho64_executable` to the production Sotlas
x86 writer. It resolves the internal ELF object with the existing owned linker,
maps the resolved payload and zero-filled BSS into an Intel Mach-O image,
and emits a separate RX startup segment. `LC_UNIXTHREAD` selects a
zero-argument scalar entry; startup aligns the stack and exits with the
entry's return value through Darwin's kernel interface. No external linker,
dyld, libc or C startup object generates or runs this image. The initial
payload segment retains the existing prototype RWX protection.

`SystemOp` IDs 16–19 represent the reserved bodyless `sotlas_darwin_read`,
`sotlas_darwin_write`, `sotlas_darwin_open` and `sotlas_darwin_close` adapters.
Their exact machine-level signatures match the existing typed I/O contract.
The backend converts Darwin's carry-flag/positive-errno response into a
negative `i64` error. ELF object platform flags distinguish real Linux and
Darwin operations; Linux process images, Windows PE images and Mach-O images
reject incompatible operations before opening the output. Syscall-shaped
constants do not select a platform. Foreign unresolved functions, missing
entry ABI notes, nonzero entry arity and malformed object tables fail closed.

Native Linux and Windows drivers expose `--build-mac OUTPUT ROOT ENTRY` with
their existing bounded source discovery. Local gates compare native-driver
Mach-O bytes against the hosted reference without host build tools on PATH,
check output preservation on rejection, and repeat both native compiler
generation chains. `tests/test_sotlas_native_macho.py` checks load commands,
segments, relocations, strings and BSS on every host; on Intel macOS it also
executes the generated images and verifies file/console I/O and error returns.
**Actual macOS execution of this candidate remains pending CI.**

Platform references: Apple's [Mach-O definitions](https://github.com/apple-oss-distributions/xnu/blob/main/EXTERNAL_HEADERS/mach-o/loader.h),
[XNU loader](https://github.com/apple-oss-distributions/xnu/blob/main/bsd/kern/mach_loader.c)
and [file flags](https://github.com/apple-oss-distributions/xnu/blob/main/bsd/sys/fcntl.h).
XNU permits static x86-64 executables; this is not an Apple Silicon or Rosetta
support claim. Code signing policies, ASLR, separate payload permissions,
native macOS argv/file driver, general FFI and full frontend parity remain
open. The legacy object ABI note proves parameter arity, not a complete
return-type schema; the supported entry contract remains `() -> u32`.
Keep the checkpoint score at **80%** until the remaining acceptance
gates close. Python files remain necessary for uncovered paths and are not
deleted by this candidate.

**Local validation (2026-10-10):** the complete Windows suite passed **2,691
tests, 50 skipped**; the previous C11 bootstrap contract step passed **707
tests**. Native Windows Stage 2/3 byte identity, original-source Linux Stage
2/3 byte identity under WSL, and Linux/Windows Mach-O cross-build parity all
passed. A fresh bundle installation verified checksums, emitted Mach-O without
host build tools, ran a Linux-produced PE on Windows, and built a Windows
compiler that compiled and ran its own application. These results do not
substitute for the pending Intel macOS runtime and full candidate CI matrix.

### SV8.26 — native Darwin compiler and process-entry generation

**Certified baseline:** [CI #1173](https://github.com/HPinho/sotlas_dev/actions/runs/38084718943)
on `e88f01bb71828d620bd5877ef6d1984db6c5b8df` passed the complete matrix and
executed the Linux-produced static Mach-O on Intel macOS. The prior Mach-O
and Darwin I/O image gates are now certified for their declared profile.

This candidate supplies `bootstrap/sotlas/native_driver/darwin.sotlas`, a
native compiler driver using the same eight production compiler modules.
It consumes original files, discovers and checks module graphs, runs the
production frontend and Target IR, writes owned native objects/Mach-O images,
and self-builds through the existing bounded project interfaces. Its Darwin
I/O adapters emit kernel operations rather than calling a C library. Output
uses Darwin creation flags and executable permissions; validation failures preserve the
previous artifact. No second language or alternate compiler frontend is added.

The reserved typed process entry is `sotlas_darwin_main(u64, Pointer) -> u32`.
Object ABI descriptor **16386** records its two machine arguments and a
distinct process marker at bit 14, outside the Boolean-argument mask. The
object writer checks its arity, parameter machine types, result and defined
body. Mach-O accepts that descriptor only for the reserved entry name;
ordinary entry signatures and Linux process notes remain separate. Startup
loads `argc` and `argv` from XNU's static stack before aligning it and calling
the compiler. This follows Apple's [exec stack construction](https://github.com/apple-oss-distributions/xnu/blob/main/bsd/kern/kern_exec.c);
the extra Mach header word belongs to dyld/Rosetta paths and is not part of
this static Intel profile.

Native Linux and Windows seeds expose `--build-mac-cc OUTPUT ROOT ENTRY`.
The native seed bundle includes the Darwin driver under
`src/sotlas/compiler/darwin_driver.sotlas`. Local cross-build gates compare
the complete native Darwin compiler image byte-for-byte with the original
source hosted oracle, while the native resolver uses a separate namespace
tree. The hosted oracle's fallback import search mixes copied/repository
roots; tests therefore compile the identical originals for that reference,
without changing the native isolated-tree requirement.

`tests/test_sotlas_native_darwin_driver.py` adds portable image/process-note
gates and Intel macOS runtime gates for checking, compiling, quoted paths,
object parity, output preservation, and the original-source Stage 2/3 fixed
point. CI also builds the macOS compiler using the installed Linux seed,
executes it on Intel macOS, checks Stage 2/3 image equality, and runs an
application compiled by Stage 3 with no host tools on PATH.

**Certification rule:** the existing score stays **8/10 certified** until
this candidate's full CI passes. A successful native macOS generation closes
the ninth checkpoint for the bounded cross-platform compiler-source profile.
Full canonical language/frontend parity remains the tenth acceptance gate.
Python files continue serving features outside the native profile; removing
them requires those features' native replacements and installed CLI parity.
Apple Silicon, general ABI/FFI, signing, ASLR and broader ownership/runtime
features remain separate scope items, not implied by a compiler fixed point.

**Local validation (2026-10-10):** the complete Windows regression suite
passed **2,697 tests, 53 skipped**. The strict C11 bootstrap contract passed
**707 tests**. Linux (WSL) and Windows native seeds built the complete Darwin
compiler with exact hosted-reference image parity; the original-source Linux
and Windows generation chains retained their Stage 2/3 fixed points. Fresh
bundle installation verified all checksums, built the Darwin and Windows
compilers from bundled modules without host build tools, and ran a program
compiled by the resulting Windows compiler. The new Darwin process entry,
file compiler and fixed-point execution remain subject to the Intel macOS CI
gates before certification.

### SV8.27 — signed i32 native frontend/backend parity

**Certified baseline:** [CI #1174](https://github.com/HPinho/sotlas_dev/actions/runs/38088181971)
on `bb9a827559436bf7e703da2bd9d45f259b74c221` passed the complete matrix,
including the Linux-produced native Darwin compiler, macOS file compilation,
Stage 2/3 byte identity and a Stage 3 application. Native compiler-source
generation is now certified on Linux, Windows and Intel macOS. This closes
the ninth explicit checkpoint; the current score is **9/10, or 90%**. The
remaining checkpoint is full canonical frontend/language parity, not another
compiler-generation percentage.

This candidate adds `i32` to the owned native scalar path. The source lowerer
uses structured CFG for signed declarations, records four-byte scalar/array
storage, admits signed pointees and fields, and validates literals against
`[-2147483648, 2147483647]`. Negative literals retain a 32-bit two's-complement
bit pattern; non-literal negation lowers to typed subtraction. Existing
unsigned pointer offsets and array-index requirements remain unchanged.

The machine writer accepts `i32` parameters, returns, typed loads/stores,
Phi copies, arithmetic and bitwise operations. Ordered comparisons use signed
condition codes. Widening an `i32` to 64 bits uses sign extension; widening a
`u32` continues to zero-extend. Narrowing retains the destination bits. Signed
division truncates toward zero and remainder follows the dividend; zero
divisors and `INT_MIN / -1` or `% -1` trap in the isolated native process.
Arithmetic right shifts preserve the sign and require an IR-proven constant
count from 0 through 31; unsupported dynamic/out-of-range counts fail before
output.

**Overflow boundary:** the owned x86 profile executes add/subtract/multiply
and negation as wrapping 32-bit machine operations. This is an explicit
backend-profile behavior, not a language-wide signed-overflow specification
or a C11 overflow-equivalence claim. The C11 differential gate uses defined,
non-overflowing signed inputs; existing language-wide overflow work stays open.
Signed `i8`/`i16`, general signed variable shifts, broader numeric promotions,
floating-point native lowering and complete frontend parity remain outside
this cut. No ownership/runtime feature is promoted by scalar-type coverage.

`tests/test_sotlas_native_i32.py` executes register/stack parameter calls,
signed boundaries, casts, negative comparisons, division/remainder/shifts,
struct/global/local-array storage, pointer stride and mutable CFG state.
It compares defined signed arithmetic with canonical C11 and checks division
faults in child processes. Native Linux, Windows and Darwin driver gates
check, compile and execute a signed program without host build tools on PATH.
Existing original-source native generation chains remain regression gates.

**Local validation (2026-10-10):** the complete Windows suite passed **2,707
tests, 55 skipped**; the C11 bootstrap contract passed **707 tests**. The seven
dedicated signed gates, defined-arithmetic C11 comparison, and isolated
division-fault cases passed. Native Windows and Linux (WSL) drivers checked,
compiled and executed the signed sample without host tools on PATH. Their
original-module Stage 2/3 fixed points passed; the dedicated signed and both
generation gates were repeated after the final redundant-guard cleanup.
This numeric extension awaits its full Linux/Windows/macOS candidate CI;
the 90% checkpoint score is certified by the preceding #1174 baseline.

**SV8.27 Windows matrix repair:** CI #1175 on
`f937b4ad9dfb469b19a854dc4c79972b09aa5e54` failed the division-fault gate on
Windows/Python 3.10 and 3.11. The old gate executed generated SysV code inside
Python through a `ctypes` memory trampoline. The logs show arithmetic faults
translated into `OSError`/exit 1 in one interpreter and `0xC0000409` termination
in the other, rather than the asserted native arithmetic NTSTATUS. The
production compiler and ordinary signed execution tests did not fail there.

The repair links each fault fixture into a complete Sotlas-owned PE and
executes it as a separate OS process. A Python launcher only sets inherited
error-reporting policy, captures the native child's exit code and emits JSON;
it never calls generated code through `ctypes`. The launcher must succeed, a
non-faulting control must return 42, and the native fault cases still require
exact `0xC0000094` (division by zero) or `0xC0000095` (division overflow).
Neither generic failure nor `0xC0000409` is accepted. Unix gates still require
`SIGFPE`, using the same owned-image linking helper.

All seven dedicated signed tests passed locally on official temporary Windows
Python **3.10.11** and **3.11.9** runtimes, and on the two available newer local
interpreters. The change is confined to the test harness and this repair
record; no backend semantics or fault assertions are relaxed. Keep CI #1174
as the certified reference until the repair's full matrix succeeds.

### SV8.28 — fixed-width signed integer family in owned native code

**Certified baseline:** [CI #1176](https://github.com/HPinho/sotlas_dev/actions/runs/38094848259)
on `cd37a3886f594a85b059b5a6bc34119e765b9b8b` passed the matrix after the
Windows fault-harness repair. Signed `i32` and the independent native-process
fault checks are now certified. The sovereignty score remains **90%**; this
candidate expands the remaining frontend parity work without closing it.

The native scalar profile now includes `i8` and `i16` parameters, returns,
locals, fields, arrays and typed pointers, and completes signed `i64`
division/remainder and arithmetic right shift. Source literal bounds match
each declared width. Negative literals carry the corresponding bit pattern;
negation, arithmetic and bitwise results are normalized to that width.
Implicit mixed-type arithmetic and signed array indices remain rejected.

Signed byte/word values are canonicalized after loads, calls, casts and Phi
copies. Register and stack parameters are normalized before any operation
reads their full slot. Memory reads/stores preserve one-byte `i8`, two-byte
`i16`, four-byte `i32` and eight-byte `i64` layout. Pointer stride, bounded
arrays and neighboring record fields use the same declared width. Signed
widening extends the sign; narrowing retains the destination bits.

Division/remainder truncate toward zero and retain the dividend's remainder
sign. The wide path emits `cqo` and `idiv`; narrow signed division uses
normalized values and detects the declared-width `MIN / -1` or `% -1` case
before executing the existing architectural overflow path. Division by zero
and minimum-value division overflow still produce the exact native arithmetic
faults tested in independent PE/ELF/Mach-O processes. No generic Python
exception or fail-fast code is accepted as a substitute.

Signed shifts require an IR-proven constant count less than 8/16/32/64 for the
respective type and use arithmetic right shift for negative values. This
also tightens the previously permissive dynamic signed `i64` left-shift path:
unsupported counts fail before output, rather than inheriting hardware masking.
Unsigned shift behavior is unchanged. Wrapping arithmetic/negation remains
an explicit owned-x86 profile behavior; the language-wide signed overflow
specification and C11 overflow equivalence remain open.

`tests/test_sotlas_native_signed_family.py` executes width boundaries,
register/stack calls, signed casts, comparisons, division/remainder/shifts,
adjacent fields, globals, local arrays and pointer stride. It rejects invalid
literals, dynamic/out-of-range shifts, signed indices and incompatible pointer
casts, checks declared-width arithmetic faults, and compares defined signed
operations with canonical C11. The former conservative signed-byte arithmetic
gate now requires execution; the signed-division negative gate rejects a
Boolean divisor. Native Linux, Windows and Intel macOS driver gates compile
and execute a mixed-width signed example without host build tools on PATH.
Native source-generation fixed points remain required regression gates.

**Local validation (2026-10-10):** the complete Windows regression suite
passed **2,717 tests, 57 skipped**, and the C11 bootstrap contract passed
**707 tests**. The structured CFG suite passed all **86 tests**. The seven
signed-family gates passed, including canonical C11 comparison and precise
native fault categories; fault/memory/arithmetic gates also passed on the
previously affected Windows Python 3.10 and 3.11 runtimes. Linux (WSL) compiled
and executed the mixed-width signed program without host tools and retained
the original-module Stage 2/3 fixed point; Windows generation and cross-build
gates remained green. A legacy self-host diagnostic fixture now rejects a
Boolean divisor rather than valid `i64` division. Full candidate CI is pending.

**SV8.28 clean-build gate repair:** [CI #1177](https://github.com/HPinho/sotlas_dev/actions/runs/38099383858)
on `110a7d0277a23964b2e3a5db276e82c92cb59e8d` failed exactly
`test_sv2_fail_closed_unsupported_operation` in all nine matrix jobs. That
earlier SV2 gate still required rejection of valid signed `i64` division.
The reported local suite had reused an older `build/sotlas_stage1` executable,
so it did not validate this gate against the newly implemented compiler.
That cached local result cannot certify the signed-family candidate.

The SV2 setup now builds the current source into its own temporary directory
on every run, using a fresh child with the public `compiler/` frontend. It
never selects the checkout's cached Stage 1. The negative fixture exercises
still-unsupported floating-point division, retaining nonzero exit and no
output assertions. An additional positive gate compiles signed division and
remainder, links an owned PE/ELF/Mach-O image and requires native exit 42.
The separate Boolean-divisor rejection remains intact.

All **46 SV2 gates** passed with fresh builds, including Windows Python
**3.10.11** and **3.11.9**. All **seven signed-family gates** also passed.
No production frontend/backend code changes are needed for this repair.
Keep CI #1176 as the certified baseline until the repair matrix completes.

### SV8.29 — native bit operations and checked variable shifts

**Certified baseline:** [CI #1178](https://github.com/HPinho/sotlas_dev/actions/runs/38102016555)
on `56ff94e021b7d67e668753c7fa4ee9e932dd009a` passed after the fresh-build
SV2 gate repair. The signed integer family is certified for the declared
profiles. The checkpoint score remains **90% (9/10)**: full canonical
frontend parity is still open.

This candidate adds unary bitwise complement and variable left/right shifts
to the owned native integer profile: signed and unsigned 8/16/32/64-bit
values, including `usize` and `isize`. Complement lowers to typed Target IR
XOR with a declared-width mask. Calls and loads retain their existing
canonical signed/unsigned representations; complement evaluates its operand
once and requires no new runtime or C emission path.

Shift counts can come from arguments, calls, memory and arithmetic expressions.
Direct invalid constants fail lowering before an object is written. Executed
shifts compare the complete count against the declared width before the x86
instruction sees CL. A failed check executes `ud2`; negative signed counts,
counts equal to the width and oversized 64-bit counts cannot inherit hardware
count masking. The 64-bit path loads and compares RCX, including its upper
dword. Signed right shifts preserve the sign; unsigned right shifts insert
zeros; left shifts retain the declared width. Operand types must match.

Shifts are now classified as potentially trapping during conditional
lowering. Short-circuit paths containing them use lazy CFG evaluation; an
invalid shift in an unchosen operand of `&&` or `||` must not run. This
replaces the old conservative rejection of variable signed/narrow counts
and tightens the previously masked wide unsigned path. These are explicit
owned-x86 rules, not invalid-shift guarantees for C11 or another backend.

`examples/native_bit_operations.sotlas` is an executable CRC-32, rotation and
byte-unpacking workload. It verifies the standard `123456789` CRC result,
empty input, normalized rotation and extraction at both ends of a word.
`tests/test_sotlas_native_bit_operations.py` checks all integer widths,
single evaluation, mutable loops, stack/memory counts, static rejections,
short circuit and exact process-level illegal-instruction faults. Defined
workload inputs are also compiled and executed through the canonical C11
oracle. Linux, Windows and Intel macOS native file-driver gates run the same
source with host build tools absent from PATH.

**Local evidence (2026-10-10):** all eight bit-operation gates passed on
Windows, on the temporary Python 3.10.11 and 3.11.9 matrix runtimes, and with
owned ELF images executed in Linux via WSL. Native Windows and Linux file
drivers checked, compiled and executed the workload without host tools on
PATH. Both original-module Stage 2/3 fixed points passed. The C11 bootstrap
contract passed all 707 tests. The complete Windows suite passed **2,729
tests with 59 skips**, using the fresh-build SV2 gates. Native source sizes
with each file driver remain below the 1 MiB input limit. Intel macOS execution
and full candidate matrix certification remain CI gates.

Floating-point native execution, broader ownership/Flow/runtime support,
full frontend diagnostics and installed CLI parity remain open. This block
does not authorize removal of the hosted bootstrap or promotion to 100%.

### SV8.30 — native floating scalars, profile CLI and compiler arena bounds

**Certified baseline:** [CI #1179](https://github.com/HPinho/sotlas_dev/actions/runs/38105046484)
passed for `4f85cf785a0ddb1bbbbf65e15482b70173f394f6`. Checked variable
integer shifts and complement are certified. This candidate extends the
remaining native frontend work; the checkpoint score stays **9/10** until
full parity is demonstrated.

The owned backend now executes `f32` and `f64` literals, add/subtract/multiply/
divide, sign-bit negation, all six comparisons, scalar calls, mutable CFG,
four/eight-byte fields, local/global arrays, typed pointer stride, zero BSS
storage and explicit conversions between the two float precisions. Target IR
preserves floating types and adds `ConstFloat`, `FloatNeg` and `FloatCast`.
Its validator rejects float bitwise/modulo operations and incompatible types.
The writer uses scalar SSE2, including ordered/unordered comparison handling:
NaN compares unequal; other ordered predicates are false. Negation preserves
negative zero and infinity. Arithmetic uses the host process's FP environment;
the gates exercise its default IEEE environment. Kernel FP initialization and
context preservation remain separate responsibilities, not a new kernel gate.

**Literal boundary:** the decimal coefficient must be below `10^18`, with at
most 18 fractional digits. An integer-only rational converter rounds directly
to the destination precision with ties to even. It does not parse through a
host double. Gates cover IEEE bit encodings and a decimal that would otherwise
double-round incorrectly to `0.5f`. Scientific notation, arbitrary decimal
precision, float/integer casts, float module constants, nonzero static float
initializers and floating external ABI remain outside this candidate.

**ABI boundary:** internal calls transport IEEE bits through the existing
GPR/stack slots and return register; this is an owned internal ABI, not SysV or
Win64 floating interoperability. External float declarations fail closed.
Object entry descriptors mark floating returns with bit 5 (`32`), so ELF,
PE and Mach-O startup cannot consume them as integer process statuses.
Application/process entries retain their existing typed contracts.

Linux, Windows and Intel macOS drivers now provide `--help` and `--capabilities`.
The report identifies float limits, the internal ABI, and unsupported ownership
runtime and Flow execution. Checking and compilation reject those forms with
the same failure code and preserve existing outputs. These rejection gates
do not constitute implementation of ownership/Flow. The hosted canonical
frontend remains necessary for their currently supported paths.

The compiler's growth exposed two capacity bugs during native self-build:

- The bootstrap arena had only 1 MiB for input plus generated symbol names.
  It now reserves 2 MiB, matching native drivers, while input remains capped
  at 1 MiB. Synthetic string and mangled-name writes check the suffix budget.
- Data address patches and relocations could silently stop at 512 entries.
  Both tables now hold 4,096 entries and fail on exhaustion or an unresolved
  data symbol. Gates require native execution above 512 and rejection above
  the new limit. The function table remains bounded to 512 functions.

`examples/native_float_profile.sotlas` executes a weighted sum through typed
buffers and both precisions. Native Stage 3 generation gates execute this
workload, in addition to requiring byte-identical Stage 2/3 images. The native
float suite covers execution, literal encodings, exceptional IEEE values,
layout/stride, CFG/calls, entry rejection and relocation bounds. The canonical
C11 oracle compares defined arithmetic. Full candidate certification is pending.

**Local validation (2026-10-11):** the Windows regression suite passed
**2,743 tests, 63 skips**. Three subsequently added encoding/entry/arena gates
also passed separately. The final native floating suite has 11 gates; the
original-module Windows and Linux Stage 2/3 closures were repeated after the
entry-descriptor change and executed the floating workload. Windows Python
3.10.11 and 3.11.9 passed the floating/SV2 set available at that run (**55
tests each**). Owned ELF floating execution, native profile output and
ownership/Flow rejection parity passed through Linux (WSL). The C11 bootstrap
contract passed **707 tests**. Intel macOS execution and full final matrix
remain CI gates. The reported local total distinguishes later gates rather
than claiming they were present in the earlier full-suite collection.

**Remaining parity:** native ownership/lifetime/ARC/runtime, Flow AST and
execution, broader numeric forms, diagnostics and installed command parity.
Python/C bootstrap removal is not authorized by this numeric/profile advance.

### SV8.31 — checked integer/float conversion and resilient installed-editor gate

**Baseline evidence:** [CI #1180](https://github.com/HPinho/sotlas_dev/actions/runs/38109769479)
passed completely for `b30c40cfe8c452d05b41f81b15493f57b09e4c0e`, certifying
the preceding bounded float/CLI block. [CI #1181](https://github.com/HPinho/sotlas_dev/actions/runs/38125346030)
tested the same commit: all compiler matrices, C11, native generation,
installation and owned PE/Mach-O jobs passed. Only the VSIX installation job
failed during VS Code version resolution, with an `ETIMEDOUT`/`ENETUNREACH`
network aggregate; it did not reach extension installation or activation.

The editor test now pins VS Code 1.141.0, caches that exact runtime in CI,
reuses it for installation/listing/activation, and bounds transient download
retries with backoff. IPv4 is preferred while IPv6 remains available. Download
timeouts are bounded and the CI smoke step has a ten-minute deadline. Archive
integrity, install, activation and diagnostic failures still fail the job.
The tests reproduce the reported network aggregate and check recovery,
exhaustion and permanent-failure propagation. Fresh-profile installation and
Problems diagnostics remain mandatory, even when the runtime is cached.

The native compiler adds `NumericCast` for explicit conversion between `f32`/
`f64` and signed/unsigned 8/16/32/64-bit integers, including size aliases.
Integer-to-float uses the current FP rounding mode. Unsigned 64-bit values
above the signed range use a sticky-bit half conversion followed by doubling
in the destination precision, retaining the rounding information.

Float-to-integer truncates toward zero and checks that the resulting integer
fits the declared type. Negative fractions that truncate to unsigned zero and
fractions that truncate to signed MIN are valid. NaN, either infinity and
unrepresentable results execute `ud2`; no indefinite integer reaches a later
instruction. Unsigned 64-bit conversion handles the high half by subtracting
`2^63`, converting the remainder and restoring bit 63. Inputs rounded to
`2^64` remain invalid. These are owned-native safety rules, not a new promise
for undefined C11 cast inputs or an external floating ABI.

The lowerer preserves scalar types, evaluates the operand once, supports
explicit numeric literal casts and rejects Boolean/pointer conversions.
Lazy conditions containing a potentially invalid cast retain short circuit.
The weighted-buffer example now converts integer samples into floats and its
result back into an integer; native Stage 3 gates execute that source.
Dedicated gates cover every width/precision pair, fractional boundaries,
the upper `u64` half, literals, single evaluation, lazy paths, exact native
faults and defined-input C11 equivalence.

Native self-build exceeded the bootstrap's old 16,384-block CFG budget. Its
block, branch-target and operand arenas now match the existing native driver
capacities (32,768 / 65,536 / 262,144); actual arrays and declared capacities
are updated together. Existing checked exhaustion behavior is retained.
The input limit remains 1 MiB and the generated-name arena remains 2 MiB.

**Local validation (2026-10-11):** the final Windows suite passed **2,754
tests, 63 skips**. All eight numeric-cast gates passed on Windows Python
3.10.11/3.11.9 and with owned ELF execution in Linux (WSL), including exact
illegal-instruction faults. Windows/Linux native original-source Stage 2/3
fixed points and the updated Stage 3 workload passed. The C11 bootstrap
contract passed 707 tests. The broad suite caught a transitional C-emission
collision with a local named `signed`; renaming it to `is_signed` preserved
the algorithm, and all six hosted SV8 gates plus the repeated full suite passed.
The editor's nine tests, VSIX packaging, clean-profile installation on local
VS Code 1.139.1 and on downloaded/cached 1.141.0, activation and diagnostic
positions passed. Cached runtimes did not replace clean-profile installation.

This candidate still requires final CI. Native ownership/ARC/lifetimes,
Flow execution, broader language/numeric forms and complete command parity
remain open; the certified checkpoint count remains 9/10.

### SV8.32 — typed literal constants, native diagnostics and semantic runtime rejection

The active frontend and ownership migration checklist is
[Native frontend and ownership closure](sotlas_native_frontend_ownership_checklist.md).
It records the complete requested scope and keeps broader parent items open
when only a smaller native contract has been validated.

Native module constants now support typed Boolean, f32 and f64 literals and
unary-negative integer/float literals in addition to positive integer literals.
Declaration validation uses the expression lowerer's type/range checks, even
for unused constants, then restores temporary IR counts and value identities.
General constant expressions and numeric forms outside the existing native
literal bounds remain rejected.

Linux, Windows and Intel macOS file drivers now print path, line, column,
compiler phase, a bounded source excerpt and a caret for located lexer,
parser, semantic and lowering failures. Parser errors retain expected and
actual token kinds; reserved declaration binders report an expected identifier.
Project coordinates still refer to the combined source stream. Original-file
mapping and detailed canonical semantic diagnostics remain open.

The backend-neutral IR still represents semantic runtime operations. The owned
x86-64 object writer now rejects every reserved ownership/state/defer opcode
before output rather than silently ignoring it. Native execution tests exercise
all eleven opcodes, unchanged IR/output storage and a normal scalar control.
This is an explicit unsupported-operation gate, not ownership runtime support.

Acceptance gates are in `tests/test_sotlas_native_frontend_closure.py` and the
three native file-driver suites. They build current sources in fresh directories
through the strict public Stage-0 frontend. Local validation passed 2,761 tests
with 65 skips, the 707-test C11 job, all four new execution gates on Windows
and Linux (WSL), and original-module Linux/Windows generation checks.
CI certification remains pending;
this block does not promote the 9/10 checkpoint score or authorize removal of
the Python/C bootstrap.

### SV8.33 — native initialized storage, constant expressions and conditional values

The production native compiler now emits writable `.data` for initialized
integer, float and Boolean scalars and repeated scalar arrays. Zero-initialized
storage remains `.bss`; the owned linker resolves both. Invalid initializers
must fail before output rather than become zero storage.

Scalar constant expressions are evaluated in Sotlas before object emission.
The evaluator covers integer and floating arithmetic, bit operations, bounded
shifts, Boolean logic and typed comparisons. Signed overflow, invalid division,
invalid shifts and nonfinite floating results are diagnosed by rejection.
References emit the folded bit pattern. Forward references, general calls,
conditional constants and additional constant types remain open.

Native numeric scanning and rational conversion now accept bounded scientific
notation, including uppercase `E` and explicit exponent signs. The optional
Stage-0/reference lexer has the same syntax for differential execution.

Native local scalar arrays accept lists and repeated runtime values; large
repetitions use a fill loop and evaluate the repeated value once. Boolean arrays
can feed CFG conditions. Scalar/Boolean/float `if/else` expressions lower to
lazy native CFG arms and a typed join value. These forms execute in calls,
returns and loops, including nested `else if`.

The native source bound is now 2 MiB with a separate checked 4 MiB extended
source arena. The growth is needed by the actual compiler sources, not credited
as language parity. The writer's conditional relocation check now uses its
existing 4,096-entry branch table correctly. Explicit unsafe same-width
integer/float pointer reinterpretation supports the native constant evaluator;
different-width and unguarded reinterpretations remain rejected.

Acceptance gates are in `tests/test_sotlas_native_frontend_closure.py` and the
existing float and native-driver suites. The requested frontend/ownership
checklist records the exact closures and remaining parent items. The complete
language migration and sovereignty checkpoint score are not promoted by this
block; full regression and CI certification are still required.

Local SV8.33 results: the complete Windows regression suite passed **2,777
tests with 65 skips**. The C11 job passed **707 tests**. The final additional
constant-type guard then passed the **43-test frontend/float/Windows-driver
set**, including a fresh original-module native generation chain. The earlier
Boolean-field rejection fixture was replaced with a genuinely unsupported
nested-array shape and a positive Boolean-field layout/copy/mutation execution
gate. Native Linux execution, Linux generation identity and the Darwin
cross-build passed; macOS runtime execution still requires CI. These results
do not close the remaining ownership/lifetime/ARC and broader frontend items.

### SV8.34 — exclusive POD transfers and read-only internal borrowing

The Sotlas parser records explicit ownership qualifiers in TypeRef metadata
and retains their full source span. The Sotlas semantic pass now tracks
exclusive POD bindings and internal transfers through calls and returns.
Use after move, duplicate consumption, implicit domain erasure and pointer
escape fail before object emission. Structured branch merges and scalar
conditional calls preserve `MAYBE_MOVED`; returned paths do not poison the
remaining live path. Repeated outer-owner consumption on loop backedges is
rejected.

Internal `whisper` POD parameters support read-only calls and forwarding.
Borrowing leaves an exclusive caller binding live. Mutation, storing/returning
the whole borrowed value, pointer escape, foreign boundaries and overlapping
borrow/consume arguments are rejected. Native record parameters use the
existing internal address ABI; scalar parameters use immutable values.
Weak storage and runtime invalidation remain separate open requirements.

TargetValue metadata preserves domains on accepted parameters, local bindings
and aggregate return destinations without changing the record ABI. An execution
gate runs the Sotlas parser, semantic pass and lowering over another source and
inspects these actual IR domains.

Compiler growth exposed residual 1 MiB project guards in all three native
drivers. These now enforce the already allocated 2 MiB input boundary, including
space for source separators. The change preserves bounded reads and output
transactionality.

This is a native ownership foundation, not completion of the entire ownership
runtime. Shared ARC, heap cleanup, owned fields/globals, stored weak references,
general borrowed-reference ABI and arbitrary ownership CFG remain open in the
[closure checklist](sotlas_native_frontend_ownership_checklist.md).

Local validation of the final block: **2,791 Windows regression tests passed
with 65 skips**. The focused frontend/Windows-driver set passed **45 tests**;
the frontend closure set passed **34 tests** on Windows, Linux (WSL) and
Windows Python 3.10.11. Linux native generation identity and Darwin compiler
cross-build passed alongside the ownership command gate. The C11 regression
step passed **707 tests**. CI certification and macOS runtime execution remain
required; this evidence does not close the remaining parent checklist items.

### SV8.35 — constant dependencies and lazy constant control flow

Native module lowering now registers layouts and scalar constant declarations
before evaluating dependencies and publishing initialized storage. Later
declarations are available to constants and static initializers. Resolution
tracks pending, resolving, ready and failed declarations; cycles fail before
object emission rather than exposing provisional zero values.

Constant `if/else`, `&&` and `||` expressions evaluate only their selected path.
Both arms still undergo the ordinary typed lowering checks. Unknown names,
type mismatches, cyclic references and general function calls cannot hide in
inactive arms. Arithmetic in an inactive arm is not evaluated. Validation
restores temporary IR counts and value identities, and resolves referenced
constants to their actual values before caching them.

The gate covers integer, float and Boolean results, initialized storage,
unsigned wrapping, signed-overflow rejection, dependency cycles, 64-declaration
capacity and bounded nested expressions. Null initializers, identity casts and
transparent unsafe scalar constants retain their prior behavior. General
constant calls, remaining conversion forms and aggregate/string constant
values remain outside this native contract.

Local validation: the complete Windows regression suite passed **2,798 tests
with 65 platform/toolchain skips** in 628.822 seconds. The frontend closure
set passed **41 tests** on Windows, Linux (WSL) and Windows Python 3.10.11.
Original-source native compiler generation and Stage 2/3 identity passed on
Windows and Linux, alongside the Darwin compiler cross-build. CI and macOS
runtime certification remain required.

### SV8.36 — record control flow and original project diagnostics

Native conditional expressions now produce record values in locals, calls,
returns, assignments and loops. Both arms must have the same record layout.
Only the selected arm runs, and its fields are copied into independent result
storage. Nested records, floating fields and accepted fixed-array fields use
the existing native copy ABI.

Exclusive POD conditional results transfer owners per path and preserve
`MAYBE_MOVED` joins. Erasing a result's domain or consuming an owner while a
conditional borrow may reference it is rejected. Raw pointer/reference
conditionals retain reference identity; record values cannot silently become
foreign-pointer arguments or escaping raw-pointer returns.

All three native drivers retain bounded original file paths and flat source
segments for projects. Compiler syntax and semantic diagnostics recover the
original file, line, column and source excerpt after import removal and
topological ordering. Explicit source lists receive the same mapping. Source
map exhaustion fails before artifact I/O, and failed compilations preserve
existing output. Synthetic/unmapped locations retain a combined-stream fallback.

The gate checks root and dependency errors, reordered arguments, source paths
with spaces, and check/build/object modes. General diagnostic cause parity,
non-POD ownership payloads and the remaining control/cleanup forms stay open.

Local validation: the Windows regression run passed **2,805 tests with 65
skips** in 639.199 seconds. The combined frontend/Windows-driver set passed
**59 tests**. The frontend set passed **47 tests** on Windows, Linux (WSL)
and Windows Python 3.10.11. The Linux source-map, original-source generation
identity and Darwin compiler cross-build gates passed. The additional
Linux/macOS source-map methods were registered after general-suite discovery
and checked separately (two expected Windows skips); the Linux method was
executed in WSL. CI and macOS runtime certification remain required.

### SV8.37 — lexical defer and structured cleanup

The Sotlas parser now accepts standalone lexical blocks. Native structured
lowering registers deferred calls, assignments and blocks without running them
at registration. Actions execute in reverse order at block exit, early return,
break, continue and loop backedge. Loop jumps preserve defers outside the loop,
and terminated paths do not also receive ordinary backedge cleanup.

Deferred actions retain the lexical bindings visible at registration and read
their current mutable storage at cleanup. Shadowed identifiers and temporary
locals in deferred blocks do not overwrite later live binding metadata.
Scalar and record return values are captured before deferred writes execute.
The no-defer path bypasses cleanup scratch allocation.

The current native contract is ownership-free. Capturing or declaring
ownership-qualified values in deferred payloads requires reservations and
drop/ARC integration that are not implemented by this block. Nested defers,
nonlocal jumps inside payloads, error propagation and bare-name cleanup fail
closed. Active defers are bounded to 128 per function; structured depth retains
the existing 64-level bound. This is not unwind/ARC closure.

Migration accounting remains tied to the broad contracts in the closure
checklist. Scoped execution gates establish partial capabilities; their count
must not be presented as a percentage completion of the 43 broad items. A
70% migration claim requires a separate full-contract audit and is not certified
by this milestone.

Local validation: the Windows regression suite passed **2,813 tests with 67
platform/toolchain skips** in 642.009 seconds. The final standalone-block CFG
selection adjustment then passed **66 frontend/Windows-driver tests**, including
native Stage 2/3 identity. All **54 frontend tests** passed on Linux (WSL) and
Windows Python 3.10.11. Linux native generation and Darwin compiler cross-build
passed. CI and macOS runtime certification remain required.

### SV8.38 — native static scalar array lists

The Sotlas frontend folds explicit global array lists using the same typed
constant evaluator as scalar declarations. Lists accept integer, floating and
Boolean elements, forward constant references and lazy conditional values.
Every element must match the declared type and the list must match the exact
array length. Runtime calls, pointer/record elements and invalid arithmetic
remain rejected.

The Sotlas object writer emits each element at its declared width in writable
ELF data, preserving mixed zero/nonzero entries and floating bits. All-zero
lists retain zero storage. Native executable linking preserves these sections
for the existing ELF, PE and Mach-O targets. Global Boolean indexed loads now
participate in native conditions instead of being rejected by the scalar load
type filter.

A flat table holds at most 4,096 explicit elements across the module. Shape,
types and capacity are checked before a range is committed. Compact repeated
initializers keep their existing representation and capacity behavior. The
table cursor resets for each module lowering.

Five execution gates cover scalar widths, forward constants, indexed mutation,
exact ELF section bytes, all-zero storage, invalid initializers and the shared
table boundary. The integer/float cases also compare against canonical C11
execution. This milestone advances static initialization parity; aggregate,
string and relocatable pointer initializers remain open.

Local validation: the complete Windows suite passed **2,819 tests with 67
platform/toolchain skips** in 752.214 seconds. All **59 frontend gates** passed
on Windows and Linux (WSL); the same gates plus the previous matrix regression
case passed **60 tests** with Windows Python 3.10.11. Linux original-source
native generation identity and the Darwin compiler cross-build passed two
additional gates. macOS runtime execution and CI certification remain required.

### SV8.39 — local record arrays through native value lowering

The native parser accepts interleaved field/index chains. The Sotlas lowering
tracks record element layouts in the local array metadata, preserves exact
strides and copies fields into independent element storage. Lists and repetition
support pointer-free records with nested records and existing scalar-array
fields. Large repetitions evaluate their source once and execute a native copy
loop instead of duplicating initialization IR for every element.

Indexed elements participate in field mutation, whole-element assignment,
local value copies, calls, direct record returns and conditional record results.
Deferred writes execute after return storage has been copied. Return checking
compares an indexed element's declared type rather than its whole array type.
Ownership analysis rejects qualified values copied into ordinary arrays.

This block accepts at most 4,096 elements and 64 KiB of record element storage
per declaration. Pointer/ownership fields, wrong record types, immutable writes,
implicit foreign pointer escape and literal out-of-range indices fail closed.
Record zero shorthand, slices, aggregate array ABI and record arrays inside
records remain pending. Five execution gates cover these capabilities and
their rejection paths. General array parity remains open.

The complete driver build exposed the previous 4,096-call patch limit on
Windows. Object emission now holds 8,192 call patches and up to 12,288 combined
relocations (including the unchanged 4,096 data-patch limit). Bounded scratch
tables use the existing global emission context rather than growing the
writer's stack or relaxing local-array limits. An additional gate executes
4,100 and 8,192 calls and rejects 8,193 calls. Emission remains sequential.

Local validation: the final Windows regression suite passed **2,825 tests with
67 platform/toolchain skips** in 654.763 seconds. The frontend/Windows-driver
run passed **77 tests**, including native Stage 2/3 generation. All **65 final
frontend gates** passed on Linux (WSL), including exact call-patch capacity;
Windows Python 3.10.11 passed those gates and the previous matrix regression
case (**66 tests**). Linux original-source generation identity and Darwin
compiler cross-build passed two additional gates. CI and macOS runtime
certification remain required.

### SV8.40 — native match statements and live-path ownership joins

The Sotlas parser preserves `MatchStmt` and `MatchArm` nodes, with source spans
for selectors, patterns and bodies. Native lowering evaluates the selector
once and emits a bounded comparison/branch chain through the existing Target
IR. Scalar integer types, Boolean values and explicit-discriminant enums are
supported; enum patterns must belong to the selector's enum. Named scalar
module constants and negative integer patterns preserve their declared widths.

Coverage requires a final wildcard. Duplicate values, mismatched patterns,
missing coverage and more than 64 arms fail closed. Block or single-statement
arms follow the existing parser syntax, with optional commas. Bindings remain
local to their arm. Nested matches, mutable storage, record returns and lexical
cleanup execute natively. Exclusive state joins combine continuing arms and
exclude returned arms, rejecting a later consume after a possible earlier move.
Owner-free loop jumps use the existing path-specific cleanup.

Wildcard-free exhaustiveness, payload bindings, guards, ranges, match
expressions and owned loop-jump joins remain pending. The dispatcher uses no
host runtime. Ten gates cover single evaluation, scalar widths, enum identity,
scopes, mutation, cleanup, return snapshots, ownership, syntax and capacity.

Local validation: the general Windows suite passed **2,835 tests with 67
platform/toolchain skips** in 650.096 seconds. The frontend/Windows-driver
run passed **87 tests**, including Stage 2/3. All **75 frontend gates** passed
on Linux (WSL); Windows Python 3.10.11 passed those gates plus the previous
matrix regression (**76 tests**). Linux original-source generation and Darwin
cross-build passed. Three file-driver match gates were registered after general
suite discovery and checked separately: actual Windows and Linux native CLI
execution passed, while macOS execution remains a CI requirement. These gates
exercise check/compile/run with an empty tool PATH and preserve the previous
executable when wildcard coverage is missing. CI certification remains pending.

### SV8.41 — finite match coverage and selector validity

Native Boolean and explicit-enum matches may omit the wildcard when their
patterns cover every declared value. Integer matches still require a wildcard.
Enum constants preserve nominal identity: constants from another enum or an
integer type cannot substitute for an enum pattern, and enum constants cannot
be used as plain integer patterns. Duplicate folded values remain rejected.

Wildcard-free dispatch includes a representation guard. A raw value outside
the proven finite domain traps through the existing checked-index operation,
before any arm executes. The final arm is entered only after domain membership
has been established. This check introduces no host runtime or new ABI; trap
unwind and cleanup on hardware faults remain pending.

Six gates cover finite coverage, nominal mismatches, early-return ownership
joins, defer order, all 64 enum cases, missing cases and invalid raw values.
The three native file-driver gates now exercise wildcard-free Boolean and enum
matches through the Sotlas-written check/compile/run path.

Record-array execution also exposed the old scalar-only stride restriction in
IndexAddr validation/emission. The neutral IR and native writer now accept
positive strides through INT32_MAX; non-power-of-two layouts use native integer
scaling after the existing bounds check. The execution gate covers 12-byte
records and 32-byte records with inline arrays, including the final element.
Payload patterns, guards, ranges and match expressions remain open.

Local validation: the final Windows suite passed **2,844 tests with 69
platform/toolchain skips** in 702.435 seconds. The frontend/Windows-driver
run passed **94 tests**, including native Stage 2/3 and wildcard-free match
execution. All **81 frontend gates** passed on Linux (WSL), where the invalid
enum case was confirmed to terminate with SIGILL; Windows confirms the illegal
instruction exception in a child process. Windows Python 3.10.11 passed **82
tests**, including the previous matrix regression. The Linux native match CLI,
original-source generation and Darwin cross-build passed three additional
gates. macOS runtime execution and CI certification remain required.

### SV8.42 — native internal direct access and original record storage

The Sotlas semantic checker accepts DIRECT for internal POD parameters and
preserves its domain in the AST and TargetValue metadata. Direct access is
read-only and non-consuming. Calls, repeated aliases, direct forwarding,
forwarding to whisper, static functions, scalar calculations and structured
loops preserve an exclusive caller's state. Consuming forwarding and a borrow
overlapping consumption in another argument are rejected.

The native call lowering reads the actual parameter domain. Direct record
arguments use the existing address instead of the ordinary record argument
copy; scalar arguments retain the immutable-value ABI. The IR execution probe
checks both the DIRECT parameter metadata and the exclusive caller operand's
original domain flag. Owning/value and whisper record argument behavior retains
its existing contract. No retain/release runtime is introduced.

Mutation, whole-value storage/return, pointer/address escape and foreign escape
fail closed. Qualifier placement remains parameter-only. Instance receivers,
stored aliases, full alias lifetimes and qualified defer captures remain open.
The native capability report includes `direct-internal`. Five frontend gates
and three platform file-driver gates exercise these contracts and their failure
paths, including output preservation after a rejected mutation.

Local validation: the final Windows suite passed **2,852 tests with 71
platform/toolchain skips** in 641.197 seconds. The frontend/Windows-driver
run passed **100 tests**, including Stage 2/3 and direct execution through the
Sotlas-written file CLI. All **86 frontend gates** passed on Linux (WSL);
Windows Python 3.10.11 passed those gates and the previous matrix regression
(**87 tests**). Linux direct CLI, original-source generation identity and Darwin
compiler cross-build passed three additional gates. The existing all-domain
rejection gate now uses a pointer payload for DIRECT, preserving its rejection
and artifact checks while the new POD parameter contract is accepted.
macOS runtime execution and CI certification remain required.

### SV8.43 — native ownership for records with scalar array fields

The Sotlas ownership verifier now recognizes fixed scalar arrays inside POD
records, including fields of recursively nested plain records. Exclusive
bindings, consuming calls, returns, `direct` reads and `whisper` reads use the
existing record layout and retain the same move/borrow checks. Plain-to-owned
value copies keep independent inline array storage. No heap runtime or drop
glue is required for these resource-free payloads.

Array field constructors now accept nonzero repetition and explicit value
lists. Lists evaluate each element once in source order; repetition evaluates
its value once and stores that value in every slot. Lowering verifies the
declared count, scalar type and literal range before emitting an object.
The field limit remains 1 through 256 elements. Primitive integers, Boolean
values and f32/f64 are accepted; pointer elements, qualified elements, arrays
of records and nested array types remain rejected.
The optional legacy C emitter still refuses nonzero field repetition after
semantic acceptance; native object execution provides this implementation.
Its older semantic-refusal gate now checks that explicit emitter boundary.

Native type inference resolves indexed scalar values to existing element
TypeRef identities rather than propagating the container type through
arithmetic, calls and returns. The source AST is not mutated. The platform CLI
gates exercise this with a sum of three borrowed array elements and preserve
the previous output when a malformed initializer is rejected.

Nine frontend gates cover transfer/return, nested independent storage, moved
and maybe-moved reads, borrow mutation/escape, capacity/type rejection, typed
field layouts, ordered list evaluation and indexed arithmetic. Windows,
Linux and Intel macOS file-driver gates check the native `check`, compile and
execute path without host build tools. The public
`examples/native_owned_packet.sotlas` demonstrates borrowing and transfer.
General ownership-bearing array elements, lifetimes, ARC, qualified defer
captures and resource cleanup remain separate migration requirements.

Local validation: the frontend/Windows-driver run passed 110 tests, including
original-source Stage 2/3 identity. Linux native CLI execution, original-source
generation identity and Darwin compiler cross-build passed three gates. The
public owned-packet example executed successfully on Windows. All 95 frontend
tests passed on Linux (WSL) and Windows Python 3.10.11 with the final source
revision. The full Windows regression suite passed 2,864 tests with 73
platform/toolchain skips in 654.002 seconds. The older struct semantic gate
also passed with its updated legacy-emitter boundary expectation.
Intel macOS runtime execution and CI certification remain required.

### SV8.44 — four frontend and four ownership advances

This revision advances eight bounded native contracts. It does not mark the
broader migration requirements complete.

| Area | Advance | Execution/rejection evidence |
|---|---|---|
| Frontend 1 | Copy local scalar arrays and record array fields into scalar array fields, including whole-field assignment | `test_native_array_fields_copy_local_and_record_arrays_independently`, `test_native_array_field_value_copies_reject_length_and_element_mismatch` |
| Frontend 2 | Infer instance-method result types through returns and nested calls | `test_native_method_results_preserve_types_in_nested_calls` |
| Frontend 3 | Accept internal direct/whisper receiver signatures and validate the enclosing record identity, including Self | `test_native_direct_and_whisper_receivers_forward_without_consumption`, `test_native_borrowed_receivers_reject_foreign_types_mutation_and_overlap` |
| Frontend 4 | Report moved-value, borrowed-mutation, escape and deferred-reservation causes with existing native source positions | `test_native_frontend_ownership_eight_advances_and_diagnostics` in all three platform driver suites |
| Ownership 1 | Convert scalar projections from qualified POD records without allowing pointer/whole-value escape | `test_native_owned_scalar_projections_cast_without_alias_escape` |
| Ownership 2 | Track receiver borrowing through forwarding and reject receiver/argument consumption overlap | `test_native_borrowed_receivers_reject_foreign_types_mutation_and_overlap` |
| Ownership 3 | Reserve qualified roots for deferred read-only calls and release reservations at lexical exit | `test_native_deferred_borrows_read_current_storage_and_release_at_scope_exit`, `test_native_deferred_borrows_reject_consumption_before_cleanup` |
| Ownership 4 | Merge runtime short-circuit move states and preserve statically skipped literal operands | `test_native_short_circuit_ownership_preserves_statically_skipped_owners`, `test_native_short_circuit_ownership_rejects_moved_and_maybe_moved_paths` |

Array field copies retain exact scalar type/count checks and independent inline
storage. Read-only receivers cannot mutate, escape or consume their caller.
Deferred reads observe current storage at cleanup; an intervening move is
rejected, including consuming returns. Ownership reservations are scoped and
do not implement ARC/drop/unwind. Only direct deferred calls acquire this new
qualified-capture contract; qualified deferred blocks/assignments stay rejected.
Both short-circuit operands are validated; runtime-dependent consumption
creates a maybe-moved state, while a skipped literal path restores its owner.

Ten frontend gates and three platform CLI gates were added. The older borrowed
array rejection fixture now checks a qualified deferred block rather than a
read-only deferred call. Its mutation/storage/pointer-escape negatives remain,
and the new deferred-call gates check both execution and rejected consumption.
Local validation: the full Windows suite passed 2,877 tests with 75
platform/toolchain skips in 847.858 seconds. All 105 frontend gates passed on
Windows, Linux (WSL) and Windows Python 3.10.11. The new Windows native CLI gate
passed independently; Linux native CLI diagnostics/execution, original-source
Stage 2/3 identity and Darwin compiler cross-build passed three additional
gates. The Windows fixed-point gates also passed in the general suite.
macOS runtime execution and CI certification remain required.

### SV8.45 — bounded owned read-only deferred blocks (2026-10-13)

**Certified starting point:** [CI run #latest green](https://github.com/HPinho/sotlas_dev/actions/runs/38374537558) at `2e63cb719d661ee4c3440a363a9b1e5453b2976b`. This cut extends the Sotlas-written frontend ownership verifier and the already certified native lexical defer lowering, **not** the Python/C11 implementation.

Qualified POD owners can already be reserved by one direct deferred read-only call. This advance accepts a bounded `defer { observe(owner); observe(owner); }` block: each statement must be an internal direct call with an unowned result, must preserve every owner state at registration, and must reserve all qualified roots until the enclosing lexical scope cleans up. Multiple reads execute in written order during cleanup, under the existing LIFO ordering among defer registrations. Consumption between registration and cleanup is rejected; moves become valid again after the scope exits.

The new gate proves native execution of two borrowed calls, their sequencing with another defer and a post-cleanup transfer. Negative gates retain fail-closed behavior for consuming/mutating payloads, owner moves before cleanup, owned value copies, nested defers and noncall control flow. There is **no** resource-bearing closure, ARC/drop, unwind, stored borrow or generally typed effect contract; the parent checklist item remains open. No sovereignty checkpoint increment or Python/C-removal percentage is credited.

**Verification:** native CI certification is pending for this cut; it is not a new green baseline before the matrix succeeds. **Next: SV8.46** — explicit effect/escape facts on native typed expressions and fail-closed validation of deferred invocation effects, followed by ownership-aware cleanup work.

### SV8.46 — native deferred borrowed-argument effect proof (2026-10-13)

**Certified green baseline:** `e14c3c686bfe45b3de4ad48315bb96283e02a3f2` / [CI #38390785874](https://github.com/HPinho/sotlas_dev/actions/runs/38390785874). All three platform matrix gates passed for SV8.45.

This cut adds a limited *effect proof* to the Sotlas-owned AST ownership verifier, without importing C11/Python semantics. A deferred call that captures a qualified POD owner must have arguments whose evaluation is statically free of mutation, `unsafe`, pointer/address operations and unknown calls. Nested internal calls are resolved through the actual native AST and their bodies are checked transitively, with bounded depth (32) and fail-closed recursion. Calls without implementations, unresolved foreign calls, cycles and unsupported effectful syntax cannot masquerade as certified read-only argument evaluation. The proof applies to standalone and block forms of borrowed deferred calls.

The *deferred observer's body itself* is not falsely classified as pure: an internal `direct` or `whisper` observer may continue to update unrelated global logs using its existing certified semantics. The verifier continues to ensure that borrowed owner states do not change, consumption before lexical cleanup is prohibited and all old defers without qualified roots are unchanged. New native execution gates evaluate nested pure helpers at cleanup and transfer the owner afterward; negative gates reject unsafe/global writes and transitive side effects in deferred argument expressions.

This does **not** finish generic effects, target capability contracts, alias lifetimes, unwind or ARC/drop; checklist parent stays open. No additional sovereignty milestone or Python/C reduction percentage is credited. **Validation:** source-level structural checks have been done, but the Linux/Windows/macOS CI matrix must pass before this candidate replaces its baseline.

**Next planned: SV8.47** — effect/capability contracts carried in typed AST and verified at native call boundaries, starting from a bounded fail-closed subset without changing the canonical frontend oracle.

### SV8.47 — four frontend plus four ownership hardening contracts (2026-10-13)

**Certified baseline:** `b497a22a41852d8723de34ece67a24c86532a711` / [CI #38397024494](https://github.com/HPinho/sotlas_dev/actions/runs/38397024494). The last native deferred-argument effects work passed the complete cross-platform matrix.

**Frontend (4 bounded advances):** (F1) lexical parameter/local identity for pure argument expressions instead of silently trusting unrecognized global reads, (F2) checked AST instance/static method callee resolution without confusing callee symbols with variables, (F3) explicit fail-closed rejection of unsafe/assembly/mutation/loops/opaque effects in deferred argument computations, and (F4) effect-specific file/line/column diagnostics on Linux, Windows and Intel macOS, preserving pre-existing artifacts.

**Ownership (4 bounded advances):** (O1) owner-preserving borrow masks for array index projections, (O2) include conditional guards alongside selected branches when gathering borrowed roots, (O3) reject same-call overlap of those roots with consuming sole arguments and reject unsupported owner-bearing expressions, and (O4) retain projected owner reservations through lexical deferred cleanup while permitting a move after exiting the scope.

The new native frontend suite contains positive execution and negative compiler tests for lexical helper lets, typed instance helpers, global/unsafe/recursive/looping effects, indexed and conditional owner masking, lexical cleanup and moved-owner rejection. Three file driver tests assert the dedicated effect cause in native `--check` and compile and verify existing output preservation. None of the previous tests is weakened or removed.

These are **partial subcontracts** of open items, not eight complete parent feature families. Complete typed AST parity, namespaces, `shared` ARC/drop, lifetimes, resource unwind, and general effects remain open. The sovereignty checkpoint score stays at 9/10 (90% of declared profile checkpoints), not an estimate of Python/C reduction. **Certification pending for this commit**; only adopt as baseline after CI green. **Next SV8.48:** typed effect/capability call boundary facts and further owner alias lifetime/escape checks, or regression repair first if any matrix job fails.

### SV8.47 regression repair — native result identity and object capacity (2026-10-13)

[CI #38404011557](https://github.com/HPinho/sotlas_dev/actions/runs/38404011557) on `dcf5c4c87392d1660488e0985439f68ef9abd3a6` failed the Ubuntu/Windows/macOS matrix. Every runner reported the same three failing gates: an older certified typed static/direct read (`number(Token::read(owner))`) was rejected, the new projected-defer executable rejected a direct inline array-list initializer in a mutable sole record, and Windows-driver Stage 1 object generation failed near the end of the merged Windows source (`23446:51`). The precise Windows backend resource limit is not proven from those logs; this is a size-sensitive candidate fix, not a certified attribution.

**Code repair:** a typed, resolved internal call that produces an unowned scalar has independent returned storage; the outer borrow checker must not inherit all owners consumed or borrowed while evaluating the nested call. Preserve fail-closed handling of unresolved calls and preserve indexed/conditional owner tracing, which continue to prohibit borrow/consume overlap. Use the existing `Sema.find_visible_binding` lexical resolver and exclude module-global bindings rather than compiling a second custom scope walker; this reduces native compiler code size and ensures consistent name visibility. The scalar-return check resolves the declared TypeRef and excludes pointer/owned results instead of treating all call results as independent. The projected-defer gate now first constructs the typed record value and transfers it to a mutable `sole` owner, matching the already certified aggregate transfer contract while *retaining* the deferred indexed read, post-registration mutation, after-scope transfer and negative premature-move test.

All existing tests are retained; a new explicit positive regression gate checks that a typed static result does not retain the original owner's borrow. **Previous certified baseline remains `b497a22a41852d8723de34ece67a24c86532a711` / [CI #38397024494](https://github.com/HPinho/sotlas_dev/actions/runs/38397024494). Do not promote this fix until the full CI matrix is green. **Next SV item remains SV8.48**; Python/C removal percentages are unchanged.

### SV8.47 CI #38413498370: isolated remaining array-field setup (2026-10-13)

[CI run #38413498370](https://github.com/HPinho/sotlas_dev/actions/runs/38413498370) on `9953faa2c7d138634e15d67aae6a07abead48f41` reports one failed test in each completed Linux, Windows and Intel macOS matrix job: `test_sv847_ownership_projected_defer_reservation_and_scope_release`. The other old regression gates, native Windows driver compilation, static/direct scalar result tests and Stage 2/3 checks passed. The failure is a deterministic native compile exit 10 at source line 3, column 42: the test's plain-typed record initializer used a direct array-list expression for the record's field. The exact phase behind that token-level error remains unverified; it is not evidence that the deferred indexed read itself failed.

**Single-test setup isolation (no acceptance weakening):** use the independently certified array-local list initializer followed by record-field value copy (`let values:[u32;2]=[20,21]; let source:Packet=Packet{values:values}; let mut owner:sole Packet=source;`). The failing test still must compile and run the *same* deferred indexed owner projection, update its underlying element before cleanup, observe the updated element, transfer the entire owner after scope exit and reject a move before cleanup. The already green `test_native_array_fields_copy_local_and_record_arrays_independently` separately checks array-local initialization, independent field storage and mutations; it is retained unchanged as the setup gate. **No existing test is deleted and no previously positive effect or ownership case is changed to a negative expectation.**

**Outstanding gap:** direct inline array-list initializers embedded in POD record fields in the combination seen above are not certified by this run; test and implement that exact construction separately before calling it complete. This is not a justification for silently weakening general array initializer rules.

**Certification remains pending:** last full green baseline is `b497a22a41852d8723de34ece67a24c86532a711` ([CI #38397024494](https://github.com/HPinho/sotlas_dev/actions/runs/38397024494)). Do not move it until the new matrix is completely green; keep SV8.48 pending. This repair does not change the claimed sovereignty checkpoint count or the Python/C dependency reduction.

### SV8.47 regression root cause: direct-borrow storage into a global (2026-10-13)

[CI #38419894158](https://github.com/HPinho/sotlas_dev/actions/runs/38419894158) on `d7a8d9bd9ab8292baae50eb0892363452a46d5a1` has exactly one failing test across every Linux, Windows and Intel macOS Python matrix job: `test_sv847_ownership_projected_defer_reservation_and_scope_release`. The returned error **line 3, column 42** did not follow any of the earlier inline-array/array-local setup changes. Crucial diagnostic interpretation: `NativeI32Tests.compile` *prepends* `module probe;
` to the source string. Thus the diagnostic points to `v` in `fn read(v:direct u32)->void{unsafe{total=v;}}`, **not** to the array initializer that sits on the third line of the test's own string. The three previous attempted source-setup changes did not address this node.

**Corrective semantics:** a `direct u32` parameter is an active borrowed alias and may not escape by being stored verbatim in the global `total`. The native ownership analyzer correctly fails closed because the RHS has a nonzero borrow domain; lowering should not suppress that rejection. The test only needs an independent scalar snapshot: `unsafe{total=total+v;}` computes a plain scalar result, stores that result and still records the updated value seen when the `defer` runs. Preserve the accepted *borrowed indexed argument*, update-before-cleanup, expected `total==42`, post-scope move and the negative move-before-cleanup test. Add a separate negative test that `unsafe{total=v;}` in the same direct-deferred context stays rejected. Existing native code and all other acceptance gates remain intact.

**Status:** candidate single-commit fix; success not asserted before full CI. The last certified green baseline remains `b497a22a41852d8723de34ece67a24c86532a711` / [CI #38397024494](https://github.com/HPinho/sotlas_dev/actions/runs/38397024494). Continue to SV8.48 only after green. No Python/C-elimination percentage or sovereignty checkpoint is advanced.

### SV8.48a — native deferred helper call-boundary capabilities (2026-10-13)

**Certified green baseline:** `41e25edfc0b870661003488a630ad17aab87e0e4` / [CI #38439105217](https://github.com/HPinho/sotlas_dev/actions/runs/38439105217), including Linux, Windows and macOS.

The native Sotlas ownership/effect verifier now inspects typed helper signatures as well as bodies when proving that a nested call used by an owned-borrow `defer` has no unmodeled effects. A call to an apparently readonly function still transfers ownership if a parameter is `sole`; such consuming or unknown-domain parameters fail closed. Ordinary typed POD inputs and read-only `direct`/`whisper` inputs remain allowed. Pointer-bearing parameters are rejected except the already supported read-only native `self:&Self` receiver; pointer and ownership-qualified results are not certified independent value outputs. The existing bounded AST/body traversal checks mutable operations, unsafe effects and transitive call chains.

New native tests cover an accepted read-only direct helper invoked during deferred cleanup, plus a forbidden sole-consuming helper whose body only reads. All prior frontend/ownership tests, Stage 2/3 fixed-point checks and cross-platform gates stay unchanged. This implements a **bounded call-boundary sub-contract**, not general ownership/lifetime analysis, effect inference, ARC/drop or capability propagation through native IR.

**Candidate until CI certification:** do not promote this commit over the green baseline until the full matrix passes. **Next SV8.48b:** explicit typed effect/capability facts propagated toward native call IR and escape-aware foreign-boundary gates. No new sovereignty checkpoint or Python/C reduction percentage is claimed.

### SV8.48b — per-argument ownership capabilities in native Target IR (2026-10-13)

**Certified baseline:** `5e6c8fd343478dac43ab5c0c83f0fc66f86dc820` passed the full Linux/Windows/macOS matrix at [CI #38448890155](https://github.com/HPinho/sotlas_dev/actions/runs/38448890155).

**Change:** Sotlas-written AST lowering now retains typed ownership roles at each native `TargetOpcode::Call` boundary using pre-existing `TargetInstruction.flags` and `immediate_bits` fields, without changing struct layout, calling convention, emitted bytes or Target IR version. For the existing bounded 24-operand native call subset, a compact two-bit role per argument represents 0=plain, 1=sole/exclusive transfer, 2=whisper borrow, 3=direct borrow. Aggregate-return hidden storage receives a plain role; source parameter roles remain in declaration order. Unknown domains fail closed. Call instructions carrying metadata must have exactly the typed-capability flag and zero out-of-range bits, verified in `target_module_validate_cfg` before emission. Legacy manually produced Call instructions with both metadata fields zero remain compatible.

**Acceptance:** positive native x86-64 execution of ordinary, direct and sole parameters in one call graph; aggregate-return sret ABI preserved; static IR contract checks verify metadata placement and shape validation. Existing native self-build, all previous ownership/effect/cleanup gates and platform cross-matrix tests remain unchanged.

**Limits:** in-memory typed call-domain metadata is not yet a complete canonical effect system, runtime ARC/drop, proof of imported-module signatures, or serialization into portable module objects. No reduction in Python or C usage or new sovereignty checkpoint is claimed. **Candidate until this commit's full CI is green**; keep previous green baseline. **Next SV8.48c:** cross-function signature consistency and explicit escape/capability checks at foreign/system call boundaries, or regression repair if CI fails.

### SV8.48b regression repair — Windows native bootstrap (2026-10-13)

CI #38455787897 failed at the same native Windows driver Stage1 compile step on every Ubuntu, Windows and macOS matrix job. The diagnostic, expanded line 23494 column 36, maps to windows.sotlas line 1121: the parity comparison after an unsigned slash-count modulo in the nested Windows argv parser. The same Windows module passed in green baseline 5e6c8fd / CI #38448890155. The additional IR-capability logic increased code generation work; the precise backend limit has not been independently proven.

Repair: keep the full typed call IR capability semantics and existing validation, but remove a redundant declared-arity pass from call_capability_profile: all call sites already validate source arity and any single hidden aggregate-return argument. The domain encoder retains its 24-argument bound and fail-closed unsupported roles. In the Windows driver, use the equivalent (slashes & 1) == 1 and (slashes >> 1) for unsigned usize, eliminating modulo and division inside the nested CFG at the point reported. Add a static plus arithmetic parity test. All runtime quoting, AST/IR, cross-platform and self-bootstrap gates remain unchanged.

Status: candidate until all 9 CI jobs pass. Last certified baseline 5e6c8fd. Next planned item SV8.48c only after green; no change to Python/C reduction or sovereignty milestone percentages.
### SV8.48b native Stage1 capacity guard — regression #38467300671 (2026-10-13)

[Actions #38467300671](https://github.com/HPinho/sotlas_dev/actions/runs/38467300671), at `ab3baffc832905759a7df7cb166cd310bee3b342`, again fails the Windows-driver Stage1 cross-build in Linux, Windows and macOS jobs: `test_sotlas_native_windows_driver.NativeWindowsDriverTests.setUpClass`, with expanded source location `23489:31`. Changing the nested Windows argv parser from unsigned division/modulo to bit operations did **not** address the failure. The same driver successfully compiled on green [#38448890155](https://github.com/HPinho/sotlas_dev/actions/runs/38448890155) at `5e6c8fd343478dac43ab5c0c83f0fc66f86dc820`, before SV8.48b enlarged the compiled native lowering/IR code. Previous failures at almost the same late-source location track increased bootstrap workload, but do not by themselves prove which buffer is exhausted.

**Bounded structural repair:** raise Stage1's in-memory SSA value capacity from 65,536 to 131,072, instruction capacity from 131,072 to 262,144, operand capacity from 262,144 to 524,288, and CFG block capacity from 32,768 to 65,536, **updating the matching real static backing arrays** in `bootstrap/sotlas/native_compiler/main.sotlas`. This is legitimate capacity headroom, not a bypass of instruction validation, ownership checking or the source-size bound. The caps continue to be checked through `append_value`, `append_instruction`, `append_operand` and block allocation; overflow still fails closed. The 24-argument metadata encoding, validator and all Windows CLI tests remain unchanged. Add a static consistency gate that ties public capacity constants to actual backing arrays and the lowerer. Native cross-platform Windows-driver compilation remains the decisive acceptance test.

**Uncertainty:** the exact first exhausted capacity is not instrumented in the existing Stage1 diagnostics; this is a capacity-based repair candidate, not yet proven green. If the failure persists, instrument the failing lowering path to expose the actual rejection reason rather than making another blind size adjustment. Only the full matrix can certify a new baseline. **Next:** SV8.48c after green; Python/C reduction remains unmeasured.

### SV8.48b Windows Stage2 → Stage3 native CFG regression (2026-10-13)

[CI #38472529418](https://github.com/HPinho/sotlas_dev/actions/runs/38472529418) at `db52f8040065b2b9419ad337514746a5f9638aaf` demonstrates that restoring matched Stage1 IR capacities fixed all Linux and Intel-macOS suites and the Windows Stage1 bootstrap/driver compile. Only the three Windows Python-version jobs fail now, each at `test_original_modules_build_native_stage2_stage3_fixed_point`: the already built native Windows seed rejects its own source in `--project-resolve-compiler`, reporting **`windows.sotlas:1123:31`** (`index = index + 1;`) in the deeply nested Windows command-line argument decoder. The native Stage1 object is already compiled successfully, so raising global IR capacities again or altering the unsigned parity arithmetic is not justified by the new evidence.

**Repair:** extract a bounded Windows `windows_parse_one_argument` subparser from the outer whitespace/argument loop. Extract the repeated append+advance+failure operation into a small `windows_push_argument_byte` function, to avoid cloning return/error/mutation branches deep inside the combined CFG. Preserve byte-for-byte quoting and backslash rules; exact 67-argument, 4095-byte-per-argument and 32768-byte command-line limits; fail-closed incomplete quotes; terminating NUL writes; and the original global pointer array. The helper reports the consumed position, with 0/error and nonprogress checks in the outer parser, so it cannot loop indefinitely. Keep unsigned bitwise parity and shifts as previously documented.

The static native source gate confirms the independent decoder boundary and fail-closed conditions. **The existing actual-Windows original-modules Stage2/Stage3 executable fixed-point test remains mandatory and unchanged**, along with quoted-path, output preservation, and all Linux/macOS tests. Baseline stays `5e6c8fd` until the new matrix is green; this is a candidate, not a claim of certification. **Next:** SV8.48c only after all nine platform suites pass. No Python/C percentage is inferred.

### SV8.48b Windows Stage2/Stage3 arena mismatch repair (2026-10-14)

Actions [#38491311681](https://github.com/HPinho/sotlas_dev/actions/runs/38491311681) on `1c1f124b127348cd62bae947aea5d4edb8ed89d1` passes Linux, macOS Intel and the Windows native Stage1 bootstrap. Only the Windows Python 3.10/3.11/3.12 jobs fail the mandatory `test_original_modules_build_native_stage2_stage3_fixed_point`, at `windows.sotlas:1131:49` while the native Windows seed recompiles its own project.

**Confirmed configuration mismatch:** the earlier [SV8.48b capacity repair](https://github.com/HPinho/sotlas_dev/commit/db52f8040065b2b9419ad337514746a5f9638aaf) enlarged `native_compiler/main.sotlas`'s Target IR static arenas, but omitted the independent arrays and `ScalarLowering::new` arguments inside `native_driver/windows.sotlas`. The Windows stage2 compiler therefore still used the smaller values/instructions/operands/CFG-block arenas; it also retained a smaller native function table. Late-source `unsupported native form` remains consistent with capacity pressure, but the first exhausted resource is not separately instrumented.

**Repair:** match the Windows file driver to the already accepted compiler arenas: 131072 `TargetValue`, 262144 `TargetInstruction`, 524288 `TargetOperand`, 65536 `TargetBlock`, 8192 `TargetFunction`. Set both each actual static array allocation and its corresponding passed constructor capacity. Keep existing operand/CFG/value overflow checks, source diagnostics, target emission validation, PE ABI, direct/whisper/sole call metadata, argv parser, and all existing tests unchanged. Add a permanent structural regression test checking compiler-versus-driver capacity parity, plus constructor and remaining arena wiring. The actual Windows Stage2 → Stage3 byte-for-byte equality test remains the acceptance gate.

Last fully certified green baseline remains `5e6c8fd343478dac43ab5c0c83f0fc66f86dc820` ([#38448890155](https://github.com/HPinho/sotlas_dev/actions/runs/38448890155)). The repair is not certified until the new CI is green; if it still fails, report measured lowerer capacity/reason instead of changing the CLI parser or bumping limits blindly. SV8.48c stays next after CI green. No independently measured Python/C elimination percentage is claimed.
### SV8.48b packaged Linux seed arena parity — regression repair (2026-10-14)

[CI #38496836673](https://github.com/HPinho/sotlas_dev/actions/runs/38496836673) on `025cb8b924ddccea18dd5d98b31ff29778640e86` passed every Python matrix test on Ubuntu, Windows and Intel macOS, all Python distribution installation jobs and the nightly snapshot. The only failed job was **Build and install native Linux seed**, at the step that uses the **installed standalone Linux-native compiler** to build a Windows PE driver without host build tools. Its native lowering again returned exit 7 at `windows_driver.sotlas:1131:49`. Consequently, dependent PE and Mach-O execution jobs were skipped.

**Confirmed remaining mismatch:** packaging `packaging/native_linux.py` builds the seed using `bootstrap/sotlas/native_driver/linux.sotlas` and includes that driver plus the Windows and Darwin native driver sources in the archive. While `native_compiler/main.sotlas` and the Windows file driver now use expanded Target IR arenas, **both Linux and Darwin file drivers still declared and passed the previous smaller buffers**. Thus the installed Linux compiler exercised by the failed job did not inherit the Stage1 or Windows fixes.

**Single coherent repair:** align the real static allocations **and** `ScalarLowering::new` capacities in the Linux and Darwin native drivers with the already accepted compiler profile: 131072 values, 262144 instructions, 524288 operands, 65536 CFG blocks, 8192 functions. Keep the independently bounded parameters (16384), phi inputs (16384) and targets (65536) unchanged. Do not weaken overflow checks, target validation, C independence, native code generation, existing Windows quoted-argv support, or the Stage2/Stage3 fixed-point test. Add a portable regression gate that checks all three native drivers against the canonical compiler capacity declarations and verifies that the Linux archive bundles those sources. This prevents the previous platform-by-platform divergence.

**Certification:** This commit is a candidate until the full workflow passes, including the installed Linux seed building both Windows and Darwin targets. The last entirely green baseline remains `5e6c8fd343478dac43ab5c0c83f0fc66f86dc820` / [CI #38448890155](https://github.com/HPinho/sotlas_dev/actions/runs/38448890155). SV8.48c remains the next planned feature only after green. Architecture checkpoint evidence and independently measured Python/C removal percentages are not changed.

### SV8.48c — native typed void-call coverage and declared capability agreement (2026-10-14)

**New certified baseline:** `8785c79f1608e88495b1ee49d5ab19dd7f399bc5` succeeded in the complete matrix and installed-native package gates in both [#38503673523](https://github.com/HPinho/sotlas_dev/actions/runs/38503673523) and [#38527902706](https://github.com/HPinho/sotlas_dev/actions/runs/38527902706). Do not weaken the real Windows Stage2/Stage3 native PE fixed-point, Linux freestanding seed, and macOS gates.

**Narrow fix to typed call coverage:** the preexisting scalar and record-return lowering tags `TargetOpcode::Call` with two-bit ownership-capability roles, but `lower_direct_void_call_statement` emitted only the ABI call symbol. A void observer or consumer now emits the same typed per-argument profile and rejects unrepresentable ownership roles. The explicit `target_module_validate_calls` call-signature checker now also compares the tagged per-argument roles to the callee's own canonical SSA parameter domain flags (0 plain, 1 sole, 4 whisper, 6 direct), in addition to exact argument scalar types and arity. External declarations have no SSA domain flags and therefore may only be matched to plain roles in this bounded proof.

**Acceptance:** native execution of a borrowed `direct` observer chained through a `whisper` void relay; fail-closed consumption of sole on a void call; a structural validator gate for exact role agreement and foreign-domain rejection. ABI, instruction layout, legacy manually authored untagged calls and compiler paths are unchanged.

**Important scope boundary:** `target_module_validate_calls` is an explicit call-signature validator and is **not yet invoked automatically by every emitter**. This SV8.48c sub-contract strengthens that validator and ensures typed metadata is present on native void calls, but does not claim complete cross-module signature proof, safe arbitrary C FFI, resource lifetime inference, ARC/drop, or effect inference. Continue with SV8.48d to wire reliable call-signature validation into native emitters with appropriate complete CFG/SSA coverage and compiler-symbol handling. **Status:** candidate until new CI green. No new measured Python/C reduction or sovereignty checkpoint is claimed.

### SV8.48d — mandatory typed call-signature gate at unified ELF object emission (2026-10-14)

**Certified baseline:** `8b8d3c28a9ad06db08df73b61c2cdf904473ce4b` / [CI #38566049760](https://github.com/HPinho/sotlas_dev/actions/runs/38566049760), full workflow green including Linux, Windows, Intel macOS and the native packaging/fixed-point jobs.

**Implementation:** integrate the explicit Sotlas-written `target_module_validate_calls` with the universal native `emit_elf64_module_object` entry point. Before writing any object bytes, the entry point now requires the full CFG validator **and** verified call target/arity/type/capability signatures. Fix the call validator's previous null Phi/target placeholders by forwarding the caller-supplied full `TargetPhiInput` and block-target tables. This preserves valid conditional branches and loop CFGs, and prevents the earlier unbound validator from being incorrectly applied to CFG-rich modules. The existing single CFG validation call is replaced, not duplicated, so the full structural pass runs once before call signatures.

Tagged ownership roles (plain/sole/whisper/direct) are checked against callee SSA parameter domain flags; external declarations without certified domain SSA must use plain roles. Unknown/mismatched roles, callee symbols, arity and scalar type mismatches fail closed. Existing untagged legacy IR remains compatible; no ABI/IR struct layout, source grammar, backend machine encoding, or ownership semantics are changed.

**Acceptance:** execute a native program whose single module contains an aggregate-return sret helper, direct-borrow void observer, sole-consuming helper, scalar function call and an `if` CFG branch; enforce a structural gate verifying that the unified emitter passes full Phi/target buffers into its mandatory typed call validator. Prior Stage1, installed Linux seed, Windows PE Stage2/Stage3 binary equality, Darwin Mach-O, and all other tests remain intact.

**Limit:** this is the **unified ELF object writer boundary**, not a claim that every specialized assembly/PE/Mach-O writer independently calls the validator, or that separately compiled modules/foreign linkers have cross-module proof. Mark SV8.48d as a candidate pending a new fully green matrix. **Next SV8.48e:** typed call validation at other emission entry points, then stronger declared FFI/system capability checks, after green. No new Python or C reduction figure is asserted.

### SV8.48d regression correction: distinct synthetic sret role (2026-10-14)

CI #38572500561 at commit 4a42688 failed four previously green ownership frontend tests on every Linux, Windows and macOS runner. All affected tests contain functions returning sole records. The newly mandatory typed call validator incorrectly compared the callee's owned return-destination SSA domain to the final hidden sret pointer argument, which has a plain call capability by ABI contract.

The fix recognizes only the final unnamed internal pointer parameter of a void ABI function as a synthetic sret destination, requires its call role to remain exactly plain, and preserves its underlying owned return value domain. Every named argument still undergoes exact type and ownership-role comparison. Malformed unnamed arguments in non-final, non-pointer or non-void positions remain rejected. The old four acceptance tests and their negative move guards remain required; two additional targeted tests now protect this ABI distinction.

The last certified green baseline stays 8b8d3c28a9ad06db08df73b61c2cdf904473ce4b (workflow #38566049760). The next feature SV8.48e remains pending a new complete green matrix. No changes to Python/C elimination estimates.

### SV8.48e — specialized native scalar CFG emitter call signatures (2026-10-14)

**Certified new baseline:** commit `5e70f47785a53d5dd2af724a085c7bbfff053302` passed full [CI #38579850351](https://github.com/HPinho/sotlas_dev/actions/runs/38579850351), including Linux/Windows/Intel macOS tests and installed native packaging. The prior SV8.48d owned-record sret role regression is closed against this baseline.

**Narrow implementation:** make two previously CFG-only native emitter boundaries, `emit_elf64_scalar_function_object` and `emit_x86_64_scalar_cfg`, require `target_module_validate_calls` before emitting any output bytes. This verifier first checks the **same full CFG, including Phi and branch targets**, then validates direct-call symbol, exact scalar ABI arity and types, and any tagged plain/sole/whisper/direct parameter roles against declared function domains. In each emitter one CFG-only gate is replaced rather than doubled. The IR/ABI representations, support for legacy untagged calls, and both emitters' previous supported instruction and parameter subsets are untouched. The unified ELF64 module writer continues to enforce its own existing typed-call gate.

**Acceptance:** permanent source-level contract test proves both entry points require the full verifier with the correct tables and no duplicate CFG-only gate. Existing scalar CFG and ELF object suites, full native selfhost, installed Linux seed and Windows PE/Mach-O fixed-point matrix remain mandatory. This is a candidate pending a new full green CI run; this change has not been executed locally.

**Limits:** the specialized multi-function scalar assembly and legacy ELF scalar module emitters have different, narrower manually-authored IR conventions. Their integration is deferred to SV8.48f so we do not accidentally reject previously valid hand-authored IR without explicit parity tests. Separately compiled symbols, general FFI/system effect rights, ARC/drop and lifetimes remain open. No new measured Python/C reduction is claimed. **Next:** SV8.48f other legacy call-bearing entry points after green.

### SV8.48f — legacy multi-function scalar emission preflight (2026-10-14)

**Green baseline:** commit `86c6279b206f891a0f1db5c5630d725d283ac974` passed [CI #38588993763](https://github.com/HPinho/sotlas_dev/actions/runs/38588993763), including Linux/Windows/Intel macOS and native installed Linux seed, PE/Mach-O execution and packaging. This is the SV8.48f baseline, **not** proof that the new candidate passed CI.

**Change:** before writing any bytes, require `target_module_validate_calls` at both `emit_elf64_scalar_module_object` and `emit_x86_64_scalar_module`. Both already receive full functions/parameters/values/blocks/instructions/operands tables. Their restricted one-block U32 IR defines no Phi or branch-target tables: null pointers for those tables are safe only because `target_module_validate_cfg` rejects nonzero declared counts. The shared verifier checks CFG structure and direct-call callee identity, return/argument ABI types, arity and tagged ownership roles. Existing opcode subsets and legacy untagged compatibility remain unchanged.

**Acceptance:** `test_sv848f_legacy_multifunction_emitters_preflight_typed_calls` guards both preflight boundaries and missing-side-table fail-closed behavior. Existing native multi-function assembly/ELF positive and bad-call tests, Stage2/Stage3 compiler selfhost, installed Linux seed and Windows/Intel macOS matrix remain mandatory. The new commit was not compiled or executed locally; CI verification is pending.

**Remaining:** specialized single-function U32 and conditional three-block assembly entry points do not receive all tables needed by the shared verifier. Cross-object/foreign rights, ownership runtime cleanup and measured Python/C dependency reduction remain open. **Next: SV8.48g** legacy single-function/conditional boundary parity with explicit negative/positive gates, then inter-module signatures.

### SV8.48g — legacy scalar typed-call and side-table proof (2026-10-14)

**Certified baseline:** `83b991cefc60cfe6a3a35289b45815cb6096a42d` passed full [CI #38598947342](https://github.com/HPinho/sotlas_dev/actions/runs/38598947342) (Linux, Windows, Intel macOS and native installation/execution checks).

**Bounded migration from the frontend/ownership checklist:** the legacy one-function x86-64 assembly emitter lacks the TargetValue and external-signature tables required for full `target_module_validate_calls`. Rather than pretend to certify those calls, it now preflights all instructions and permits tagged calls only with **plain (zero-bit) capabilities, exact self-function symbol, U32 signature and matching arity**; tagged external, borrowed/sole/whisper/direct calls or forged profiles fail before emission. Previously supported *untagged* standalone external calls remain explicitly legacy, not certified for capabilities or effects. This preserves the existing emitter ABI and prevents unauthorized typed claims in codegen.

The three-block conditional assembly emitter rejects nonempty Phi tables and Call/Phi operations before emitting output; the constant-only assembly entry point rejects unrepresentable Phi/target side tables and per-instruction hidden metadata. This does not infer effects or add a general ownership runtime; tests guard the source-level entry boundaries and the established native Stage2/Stage3 positive suites and platform matrix remain required. **This candidate has not yet passed CI.**

**Next: SV8.48h** expand the canonical typed ownership/effect proof to separately compiled module signatures and foreign boundaries (including persistent metadata and no unproven legacy call equivalence), without changing Stage2/Stage3 native fixed point.

### Stage evidence and dependency accounting

Local structural-block regression evidence (2026-10-07): the complete test
suite passed **2,574 tests** with **33 skips** on Windows; the ten new structured
CFG gates add no skips on Windows and execute isolated native machine code.
Linux executes their objects through the Sotlas linker; macOS checks object
emission. Cross-platform CI certification of this block is still pending.

Stages are successive compiler generations, not independent percentages of
completion. The following distinctions must remain visible in progress reports:

| Generation | Evidence already available | Required native closure |
|---|---|---|
| Stage 1 | Native Linux, Windows and Intel macOS seeds run the production compiler core, certified in CI | Full canonical frontend parity |
| Stage 2 | Native seeds on all three supported hosts build Stage 2 from the original source modules, certified in CI | Broaden native language and target profiles |
| Stage 3 | Stage 2 produces byte-identical Stage 3 images on all three supported hosts; Stage 3 compiles a runnable program, certified in CI | Broader canonical language features and additional architectures |

The current sovereignty checkpoint score is **90%: 9 of 10 closures certified
in CI for the declared profiles**. This replaces the historical unweighted 40% estimate with an
explicit checklist. It measures architecture milestones, not lines of code,
effort remaining or a percentage of installed dependencies already removed.

| Checkpoint | Evidence / remaining work | State |
|---|---|---|
| Production native frontend | Lexer, Parser and Sema execute in native images | Certified |
| Compiler-core Target IR lowering | Complete production lowerer emits native objects | Certified |
| Native machine/object backend | Complete production x86 writer emits native objects | Certified |
| Owned ELF linking | Application and kernel image gates; native runtime linking | Certified for declared profile |
| Native file compiler driver | Real argv and file input/output through kernel/OS adapters | Certified for Linux, Windows and Intel macOS profile |
| Native generation chain | Original-source self-build and Stage 2/3 native fixed point | Certified for Linux, Windows and Intel macOS profile |
| Native imports and project builds | Bounded native glob discovery, graph checks and project builds | Certified for declared profile |
| Full language/frontend parity | Broader canonical features and diagnostics remain | Open |
| Native Windows/macOS toolchains | Windows and Intel macOS file drivers, execution and native generation | Certified for declared profiles |
| Installed seed/distribution closure | Reproducible Linux static seed, original sources, verified installation | Certified for Linux profile |

The native Linux profile can compile and self-build after receiving an initial
seed without Python or C tooling. The default installed cross-platform
toolchain still retains hosted bootstrap dependencies. Historical percentages
in earlier milestone entries describe their snapshots and are not the current
checkpoint score. Promote local closures to certified only after their CI
gates pass.

### SV8.7 structural CFG validation: acceptance contract

The native object probe reproduced on the certified baseline fails at
`target_ir.sotlas:571:5`, the helper-call guard immediately before the
function-table loop in `target_module_validate_cfg`. The structural CFG block
reached the nine-argument call at `1149:13`; the call ABI block now advances
through call validation and into SSA dominance. This progress is not yet
CI-certified. The command uses Stage 1's `--compile-obj` path;
successful C emission is not evidence for this milestone.

The SSA validator lowers through its reachability and dominator byte buffers.
The native global-array cast and larger ELF branch tables now allow Stage 1 to
emit the complete real Target IR module. The regression gate requires the ELF
object and representative validator and global symbols. A native Stage 2 build
requires additional compiler modules and remains a separate gate.

The current `lower_declared_function` dispatches to specialized terminal-loop
helpers (`lower_while_search_then_return`, `lower_while_if_jumps_then_return`
and `lower_while_jump_then_return`). Those helpers do not cover the validator's
nested function/parameter/block/instruction loops. The implementation block
therefore needs these connected capabilities:

- Structured statement lowering with explicit loop headers, body blocks,
  latches and exits; `break` and `continue` must target the innermost loop.
- Correct mutable state across backedges and branch joins, with typed Phi
  inputs or explicit typed storage, and lexical removal of inner-loop locals.
- Conditional paths that return early or continue without emitting subsequent
  statements on the terminated path. Preserve short-circuit evaluation when
  a condition contains calls or potentially trapping memory reads.
- Deterministic block and value identities, valid flat table ranges and SSA
  dominance, plus fail-closed behavior on exhausted buffers and unsupported
  forms. A failed lowering attempt must not publish partially built IR.

Acceptance requires positive nested-loop and mutable-state execution cases,
negative scope/CFG/capacity cases, and the unchanged real `target_ir.sotlas`
native probe. Existing scalar-loop, machine-backend and hosted Stage1/2/3
equivalence gates remain regression requirements. The baseline CI being green
does not imply this new native milestone is already closed.

The hosted fixed-point evidence below remains a regression oracle while native build-chain closure is implemented.

### Fixed-Point Equivalence Gates:
1. **Source Emission Equivalence:**
   `hash(Stage 2 output) == hash(Stage 3 output)`
   The emitted C compiler source reaches exact convergence in the current hosted bootstrap; this is an oracle, not the final sovereignty proof.
2. **Application Object Determinism:**
   `SHA256(Stage1.compile_obj(app)) == SHA256(Stage2.compile_obj(app)) == SHA256(Stage3.compile_obj(app))`
   Bit-for-bit identical ELF relocatable objects.
3. **Freestanding Kernel Object Determinism:**
   `SHA256(Stage1.compile_obj(kernel)) == SHA256(Stage2.compile_obj(kernel)) == SHA256(Stage3.compile_obj(kernel))`
   Bit-for-bit identical freestanding ELF objects.
4. **Application Executable Link Equivalence:**
   `SHA256(Stage1.link_exe(app.o)) == SHA256(Stage2.link_exe(app.o)) == SHA256(Stage3.link_exe(app.o))`
   Bit-for-bit identical static ELF executables.
5. **Freestanding Kernel Image Link Equivalence:**
   `SHA256(Stage1.link_exe(kernel.o)) == SHA256(Stage2.link_exe(kernel.o)) == SHA256(Stage3.link_exe(kernel.o))`
   Bit-for-bit identical freestanding kernel images.
6. **Application C Emission Determinism:**
   `SHA256(Stage1.emit_c(app)) == SHA256(Stage2.emit_c(app)) == SHA256(Stage3.emit_c(app))`
   Bit-for-bit identical generated C code across stages.

### Verification Routine:
- `verify_stage_fixed_point` in `bootstrap_pipeline.py`.
- **Validation Suite:** `tests/test_sotlas_sovereignty_sv8.py` (5/5 tests passing).

---

## SV9 Certification: Native Compiler/Backend as Default Installed Path

Milestone **SV9** transitions the native Stage 1 compiler to the default compilation path for all Sotlas CLI invocations:

### SV9 Audit Evidence
1. **Default Backend Configuration:**
   - `sotlas compile` defaults to `--backend native`.
   - The CLI argument parser specifies `choices=["native", "llvm", "c11", "sotlas-x86_64"]` with `default="native"`.
2. **Native Pipeline Execution:**
   - `sotlas compile app.sotlas -o app.o` emits an ELF64 object directly via `sotlas_stage1 --compile-obj`.
   - `sotlas compile app.sotlas -o app.bin` links an ELF64 static executable directly via `sotlas_stage1 --link-exe`.
   - Output files are valid ELF64 binaries (`0x7f, 'E', 'L', 'F'`, 64-bit, little-endian, `EM_X86_64`).
3. **Freestanding Support:**
   - `sotlas compile kernel.sotlas --target x86_64-freestanding -o kernel.bin` links a freestanding binary directly with entry point `_start`.
4. **Reference / Legacy Tooling Preservation:**
   - `--backend c11` remains available for explicit reference validation and backward compatibility.
   - Non-native backends (`c11`, `llvm`, `sotlas-x86_64`) are accessible on demand.
5. **Fail-Closed Argument Validation:**
   - Missing input files, invalid targets, and invalid backends fail closed with clean, non-zero exit codes.
- **Validation Suite:** `tests/test_sotlas_sovereignty_sv9.py` (7/7 tests passing).

