# Core standard library contracts

This page describes the public ownership and failure contracts in `alloc.sotlas`,
`result.sotlas`, and `string.sotlas`. All sizes and string indices count bytes.
`StringSlice` construction does not validate UTF-8 or prove that its pointer
covers `length` readable bytes. Callers must provide a live readable range for
every non-empty slice; call `string_is_valid_utf8` when text validity matters.

## Strings

| API | Ownership and mutation | Failure behavior |
|---|---|---|
| `string_from_raw`, `string_as_bytes`, `string_slice`, `string_trim*` | Borrow the original storage; the caller keeps it alive. Slices do not copy or free bytes. | Invalid bounds return an empty slice. A non-empty pointer and its stated extent remain the caller's responsibility. |
| `string_len`, `string_is_empty`, `string_char_at`, `string_try_byte_at`, `string_equals`, `string_compare`, `string_starts_with`, `string_ends_with`, `string_find*`, `string_split_once` | Read borrowed inputs only; indices and results count bytes. | `string_char_at` returns `0` for a missing pointer or out-of-range index. `string_try_byte_at` returns `false` for invalid input and leaves its output unchanged, so embedded NUL bytes remain distinguishable. `string_find*` returns `-1` when absent or malformed; `string_compare` returns `-2` for a non-empty null slice. Empty needles are handled without dereferencing their pointer. |
| `string_is_valid_utf8` | Reads a borrowed byte slice and does not allocate. | Returns `true` for empty input, including a null-backed empty slice. Returns `false` for a non-empty null slice, malformed sequences, overlong encodings, surrogate code points, truncated sequences, and code points above U+10FFFF. It validates but does not change the byte-oriented behavior of other string APIs. |
| `string_new` | Wraps caller-owned mutable storage. The `String` does not own or free that buffer. | No allocation occurs. Mutating operations return `false` when capacity is insufficient. |
| `string_new_in_arena`, `string_reserve_in_arena` | Storage belongs to the supplied arena. The arena must outlive the string; resetting the arena invalidates all strings allocated from it. | Allocation failure returns an empty string or `false`. Failed reserve leaves the original string fields and contents unchanged. |
| `string_parse_u32` | Parses a borrowed slice without allocation; accepts ASCII decimal digits only and does not trim whitespace or accept a sign. | Returns `ResultU32::ok` for values through `4294967295`, `InvalidParam` for empty, null-backed, or non-decimal input, and `Overflow` above the `u32` limit. |
| `string_parse_i32` | Parses a borrowed slice without allocation; accepts ASCII decimal digits with one optional leading `+` or `-`. It does not trim whitespace. | Returns `ResultI32::ok` for values from `-2147483648` through `2147483647`, `InvalidParam` for empty, null-backed, sign-only, or non-decimal input, and `Overflow` outside the `i32` range. |
| `string_new_with_allocator`, `string_reserve`, `string_append*`, `string_concat_into` | Allocator-backed strings own their current buffer. Keep the allocator and its context alive until deinitialization. Slice inputs are borrowed and copied into the destination; appending an empty slice is a successful no-op, including a null-backed zero-length slice. Appending a slice of the destination itself is supported, including when growth relocates its buffer; overlapping fixed-buffer copies preserve the source bytes. | Allocation, capacity overflow, malformed non-empty input, and insufficient storage return `false` or an empty allocation result. Failed growth preserves the original data, length, capacity, and allocator. |
| `string_deinit` | Releases an allocator-owned buffer and clears the string. Call once for each live owned string; the allocator must outlive the call. Caller-owned and arena-owned buffers must not be passed as allocator-owned values. | Null input is a no-op. The function clears fields, making a second call a no-op. Automatic destruction is not provided by this API. |

Owned strings returned by value require the caller to preserve one live owner and
call `string_deinit` exactly once. The current language does not yet connect this
library contract to automatic move-aware destruction for every return path.

## Allocators

`Allocator` is a borrowed callback table. Its `context` and callback functions
must remain valid while any allocation made through it is live. `allocator_alloc`
and `allocator_realloc` return null on failure; callers retain responsibility for
the old allocation if reallocation fails. `allocator_free` invokes the configured
callback and does not clear aliases held elsewhere.

`ArenaAllocator` and `BumpAllocator` use caller-provided backing memory and never
obtain storage from the operating system. An allocation returns null when the
buffer cannot satisfy the requested size/alignment. `arena_reset`,
`arena_restore`, and `bump_reset` invalidate allocations after the selected
point; every pointer into that storage must be treated as expired. A checkpoint
is only valid for the same arena and a position previously reached by that arena.
Arena allocation rejects offsets beyond capacity, address wraparound, and size or
alignment requests that exceed the remaining buffer. Capacity arithmetic is
validated before the offset is advanced.

## Foundation string buffer

`foundation::string_buf::StringBuf` is a caller-owned, fixed-capacity,
null-terminated byte buffer. Its capacity includes the trailing NUL byte, so a
zero-capacity buffer cannot accept appends and a one-byte buffer can only hold
the terminator. `string_buf_append_str` and `string_buf_append_bytes` either
append the complete input or return `false` without changing the buffer. Byte
appends support input ranges that overlap the destination buffer. The caller
must provide readable source storage and writable backing storage for their
declared extents. The API is byte-oriented and does not validate UTF-8.

## Ring buffer

`core::ring_buffer::RingBuffer` is a single-threaded FIFO over caller-owned
storage. The storage must remain writable and live for the entire initialized
lifetime. `ring_init` resets the struct before validating its inputs, so a null
storage pointer or zero capacity leaves a safe empty state. Push, pop, peek,
and batch operations reject zero capacity, out-of-range indices, and counts
larger than capacity before indexing storage or applying modulo. The fields are
public, so callers must not mutate them while using the API. The type uses no
atomics or locks; concurrent and interrupt access requires external
synchronization and is outside this contract.

## Reference counting

`core::arc::ArcHeader` provides atomic `arc_retain`/`arc_release` operations for
shared references and explicitly single-threaded `arc_retain_local`/
`arc_release_local` helpers. Retain fails for a zero or saturated count. Release
returns `true` only for the transition from one reference to zero; a repeated
release at zero returns `false` and leaves the count unchanged. Local helpers
must not be used for references shared across threads or CPUs. Callers remain
responsible for freeing the allocation exactly once after the final release.
`SharedCounter.retain` returns whether the atomic retain succeeded.

## Bounded vector and result values

`foundation::generic_vec::Vec<T>` is an experimental source declaration. The
current C11 backend does not specialize generic structs or methods. It accepts
the declaration for parsing and type checking, then fails closed with a Sotlas
diagnostic when asked to emit that generic module or to call a generic method;
no invalid C is emitted. Parsing and type checking the declaration do not make
the generic collection usable at runtime. Use `foundation::vec::VecU32` for native
programs in this preview. That bounded collection uses caller-provided storage,
reports zero capacity when constructed with a null backing pointer, and does
not allocate or destroy elements. Its `clear` operation only resets length;
element cleanup remains the caller's responsibility.

`foundation::vec::VecU32` is a fixed-capacity vector over caller-provided
mutable storage. The backing array must outlive the vector and have at least
`cap` writable elements. Constructing it with a null backing pointer yields an
empty vector with zero capacity. Query functions treat null vector pointers,
unavailable backing storage, and malformed lengths as empty; mutating functions
are no-ops or return failure. `vec_push`
returns `false` without changing length when the pointer is null or the vector
is full. `vec_get` and `vec_pop` return
`OptionU32` with `has_value == false` for missing elements; neither operation
allocates. `vec_clear` resets length but does not zero or destroy elements.
`vec_pop` returns the last value and decrements length; popping an empty vector
fails. Reads and pop also fail closed if the public `length` field exceeds
capacity.
This concrete `u32` collection does not provide generic element destruction.

`core::result::ResultBool`, `ResultU32`, `ResultI32`, and `ResultU64` carry a
`ResultCode` and a scalar value. `ok` sets `ResultCode::Ok`; `err` stores the
supplied code and clears the value (`false` for `ResultBool`). The code set includes `Overflow` for numeric conversion
outside a result type's range. `unwrap_or` returns the value only for `Ok`, while
`unwrap` uses zero as its fallback. `try_unwrap(out)` copies the value and
returns `true` only for `Ok`; it leaves `out` unchanged for an error or null
pointer. Use it when zero is a valid success value and the caller needs an
unambiguous success check. These result records own no heap memory. Native
coverage checks zero-valued success, signed and maximum-width values, and that
errors preserve both their code and the caller's output storage.

`foundation::hashmap::HashMapU64` uses caller-provided fixed-capacity storage.
Constructing it with a null entries pointer yields an empty table with zero
capacity.
`hashmap_get` returns `OptionU64` and preserves all 64 value bits. Updating an
existing key does not increase the count; removal repairs the affected probe
cluster so later colliding keys remain searchable. The table does not allocate
or grow. When storage is full, a new key is rejected while an existing key can
still be updated without changing the count. Lookup and removal reject zero
capacity before computing a probe index, including when public count fields have
been corrupted.

## Verification scope

`tests/native/test_string_native.sotlas` exercises empty and malformed slices,
failed fixed-buffer and arena growth, allocator-backed growth, overlapping
fixed-buffer append, self-append across relocating reallocation, and explicit
cleanup through the checked C11 project pipeline. `test_arena_overflow_native.sotlas`
checks exhaustion and address wraparound; `test_string_buf_native.sotlas` checks
zero, one, and two-byte capacities in native execution. These tests do not
dereference arbitrary invalid non-null addresses, because that is undefined
behavior in the C11 runtime.

`tests/native/test_string_buf_native.sotlas` also checks atomic rejection when a
string does not fit, overlapping self-append, and source and destination address
wraparound. `tests/native/test_ring_buffer_native.sotlas` executes wraparound,
FIFO ordering, full and empty behavior, invalid reinitialization, and corrupted
public index and count rejection through the canonical C11 compiler.
The canonical shared-domain gate also exercises `VecU32` full/empty and bounds
behavior with `ResultU32` success and error construction through native C11.
The stdlib runtime test covers null handles, full/empty behavior, successful and
empty `pop`, `clear` preserving capacity and backing bytes, and a corrupted
`VecU32.length` above capacity; the malformed reads/pop fail without indexing
storage or decrementing length.
The hashmap native gate checks full-width values, updates while full, rejection
of a new key at capacity, stable counts, and lookup through a collision cluster
after removal. It also corrupts the public count while capacity is zero and
checks that lookup/removal fail without a divide-by-zero trap or count mutation.
When backing storage is unavailable or `count > capacity`, length reports zero
and insert, lookup, and removal fail closed. The test verifies that operations
leave the corrupted entry and count unchanged.
