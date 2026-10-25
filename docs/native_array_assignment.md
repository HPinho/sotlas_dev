# Native whole-array assignment

Mutable fixed-array storage can receive a complete replacement value. The native
parser, semantic checker and Target IR lowering are written in Sotlas; execution
uses the owned machine-code backend, object writer and linker.

```sotlas
pub fn main_entry()->u32 {
    let mut values:[u32;2]=[20,22];
    values=match true { true=>[values[1],values[0]],false=>[0;2] };
    return values[0]+values[1];
}
```

## Destinations and values

- Mutable local arrays and internal by-value array parameters accept assignment.
  Changing a parameter still changes its independent value copy.
- Inline array fields work in local/nested records, indexed record elements and
  supported raw-pointer receivers. The destination is evaluated once, before the
  right-hand value. Dynamic indexed receivers retain their bounds checks.
- Existing mutable global arrays and array-valued global fields can be replaced
  under the native `unsafe` access rules. Immutable globals remain rejected.
- Lists, one-evaluation repetition, compatible stored arrays/fields, internal
  array-returning calls, contextual matches and conditionals supply values.
- Scalar elements cover Boolean, signed/unsigned integers and F32/F64. Record
  elements must be pointer-free POD and preserve their nominal identity, including
  nested inline storage. Bounds are 1–256 elements and at most 4096 bytes.

## Evaluation and cleanup

The compiler creates a complete temporary array before copying into the captured
destination address. Reordering elements of the destination, assigning it to
itself and copying overlapping compatible views therefore preserve the original
right-hand values. Lists evaluate in source order; repetition evaluates once.

A value-block tail is captured before its LIFO defers. The final assignment copy
occurs after that cleanup. A path that returns from the enclosing function does
not publish an incomplete assignment. Right-hand expressions and defers can still
have their own observable effects, including explicit writes through unsafe
aliases. This staging is neither rollback of those effects nor an atomic memory
transaction for other threads or devices.

## Exclusive owners

A mutable `sole`/`exclusive` array can be reinitialized after a definite move.
An incoming owner is consumed; a fresh POD value creates the new owned contents.
Both paths reset the existing native ownership state to live. A live owner cannot
be overwritten, and a `MAYBE_MOVED` array must first have its control flow resolved.
Self-use after a move, duplicate consumption and borrowed destinations remain
rejected. This extends the existing move/reinitialization contract without
introducing destruction of resource-bearing elements.

## Validation and limits

Array shape, element types and nominal identity are checked in semantic analysis,
including unselected arms and assignments after a return. Lowering checks the
complete storage shape again before emission. Boolean literals cannot silently
initialize numeric arrays, including in unreachable code.

Immutable bindings, `whisper`/`direct` destinations, const-pointer projections,
unprotected mutable-global access, resource/pointer elements, slices and oversized
whole-array values remain rejected. Existing stack, local, layout, field, CFG and
nesting budgets apply; staging uses additional bounded stack storage. A large
scalar array accepted for indexed local access is not thereby accepted for whole-
array assignment. This does not change foreign or independently compiled array
signatures, general inferred array expressions or canonical Stage-0/C11 support.

## Evidence

- `tests/test_sotlas_native_array_assignment.py`: 21 tests, with scalar-width and
  negative subcases, execute the array updates and check rejection boundaries.
- `tests/native/match_profile/array_assignment*.sotlas`: shared rebuilt Stage 3
  check/compile/run cases with located failures and previous-output preservation.
- Existing array ABI, ownership, match-result and record-storage suites remain
  enabled. [The public example](../examples/native_match_values/main.sotlas)
  replaces a parameter array from a match and then swaps its elements.


## Local validation

Local validation: 351 native match, ABI, resource and whole-array assignment
tests pass on each Windows/Linux host, plus 76 shared rebuilt Stage 3 driver
cases per host. All 21 new assignment tests also pass through the hosted seed
route, alongside 58 existing array-result/record-storage tests. Another 231
focused parser, semantic, numeric, frontend, bootstrap and documentation tests
pass. Native Stage 2/3 images are identical within each host. The exact Windows
original-module CI gate passes, including calculator, GUI and UI-model checks.
Public-example objects and ELF/PE/Mach-O images match across hosts; Windows/Linux
images execute with exit 42. The new GitHub matrix and actual Intel macOS
execution remain pending.

