# Sotlas Sovereignty Roadmap

**Status:** active implementation track  
**Started:** 2026-10-03 (America/Fortaleza)  
**Green baseline at track start:** `7162167dec6fd5fa0a216121b147335d222e43f1` / CI #1063  
**Current certified baseline:** `f963c933af39e5dba989594efb34bfbfdf535823` / [CI #1130](https://github.com/HPinho/sotlas_dev/actions/runs/37649186099) (completed successfully; verified 2026-10-07)

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
| Stage 1 | Native Linux and Windows seeds certified; native Intel macOS driver implemented with execution gates pending CI | Full canonical frontend parity and macOS candidate certification |
| Stage 2 | Native Linux and Windows seeds build Stage 2 from the original source modules, certified in CI | Broaden the native language and target profiles |
| Stage 3 | Native Linux and Windows Stage 2 build identical Stage 3 images; Stage 3 compiles a runnable program, certified in CI | Extend native generation closure to macOS and broader language features |

The current sovereignty checkpoint score is **80%: 8 of 10 closures certified
in CI for the declared profiles**. This replaces the historical unweighted 40% estimate with an
explicit checklist. It measures architecture milestones, not lines of code,
effort remaining or a percentage of installed dependencies already removed.

| Checkpoint | Evidence / remaining work | State |
|---|---|---|
| Production native frontend | Lexer, Parser and Sema execute in native images | Certified |
| Compiler-core Target IR lowering | Complete production lowerer emits native objects | Certified |
| Native machine/object backend | Complete production x86 writer emits native objects | Certified |
| Owned ELF linking | Application and kernel image gates; native runtime linking | Certified for declared profile |
| Native file compiler driver | Real argv, file input/output, kernel syscalls; no C runtime | Certified for Linux |
| Native generation chain | Self-object equivalence and Stage 2/3 native fixed point | Certified for Linux and bounded Windows profile |
| Native imports and project builds | Bounded native glob discovery, graph checks and project builds | Certified for declared profile |
| Full language/frontend parity | Broader canonical features and diagnostics remain | Open |
| Native Windows/macOS toolchains | Windows generation and Intel Mach-O execution certified; native Darwin compiler and generation gates implemented | Candidate pending full CI |
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

