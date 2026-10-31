# Explicit tags on native payload enums

Payload variants can declare an unsigned 32-bit discriminant after their
payload, using the existing enum assignment syntax:

```sotlas
enum Packet {
    Ping = 1,
    Data([u8; 4]) = 32,
    Close = 255,
}
```

This makes the variant identifier explicit while preserving the native tagged
union layout. The tag remains a four-byte value at offset zero. Payload offsets,
alignment, padding and the internal aggregate ABI retain their existing rules.
Declaring a tag does not turn the enum into a packed network packet or a foreign
C ABI type. Decode/encode external bytes explicitly.

## Values and validation

- Explicit payload tags are integer literals from 0 through 4294967295, with
  the existing decimal/radix/separator rules. Negative, floating, Boolean,
  named-constant and arithmetic-expression tags remain outside this profile.
- An implicit variant uses the preceding value plus one, including after an
  explicit payload tag. A later explicit tag may reset the sequence.
- Duplicate tags across any variants of a payload enum are rejected, including
  collisions between implicit, explicit, payload and unit variants. An implicit
  successor after the maximum u32 tag fails; an explicit reset remains valid.
- Tags are checked during metadata registration even when the enum is never
  constructed. Existing arity, nominal type, POD/resource and coverage checks
  remain mandatory.

The native parser retains the source-backed tag literal as an annotation node
referenced by `EnumVariant.int_value`. Payload child lists remain TypeRefs, so
constructor arity and payload binding do not mistake the tag for another field.
The literal retains its original span and declaration parent; native registration
checks that reference before decoding it. The existing scalar-enum AST shape is
preserved. This does not add a new AST record layout or Target IR opcode.

## Connected execution paths

Constructor storage, match discriminators and coverage, static data, global
record tables, internal calls/returns, POD moves and nested payloads all use the
registered discriminant table. Concrete `Ok(T)`/`Err(E)` results can also declare
their tags: `?` compares the actual registered `Ok` value and preserves the
entire error enum before cleanup. Reversing the order or choosing a nonzero
success tag does not change propagation semantics.

The optional legacy Sotlas C emitter continues to reject payload-enum lowering.
This block does not implement generic enums, resource-bearing payloads, custom
enum backing widths, foreign aggregate calls or automatic serialization.

## Example and gates

The [protocol decoder](../examples/native_payload_tags/main.sotlas) uses bounded
binary reads, fixed wire identifiers, nested payload matches and explicitly
tagged result propagation. It verifies valid, truncated and unknown-tag input,
then exits with 42. Native host rebuild gates include original-source check,
object/direct build, execution and ELF/PE/Mach-O emission.

`tests/test_sotlas_native_payload_tags.py` reads actual native tag memory rather
than relying only on matching the same table twice. It covers zero/max values,
implicit successors/resets, radices, scalar/record/array/nested payloads, static
tables, layout equality, POD moves and tagged `?`, plus duplicate/overflow,
syntax and constructor rejection. Full CI certification is pending.

Local focused evidence: 148 native execution/rejection tests passed per
Windows/Linux producer, including payload tags, tagged/status results, match
ownership, inline arrays, composed values, static tables and owned array ABI.
Hosted runs passed 117 payload/result/CFG tests and 41 AST/inventory/contract
tests. The phase-matrix consistency check also passed.

The original-source protocol example passed native check/build and execution
with exit 42 on Linux; its ELF and Mach-O emission passed. Object bytes produced
on Windows and Linux matched. The Windows-produced example passed check/object
and executable generation, but Defender blocked its PE execution locally
(`Program:Win32/Wacapew.C!ml`, WinError 225). Reading the Linux cross-emitted PE
through the Windows-mounted workspace was also blocked. Those PE checks are not
counted as passing.

Linux original-source reconstruction preserved strict Stage 2/3 identity with
host build tools absent from PATH. The Windows self-build reached Stage 3 but
Defender quarantined Stage 2 before its equality check completed. Windows fixed
point and example execution therefore remain uncertified locally. No protection
settings were changed and no quarantined executable was restored or retried.
The normal Windows and Intel macOS execution gates remain mandatory in CI.

Linux Stage 2/3 SHA-256:
`224026a3b2971382c1ef6e15eeae1616098cf186d6bea5bd7650af803df3dfda`.
