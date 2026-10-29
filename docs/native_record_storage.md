# Typed native record-array storage

The native frontend and Target IR lowering now accept an explicit unsafe cast
from a bound local POD record array to a raw pointer to its exact element type.
This exposes the existing array storage; it does not allocate, copy the array
or reinterpret its layout. Pointer arithmetic uses the record's complete size,
including padding and nested inline storage.

This closes a practical native compiler gap: `NativePoolSlot` metadata can be
declared as a record array and passed directly to `native_pool_open`. Applications
no longer need to encode that metadata as u64 words or route its address through
an integer. The scalar-word pool API remains available for callers that need it.

## Contract

| Source and destination | Native behavior |
| --- | --- |
| Immutable local `[Row; N]` to `*const Row` | Accepted inside unsafe; reads the original storage |
| Mutable local `[Row; N]` to `*const Row` | Accepted inside unsafe; subsequent array edits are observable |
| Mutable local `[Row; N]` to `*mut Row` | Accepted inside unsafe; writes update the original array |
| Immutable local array directly to `*mut Row` | Rejected |
| Record array to another nominal record or scalar pointer | Rejected, even when sizes happen to match |
| New record-array cast outside unsafe | Rejected |
| Qualified owner/resource escape through the new cast | Existing ownership gate remains enforced |
| Pointer-bearing/non-POD element arrays | Remain outside this profile |

The array must already have a local binding, including a supported array return
value bound to a local. A mutable by-value array parameter uses the callee's
private copy; taking its address does not mutate the caller's value. A plain
record initialized from dereferencing the resulting pointer remains a snapshot.
Assigning another array value into the existing local storage is visible through
an already captured pointer. Existing static record-array pointers are unchanged.

This adds no general pointer reinterpretation, field-address operator, address
of a temporary, dynamic slice, automatic lifetime analysis or alias ownership.
The array must outlive every pointer use. Raw pointer arithmetic is not bounds
checked and must stay within accessible live storage with the required alignment.
Raw pointer casts and dereferences outside this direct array conversion retain
their existing contracts; the mutable-binding check is not a new general borrow
checker. The compiler does not prove hardware register validity or volatile/MMIO
semantics for arrays whose records resemble device descriptors.

## Executable examples

The subsequent [interior-address extension](native_projected_addresses.md) covers
selected fields/elements. It has its own mutability and receiver restrictions;
the array-to-element-pointer conversion described here remains unchanged.

[Typed record storage](../examples/native_record_storage/main.sotlas) passes a
descriptor array into a function, writes successive records through typed
pointers and checks the resulting fields. It then initializes a native reusable
pool over typed `NativePoolSlot` metadata, allocates/releases a slot and observes
the same metadata from the array. Expected process exit: 42.

[The configuration map](../examples/native_config_map/main.sotlas) now also uses
typed pool metadata, connecting the compiler change to the existing UTF-8
collection, checked views and deferred cleanup. No new C or Python production
code is required for these operations.

## Validation

`tests/test_sotlas_native_record_storage.py` exercises original-storage identity,
mutations, alignment/padding, nested records and arrays, scalar widths, floats,
signed members, pointer calls, returned and by-value arrays, snapshots, deferred
reads, existing static storage, rejection cases and typed pool integration.

The Linux, Windows and Intel macOS original-source Stage 3 gates include the
imported example. They check source/build acceptance, emit an object and all
three executable formats, and execute the native host format with host tools
absent from PATH. Emitting a foreign format does not replace execution on its
actual platform.

Local candidate evidence: 17 new storage tests passed through the hosted
producer. Rebuilt native Windows/Linux compilers each passed 129 storage,
pointer-projection, array-assignment, owned-array, pool and configuration-map
tests. Another 41 Target IR/reality/phase/manifest/self-host checks passed, as did
the generated phase-matrix check. Both imported examples passed native builds
and host execution with exit 42; their objects and ELF/PE/Mach-O output were
byte-identical across the two producers.

Original-source Stage 2 and Stage 3 compiler images were identical within each
host, built without host tools on PATH. Verified SHA-256:

- Windows: `1916f39c14ab813f1d5c0233cf64b320902c12789c4330f33f973a1bac5a7fa6`
- Linux: `7ecf6cb81d34bf88a0dd4099b6d51f66bdae82f7d7eec294fbd5b08d17d1cae8`

The reconstruction scripts also checked native self-tests, application execution
and preservation of existing output after rejection of use-after-move. Actual
Intel macOS execution and the new full CI run remain pending. The starting
baseline was commit `8268ee0`, certified by
[CI #1321](https://github.com/HPinho/sotlas_dev/actions/runs/40840985644).
