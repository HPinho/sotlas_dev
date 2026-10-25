# Native global record tables

Global fixed arrays of pointer-free records now accept explicit constant lists
and repetition. The Sotlas-written compiler serializes complete elements using
their padded record size; it emits initialized data or BSS when every byte is zero.
The existing native object/linker path produces ELF, Windows PE and Intel Mach-O.

```sotlas
struct Entry { pub code:u16; pub value:u32; }
static table:[Entry;2]=[Entry{code:1,value:20},Entry{code:2,value:22}];
pub fn main_entry()->u32 {
    unsafe { return table[0].value+table[1].value; }
}
```

## Executable contract

- Initialize from exact-length record lists or `[Record{...};N]`.
- Fold supported typed scalar constant expressions inside each element, including
  integer, floating-point and Boolean fields and module constants.
- Initialize nested records and scalar/record array fields recursively.
- Read fields with dynamic indexing; copy and return elements as independent
  record values, or pass them through supported internal borrow calls.
- Update fields or replace elements of explicitly mutable tables. Immutable
  tables reject both field and whole-element writes.
- Use actual element stride, including padding; keep padding bytes zero.
- Reject out-of-range literal indices and trap on a failing dynamic bound before
  reading/writing the element. Only supported unsigned index types are accepted.
- Resolve bindings lexically so a local with the same name cannot inherit the
  global table's element type or storage address.

The [dispatch example](../examples/static_dispatch/README.md) executes an immutable
command lookup. It contains data entries, not function pointers.

## Limits

Explicit list/repetition initialization accepts 1-256 elements. Serialized bytes
share the existing 4,096-entry initializer pool with static records and scalar
lists; record padding also consumes entries. Invalid counts, nominal types,
constant values, runtime calls, pointers, ownership/resource-bearing records and
pool exhaustion are rejected before object emission.

The existing `=0` array storage shorthand is preserved, including larger bounded
zero-storage arrays used by the compiler. This change does not certify arbitrary
resource zero-initialization or direct copies of pointer/resource-bearing elements.
The new checked direct-record access profile requires pointer-free records.
Existing source/table/IR/object limits and nested serialization limits still apply.

Bounded [whole-array assignment](native_array_assignment.md) is now available.
General slices and resource destruction remain separate work. Internal bounded
array parameters/returns use the [value-array ABI](native_value_array_abi.md).
Foreign/separate-object aggregate signatures, pointer relocations
and string initializers are not added. Native support does not assert canonical
Stage-0/C11 parity; this example is EXPERIMENTAL under the public snippet policy.

## Evidence

`tests/test_sotlas_native_static_tables.py` executes the source fixtures and
checked-in example, checks real object bytes/BSS, exercises a dynamic bounds trap
and rejects incompatible, immutable, resource-bearing and oversized forms.
Existing static-record/frontend/Target IR tests and native compiler rebuilds
exercise compatibility with the compiler's own zero-storage tables.
The previous unsupported single-record-table negative fixture is now covered
by a native execution test; its rejection slot retains a pointer-bearing record
case. Scalar, pointer, shape and runtime-initializer negative gates remain active.
