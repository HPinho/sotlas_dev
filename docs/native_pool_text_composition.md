# Persistent Unicode text composition (SV8.103)

This connected native-runtime block extends `sotlas::runtime::pool_text`,
reusing the fixed-size reusable pool introduced in SV8.102's successor delivery.
It performs checked UTF-8 editing and persistent text composition entirely
in Sotlas without hidden Python, C, an OS allocator or an external linker.

## APIs

| API | Behavior |
| --- | --- |
| `native_pool_text_append_scalar` | Append one checked Unicode codepoint |
| `native_pool_text_insert_scalar` | Insert one scalar at a scalar index |
| `native_pool_text_remove_scalar` | Remove and return the scalar at an index |
| `native_pool_text_pop_scalar` | Remove and return the final codepoint |
| `native_pool_text_reset` | Reuse a slot without release, optionally wiping used bytes |
| `native_pool_text_append_from` | Append all bytes of another live text, including self |
| `native_pool_text_append_scalars` | Append a checked scalar range from a live text |
| `native_pool_text_replace_from` | Replace a scalar range with another text's scalar range |
| `native_pool_text_clone_scalars` | Allocate an independent clone of a scalar range |
| `native_pool_text_equal_handles` | Compare two validated live texts |
| `native_pool_text_split_once` | Split checked text at first valid UTF-8 separator, returning revision-bound views |
| `native_pool_text_parse_u32` | Parse a checked view as a strict decimal u32 |

Scalar indices count Unicode codepoints rather than UTF-8 bytes, grapheme
clusters or display columns. A separator is required to be nonempty and valid
UTF-8. A missing separator returns `found=false` with invalid views.
The split does not allocate. Clients may parse the right-side view without
unrestricted raw-pointer lifetime assumptions.

Cross-slot replacement reads validated source data without consuming the
source; the destination's successful mutation invalidates only its own views.
Nonempty self replacement fails closed through the existing aliased-source
guard; self append uses the existing memmove-ordered append path. Independent
range cloning allocates exactly one new reusable slot, copies bytes and
preserves the original slot and revision. Full pools produce invalid handles
without mutating the original. Allocation identity and view generations remain
explicit: copying a `NativePoolHandle` does not retain ownership.

Successful edits invalidate previously captured views for that allocation;
failures preserve bytes, slot identity, length and revisions. Invalid or stale
views fail before byte access. Revision saturation rejects mutations instead
of wrapping. Reset uses the checked pool resize path and can recover malformed
UTF-8 without reading it. The optional wipe is ordinary zeroing, not a
cryptographic erasure guarantee.

## Evidence and limits

`tests/test_sotlas_native_pool.py` covers scalar widths, field splitting,
decimal parsing, cross-slot composition, self append, stale views,
generation changes, pool exhaustion, revision saturation, malformed UTF-8,
alias rejection and independent copies. The
[executable demo](../examples/native_pool_text/main.sotlas) now creates a
UTF-8 record, obtains and parses a numeric field, clones a slice, composes
text in separate allocations and rejects stale views before closing the pool.
The existing shared Stage 3 native-driver gate runs that demo on the
Linux, Windows and Intel macOS supported platforms.

The hosted Stage 1 seed and CI test harness still use Python, and the separate
canonical C11 backend remains supported. These APIs do **not** certify
automatic ARC/drop, synchronized concurrent text access, OS-heap allocation,
general string syntax or compiler-proven borrowing. Callers must preserve
the pool's control/metadata storage and disjointness contract.

**Next milestone:** integrate resource lifetime/escape analysis into compiler
acceptance and native cleanup for a bounded resource-bearing aggregate profile.
Only claim this after source-to-native tests, negative checks, deterministic
Stage 2/3 reconstruction and full platform CI.
