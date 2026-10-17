# Typed native import/export contract — SV8.68

**Status:** Sotlas-owned pre-link metadata verification candidate.
Latest certified green baseline: [CI #1253](https://github.com/HPinho/sotlas_dev/actions/runs/38980061670),
commit `e3abf81191a1a928d6a981b9d29eb00c0d6155ff`.

**Code:** `bootstrap/sotlas/native_compiler/backend/target_ir.sotlas`.
**Tests:** `tests/test_sotlas_native_migration_sv868.py`.

## Objective

A compiler cannot safely link an import to a same-named export with
different machine ABI types, ownership roles, effect sets or capabilities.
SV8.68 establishes an executable pre-link contract on caller-provided
metadata. The validation is implemented in Sotlas and executes as
Sotlas-produced machine code. Python remains a CI test launcher only.

`TargetInterface` records a source-name slice, return type, parameter
range, import/export tag, effect bitmask and required capability mask.
`TargetInterfaceParameter` records an ABI type and role: 0 plain,
1 sole, 2 direct, 3 whisper. Parameter count is limited to 24.
Only scalar and pointer ABI shapes are admitted; generic aggregates,
variadics and arbitrary resource payload layouts are rejected.
All source names must be nonempty, bounded by the immutable name buffer
and no longer than 4,096 bytes.

The exporter may require a **subset** of the effects and capability
bits allowed by an importing declaration, never a superset. These bits
are caller-defined metadata and do not yet represent whole-program
enforcement. Parameters' ABI types and ownership roles and the
return ABI must match exactly.

## API and invariants

| Sotlas function | Contract |
|---|---|
| `target_interface_valid` | Validate names, ranges, flags, parameter roles and supported ABI shapes |
| `target_interfaces_unique` | Reject duplicate or malformed import/export declarations |
| `target_interface_compatible` | Enforce exact ABI/role signatures and non-escalating effects/rights |
| `target_interface_resolve` | Find one unambiguous compatible export, preserving output on failure |
| `target_interface_bind_manifest` | Validate every import before publishing any export indices |

The manifest resolver uses two passes over caller-owned input records.
The name buffer, parameter table, import list and export list must
remain stable, immutable and disjoint from writable output during
the entire call. The first pass proves all symbols resolve, including
later imports; the second publishes binding indices only after that
proof, guaranteeing unchanged output on a validation failure in this
single-threaded profile.

## Verification

Nineteen native tests cover exact scalar and sole/direct/whisper
signatures, effect/capability narrowing versus escalation, mismatched
parameters, returns and arity, illegal aggregates/roles/flags,
bad name slices, unresolved/duplicate exports and imports,
insufficient output capacity, zero imports, two-import resolution and
transactional failure of the second import preserving both previous
indices. Existing SV8.66/SV8.67 tests and Linux, Windows, macOS
fixed-point and packaging gates remain enabled.

## Required next steps

1. Encode/serialize versioned import/export interface records in the
   real native ELF/PE/Mach-O object output.
2. Make the actual separate-object linker verify imported signatures
   and reject missing/ambiguous/privilege-elevating symbols before
   replacing an executable.
3. Connect compiler symbols, imports, source ownership domains and
   effect/capability metadata to these records.
4. Prove general compiler-emitted ARC/drop and typed resource lifetimes.
5. Audit first-seed bootstrap and distribution for remaining mandatory
   Python/C tools; only measured dependency removal counts as progress.

**This stage is a pre-link contract, not completed true cross-object linking.**
## SV8.69 — Stable binary wire format, v1 (candidate)

The format serializes **one** validated `TargetInterface` and its
parameter slice into caller-backed output bytes; it does **not** yet
embed records into ELF/PE/Mach-O object metadata. It is fully encoded
in Sotlas, without packed C structs, Python marshaling or host pointer
layout. The version is fixed at 1; unknown versions fail closed.

| Byte offset | Width | Little-endian field |
|---|---:|---|
| 0 | 4 | Magic `0x49544F53` (bytes `SOTI`) |
| 4 | 4 | Version = 1 |
| 8 | 4 | Import = 2; export = 1 |
| 12 | 4 | Scalar/pointer/void return type tag |
| 16 | 4 | Symbol offset in external immutable source-name buffer |
| 20 | 4 | Symbol length (1..4096) |
| 24 | 4 | Parameter count (0..24) |
| 28 | 4 | Reserved, must be zero |
| 32 | 8 | Allowed/used effects mask |
| 40 | 8 | Required capability mask |
| 48 + 8*i | 4 | ABI type tag of parameter i |
| 52 + 8*i | 4 | Ownership role (0 plain, 1 sole, 2 direct, 3 whisper) |

A record's exact length is `48 + 8 * parameter_count`, maximum
**240 bytes**. All integer fields use explicit little-endian byte
operations, independent of host architecture, endian, unaligned
access or structure padding. Imported/exported names point to a
separately supplied immutable byte buffer, not stored pointers.
Parameter records are decoded into separately supplied native
Target IR structures with a first-parameter index of zero.

**API** in `backend/target_ir.sotlas`:
`target_interface_wire_size`,
`target_interface_wire_encode`,
`target_interface_wire_valid`,
`target_interface_wire_decode`,
`target_interface_wire_compatible`. It enforces exact ABI and role
matches and rejects exported effects or required capabilities that
exceed what the importing declaration permits.

**Write atomicity:** encoding checks the complete source record and
output capacity before its first write; rejected writes do not alter
the destination or length. Decoding validates all wire fields and
the destination capacity before its first typed output/parameter
write. Both require stable, disjoint input/output buffers for the
duration of the call (single-threaded bounded compiler contract).

**Tests:** `tests/test_sotlas_native_migration_sv869.py` adds 15 native
compile/link/execute cases for exact bytes, endian/alignment, record
roundtrip, corruption, capacity boundaries, ownership role matches,
ABI mismatch, effect/capability escalation and 64-bit masks.
Prior SV8.68 tests are unchanged. Baseline before SV8.69:
[CI #1255](https://github.com/HPinho/sotlas_dev/actions/runs/39011203750)
(`43bb572`); the new commit requires its own full matrix.

**Still open:** injecting this format into actual native object
writers, versioned ELF/PE/Mach-O metadata, checking imported symbols
within the real multi-object link operation, canonical frontend
signature synthesis and reproducible zero-Python/C first-seed builds.


### SV8.69.1 — u64 shift-count lowering compatibility

[CI #1256](https://github.com/HPinho/sotlas_dev/actions/runs/39038976982)
showed a cross-platform compiler regression: the 64-bit record
writer/reader used `number >> ((index*8) as u32)` and
`number << ((index*8) as u32)`, which the native backend rejects
for 64-bit left operands. This was a source-level lowering mismatch,
not a reason to remove interface serialization.

Both 64-bit helpers now use `(index as u64)*8` for shift counts,
matching the already accepted Sotlas binary runtime. A 16th
native wire test verifies byte order across all eight bytes of
two distinct `u64` values and checks decoding. The original 15
positive and negative tests and all SV8.68 gates are untouched.
The repair is uncertified until its own CI; last green #1255.


## SV8.70 — integration with the production ELF64 linker

The new `--link-elf-typed-pair` opt-in CLI consumes separately compiled
ELF64 importer/exporter objects plus one serialized SOTI import and one
export record. The native driver checks wire compatibility and proves that
the imported and exported name correspond to actual, distinct ELF symbol
table records of the required definition state **before** calling the
existing native ELF linker. All errors leave prior executable output
untouched. See [SV8.70 contract](native_typed_elf_pair.md).

This is **not** automatic compiler emission or object-embedded metadata.
Sidecars can be forged and do not prove that claimed roles or effects
describe the actual instructions. A future linker must require typed
metadata for every covered unresolved symbol and derive it from
compiler-owned typed AST/Target IR declarations.

## SV8.71 — compiler-owned plain ABI serialization

The new `target_interface_wire_encode_from_function_abi` reads
`TargetFunction` and `TargetParameter` source records from the
native compiler's own typed Target IR. It checks name slices,
parameter-table extents, 24-parameter capacity, scalar/pointer
return/parameter tags and import/export flag shape *before*
writing any SOTI bytes. Encoded source-name offset is normalized
to zero for a separately supplied exact name spelling. Unsupported
aggregates and unknown function flags fail closed.

**Trust boundary:** the IR parameter table has no certified
sole/direct/whisper role field yet, so only `plain` roles are
generated. The effects and capability bits passed to this API are
caller assertions, not semantic inference. This is a typed ABI
derivation primitive, not full authenticated metadata issuance
or automatic ELF section serialization.

Eight dedicated native execute/rejection tests accompany the earlier
SOTI wire cases. The ELF typed pair link path verifies an actual
exporter's existing compiler-emitted `.note.sotlas.abi` arity,
boolean mask and float-return classification before linking,
rejecting claims the note cannot certify.
