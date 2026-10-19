# Native static record initialization

The Sotlas-written compiler serializes pointer-free record literals into native
object data. Records whose complete initialized representation is zero use BSS.
Layout padding is initialized to zero, and scalar bytes use the target's
little-endian representation. The existing native object/linker path carries
the data into ELF, Windows PE and Intel Mach-O images.

```sotlas
struct Config { pub tag:u8; pub value:u64; }
static mut config:Config=Config{value:40+2,tag:1};
pub fn main_entry()->u32 { unsafe { return config.value as u32; } }
```

## Supported operations

- Scalar fields use the existing typed constant evaluator, including integer,
  Boolean and floating-point values and supported module-constant expressions.
- Nested pointer-free records, scalar array fields and record array fields can
  be initialized recursively from typed literals and exact-count repetition.
- Named fields can be written in any order; every field must appear exactly once.
- Native code can read fields, mutate explicitly mutable globals, replace their
  values, index array fields and copy supported containers into independent locals.
- Internal record returns and supported borrows reuse the existing aggregate ABI.
- Static storage is emitted as bytes, without generated startup constructors,
  C initializers or a C linker in the post-seed native path.

The [configuration example](../examples/static_config/README.md) demonstrates
initialized channel records, a returned snapshot and dynamic array indexing.

## Limits

This is a fixed-layout POD profile. Pointers, resource-bearing/ownership-qualified
records, runtime calls and reads of another mutable static are rejected as
initializers. Aggregate module constants, nonzero standalone global record arrays,
string relocations and general foreign/aggregate library ABI are not added here.

The existing shared initializer pool contains 4,096 entries. A record consumes
one entry per layout byte, including padding; scalar array lists consume one
entry per element. The compiler rejects exhaustion before producing an object.
Nested serialization is bounded to depth 32, in addition to the existing record,
field, array and constant-evaluator limits. Global storage retains the native
compiler's current alignment and mutability rules. A raw pointer/resource
runtime and automatic destruction are separate contracts.

## Verification

`tests/test_sotlas_native_static_records.py` compiles and executes original Sotlas
sources. Its gates cover padding, declaration order, constants, nested layouts,
arrays, zero/data separation, mutations across calls, copies/returns/borrows,
name shadowing, exact capacity and rejected nonconstant/invalid/resource values.
The checked-in example is executed by the same suite. Native self-builds and
existing frontend/Target IR/array gates cover compiler reconstruction and regressions.

This native profile is classified EXPERIMENTAL in the public snippet inventory;
it does not promise acceptance by the canonical Stage-0/C11 frontend.
