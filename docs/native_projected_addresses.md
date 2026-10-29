# Native interior storage addresses

The Sotlas-written parser and Target IR lowering now support explicit raw
addresses of fields and fixed-array elements. The source form is an unsafe cast
of `&place` to its exact const pointer type, or `&mut place` to its exact mutable
pointer type. The address selects the original live storage, not a temporary
copy of the selected value.

## Accepted places

- Scalar fields of local records, including nested inline records.
- POD record fields and POD record elements of fixed arrays.
- Scalar elements of local fixed arrays and inline fixed-array fields.
- Scalar fields inside record-array elements.
- Field projections through an existing typed record pointer, with the existing
  unsafe and const boundaries preserved.

Pointers use the declared scalar width or nominal record layout. Equal sizes
do not allow substituting another scalar type or another record declaration.
Pointer-valued fields, whole array-field addresses, resource-bearing aggregates
and temporary aggregate addresses remain outside this block.

## Mutability and evaluation

The parser now retains the full `&mut` qualifier span, including whitespace or
comments between tokens. No AST layout or operator-tag ABI changed. Lowering
uses that parsed qualifier rather than treating `&` and `&mut` as interchangeable.
The new projected-address path enforces:

- Creating a mutable pointer requires `&mut` and mutable underlying storage.
- Creating `&mut` from immutable storage is rejected even if the final pointer
  is const.
- A crossed const pointer cannot grant mutable access to an interior field.
- The entire new conversion must occur inside unsafe.
- Owned-resource escape checks run before lowering; they are not bypassed by
  selecting a scalar field of an owner.

The receiver/index address is evaluated once, in normal expression order.
Selecting an array element reuses the existing native bounds check; a dynamic
out-of-range index traps before a memory operation. A valid address can be passed
to functions, used in a loop or read by a deferred call while its storage remains
alive. The compiler does not extend the storage lifetime.

This is not a general borrow checker, alias graph or pointer-provenance proof.
Raw pointers can still be copied, and the caller must keep their storage alive
and coordinate aliases. Addressing a record value returned by a call, a literal,
a conditional temporary or a pointer-returning call receiver fails closed in
this path. Bind a supported value/pointer to a local before taking a projection.
Existing plain-variable address and raw-pointer conversion contracts are unchanged.

## Runtime integration

[The executable example](../examples/native_projected_storage/main.sotlas) passes
an embedded counters record and one sample element into functions, then reads
the updated original state. It also opens a native pool over the middle two
records of a four-record metadata array. Allocation/release must update only
that selected region; the neighboring records retain their canary generations.
Expected process exit: 42. No hardware register or MMIO access is performed.

`tests/test_sotlas_native_projected_addresses.py` covers scalar/record fields,
array elements, nested pointer projections, nominal typing, mutability,
qualifier spelling, evaluation order, repeated loop addresses, multiple interior
arguments, numeric widths and a real out-of-bounds trap in a child process.
The source-stage tests also include negative cases for owner escapes, immutable
storage, dropped qualifiers and temporaries.

The imported example is included in all three original-source Stage 3 platform
gates. Those gates check source/build acceptance, emit an object and ELF/PE/Mach-O
images, and execute the native host image with host tools absent from PATH.
Certification of this candidate still requires its own full CI run.

Local evidence: 21 new address tests passed through the hosted producer. The
rebuilt native compilers each passed 150 address/storage/projection/array/pool/map
tests on Windows and Linux, including the out-of-bounds instruction trap. Another
46 Target IR, phase/reality, manifest, self-host and parser/AST checks passed,
along with the generated phase-matrix check. Native check/object rejection of
an invalid interior address preserved an existing output file on both hosts.

Both original-source reconstructions produced identical Stage 2/3 images with
host tools absent from PATH. SHA-256 of each verified native compiler:

- Windows: `dd6e2db6048dd5a956acb64434cb9c259b05cc957a3f891e903eaa800e105331`
- Linux: `bb9d3d23d44985235f9c807aac20d13730f4af6b24d106aed72a973f59f93e6b`

Interior-storage and record-storage examples passed imported check/object/direct
build and host execution; their objects and ELF/PE/Mach-O outputs were identical
across the two producers. The separate pre-existing configuration-map example
had a local Windows Defender block (`WinError 225`), which also prevented reading
its PE artifact through the Windows-mounted Linux workspace. Its object was
identical to the prior baseline on both hosts. This is recorded as a blocked
artifact gate, not a passing execution result; protection was left unchanged.
Actual Intel macOS execution and the new full platform CI remain pending.
