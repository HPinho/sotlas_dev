# Native compiler examples

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

## Native compilation and linking

`pipeline_native.sotlas` integrates the production Lexer, Parser, Sema,
ScalarLowering, Target IR, x86-64 object writer and ELF linker in one native
image. It compiles an embedded program with a scalar parameter, multiplication
and an internal function call, then links the generated object for `answer`.
The embedded program returns 42.

```sh
./build/sotlas_stage1 --compile-obj \
  bootstrap/sotlas/native_examples/pipeline_native.sotlas \
  build/pipeline_native.o
./build/sotlas_stage1 --link-exe \
  build/pipeline_native.o build/pipeline_native.elf main_entry
./build/pipeline_native.elf
```

The pipeline returns zero after checking the complete generated ELF's length
and FNV-1a fingerprint against the runnable reference artifact. Tests build and
execute the reference program separately, require the same fingerprint, and
check that changed input returns 10 instead of passing the reference check.
This deterministic fixture is a differential compiler gate, not a cryptographic
integrity mechanism.

Exit codes 1–4 report frontend failures, 5 reports lowering failure, 6 reports
object emission failure, 7 reports linking failure, and 8–10 report artifact
validation failure. Update the byte length when changing the embedded source;
update the fingerprint only after reviewing and running the new reference ELF.

The executable performs compilation and linking without Python, emitted C or
a C runtime. Building its initial Stage 1 producer still uses the hosted
bootstrap. This fixture has embedded input and in-memory output; it is not yet
a standalone compiler CLI or the Stage 1 -> Stage 2 self-build gate.
