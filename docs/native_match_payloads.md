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
- A pattern names its enum variant and supplies one immutable identifier or `_`
  per field. Duplicate names and incorrect arity are rejected.
- Tag selection precedes field loads and guard evaluation. A false guard continues
  to the next arm; guarded patterns do not establish exhaustiveness.
- Unguarded variant patterns cover the entire variant. All variants or a final
  wildcard are required; unreachable repeated variants are rejected.
- The subject is evaluated once. Only the selected arm executes. Arm bindings
  cannot escape into sibling arms or the surrounding scope.
- Nested enum values can be unpacked by another match in the selected arm.

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

Nested/refutable field patterns, named-field patterns and or-patterns are not
part of this contract. Use a binding followed by a guard or a nested match.
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
- `tests/native/match_ranges/cases.txt`: the shared rebuilt Stage 3 driver gate
  executes the public example and checks located diagnostics/output preservation.
- [Executable example](../examples/native_match_values/main.sotlas).
