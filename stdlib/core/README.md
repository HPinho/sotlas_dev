# Core standard library contracts

This page describes the public ownership and failure contracts in `alloc.sotlas`
and `string.sotlas`. All sizes and string indices count bytes. `StringSlice` does
not validate UTF-8 or prove that its pointer covers `length` readable bytes.
Callers must provide a live readable range for every non-empty slice.

## Strings

| API | Ownership and mutation | Failure behavior |
|---|---|---|
| `string_from_raw`, `string_as_bytes`, `string_slice`, `string_trim*` | Borrow the original storage; the caller keeps it alive. Slices do not copy or free bytes. | Invalid bounds return an empty slice. A non-empty pointer and its stated extent remain the caller's responsibility. |
| `string_len`, `string_is_empty`, `string_char_at`, `string_equals`, `string_compare`, `string_starts_with`, `string_ends_with`, `string_find*`, `string_split_once` | Read borrowed inputs only. | `string_char_at` returns `0` for a missing pointer or out-of-range index; `string_find*` returns `-1` when absent or malformed; `string_compare` returns `-2` for a non-empty null slice. Empty needles are handled without dereferencing their pointer. |
| `string_new` | Wraps caller-owned mutable storage. The `String` does not own or free that buffer. | No allocation occurs. Mutating operations return `false` when capacity is insufficient. |
| `string_new_in_arena`, `string_reserve_in_arena` | Storage belongs to the supplied arena. The arena must outlive the string; resetting the arena invalidates all strings allocated from it. | Allocation failure returns an empty string or `false`. Failed reserve leaves the original string fields and contents unchanged. |
| `string_new_with_allocator`, `string_reserve`, `string_append*`, `string_concat_into` | Allocator-backed strings own their current buffer. Keep the allocator and its context alive until deinitialization. Slice inputs are borrowed and copied into the destination. | Allocation, capacity overflow, malformed input, and insufficient storage return `false` or an empty allocation result. Failed growth preserves the original data, length, capacity, and allocator. |
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
the terminator. Append operations return `false` when no payload byte fits. The
API is byte-oriented and does not validate UTF-8.

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

## Verification scope

`tests/native/test_string_native.sotlas` exercises empty and malformed slices,
failed fixed-buffer and arena growth, allocator-backed growth, and explicit
cleanup through the checked C11 project pipeline. `test_arena_overflow_native.sotlas`
checks exhaustion and address wraparound; `test_string_buf_native.sotlas` checks
zero, one, and two-byte capacities in native execution. These tests do not
dereference arbitrary invalid non-null addresses, because that is undefined
behavior in the C11 runtime.

`tests/native/test_ring_buffer_native.sotlas` executes wraparound, FIFO ordering,
full and empty behavior, invalid reinitialization, and corrupted public index and
count rejection through the canonical C11 compiler.
