# Sotlas-native static libraries

The native compiler creates deterministic regular `ar` libraries and links
their ELF members without running a host archiver or linker. Library members
keep the compiler-generated integer ABI metadata introduced in SV8.72.

## Create and use a library

```sh
sotlas-native examples/separate_modules/app.sotlas app.o --object
sotlas-native examples/separate_modules/left.sotlas left.o --object
sotlas-native examples/separate_modules/right.sotlas right.o --object
sotlas-native --archive-elf libnumbers.a left.o right.o
sotlas-native --link-elf-libraries result main_entry app.o libnumbers.a
./result
echo $? # 42 on Linux x86-64
```

The same commands are registered in the Linux, Windows and Intel macOS native
drivers. SV8.74 additionally links these libraries into Windows PE and Intel
Mach-O executables through [explicit output-target commands](native_library_targets.md).
Libraries still use internal ELF objects; COFF/Mach-O object archives and
arbitrary foreign static libraries remain separate work.

## Selection and ABI rules

Object files listed directly are roots and are always included. At least one
direct object is required. For every unresolved function import in a selected
object, the linker first searches selected definitions, then adds the first
matching archive member in input/member order. Newly selected members have
their imports processed too. This handles transitive dependencies and cycles
across libraries without requiring a manual library group or repeating inputs.

An unused member is not linked, so its unresolved imports and duplicate
definitions do not affect the executable. All input members must nevertheless
be well-formed ELF objects with complete native ABI manifests. A malformed
unused member rejects the library before output publication.

The first selected provider must match the import's ABI. A mismatch is an
error; the linker does not search later providers to hide the disagreement.
Every import in a selected object is checked, including unused declarations.
Duplicate definitions in selected objects still fail in the production linker.

The [integer ABI contract](native_embedded_abi.md) applies: exact return and
parameter tags, integer signedness and width, Bool identity, and arity.
Pointer lifetimes, aggregate interfaces, floating-point foreign-call ABI,
ownership, visibility and effects are not certified by these library commands.

## Bounds and format

| Limit | Value |
| --- | --- |
| Inputs to `--archive-elf` | 1–16 independent ELF objects |
| Inputs to `--link-elf-libraries` | 1–16 object or archive files |
| Combined bytes read by either command | 8 MiB |
| Candidate objects, including archive members | 256 |
| Selected objects passed to the existing linker | 16 |

Archives use the standard regular `!<arch>\n` magic, 60-byte headers and newline
padding after odd-sized members. Writer timestamps, owner and group IDs are
zero; mode is `100644`; names are `m00000000.o/`, `m00000001.o/`, and so on.
Member bytes and input order are preserved. Renaming or relocating identical
input objects does not change the archive.

The supported container subset uses short names terminated by `/`. GNU symbol
indexes and long-name tables, BSD extended names, thin archives, nested
archives, weak bindings and non-ELF members are rejected explicitly. Libraries
do not contain a host-tool symbol index; the native linker scans their members.
This is not a promise to consume arbitrary libraries from another toolchain.

## Errors and output handling

Both commands load and validate inputs before opening their destination.
Invalid arguments, missing files, invalid containers, unresolved functions,
ABI mismatches and capacity failures preserve existing destination bytes.
Successful creation can replace an existing library, which makes rebuilds
repeatable. As with existing native artifact writes, a filesystem failure
during the final write is not a transactional replacement guarantee.

Exit statuses follow the native driver contract: `1` for argument bounds,
`2` for missing inputs, `3` for read/input limits, `8` for invalid ELF/archive
storage, `9` for selection/link/ABI rejection, and `10`/`11` for output I/O.

## Evidence

`tests/test_sotlas_native_static_libraries.py` exercises actual native compiler,
archiver, member selector and linker output. It includes the checked-in
three-module example, deterministic bytes, odd-size padding, transitive/cyclic
imports, lazy duplicate handling, ABI rejection, corrupt headers and members,
input/selection/candidate bounds and preservation of previous artifacts.
Linux runs the generated executables with host tools absent from PATH.

The commands are implemented in Sotlas. Test orchestration may use Python;
the native archive and link operations do not launch Python, C, `ar` or a host
linker. The initial seed and full zero-hosted distribution remain separate
bootstrap milestones.
