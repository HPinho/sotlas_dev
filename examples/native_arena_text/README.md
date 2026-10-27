# Growing text in a Sotlas arena

Allocate a small text buffer, interleave another allocation, then build a
551-byte report. Growth moves the text when necessary and extends the last
allocation in place afterward. The report checks its neighboring allocation,
edits a value and returns a scalar count before deferred close clears the current
text. The caller rewinds the arena after that scope has finished.

Expected exit status: **42**. The example uses fixed input and prints no output.
It exercises Sotlas-written allocation, UTF-8 operations, results and cleanup.

After rebuilding a native compiler from SV8.100 sources:

```sh
sotlas-native --check-build build/native-selfhost/src examples/native_arena_text/main.sotlas
sotlas-native --build build/arena-text build/native-selfhost/src examples/native_arena_text/main.sotlas
./build/arena-text
```

Use `--build-win` and an `.exe` output name on Windows. The generated source root
contains the required runtime modules. No host compiler or linker is used by this
post-seed path. See [arena text](../../docs/native_arena_text.md) for generation,
alias, allocation-failure and reclamation rules.
