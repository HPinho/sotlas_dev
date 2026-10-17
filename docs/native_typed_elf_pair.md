# SV8.70 — Opt-in typed ELF64 object-pair linking

**Status:** candidate, awaiting new full CI. Baseline:
`6593c521966ab1fa8c1531312bb4214948502fdf`,
[workflow #1257](https://github.com/HPinho/sotlas_dev/actions/runs/39042389972).

## SV8.70.1 — cross-host opt-in typed ELF linker regression repair (2026-10-17)

**Last fully green baseline:** `6593c521966ab1fa8c1531312bb4214948502fdf` /
[CI #1257](https://github.com/HPinho/sotlas_dev/actions/runs/39042389972).
[CI #1258](https://github.com/HPinho/sotlas_dev/actions/runs/39048032064)
failed on the SV8.70 candidate. The complete next matrix must certify
this repair before SV8.71 begins.

The log evidence isolates **three independent causes**:

1. The new `--link-elf-typed-pair` command had only been registered in
   `linux.sotlas`. The separately compiled `darwin.sotlas` and
   `windows.sotlas` drivers still returned usage exit 1 for every
   new command. Both now get the identical native, bound-checked
   ELF/SOTI typed-pair handler, static name/record storage and explicit
   dispatcher registration; no Python/C execution fallback is added.
2. A backend source comment literally contained the forbidden marker
   `@extern(C)`, violating the preexisting sovereignty contract
   `test_x86_scalar_emitter_is_fail_closed_and_target_ir_native`.
   The comment now says "foreign-call declarations". The compiler's
   actual ABI handling and the test itself are unchanged.
3. All 15 new test cases shared the same image path. Negative tests
   first wrote a mode-0644 sentinel; a subsequent positive link
   truncated the existing file without restoring executable mode.
   Linux therefore returned `PermissionError: [Errno 13]` on
   an otherwise successfully linked ELF. Each case now owns a
   unique output path derived from its test method while still
   protecting the previous image byte-for-byte **within that case**.

**Nothing weakened:** all fifteen native positive/rejection tests, all
pre-existing per-platform tests, SOTI ABI/effect/ownership security
checks, legacy multi-object ELF linking, and Stage2/Stage3 fixed-point
gates are preserved. This candidate awaits its own full Linux,
Windows and Intel macOS workflow with installer/package jobs.

## What this integration implements

The Sotlas native compiler already emits relocatable ELF64 objects with
global symbols and R_X86_64 relocations. The native linker already links
up to 16 objects, but the linker did not consume SOTI signatures from
SV8.68/8.69. The opt-in `--link-elf-typed-pair` command now inserts
an ABI-and-authority *preflight* in front of the real linker. It handles
**two independently compiled objects** and **exactly one named cross-object
function import/export pair**.

Invocation, from the native CLI:

```sh
sotlas-native --link-elf-typed-pair OUTPUT ENTRY NAMES \
    IMPORT.o IMPORT.soti EXPORT.o EXPORT.soti
```

`NAMES` is a binary name buffer (maximum 4,096 bytes). Each
`.soti` sidecar is the portable little-endian SOTI v1 record defined
in [the wire contract](native_typed_interfaces.md), maximum 240 bytes.
Both objects must pass `validate_elf64_object`. Record validation
rejects version/magic/flags/count/name/role and ABI errors. The
import and export must agree on symbol, result type, parameter
types and ownership roles, with the export requiring no more
effects/capabilities than the importer allows.

The new `elf_typed_function_symbol_exists` is implemented in
Sotlas and scans the validated ELF64 symbol table, rejecting
ambiguous duplicate matching entries. It requires one actual
undefined global function reference in the importer and one
actual defined global function in the exporter. The check
recognizes the current ELF writer's `STT_NOTYPE` undefined extern
symbols and `STT_FUNC` definitions.

Only after this preflight does the driver invoke the existing
`link_elf64_executable` on both objects; the output is written only
on linker success. A failed read, malformed ELF or wire contract,
missing symbol, wrong entry, incompatible ABI or escalation leaves a
previous output file unchanged.

**Code:** `bootstrap/sotlas/native_driver/linux.sotlas`,
`bootstrap/sotlas/native_compiler/backend/x86_64_scalar.sotlas`.
**Tests:** `tests/test_sotlas_native_typed_elf_pair.py`: 15 positive
and negative native CLI gates. They compile independent objects,
execute the linked program on Linux, check deterministic output and
protect prior artifact bytes across invalid conditions. Existing
`--link-elf-objects` and all earlier tests are unchanged.

## Important security and scope boundary

**The sidecars are caller-supplied and are NOT authenticated.**
Their consistency with each other and with ELF symbol *names and
definition states* is checked. Their declared types, roles and
effect/capability masks are not yet proven to originate from the
canonical compiler-generated typed AST or corresponding machine
instructions. The command is an opt-in bounded integration, not
full native typed linking or a general library ABI checker.

Untyped objects, additional imports and separate global symbols
are still evaluated by the historical linker without mandatory SOTI
records. No new runtime depends on Python or C, but the initial seed,
package creation, ARC/drop and broader backend parity remain open.

## Next SV8.71 work

Generate signatures from owned frontend/Target IR declarations,
serialize them into real object sections, require complete import
coverage and tamper-resistant enforcement, then expand to Windows
PE and Intel macOS Mach-O under the complete native matrix.
