# Typed descriptor and allocation metadata storage

This executable demonstrates exact record-array addresses in the native compiler:

- A function writes two descriptor records through a typed pointer, respecting
  record stride and updating the caller's original array.
- A reusable pool uses an actual `NativePoolSlot` array rather than a scalar-word
  encoding or an integer address conversion.
- Allocation/release updates are checked through the original metadata array.

Expected exit code: **42**. No hardware register access or output is performed.
The descriptors are ordinary caller-owned records, not a DMA/driver API.
See [the compiler contract](../../docs/native_record_storage.md).

With a rebuilt native compiler named `sotlas-native.exe` in the repository root,
PowerShell can stage and build the example without Python or a C compiler:

```powershell
$runtime = 'build/record-storage/src/sotlas/runtime'
New-Item -ItemType Directory -Force $runtime
'managed','pool' | ForEach-Object { Copy-Item "runtime/native/$_.sotlas" $runtime }
Copy-Item examples/native_record_storage/main.sotlas build/record-storage/src/main.sotlas
.\sotlas-native.exe --check-build build/record-storage/src build/record-storage/src/main.sotlas
.\sotlas-native.exe --build-win build/record-storage/app.exe build/record-storage/src build/record-storage/src/main.sotlas
.\build\record-storage\app.exe
$LASTEXITCODE
```

On Linux or Intel macOS, stage the same two modules and main file, then use
`--build` or `--build-mac` respectively. Older seeds need to rebuild the updated
compiler first; they do not gain the new array conversion merely by importing
the runtime. The compiler build scripts verify Stage 2/3 identity.
