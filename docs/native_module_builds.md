# Native builds from independent source modules

Source-list builds compile each file through the native lexer, parser, semantic
checker, lowering and object writer independently. They then create a static
library or select and link the resulting objects into an executable. No C
generation, subprocess compiler, host linker or Python build driver is used.

## Commands

```text
sotlas-native --build-library OUTPUT SOURCES.list
sotlas-native --build-elf-modules OUTPUT ENTRY SOURCES.list [LIBRARIES.list]
sotlas-native --build-pe-modules OUTPUT ENTRY SOURCES.list [LIBRARIES.list]
sotlas-native --build-macho-modules OUTPUT ENTRY SOURCES.list [LIBRARIES.list]

// SV8.89b: the same four commands with OS-backed create-new protection.
sotlas-native --build-library-new OUTPUT SOURCES.list
sotlas-native --build-elf-modules-new OUTPUT ENTRY SOURCES.list [LIBRARIES.list]
sotlas-native --build-pe-modules-new OUTPUT ENTRY SOURCES.list [LIBRARIES.list]
sotlas-native --build-macho-modules-new OUTPUT ENTRY SOURCES.list [LIBRARIES.list]
```

All native host drivers register the same commands. The output format is
explicit; it does not depend on the host. PE executes on Windows, ELF on Linux
and the static x86-64 Mach-O profile on Intel macOS.

## Reproduce the example

From the repository root, use the checked-in lists to build all three modules
directly into an application:

```sh
sotlas-native --build-elf-modules program-linux main_entry examples/separate_modules/modules.list
sotlas-native --build-pe-modules program.exe main_entry examples/separate_modules/modules.list
sotlas-native --build-macho-modules program-macos main_entry examples/separate_modules/modules.list
```

Or build the providers as a reusable library, then compile only the application:

```sh
sotlas-native --build-library numbers.a examples/separate_modules/providers.list
sotlas-native --build-elf-modules program-linux main_entry examples/separate_modules/application.list examples/separate_modules/libraries.list
sotlas-native --build-pe-modules program.exe main_entry examples/separate_modules/application.list examples/separate_modules/libraries.list
```

The appropriate executable returns 42. The supplied library list refers to
`numbers.a` in the process working directory. Output directories must already
exist. Successful builds replace the named output using the established
native artifact writer **for the existing commands**. The `-new` commands
instead use the already-certified native exclusive-create path: Linux
`O_CREAT|O_EXCL`, Darwin `O_CREAT|O_EXCL`, and Win32 `CREATE_NEW`.
The check and creation happen in one native kernel/API operation when the
finished artifact is published, after validation and linking, rather than
through a non-atomic file-existence probe. Status `10` means the output could
not be created, including when its name already exists. Unlike the default
commands, `-new` never truncates an existing destination. A target name that
is itself a symbolic link (including a dangling one on POSIX) or a different
hard-link name already exists and is rejected, preserving its bytes and link.

`-new` applies to source-list builds only, not every Sotlas CLI write mode.
It is a **no-clobber creation policy**, not a general file-identity oracle:
different source and library paths resolving to one inode are not otherwise
deduplicated. Existing-output replacement through the original commands, paths
that contain symlinked parent directories, access errors after a successful
new-file creation, filesystem races on ancestor directories, and metadata-based
link equivalence remain outside this block. These need a separate checked
file-identity and atomic-output implementation.

## List and compilation semantics

- One path per line; LF/CRLF, blank lines, `#` comment lines and horizontal
  whitespace around each path are accepted. Do not quote paths with spaces.
- Relative paths resolve against the process working directory, matching
  existing native manifest commands. They are not relative to the list file.
- Each source list and optional library list contains 1–16 paths and is bounded
  to 65,535 bytes. Omit the optional library argument when no library is needed.
- Source and library lists reject the same byte-exact path appearing more than
  once. Duplicate source roots and duplicate library roots both fail with the
  existing invalid-argument status (1), before a destination file is opened.
- The output path cannot be byte-identical to a listed source, a linked
  library, the source list itself or the optional library list. On rejection,
  the original input bytes and any pre-existing output remain unchanged.
  Checks occur before source compilation or before reading the archives.
  These guards are implemented in the native Linux, Windows and macOS
  drivers without a Python helper or host linker.
- SV8.89a replaces byte-exact-only matching with bounded **lexical**
  normalization in the native drivers. Repeated separators, `.` and safely
  reducible `..` components compare equal. POSIX paths remain case-sensitive,
  with leading double slash distinct. Windows normalizes both slash styles,
  ASCII letter case and drive letters while distinguishing rooted, drive-
  relative and UNC prefixes. Relative versus absolute paths stay distinct;
  leading relative `..` is retained and traversal beyond a root is not folded
  into a relative path. The comparison is bounded to the existing 4095-byte
  path limit and does not call the host shell, Python, C compiler or linker.
- This is **not filesystem identity**: an absolute path and a relative path
  resolved against a process directory, hard links, symbolic links, junctions,
  short names, Unicode case folding, device paths, and filesystem races require
  separate host metadata and atomic-output safeguards (SV8.89b).
- Source units do not share symbol tables, types or static compiler state.
  A sibling implementation cannot satisfy an undeclared source-level name.
- The current cross-object boundary uses explicit foreign-call declarations
  and compiler-checked integer ABI metadata. Imported source modules, namespace
  mangling, private symbol linking and automatic dependency discovery are not
  introduced here. Globally emitted function/data names must not conflict.
- Every directly compiled object is a root. Library members are selected
  lazily and their transitive imports are resolved by the native selector.
- Library creation permits unresolved imports so dependencies may be supplied
  when building the final application. Executable linking requires a matching
  definition for every import in selected objects.

The [archive](native_static_libraries.md), [integer ABI](native_embedded_abi.md)
and [output-target](native_library_targets.md) contracts remain authoritative.
PE/Mach-O library startup requires an attested zero-argument U32 entry.

## Storage, diagnostics and failures

Each source uses the existing native single-unit input limit, below 2 MiB.
The driver retains compiled objects in an additional bounded 8 MiB arena;
compiled object bytes plus subsequently loaded archive bytes must fit there.
Candidate selection is limited to 256 objects. Final output uses at most
16 selected objects for ELF/Mach-O or 15 for PE, which reserves a startup slot.

The native compiler checks every source before opening the destination. It
emits no intermediate `.o`, generated C or temporary source files. A late
syntax/semantic failure, missing source/library, malformed list, invalid
archive or ABI/linking failure preserves the previous destination. Diagnostics
for source failures retain the failing file's path, line and column. Final
filesystem write failures retain the existing artifact writer's limitations;
this is not an atomic-filesystem replacement guarantee.

This is a complete source-list build path for the declared integer module
profile. It does not replace the package manager or establish general frontend,
ownership/effect, generic library or independent first-seed parity.

## Validation

`tests/test_sotlas_native_module_builds.py` drives the production native compiler
and checks application/library builds, absence of intermediate files, equality
with individually compiled archives, source isolation, type/data state resets,
late failures and diagnostics, library dependencies and target bounds.
The SV8.88 and SV8.89a preflight cases cover duplicates, output collisions,
lexical dot/parent aliases and Windows ASCII case/separators across targets.
SV8.89b additionally executes exclusive-create library/ELF/PE/Mach-O
commands and verifies that existing destinations, hardlinks and symlinks are
never overwritten (subject to host filesystem support for those link types). PE runs
on Windows, ELF on Linux and Mach-O on Intel macOS when that runner is present.
