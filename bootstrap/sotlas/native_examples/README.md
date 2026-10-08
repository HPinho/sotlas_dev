# Native frontend example

`frontend_native.sotlas` embeds a small Sotlas program, tokenizes it with the
production Lexer, builds its AST with the production Parser, and checks it with
the production Sema. These modules execute as native machine code in the image.

The example returns zero when the embedded program is accepted. Exit codes 1–4
report lexical failure, token capacity exhaustion, parse failure, and semantic
rejection respectively. Changing the embedded source also requires updating its
byte length.

Build the current Stage 1 compiler first. This bootstrap still requires the
Stage 0 Python compiler and Clang. Once Stage 1 is available, the following Linux
commands use the Sotlas-owned object writer and linker for the example:

```sh
./build/sotlas_stage1 --compile-obj \
  bootstrap/sotlas/native_examples/frontend_native.sotlas \
  build/frontend_native.o
./build/sotlas_stage1 --link-exe \
  build/frontend_native.o build/frontend_native.elf main_entry
./build/frontend_native.elf
```

On Windows, use `build/sotlas_stage1.exe` to generate the same ELF artifact and
run it under Linux or WSL. The executable needs neither Python nor a C runtime.

This example validates source. It does not lower the embedded program to Target
IR or produce a Stage 2 compiler. Those remain subsequent bootstrap gates.
