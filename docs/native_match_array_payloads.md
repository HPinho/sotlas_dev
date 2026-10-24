# Inline array payloads and owned subjects

The native compiler stores fixed arrays directly in enum payloads. A wrapper
record is no longer required. Parsing, checking, layout and machine lowering are
written in Sotlas; user programs use the owned object writer and linker.

```sotlas
enum Samples { Missing, Values([u32;2]) }

fn read(value:whisper Samples)->u32 {
    return match value {
        Samples::Missing=>0,
        Samples::Values(items)=>items[0]+items[1]
    };
}

pub fn main_entry()->u32 {
    let value:sole Samples=Samples::Values([21;2]);
    return read(value);
}
```

## Construction and storage

- Scalar arrays cover Boolean, signed/unsigned integers and F32/F64. Pointer-free
  POD record arrays reuse the existing native record layout and copy operations.
- Constructors accept element lists, repetition, compatible local arrays and
  array-valued record fields. Counts, element types and record identities must
  agree with the declaration.
- Lists evaluate their elements in source order. Repetition evaluates its value
  once and copies it into each element. Source arrays and enum copies own
  independent inline storage.
- Arrays participate in the existing private tagged layout, aggregate calls,
  returns and match results. Inactive storage is initialized before whole-value
  copies. This is an internal ABI, not a stable public or foreign enum format.
- Each array contains 1 to 256 elements. The full padded enum layout, including
  its tag and slots for all variants, must fit within 4096 bytes.

## Matching and ownership

Array fields accept an immutable binding, `_`, or the
[inline element patterns](native_match_array_patterns.md) added in SV8.90.
Slicing remains outside this block. Bindings retain element types/counts and get an
independent copy before guards execute. A false guard cannot modify the snapshot
seen by a later arm through its capture. Root/nested alternatives require matching
binding types and array lengths. Indexing uses the existing checked native array
address operation; out-of-bounds scalar accesses trap.

Statement and expression matches may read a named `sole`/`exclusive`, `whisper`
or `direct` binding when its complete type is pointer-free POD. The subject is
read once into independent storage. Matching does not consume the owner. The
selected arm may subsequently transfer that original owner, and live successors
retain the existing moved/maybe-moved checks. Guards cannot consume an owner
before fallthrough. Returns capture their value before LIFO deferred cleanup.

These operations do not implement automatic destruction of resource graphs.
Pointer/resource array elements, ownership-qualified payload fields, shared ARC,
weak invalidation and general resource drop glue remain rejected. Owned temporary
expressions as match subjects retain their existing rejection. Standalone array
parameters/returns and slices keep their separate ABI and language contracts.

## Evidence

- `tests/test_sotlas_native_match_array_payloads.py` covers all scalar memory
  widths, records, repetition order, copies, nested enums, calls/returns,
  alternatives, guards, owned/borrowed subjects, loop edges, LIFO defers, layout
  limits, traps and negative ownership/type/shape cases.
- `tests/native/match_profile/array_payload*.sotlas` run in the shared rebuilt
  Stage 3 driver gate, including located errors and previous-output preservation.
- [Public match example](../examples/native_match_values/main.sotlas).

Native self-builds and host execution are checked locally on Windows and Linux.
Intel macOS and the new GitHub matrix require their CI acceptance gates.

## Local validation

Local evidence: 179 match tests pass on each Windows/Linux host, along with
48 shared rebuilt Stage 3 driver cases per host. The exact Windows original-module
Stage 2/3 CI gate and all 19 new array-payload tests pass through the hosted seed
route; calculator and GUI gates pass too. Another 155 frontend/documentation
tests pass. Native Stage 2/3 fixed points hold within each host. The public example
executes with exit 42 on Windows/Linux, and its object plus ELF/PE/Mach-O outputs
are byte-identical across hosts. The new GitHub CI and Intel macOS execution gates
remain pending.

