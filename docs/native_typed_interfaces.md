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
