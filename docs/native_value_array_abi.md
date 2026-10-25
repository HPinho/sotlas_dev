# Native internal value-array ABI

Internal function bodies can accept and return bounded fixed arrays by value.
The parser, semantic checks, layout and lowering are written in Sotlas. The
owned backend emits machine code directly; this path does not generate C.

```sotlas
fn make_samples()->[u32;2] { return [20,22]; }

fn sum_samples(values:[u32;2])->u32 {
    return match values { [first,last]=>first+last };
}

pub fn main_entry()->u32 { return sum_samples(make_samples()); }
```

## Parameters and returns

- Each array argument is evaluated and copied before the next argument. Passing
  the same source twice creates independent copies. A mutable parameter changes
  its own storage, including when called from a deferred operation.
- Array-returning functions write into caller-owned return storage through a
  final hidden pointer. Return expressions are captured before LIFO defers.
- This private ABI supports void callees, forwarding, nested calls, recursion
  and stack-passed arguments. It reuses the native aggregate calling convention.
- Literals, one-evaluation repetition, compatible stored arrays, fields and
  internal array-returning calls can supply arguments and returns. Contextual
  `match` and conditional expressions use the declared element type and count.
- A returned array can initialize a typed local, inline record field or enum
  payload, or be matched directly. A local initialized by an array-returning
  function call can infer its array type from the function signature.
- Semantic checks reject incompatible counts, element types and nominal record
  identities, including calls and returns in unreachable code. Lowering checks
  the storage shape again before publishing an artifact.

## Limits

Arrays contain 1–256 Boolean, integer, F32/F64 or pointer-free POD record elements
and occupy at most 4096 bytes. Existing layout, field, local, frame, CFG, nesting
and match-row limits still apply. Copies preserve the semantic fields of nested
POD records; they do not implement resource ownership or automatic destruction.

This contract applies to internal calls whose signatures and bodies are available
in one compilation unit. Foreign/bodyless array signatures are explicitly
rejected. It does not define a stable exported ABI, C interoperability or typed
array signatures across independently compiled objects. Slices, resource or
pointer elements, ownership-qualified arrays, arbitrary array reassignment and
general inference of untyped array expressions remain separate work.

Native execution does not establish canonical Stage-0/C11 frontend parity.

## Evidence

- `tests/test_sotlas_native_array_abi.py`: scalar widths, POD records, independent
  copies, evaluation order, recursion, stack arguments, cleanup and negative gates.
- `tests/native/match_profile/array_*abi*.sotlas`: rebuilt Stage 3 driver cases,
  including located failures and preservation of existing output files.
- [Public match example](../examples/native_match_values/main.sotlas).


## Local validation

Local validation: 256 native match/array-ABI tests and 67 shared rebuilt Stage 3
cases pass on each Windows/Linux host. All 15 new ABI tests also pass through
the hosted bootstrap route. Another 231 focused parser, semantic, frontend,
bootstrap and documentation tests pass. Native Stage 2/3 images are identical
within each host. The exact Windows original-module CI gate passes, including
calculator, GUI and UI-model gates. Public-example objects and ELF/PE/Mach-O
images match across hosts; Windows/Linux images execute with exit 42. New GitHub
CI and actual Intel macOS execution remain pending.

