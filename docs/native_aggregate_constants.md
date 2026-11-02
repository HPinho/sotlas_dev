# Native aggregate constants

Module `const` declarations can store concrete POD records, payload enums and
bounded arrays in the native object:

```sotlas
struct Item { pub value: u32; }
const COUNT: usize=2;
const ITEMS: [Item;COUNT]=[Item { value: 20 }, Item { value: 22 }];

fn total() -> u32 {
    let mut sum: u32=0;
    for item in ITEMS { sum=sum+item.value; }
    return sum;
}
```

These are immutable named data objects. They are not runtime initializers or
a general compile-time interpreter. Existing scalar constants retain their
checked value/dependency table and their unsigned dimension rules.

## Initializers and limits

Accepted initializers reuse the existing native static-data serializer:
record literals with every field initialized, supported payload constructors,
array lists/repetitions and scalar-array zero forms. Record/enum arrays require
typed element constructors; raw zero storage could contain an invalid enum tag.
Supported graphs contain
numeric/bool scalars, pointer-free records, inline record arrays and POD payload
enums, including explicit discriminants and nested arrays. Packed records retain
their native layout. Scalar constant expressions and forward scalar dependencies
can supply initializer fields and capacities.

Arrays in aggregate const declarations have at most 256 elements and 4096 bytes.
The existing shared initializer pool, symbol and layout limits also apply.
Raw-pointer arrays, pointer/resource fields, ownership-qualified graphs,
incomplete/wrong nominal literals, invalid sizes and runtime calls are rejected,
including declarations that are never read. Aggregate-to-aggregate initializer
aliases and compile-time field/index projections are not introduced. A record
constant cannot serve as an array dimension.

## Reads, copies and receivers

Field/element reads, match/if-let decisions, fixed-array iteration and existing
internal value calls/returns use the named storage. Typed local record/array
copies own independent POD storage: changing a mutable copy does not change the
constant. Array-copy layout registration now handles identifier, field and
unsafe-wrapper initializers through the same bounded snapshot representation.

Direct assignment, field/element writes and mutable address creation reject an
immutable const binding. Readonly interior addresses retain existing raw-pointer
contracts. A direct constant-record receiver can call a method declared with a
readonly reference such as `self: &Self`. Mutable receivers are rejected for
both value-returning and void calls, including receivers rooted in a constant's
fields/elements. Local mutable copies retain their ordinary methods.

These checks enforce source-level immutability in the native profile. The
objects reuse existing initialized/zero storage and do not introduce physical
read-only pages, a new section ABI, general alias/lifetime analysis, resource
drop glue or foreign aggregate guarantees. Other receiver forms retain their
existing gates. Separate-object semantic module parity remains open.

## Application and verification

The [profile-table example](../examples/native_aggregate_constants/main.sotlas)
stores records with weights and explicitly tagged policies. It verifies a local
copy can change independently, reads a default record, iterates the constant
table and exits 42. This fixed configuration bounds its arithmetic to u32.

`tests/test_sotlas_native_aggregate_constants.py` covers records, scalar/record
arrays, nesting, payload tags, calls/returns, shadowing, packed layout, addresses,
receivers and rejection of mutation/resource/runtime initializer forms. Native
platform rebuild gates include imported check/build, object generation, host
execution and ELF/PE/Mach-O emission. Full CI certification remains pending.

## Local validation

The final contract passed 23 focused tests, alongside 87 CFG/AST checks and
21 public-inventory/phase checks. The generated phase matrix stayed consistent.
Native runs passed 196 tests per Linux/Windows producer, including existing
static records/tables, named dimensions, arrays, internal ABI, field layouts
and pattern values.

The imported profile application passed check, object generation, direct build
and execution with exit 42, with host tools absent from PATH. Object, ELF, PE
and Mach-O files matched byte for byte between producers. Actual Mach-O
execution remains a macOS platform-gate responsibility.

Original-source native rebuilds retained strict Stage 2/3 byte equality on
each host. Focused native tests used Stage 2; Stage 3 images are identical.
Compiler SHA-256 values:

- Windows: `3d3c0aead7bb8a0fe35935d3cd7ca7028676d3f3237a7b347512ad5d3d45741e`
- Linux: `84a0527de5b0f6075f86503ec679b293d36202dcb65bbc1a89850ec0d0e7ec49`

This evidence covers the declared POD profile, not full constant evaluation,
resource ownership, separate-object semantic parity or native distribution.
