# Three independently compiled Sotlas modules

This example returns 42 through calls across three separately emitted ELF
objects. The native linker checks every imported integer function signature
against the compiler metadata embedded in its provider object.

See [build commands and ABI contract](../../docs/native_embedded_abi.md).

To distribute the two providers as a static library, use:

```sh
sotlas-native --archive-elf libnumbers.a left.o right.o
sotlas-native --link-elf-libraries result main_entry app.o libnumbers.a
```

The native linker extracts the required members and checks every selected
integer function boundary. See the [static library contract](../../docs/native_static_libraries.md)
for selection rules, format restrictions and limits.

The same objects and archive can produce native Windows and Intel macOS images:

```sh
sotlas-native --link-pe-libraries result.exe main_entry app.o libnumbers.a
sotlas-native --link-macho-libraries result-macos main_entry app.o libnumbers.a
```

Run each image on its corresponding operating system. See the
[output-target contract](../../docs/native_library_targets.md) for entry ABI
requirements and platform-specific bounds.

The existing foreign-call declaration syntax names the cross-object ABI here.
All three implementations are Sotlas; no C source or C library is involved.
Native module imports with ownership/effect signatures remain separate work.
