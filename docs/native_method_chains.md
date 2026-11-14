# Method chains and selected receivers

The Sotlas-written native frontend accepts record-valued calls, fields and
fixed-array elements as method receivers. This extends the existing record
method ABI; it does not add indirect function calls.

```sotlas
struct Token { pub value:u32; }
impl Token {
    fn add(self:sole Self,n:u32)->sole Self {
        return Token{value:self.value+n};
    }
    fn take(self:sole Self)->u32 { return self.value; }
}
fn make()->sole Token { return Token{value:40}; }
pub fn main_entry()->u32 { return make().add(2).take(); }
```

## Evaluation and ownership

The receiver is evaluated once, before explicit arguments, in source order.
Indexed receivers evaluate the index once. Mutable borrowed methods on fields
and indexed records use the selected storage. Constant roots retain mutation
checks, and fixed-array accesses retain bounds checks.

Consuming a qualified binding through a chain moves that binding. Further
reads, calls and moves are rejected. Borrowed bindings cannot be consumed.
Methods returning `Self` resolve that name in their defining implementation,
including when the chain appears outside it. Ordinary unqualified record
values retain the existing copy semantics.

## Kernel resources

The kernel foundation exercises both returned owners and chained resize:

```sotlas
native_kernel_buffer_acquire(p,7,1,true).resize(9,1,true).close();
```

Resize preserves the live claim on failure. Closing consumes the returned
claim. A chain does not introduce automatic destruction: keep an owner in a
binding with explicit or deferred cleanup when it must survive an operation.
Raw heap and page-descriptor lifetimes remain caller obligations.

## Deferred calls

A deferred factory call without captured owners, such as `defer make().close()`,
creates and closes its value at cleanup time. It does not eagerly acquire a
resource when registered. Chains that consume captured owners remain subject
to the existing capture/effect restrictions; `defer owner.forward().close()`
is rejected. Use a bound owner and a direct deferred close instead.

## Scope and verification

This delivery covers record-valued calls, selected fields and fixed arrays of
records in the existing native profile. It does not complete general closures,
indirect calls, raw-pointer lifetime analysis or resource-bearing aggregate drop.

`tests/test_sotlas_native_method_chains.py` executes value and void chains,
receiver/argument evaluation order, mutable fields, indexed receivers and
deferred factory timing. Negative cases exercise moved and borrowed owners,
immutable roots, invalid indices, unknown methods and captured-owner chains.
`tests/native_kernel_gate.py` also checks rejected programs through both
project checking and object emission, then verifies integrated reclamation.
Linux QEMU runs cover 32, 64 and 128 MiB memory configurations.

Local validation for this delivery passed 278 focused regression tests and
35 contract/documentation checks. The six method-chain tests also passed
using rebuilt native compilers on Linux and Windows. Both hosts produced
byte-identical Stage 2/3 compilers for their respective targets and identical
kernel images across hosts. These local results do not certify platform CI.
