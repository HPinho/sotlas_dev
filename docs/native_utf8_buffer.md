# Caller-backed UTF-8 buffers

SV8.99 adds `sotlas::runtime::utf8_buffer`. `NativeUtf8Buffer` stores a raw backing
pointer, capacity, used byte length and validity flag. The program supplies the
storage, so text can exceed the 256-byte inline value profile. The library does
not allocate, grow the backing, add terminators or invoke C glue.

| API | Behavior |
| --- | --- |
| `native_utf8_buffer_open` | Start an empty descriptor over caller storage |
| `native_utf8_buffer_shape` | Check descriptor/range arithmetic without reading content |
| `native_utf8_buffer_check` | Validate used UTF-8; return Unicode scalar count |
| `native_utf8_buffer_view` | Borrow the initialized bytes as `NativeByteSlice` |
| `native_utf8_buffer_append/append_slice` | Validate then append, including overlapping source |
| `native_utf8_buffer_append_u32/append_scalar` | Append checked decimal/scalar encoding |
| `native_utf8_buffer_replace` | Replace a scalar-aligned byte range and shift its suffix |
| `native_utf8_buffer_truncate` | Shorten at a scalar boundary without clearing the tail |
| `native_utf8_buffer_reset` | Reset length, optionally clearing the used bytes |

Operations return `NativeU32Result` and compose with native `?` and explicit
defer cleanup. Edits return the resulting byte length; validation returns scalar
count. Status 1 means null nonempty input, 7 invalid shape/range/capacity/alias,
and 8 malformed UTF-8 or a split scalar. Offsets identify the relevant byte in
the source or destination operation. Capacities above the u32 maximum are
rejected so counts and successful lengths remain representable.

Every content-preserving edit validates the existing text and complete source,
checks boundaries and capacity before writing, then publishes its new length.
Failure preserves the descriptor and all backing bytes. Append uses memmove
order for overlapping source. Replacement rejects any nonempty source range
overlapping destination backing before shifting bytes. This distinction avoids
reading replacement bytes after a suffix move has overwritten them.

Input fragments must each contain complete UTF-8 sequences; this is not a
streaming decoder. Empty append accepts a null source. Reset can recover from
malformed content when the descriptor shape remains valid. Wipe clears only the
previously used range, not all capacity, and makes no secure-erasure guarantee.

The caller must provide accessible storage, keep the descriptor and backing
disjoint, and keep source bytes stable during a call. Pointer/range checks cannot
prove accessibility, lifetime or provenance. Borrowed views are invalid when
backing is destroyed and may observe later edits; reset does not revoke aliases.
Concurrent access is outside the contract. Validation scans current content on
each edit, so repeated tiny appends should be batched when performance matters.

[The report example](../examples/native_text_buffer/README.md) builds text beyond
256 bytes and exercises edits, self append, Unicode boundaries and defer. Tests
run the same native implementation through hosted and rebuilt native drivers.
OS-heap allocation, general compiler-tracked slice lifetimes and ARC-backed
string storage remain open.

[Arena text](native_arena_text.md) now layers explicit arena-managed allocation
and growth over this buffer API. The fixed caller-backed buffer itself retains
the capacity and lifetime contract described above.
