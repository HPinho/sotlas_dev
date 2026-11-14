# Consuming methods

The Sotlas-written native frontend accepts `sole` receivers on POD records.
Both the record name and `Self` can name the receiver type.

```sotlas
struct Token { pub value:u32; }
impl Token {
    fn forward(self:sole Self)->sole Self { return self; }
    fn take(self:sole Self,extra:u32)->u32 { return self.value+extra; }
}
pub fn main_entry()->u32 {
    let first:sole Token=Token{value:40};
    let next:sole Token=first.forward();
    return next.take(2);
}
```

Calling a consuming method transfers a qualified owner. Subsequent reads,
moves and method calls on that binding are rejected. A borrowed
`whisper` or `direct` receiver cannot be consumed. Additional arguments
follow the existing call contracts, including rejection of an argument that
borrows a receiver consumed by the same call.

For a local or parameter with an ordinary unqualified record value, the method
receives a copy, matching
the value-parameter ABI. Mutating the method's local `self` does not alter
the caller's record. Nested POD fields and arrays use the same recursive
copying as ordinary calls. [Method chains](native_method_chains.md) also accept
returned records, selected fields and fixed-array elements as receivers.

## Deferred methods

A resolved method returning `void` can consume its receiver in a direct
deferred call or a [cleanup call block](native_cleanup_blocks.md). Associated
functions without a receiver can also be deferred through `Type::name`.

```sotlas
defer {
    buffer.length();
    buffer.close();
    pages.close();
}
```

Registration transfers consumed bindings into cleanup and reserves their
storage. Calls inside a block run in source order, and separate defers run in
LIFO order. Reading or reassigning a captured binding, closing it twice or
returning it as another owner is rejected. Consuming deferred calls that
return a value remain outside this contract.

## Kernel resource methods

`NativeOwnedBuffer` exposes `length()`, consuming
`resize(size, alignment, zero_tail)` and consuming `close()`.
`NativeOwnedPages` exposes `load(offset)` and consuming `close()`.
Factories and the other resource operations retain their function forms.
The [buffer](native_owned_buffers.md) and [page](native_owned_pages.md)
lifetime and generation contracts still apply.

## Verification

`tests/test_sotlas_native_consuming_methods.py` executes scalar and owned
returns, nested-field and array copies, both value and void method paths,
associated cleanup, LIFO and loop jumps. Negative cases cover moved and
borrowed receivers, overlapping arguments, branch merges, wrong receiver
types and nonvoid deferred consumption.

The [kernel foundation](native_kernel_foundation.md) uses consuming resize,
deferred close and grouped method cleanup while timer interrupts allocate
from the shared heap. Its frontend gate checks the rejected cases through
both `--check-build` and `--build-obj`.
