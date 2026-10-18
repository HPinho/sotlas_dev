# Static libraries producing ELF, PE and Mach-O executables

The same independently compiled Sotlas integer modules can now be linked into
Linux ELF, Windows PE32+ and Intel macOS Mach-O executables. Native drivers on
all three hosts expose explicit output-format commands.

The libraries contain Sotlas's internal ELF objects. This does not add COFF
or Mach-O object archives, arbitrary vendor libraries or a foreign C ABI.

## Example

Compile and archive the [three-module example](../examples/separate_modules/README.md)
with a native compiler built from SV8.74 sources:

```sh
sotlas-native examples/separate_modules/app.sotlas app.o --object
sotlas-native examples/separate_modules/left.sotlas left.o --object
sotlas-native examples/separate_modules/right.sotlas right.o --object
sotlas-native --archive-elf libnumbers.a left.o right.o
sotlas-native --link-elf-libraries result-linux main_entry app.o libnumbers.a
sotlas-native --link-pe-libraries result-windows.exe main_entry app.o libnumbers.a
sotlas-native --link-macho-libraries result-macos main_entry app.o libnumbers.a
```

Run the corresponding image on its target operating system. Each returns 42.
Building a PE on Linux does not make that image executable on Linux.
The Mach-O path uses the existing static Intel macOS startup; ARM64, code
signing, hardened runtime, dylibs and general macOS distribution remain open.

## Shared guarantees

All three paths use the [native archive selector](native_static_libraries.md).
Direct objects are roots; required library members are selected recursively.
Unused members are not emitted. Every selected integer function import must
resolve to one definition with the same return type, arity and parameter tags.
The [embedded ABI contract](native_embedded_abi.md) describes these checks.

PE and Mach-O library startup require an embedded signature proving an entry
of the form `fn name() -> u32`. The entry may be in any selected object, even
a member pulled from a library to satisfy another import. Merely placing an
entry in an otherwise unused archive does not make it a root.

Internal Sotlas calls retain the compiler's native ABI. The existing PE startup
bridge converts the Windows process entry into that ABI and calls `ExitProcess`
after the entry returns. The Mach-O startup exits through XNU. No C startup
source, host linker or host archive utility is launched.

## Target checks and limits

| Output | Selected object limit | Platform requirements |
| --- | --- | --- |
| ELF | 16 | Existing Linux linker contract |
| PE32+ | 15 | No Linux/Darwin operation flags in selected objects |
| Mach-O x86-64 | 16 | No Linux operation flags in selected objects |

PE reserves one of the resolver's sixteen slots for its existing OS startup
bridge. Its selected object storage also reserves space for that provider
within the existing 8 MiB scratch buffer. All commands retain the archive
input limits: sixteen files, 8 MiB total input and 256 candidate objects.

Only the selected members are subject to executable platform checks. An unused
member can target another platform while remaining a structurally valid
archive member. A selected module requiring another OS fails before writing
the executable.

The library commands require all imported functions to resolve within the
selected Sotlas modules. General Windows API imports, dylib symbols and other
system-library boundaries are not added by this block. Existing single-object
PE OS imports and Darwin process-entry APIs keep their previous paths.

Ownership/effect signatures, pointer/aggregate inter-module contracts, dynamic
libraries, symbol indexes for external archivers and package visibility remain
separate work. Successful linking is not a proof of those language guarantees.

## Validation

`tests/test_sotlas_native_library_targets.py` builds actual objects and archives
through the production native driver. It checks both executable formats on
every host and executes PE on Windows and Mach-O on Intel macOS. Cases cover
the checked-in example, entry placement, signed/Boolean arguments, stack
arguments, initialized/zeroed data, unused members, deterministic output,
target limits and rejections that preserve existing images.

The old one-object APIs delegate to the generalized implementation, retaining
their existing import and startup contracts. Self-build and previous object,
manifest, archive and ABI gates remain enabled. Actual Intel macOS execution
requires its CI runner; local format checks do not certify macOS execution.
