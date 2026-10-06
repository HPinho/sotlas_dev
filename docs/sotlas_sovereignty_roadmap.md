# Sotlas Sovereignty Roadmap

**Status:** active implementation track  
**Started:** 2026-10-03 (America/Fortaleza)  
**Green baseline at track start:** `7162167dec6fd5fa0a216121b147335d222e43f1` / CI #1063  
**Current certified baseline:** `a8605eb6cf276809248192dd02bccd7c12df4c1a` / CI #1106

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

## Sovereignty milestones

| Milestone | Objective | State |
|---|---|---|
| **SV0** | Recover a green cross-platform baseline before sovereignty work | ✅ CERTIFIED (`7162167d`, CI #1063) |
| **SV1** | Define backend-neutral Target IR in Sotlas, independent of C/Python containers | ✅ CERTIFIED |
| **SV2** | Lower the Sotlas-written native frontend AST/sema subset into native Target IR | 🟡 IN PROGRESS (scalar/struct memory, scalar enums, string literals, constrained static/receiver methods, wide calls/comparisons and integer module constants are certified; general arrays/slices, payload enums/match and richer compiler expressions remain open) |
| **SV3** | Feed native Target IR into the Sotlas-owned x86-64 backend for scalar functions | ✅ CERTIFIED (single-block U32 subset) |
| **SV4** | Native CFG, calls, aggregates, ownership/effects and ABI parity required by real apps | 🟡 IN PROGRESS (x86 backend emits validated scalar CFGs with backedges; source lowering covers return branches and a constrained `while`/`break`/`continue` subset; same-module direct `u32` calls execute on host ABI; aggregates and ownership/effects remain open) |
| **SV5** | Sotlas-owned object emission and freestanding/native linking for supported targets | 🟡 IN PROGRESS (ELF64 multi-object linking certified in `tests/test_sotlas_sovereignty_sv5.py`; Windows PE/COFF, macOS Mach-O and archives pending) |
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
- **Current item — SV4.8b / SV8 prerequisite:** checked dynamic reads from global fixed arrays using native `base + index * stride` addressing. Element type/stride/count are preserved in BSS metadata and out-of-bounds access traps before memory is touched. CI #1107 exposed and the follow-up fixes the ELF narrow-return whitelist plus base-register preservation in indexed addressing; #1106 remains the certified baseline until the repair workflow is green.
- **Next item — SV4.8c / SV8 prerequisite:** indexed stores plus raw-pointer indexing/provenance rules; unsupported pointer shapes remain fail-closed.
- **Following gate — SV8.7:** Stage1 compiles the real `bootstrap/sotlas/native_compiler/backend/target_ir.sotlas` module to a native ELF object without C emission.
- **Sovereignty metric:** application/kernel native gates are C/Python-free; compiler bootstrap gates remain hosted. Current tracked reduction is 40% eliminated / 60% remaining for both Python and C until a native Stage1→Stage2 build gate closes.

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

