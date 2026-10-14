# Native compiler drivers

`linux.sotlas` is a Linux x86-64 compiler driver written in Sotlas. It reads
source files, runs the production frontend and Target IR lowerer, writes ELF
objects and links executable images. File operations use kernel syscalls;
the generated compiler has no ELF interpreter or dynamic C runtime.

## Initial seed

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

## Compile files

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

## Experimental Windows executable output

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

## Native Windows compiler

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

### Windows platform imports

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

## Check source without writing artifacts

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

## Explicit multi-file builds (SV8.21a)

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

## Bounded native module resolution (SV8.21b1)

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

## Discover imported files

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

## Install a native seed bundle

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

## Explicit native self-build

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

## Kernel interface

Reserved bodyless scalar declarations named `sotlas_linux_read`,
`sotlas_linux_write`, `sotlas_linux_open` and `sotlas_linux_close` lower to a
validated `SystemOp`. The existing C ABI syntax describes the scalar boundary;
these calls do not bind libc symbols. The backend emits Linux x86-64 syscalls
0, 1, 2 and 3 directly and preserves negative kernel error returns as `i64`.
Other declarations continue to use ordinary external-call linking. The Linux
process-entry ABI has a dedicated ELF note flag; it cannot be selected by
supplying arbitrary constant entry arguments or a freestanding target.

## Experimental Intel macOS output

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

## Native Intel macOS compiler

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

## Native signed 32-bit profile

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

## Signed byte, word and wide integers

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

## Bit operations and variable shifts

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

[`native_bit_operations.sotlas`](../../../examples/native_bit_operations.sotlas)
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

## Floating scalars and profile discovery

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

## Initialized storage and expression values

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

## Native match statements

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

## Local record arrays

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

## Static scalar tables

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

## Lexical defer and cleanup

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

## Deferred owned-borrow argument effects (SV8.46)

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

### SV8.47 regression clarification — field-array setup

The native projected-`defer` acceptance gate now constructs its
two-element array through a verified local array-list initializer, copies
that value independently into a POD record field, then transfers the
record to a mutable sole owner. Both steps have explicit native execution
coverage. The deferred indexed read and its reservation, before-cleanup
mutation, after-cleanup move and premature-move rejection are unchanged.

Embedding an array-list literal directly into the same record initializer is
tracked as a separate validation gap instead of silently treating a
type-error during test setup as a `defer`-ownership failure.

### SV8.47 direct-borrow cleanup regression — corrected error position

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

## SV8.47 regression note

Resolved internal scalar calls return independent values, not borrow aliases of
their argument owners. The checker must retain owner roots for direct indexed
and conditional references but must not carry those roots through the already
checked independent scalar return. The lexical pure-name verifier uses bounded,
shared local/parameter scanning to avoid unnecessary native codegen growth.
The deferred indexed-array test constructs a plain value before transferring
it into a mutable sole owner, preserving the scope-reservation contract.
The last certified CI remains the SV8.46 green run until all platforms pass.

## SV8.47 — checked effect names and projected borrow roots

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

## SV8.48a — native deferred helper capabilities

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

## SV8.48b — typed native call capability metadata

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

## SV8.48b Windows bootstrap regression repair

The native call-capability encoder relies on the existing call-site arity check instead of scanning declarations a second time. It retains the strict 24-argument limit and fail-closed unknown domain handling, including the plain hidden aggregate-return pointer.

The Windows argv parser uses unsigned bitwise parity and shift for the slash count. For usize, (slashes & 1) == 1 is equivalent to slashes % 2 == 1, and slashes >> 1 equals slashes / 2. Both avoid expensive native division/modulo lowering inside nested control flow. Existing quoted path execution tests and IR invariants remain required.
## SV8.48b native Stage1 IR headroom

The self-hosting Stage1 now allocates 131,072 TargetValue slots, 262,144
TargetInstruction slots, 524,288 TargetOperand slots, and 65,536 TargetBlock
slots, with the same bounds enforced by the native IR builder. This prepares
for large combined-module cross-builds such as the Windows file driver and
does not change the language, parser capacity, ABI, ownership validation or
emitted Target IR format. Capacity constants are required to match their
actual static backing arrays by a dedicated contract gate. The full matrix
must succeed before treating this as a certified fix.

## SV8.48b Windows native Stage2 fixed-point CFG hardening

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

## SV8.48b Windows self-hosted Target IR arena parity

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
## SV8.48b — installed native Linux seed and driver arena parity

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

## SV8.48c — typed void calls and capability-signature agreement

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

## SV8.48d — checked signatures at ELF object emission

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

## SV8.48d owned aggregate-return call validation

The unified ELF signature validator treats the final unnamed pointer
parameter of a void-ABI internal function as a synthetic return destination.
Its call role must be plain even when the destination SSA value preserves
sole ownership from a returned record. Named parameters still require exact
plain/sole/whisper/direct role equality; forged synthetic positions fail.
All native Stage2/Stage3 and platform matrix acceptance gates remain intact.

## Project diagnostics

Project compiler diagnostics map resolved source positions back to the original
file, line, column and source excerpt after import removal and topological
ordering. Explicit source lists retain their original file positions too.
The source map holds at most 8,192 segments across 64 files and rejects
capacity exhaustion before output I/O. Paths remain bounded to 4,095 bytes.

## Constant dependencies and control flow

Constant `if/else`, `&&` and `||` expressions evaluate only the selected path.
Inactive arms still undergo type and name validation, and cannot hide function
calls or cyclic dependencies. Static initializers may refer to later scalar
constants. Validation preserves real dependency cache values and restores all
temporary IR identities. Tables remain bounded to 64 declarations, nesting to
64 levels and each temporary expression to 128 instructions. Null pointer
initializers, identity casts and transparent unsafe scalar values retain their
existing behavior.

## Owned records with scalar array fields

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

## Internal direct access

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

## Exclusive POD transfers and internal whisper parameters

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
destinations. See the [closure checklist](../../../docs/sotlas_native_frontend_ownership_checklist.md)
for the remaining migration requirements.
