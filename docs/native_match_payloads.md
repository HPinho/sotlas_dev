# Native payload matching

The Sotlas-written compiler constructs tagged enum values and destructures them
through statement and expression `match`. The implementation is in the native
parser, semantic checker and Target IR lowering; it does not generate C.

## Executable contract

- Variants may declare positional scalar or pointer-free POD record fields.
- Qualified constructors check arity, nominal types and integer bounds.
- Unit variants remain valid alongside variants with fields.
- Internal parameters, returns and match results use the existing aggregate ABI.
- The private layout stores a U32 tag followed by aligned variant field slots.
  Slots do not overlap. Construction zeroes inactive fields and padding before
  storing the selected payload, so full value copies never read uninitialized data.
- Payload constructors and record bindings copy their POD storage independently.
- A pattern names its enum variant and supplies one field pattern per payload.
  Fields accept immutable identifiers, `_`, integer/Boolean literals, module
  constants, integer ranges, nominal scalar enum variants and nested variants.
  Duplicate binding names across the entire nested pattern and incorrect arity
  are rejected.
- Tag selection precedes field loads and guard evaluation. A false guard continues
  to the next arm; guarded patterns do not establish exhaustiveness.
- An unguarded variant whose fields are all captures covers the entire variant.
  Refutable field patterns contribute no whole-variant coverage: include a
  capture-only variant fallback or a final wildcard. An earlier unguarded total
  variant makes later patterns for that variant unreachable and is rejected.
- The subject is evaluated once and aggregate subjects are copied into a private
  snapshot before dispatch. Only the selected arm executes. Arm bindings
  cannot escape into sibling arms or the surrounding scope.
- Nested enum values can be unpacked directly in a pattern or by another match.
  Each nested tag is tested before accessing that variant's fields; guards run
  only after all field patterns match. Bindings retain their declared field types.

## Ownership and cleanup

Expression arms analyze exclusive POD moves independently. Live successors merge
to moved or maybe-moved states. A guard may borrow an owner but cannot consume it
before fallthrough. Value blocks use the same sequence analysis as statements,
including locals, early return and defer reservations. Yielding an owned value
requires an owned destination. Result storage is populated before LIFO cleanup.

These are exclusive POD transfers. Resource fields, shared ARC and weak-reference
cleanup still require their general runtime implementation; they remain rejected.

## Bounds and exclusions

The existing 32 record layouts, 32 enum tables, 256 total variants/fields,
128 local slots and 64 match-arm limits apply. A payload enum consumes one private
record layout. Its complete padded storage must fit within 4096 bytes. Layouts
with unresolved forward enum dependencies, recursive resource graphs, raw pointers
or ownership-qualified fields are rejected. Enums embedded in record fields whose
layout was registered before the enum aggregate are also rejected rather than
retaining a stale scalar layout. Direct array/slice payloads need their own ABI;
POD record payloads can contain supported inline arrays.

Nested patterns have a maximum depth of 32. Named-field patterns, or-patterns,
float equality patterns and product-space exhaustiveness proofs are not part of
this contract. Use captures and guards for float conditions. Refutable field
patterns require an explicit total variant fallback or a final wildcard.
The layout is internal and does not define a C enum ABI or a stable public format.
Native support does not certify canonical Stage-0/C11 parity or every master
language ownership domain.

Scalar enums keep the existing U32 discriminant conversion contract, including
paths used in U32 initializers, comparisons and returns. Aggregate inference for
unit-variant paths applies only when their enum has payload variants. The optional
native C11 emitter still rejects payload declarations, with a diagnostic at the
opening payload delimiter; parsing a payload does not imply C11 layout support.

## Evidence

- `tests/test_sotlas_native_match_payloads.py`: construction, calls/returns,
  nested values, scalar/record/array contents, guards, single evaluation,
  coverage, independent copies and rejection cases.
- `tests/test_sotlas_native_match_ownership.py`: disjoint moves, owned results,
  maybe-moved rejection, borrowing/consuming guards and value-block defer.
- `tests/test_sotlas_native_match_patterns.py`: nested tags, bindings, field
  literals/ranges/constants, nominal types, guard ordering and cleanup.
- `tests/native/match_ranges/cases.txt`: the shared rebuilt Stage 3 driver gate
  executes the public example and checks located diagnostics/output preservation.
- [Executable example](../examples/native_match_values/main.sotlas).
