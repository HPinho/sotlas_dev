# Arena-allocated growing UTF-8 text

SV8.100 adds `sotlas::runtime::arena_text`. `NativeArenaText` combines a
`NativeUtf8Buffer`, its `NativeArena` pointer and the arena generation at creation.
The arena supplies storage: capacity grows on demand while UTF-8 and native
result contracts remain explicit. All allocation and editing code is Sotlas.

| API | Contract |
| --- | --- |
| `native_arena_text_empty/init` | Empty descriptor; initialize once against a valid arena |
| `native_arena_text_alive/check` | Verify generation/range, then validate initialized UTF-8 |
| `native_arena_text_view` | Borrow current initialized bytes |
| `native_arena_text_reserve` | Ensure capacity, returning actual capacity |
| `native_arena_text_append/append_slice` | Append validated input, growing as necessary |
| `native_arena_text_append_u32/append_scalar` | Encode decimal values or Unicode scalars |
| `native_arena_text_replace/truncate` | Edit only at UTF-8 scalar boundaries |
| `native_arena_text_reset` | Clear length, optionally wipe used bytes, retain capacity |
| `native_arena_text_close` | Reset then detach, optionally wipe current used bytes |
| `native_arena_text_detach` | Clear only the descriptor, including a stale descriptor |

Capacities grow geometrically from at least 16 bytes. The last allocation grows
in place when possible. If another allocation follows it, reserve allocates and
copies to a new block. An exact-size fallback is attempted when the geometric
size does not fit. Old blocks remain allocated until arena rewind; close does
not rewind or invalidate unrelated allocations. Zero-capacity initialization is
lazy and consumes no arena storage.

Native `NativeU32Result` APIs return new length for edits, capacity for reserve
and scalar count for check. Status 10 means arena exhaustion; other statuses
retain the [buffer contract](native_utf8_buffer.md). Exhaustion leaves arena
cursor, descriptor, length and existing bytes unchanged. Input/UTF-8/boundary
failures are checked before growth and do not allocate. Append supports a view
of its current text even when growth relocates it. Replacement rejects aliasing
with current backing consistently, independent of whether growth is required.
Sources overlapping the arena's unallocated tail are rejected when growing.

Rewind and last-allocation shrink advance the arena generation. Every text
operation checks that generation before reading text backing, and rejects stale
descriptors. This detects arena invalidation; it does not prove arbitrary raw
pointer validity. The descriptor and arena header must remain accessible and
disjoint from backing, inputs must stay stable during each operation, and callers
must preserve the arena's allocation records. Copying a descriptor shares raw
storage; it is not an independent string copy or an ARC retain. Borrowed views
are caller-managed and are not revoked by close, growth or rewind.

Use explicit defer close for scope cleanup. Close with wipe clears current used
bytes only; old copies from relocation and spare capacity are not securely erased.
Detach deliberately performs no backing access, allowing disposal of a stale
descriptor. Arena rewind is a separate caller decision after every affected
allocation has stopped being used. Concurrent mutation is outside the contract.

[The report example](../examples/native_arena_text/README.md) validates relocation,
in-place growth, neighboring allocation preservation, UTF-8, result capture and
cleanup before rewind. Tests add exact-capacity fallback, exhaustion, malformed
input, self append, stale epochs, descriptor reuse and failure atomicity.

This implements arena-managed allocation and growth. OS-heap strings, automatic
ARC/drop, compiler-proven slice lifetimes, allocation identity/alias tracking and
general string-language parity remain open.

SV8.101 adds [Unicode scalar-indexed queries and editing](native_arena_unicode.md)
with cross-text composition. This extends the explicit-arena profile; it does
not add automatic ownership, OS allocation or compiler-proven borrow lifetimes.
