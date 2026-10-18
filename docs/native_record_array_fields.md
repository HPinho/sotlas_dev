# Native inline arrays of records inside structs

The native compiler accepts fixed array fields whose elements are pointer-free
records. Element storage is inline: copying an enclosing value creates
independent element storage instead of aliases to the original table.

```sotlas
struct Item { pub value:u32; }
struct Table { pub items:[Item;2]; }

pub fn main_entry()->u32 {
    let original:Table=Table{items:[Item{value:20},Item{value:22}]};
    let mut edited:Table=original;
    edited.items[0].value=0;
    return original.items[0].value+original.items[1].value;
}
```

The [inventory example](../examples/record_table/README.md) also exercises
record returns, a read-only `whisper` parameter and dynamic indexing in a loop.

## Accepted forms

- Typed element lists and repetition such as `[Item{value:21};2]`.
- Repetition evaluates its initializer once and copies the resulting value.
- Initialization from an existing local record array or another compatible field.
- Element reads, nested field reads/writes and whole-element replacement.
- Whole-field replacement from lists, repetition and compatible array storage.
- Lists/repetition stage their complete array value before replacing a field,
  preserving swaps such as `table.items=[table.items[1],table.items[0]]`.
- Nested pointer-free records, scalar arrays inside elements, nested record
  array fields and local arrays of these containers.
- Enclosing record copies, function returns and supported internal borrows.
- Exclusive POD containers keep the existing `sole` transfer/use-after-move
  rules. This does not add runtime destruction for resource-bearing elements.

Record alignment and padded size determine array stride. Dynamic indexing uses
the native checked `IndexAddr` instruction. Out-of-range literal subscripts
are rejected; a failing dynamic bound traps before the element is read.

## Limits and rejection

Each field accepts 1–256 elements and at most 65,536 bytes of inline element
storage. Existing compiler table, nesting, instruction and total frame limits
still apply; a large nested value may exceed a different compiler capacity.
Layout alignment and size accumulation reject unsigned overflow rather than
wrapping an oversized record into a smaller allocation.
List staging uses temporary stack storage and recursive field copies.

Element types must already be available to the native record layout pass.
Pointers, ownership-qualified resource fields and recursive by-value layouts
are rejected. Scalar multidimensional array syntax is not added; nested record
types provide the supported matrix representation. Nominal element identity
and exact declared counts must agree even when two record layouts happen to
have the same size. Immutable and borrowed mutation remains rejected.

These are native language values, not an expansion of cross-object library
ABI. Pointer/aggregate library signatures, general slices, record array
parameters/returns as standalone arrays, non-POD elements, ARC/drop glue and
the remaining ownership domains are still separate roadmap work.

## Evidence

`tests/test_sotlas_native_record_array_fields.py` executes positive cases as
native machine code and rejects incompatible layouts/counts, pointer/resource
payloads, invalid indices, ownership erasure and prohibited mutation. A dynamic
out-of-bounds case verifies the trap. Existing frontend/ownership gates remain
enabled; the old unsupported `[Inner;3]` negative case is replaced by a
pointer-bearing record array because plain record fields are now supported.

Support is claimed for this native profile. It is not a certification of full
canonical C11 parity or every master-roadmap array/ownership combination.
