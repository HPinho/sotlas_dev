# Embedded integer ABI and separate compilation

The native compiler writes function signatures into production ELF objects.
`--link-elf-abi-objects` reads these signatures before resolving imports and
publishing an executable. No hand-authored interface files are needed.

This is a machine ABI check. Ownership, effects, capabilities and package
visibility still need their own cross-module contracts.

## Build and run

Use a native compiler built from sources containing SV8.72. Each source is
compiled independently; the linker accepts one to sixteen object files.

```sh
sotlas-native examples/separate_modules/app.sotlas app.o --object
sotlas-native examples/separate_modules/left.sotlas left.o --object
sotlas-native examples/separate_modules/right.sotlas right.o --object
sotlas-native --link-elf-abi-objects result main_entry app.o left.o right.o
./result
echo $? # 42 on Linux x86-64
```

The Linux, Windows and Intel macOS native drivers expose the same ELF command.
The linked ELF runs on Linux x86-64; producing it on another host does not
make it a Windows or macOS executable. PE and Mach-O typed linking are pending.

## Checked boundary

- Every object must carry a valid, complete compiler manifest.
- Every imported function, including an unused declaration, must resolve to
  exactly one definition in the supplied objects.
- Return type, parameter count, parameter order, integer width and signedness
  must agree exactly. `bool` and integer tags are distinct; `usize` and `u64`
  are also distinct even on x86-64.
- Integer and Boolean parameters, integer/Boolean/void returns and stack
  arguments are supported. The native limit is 24 parameters per function.
- Multiple imports and exports per module, transitive imports, different
  object orders and up to sixteen inputs are accepted.
- Data and string sections inside a module keep working. Imported global data,
  weak symbols and pointer/aggregate/float function boundaries are rejected by
  this command. Untyped linking remains available through the existing command.
- Missing or malformed manifests, duplicate record IDs, invalid tags, excessive
  arity and nonzero unused slots fail before the output file is opened.
- The existing ELF linker validates relocations, duplicate definitions, entry
  ABI and image bounds after these checks. The combined input limit is 8 MiB.

No Python, C compiler or external linker is launched by the native command.
Obtaining the first native compiler seed is a separate bootstrap requirement.

## On-disk representation

The production module writer preserves the existing `.note.sotlas.abi`
descriptor and appends a second ELF note in that same section:

| Field | Encoding |
| --- | --- |
| Name | `SOTLAS`, NUL terminated, padded to eight bytes |
| Note type | `3` |
| Descriptor version | little-endian `u32`, currently `1` |
| Function record count | little-endian `u32`, at most 1024 |
| Records | 108 bytes per function |

Each record contains its actual ELF symbol index, native return type tag,
parameter count and 24 parameter type tags. All fields are little-endian
`u32`; unused parameter tags are zero. Records include external declarations
and definitions. Record order follows the compiler's Target IR; symbol IDs
account for data symbols inserted by the ELF writer.

The parser checks each record against the symbol table and requires complete
function coverage. Existing consumers can continue reading the first note.
Older objects without the second note must be recompiled for this command.

These records are not cryptographic signatures. Someone modifying an object
can also modify its manifest. They catch ABI disagreement between compiled
modules; they do not establish trust in arbitrary executable input.

## Validation

`tests/test_sotlas_native_embedded_abi.py` compiles independent sources through
the production native driver, links actual ELF files and runs them on Linux.
It covers all integer tags and Bool, void returns, stack arguments, initialized
module data, multiple providers, sixteen objects, deterministic output and
rejections that preserve an existing executable. Corruption cases exercise the
wire parser rather than substituting a test implementation for the linker.

Full ownership/effect signatures, pointer lifetimes, public package APIs,
archives, dynamic libraries and the corresponding PE/Mach-O metadata remain
outside this integer ABI delivery.
