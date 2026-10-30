# Native layout queries

The Sotlas-written parser and native lowering now implement the language's
existing `span_of`, `stride_of`, `align_of` and `field_offset!` syntax directly.
Values come from the same registered x86-64 layouts used by field access, array
addressing and the machine ABI. No C compiler or foreign layout helper is called.

## Queries and types

| Query | Meaning |
| --- | --- |
| `span_of::<T>()` | Complete storage size of T, including padding |
| `stride_of::<T>()` | Distance between successive T values; complete sizeof-style storage size |
| `align_of::<T>()` | Required native alignment of T |
| `field_offset!(Record, field)` | Byte offset of a named struct field, including valid offset zero |

The existing spelling without `::`, such as `span_of<T>()`, is also accepted.
Results have the native `usize` representation, normalized to the backend's
unsigned 64-bit scalar tag. Use an explicit conversion to a narrower integer.
Ordinary calls to a function named `span_of` are still ordinary calls when no
type-query syntax is present.

The current profile covers scalar integers, bool and floats; known pointer
types; registered record layouts; simple/payload enum size and alignment; and
fixed arrays of scalars or supported POD records with 1–4096 elements. Querying
an array's stride returns the size of the **entire queried array**, not the
stride of one element. Pointer-bearing records can be queried individually,
including runtime controls. That does not enable pointer-bearing array values.
`Self` resolves inside a supported impl. Field offsets address struct fields,
not enum variant payloads or nested field paths.

Unknown types/fields, standalone void, qualified ownership layout requests,
unsupported array forms, oversized/invalid counts and implicit narrowing are
rejected. The compiler validates every query after registering aggregate layouts,
including queries in unreachable statements and uncalled functions. An invalid
type cannot become accepted merely because control flow skips its query.

Native `@packed`, `@aligned` and `@align` requests, including packed/alignment
arguments to `@repr`, are now explicitly rejected rather than silently discarded
by the attribute parser. Their requested layouts are not implemented in this
backend. This does not implement general attribute parity.

Queries emit integer constants into Target IR and work in native module
constants, arithmetic, conditions, calls and returns. Constant dependencies can
refer to records declared later in the module. Constructors and value expressions
are not evaluated. This does not add arbitrary compile-time execution or permit
query expressions in array-length type syntax. Generic type instantiation,
dynamic slices, packed/custom alignment and other targets retain their existing
support gates. This delivery does not extend the legacy Sotlas C emitter path.

## Runtime integration

The reusable pool now derives slot/control size and alignment from its actual
record declarations. Its optional scalar backing derives the required word count
from the slot and u64 layouts. The text map likewise queries its control layout
and derives the seven-word entry byte size. Literal schema positions and entry
word counts remain explicit; they are not confused with struct field offsets.
Capacity, alignment, overlap and stale-generation checks remain enforced.

Public constants include `NATIVE_POOL_SLOT_SIZE`, `NATIVE_POOL_SLOT_ALIGN`,
`NATIVE_POOL_SLOT_WORDS`, `NATIVE_POOL_CONTROL_SIZE`,
`NATIVE_POOL_CONTROL_ALIGN`, `NATIVE_TEXT_MAP_CONTROL_SIZE`,
`NATIVE_TEXT_MAP_CONTROL_ALIGN` and `NATIVE_TEXT_MAP_ENTRY_SIZE`.
The current layouts still have their documented sizes; the runtime no longer
duplicates those sizes in its control/metadata range checks.

[The executable example](../examples/native_layout_queries/main.sotlas) compares
queries against real addresses of adjacent descriptor records and a selected
field, then exercises a pool whose checks use queried metadata layouts. Success
exits with 42. The example performs ordinary memory access, not MMIO or physical
device access.

## Evidence and limits

`tests/test_sotlas_native_layout_queries.py` executes scalar/record/array/enum
queries, padding, actual field addresses and array stride, module constants,
forward references, Self, calls, returns and negative/dead-code cases. Existing
pool/map tests exercise allocation and cleanup after the runtime migration.
The original-source Stage 3 gates on Linux, Windows and Intel macOS now include
the imported layout example, host execution and ELF/PE/Mach-O emission.

The starting baseline is `b713137`, reported green by the user. The new delivery
remains a candidate until its own full CI completes. These are native profile
capabilities, not full frontend parity or removal of every Python/C requirement.

Local final evidence: 171 layout/storage/address/array/pool/map execution tests
passed per rebuilt native Windows/Linux host. A separate hosted run completed
91 layout, parser/AST, Target IR, compatibility, kernel-profile and contract
checks with 89 passing and 2 environment skips. The generated phase matrix
also passed its consistency check. Invalid unknown-layout and alignment requests
failed native check/object emission without changing an existing output artifact.

Original-source Stage 2 and Stage 3 images were identical within each host,
with reconstruction and application execution using no host build tools on PATH:

- Windows SHA-256: `f275d79031d1cf93c302a469b09a0a29c99cb4f25a86ed24eba8b37efd1ee5d8`
- Linux SHA-256: `9255d89d495d5c00b45d31f3841bc96bea263eb865f6bf29d2816cdfc0f93f90`

Layout and interior-storage examples passed imported check/object/direct build
and host execution with exit 42. Their object and ELF/PE/Mach-O bytes matched
across the native producers. The separate standalone configuration-map PE gate
again encountered the previously recorded local Defender block (`WinError 225`),
including access to its PE artifact from the Windows-mounted Linux workspace.
That gate is not counted as passing; its native map unit cases passed. Protection
was not modified. Actual Intel macOS execution and the new full CI remain pending.
