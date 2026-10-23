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

// Linux SV8.89c3a / Intel macOS SV8.89c3b1: staged atomic replacement.
sotlas-native --build-library-atomic OUTPUT SOURCES.list
sotlas-native --build-elf-modules-atomic OUTPUT ENTRY SOURCES.list [LIBRARIES.list]
sotlas-native --build-pe-modules-atomic OUTPUT ENTRY SOURCES.list [LIBRARIES.list]
sotlas-native --build-macho-modules-atomic OUTPUT ENTRY SOURCES.list [LIBRARIES.list]
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
- **SV8.89c2b repair (Intel macOS x86-64):** the original preflight
  mistakenly paired legacy XNU `fstat` (syscall 189) with the newer
  64-bit-inode layout, treating unrelated regular files as identical
  and breaking CI #1294/#1295. The repaired preflight uses
  `open(O_RDONLY)` + `fstat64` (BSD syscall **339**, 0x02000153)
  + `close` via the reserved typed `sotlas_darwin_fstat64` adapter.
  This writes the explicit `user64_stat64` format into a 256-byte
  native buffer; device ID is 32-bit at byte 0 and inode is 64-bit
  at byte 8. The legacy adapter (189) remains separately available
  but is not used for these 64-bit file identity comparisons.
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

### Intel macOS atomic replacement — SV8.89c3b1

The Intel macOS native driver now also accepts all four `-atomic`
source-list commands described above. Like the Linux profile, it compiles
the full result in memory and publishes through a bounded,
same-directory `.sotlas-stage` name. It uses Darwin `open` with
`O_CREAT|O_EXCL`, a complete write and close, and the typed native XNU
`rename` syscall 128 (`0x02000080`) to replace the directory entry.
The native `unlink` syscall 10 (`0x0200000A`) provides best-effort
staging cleanup after a failed write or rename. The direct syscall
adapters preserve the negative-errno convention used by the Darwin driver.

An occupied staging name is never clobbered or deleted: the command fails
with status `10` and preserves the previous published output. On failed
rename or partial write it returns status `11`, attempts to remove its
own stage, and preserves the previous output. Compilation and linking
errors occur before staging. The ordinary replace commands and existing
`-new` commands retain their current behavior.

As on Linux, this is **atomic namespace replacement only**, with a
deterministic single-writer staging name. There is no file/directory
`fsync`, post-crash cleanup guarantee, preservation of prior
permissions/ACLs, defense against path swaps, or proven safety with
concurrent writers. Windows does not yet expose `-atomic` commands.

Tests: `tests/test_sotlas_native_module_builds.py` checks artifact
replacement across library/ELF/PE/Mach-O, staging collisions, failed
rename and prior-output preservation. `tests/test_sotlas_native_macho.py`
proves syscall encodings, direct XNU rename/unlink execution, negative
errno handling and invalid-signature rejection. The post-commit matrix
must pass before the macOS implementation is considered certified.

### Linux atomic replacement — SV8.89c3a

Opt-in `-atomic` commands are available **only on the Linux x86-64 native
driver**. They compile and link exactly as the existing source-list forms
before publishing the result to disk.

The Linux driver appends the fixed suffix `.sotlas-stage` to the output
path, bounds the resulting path to 4095 bytes, opens that name with
`O_CREAT|O_EXCL`, writes and closes the entire artifact, and finally
uses native Linux `rename` syscall 82 to atomically replace the output
directory entry. If a stage already exists (including a symlink), it is
**never overwritten or deleted** and the command returns status 10.
For failed writes or failed rename, status 11 is returned and the driver
attempts cleanup through native Linux `unlink` syscall 87. The previous
output remains unchanged until rename succeeds. The stage lives next to
the output, so the rename does not cross filesystem boundaries.

This is a bounded, deterministic **single-writer contract**, not a
concurrent-writer or hostile-directory protocol: an existing stage blocks
the operation, and a malicious parent-directory swap or path race is
not prevented by a preflight check. Cleanup after an I/O failure is
best-effort; a process crash can leave a stage that must be examined and
removed deliberately. A successful rename gives atomic namespace replacement,
**not crash durability**: no fsync of file or parent directory, multi-file
transaction, permissions/ACL preservation, or simultaneous no-clobber
semantics is claimed. Successful replacement uses the new 0755 artifact
permissions rather than preserving the old inode's attributes.

The default source-list commands and existing `-new` modes remain unchanged
on Linux, Windows and Intel macOS. Darwin is covered by SV8.89c3b1;
**Windows does not yet implement `-atomic` publication**. The next
SV8.89c3b2 step targets Win32 staged publication; handle-backed identity
and durable crash recovery remain separate certification milestones.

Evidence: `tests/test_sotlas_native_module_builds.py` includes Linux
library/ELF/PE/Mach-O publication, forced staging collision, failed rename
and late compile failure; `tests/test_sotlas_native_linux_driver.py` checks
the owned rename/unlink syscalls and rejects invalid declarations. The new
post-commit CI is required before claiming the atomic mode certified.

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
The Mach-O execution test now verifies the typed XNU `fstat64` adapter's
negative errno and explicitly checks both halves of the identity contract:
hard links must compare equal, while two independently created files
with identical contents must have different inodes. It also checks
the exact emitted syscall encoding, without a host C runtime. PE runs
on Windows, ELF on Linux and Mach-O on Intel macOS when that runner is present.
