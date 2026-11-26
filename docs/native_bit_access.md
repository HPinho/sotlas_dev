# Native bit access

Use `.slit[lo..hi]` to extract an inclusive bit range and `.notch[n]` to
read a single bit. Bit zero is the least significant bit.

```sotlas
const TYPE_BIT: usize = 4;

fn header_type(header: u16) -> u8 {
    return header.slit[TYPE_BIT..TYPE_BIT + 3] as u8;
}

fn has_payload(header: u16) -> bool {
    return header.notch[15] == 1;
}
```

The native x86-64 compiler accepts unsigned `u8`, `u16`, `u32`, `u64` and
`usize` operands. An untyped integer literal uses `u64`. Both accessors
return `u64`; use an explicit cast if the destination has a narrower type.
`.notch` returns zero or one. `.slit[0..63]` on a `u64` returns the full word.
The operand is evaluated once. The compiler lowers the extraction to an
unsigned shift and mask using existing Target IR operations.

Bounds are compile-time unsigned expressions. Integer literals, unsigned
module constants and checked arithmetic follow the
[fixed-array dimension evaluator](native_array_dimensions.md). A bound may
not use a runtime local or parameter. The compiler rejects reversed ranges,
positions outside the operand width and non-unsigned bases. `slit` and `notch`
can still be used as ordinary field names outside the bit-access syntax.

This covers reads of values already available to the program. Assigning to
these accessors, `.strand`, variable bit ranges and use in module constant
initializers are outside the native profile. Pointer dereference and MMIO
keep their own access and safety rules.

The [native contract cases](../tests/native/contracts/README.md) cover every
unsigned width, the full word and its top bit, field reads, one-time operand
evaluation, constant bounds and rejection of invalid requests.
