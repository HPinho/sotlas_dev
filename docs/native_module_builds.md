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
not be created, including when its name already exists.
The SV8.89c1 identity preflight also detects linked output names before
publication. To preserve the established error contract, these destination
collisions return status `10` under `-new`, even when rejected earlier by the
native inode/device check. Duplicated source or library entries and invalid
lists still return status `1`. Replace-capable commands keep status `1` for
their preflight collisions. The kernel's exclusive-create remains authoritative
for avoiding overwrites, rather than relying on this preflight alone. Unlike the default
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
- **SV8.89c1 (Linux x86-64):** path collision checks additionally compare
  real file identity using the native `open(O_PATH)` + `fstat` + `close`
  syscall route, with device/inode read from the kernel's Linux x86-64
  `struct stat` layout. This recognizes existing hard links, symlinks to
  files, paths through symlinked directories and absolute/relative spellings
  of the same file, including differences not covered by lexical normalization.
  Source and library duplicates are rejected; an existing output that
  resolves to any source, library or manifest is rejected **even for the
  original replace-capable commands**, before output truncation.
- The Linux implementation uses a bounded 256-byte native stat buffer, two
  numeric file identity slots and no allocation, Python/C runtime or external
  compiler. Missing paths fall through to the established diagnostics;
  unexpected open/fstat/close errors reject the operation conservatively.
  It does **not** deduplicate equal-content files with different device/inode.
- **SV8.89c2a (Windows x64):** the native Windows source-list driver now
  compares volume serial numbers and 64-bit file indexes obtained directly
  through `CreateFileA` (metadata-only access, OPEN_EXISTING), the typed
  `GetFileInformationByHandle` import, and `CloseHandle`. It follows ordinary
  file symlinks and recognizes hard links and paths through linked parent
  directories. The compiler's owned PE import bridge resolves the new Win32
  function with a signature-checked two-argument Win64 thunk; ID 11 remains
  the internal scalar bridge, and the OS import table stays contiguous.
  Linux retains its device/inode path from SV8.89c1.
- For Win32, missing files (ERROR_FILE_NOT_FOUND / ERROR_PATH_NOT_FOUND)
  preserve existing diagnostics; other open/metadata/close errors reject the
  operation conservatively. Win32's 64-bit FileIndex + volume-serial tuple
  is a bounded identity profile, not a general identity certificate for ReFS
  (which can require a 128-bit file ID), remote/virtual filesystems or Unicode
  aliases. Do not claim complete ReFS/SMB/Unicode support.
- **SV8.89c2b (Intel macOS x86-64):** native Darwin path preflight now
  adds `open(O_RDONLY)` + `fstat` (XNU syscall 189) + `close` through the
  reserved typed `sotlas_darwin_fstat` adapter. The owned x86-64 machine
  emitter encodes BSD syscall 0x20000BD without using a C runtime or
  linking to libc. A bounded 256-byte kernel stat buffer supplies
  the device ID (32-bit at byte 0) and inode (64-bit at byte 8)
  from the Intel Darwin user64_stat ABI.
  The same source/library duplicate and output/manifest collision
  checks as on Linux and Windows now reject hard links, ordinary
  symlink aliases and paths through symlinked parent directories.
  Source and library duplicates return status 1; protected `-new`
  destinations return status 10; existing replace-mode collisions
  return status 1.
- Darwin's O_RDONLY metadata probe may lack permission even when the
  source can be inspected another way. Unexpected open, fstat or close
  errors fail closed; ENOENT preserves ordinary missing-input handling.
  The identity check is **not atomic** with final output creation.
  Tests cover a native Mach-O fstat ABI probe, negative errno,
  invalid signatures, duplicate inodes and preservation of inputs.
  The post-commit Intel macOS matrix remains the acceptance gate.
- No platform is protected against a concurrent filesystem swap between
  identity checking and later output opening, nor all dangling-link and
  symlink-parent races. Full handle-backed publication and atomic-replace
  protection remain separate certification work.

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
never overwritten (subject to host filesystem support for those link types).
SV8.89c1 adds Linux-only inode/device identity regression cases for duplicate
hard-/symbolic-linked sources, library inputs, destination aliases through
hard links or linked parent directories, and same-content independent inodes.
The SV8.89c1 regression repair keeps strict-output status 10 and duplicate-input
status 1 distinct and tests preservation for sources, manifests and libraries
on the target matrix (CI #1291 diagnosed the mismatch on Ubuntu).
SV8.89c2a adds Windows-hosted positive/negative file-ID gates covering
hard-linked or symlinked sources, linked output destinations, repeated library
identities and symlink-parent aliases; a direct PE import/return/ABI probe
and invalid signatures validate the kernel32 bridge on the test matrix.
SV8.89c2b adds Intel-macOS-hosted source-list identity gates for hardlinked
or symbolic-linked sources, output path aliases, linked parent directories,
duplicate libraries and different-inode files with identical contents.
A Mach-O execution test verifies the typed XNU fstat adapter's errno
normalization and dev/inode metadata bytes without a host C runtime. PE runs
on Windows, ELF on Linux and Mach-O on Intel macOS when that runner is present.
