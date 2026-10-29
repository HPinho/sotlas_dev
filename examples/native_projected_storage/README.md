# Interior pointers to caller-owned storage

The executable updates an embedded counters record and a scalar array element
through exact typed interior pointers. It then selects the middle of an existing
metadata array for a reusable pool, checking that the surrounding records remain
unchanged after allocation and release. Success exits with **42** without output.

This demonstrates compiler storage semantics for applications and low-level
code; the program does not communicate with physical devices. The raw pointers
must not outlive their source records/arrays. See
[the contract](../../docs/native_projected_addresses.md).

After rebuilding the updated native compiler as `sotlas-native.exe`, PowerShell
can stage and build the example without Python or a C compiler:

```powershell
$runtime = 'build/interior-storage/src/sotlas/runtime'
New-Item -ItemType Directory -Force $runtime
'managed','pool' | ForEach-Object { Copy-Item "runtime/native/$_.sotlas" $runtime }
Copy-Item examples/native_projected_storage/main.sotlas build/interior-storage/src/main.sotlas
.\sotlas-native.exe --check-build build/interior-storage/src build/interior-storage/src/main.sotlas
.\sotlas-native.exe --build-win build/interior-storage/app.exe build/interior-storage/src build/interior-storage/src/main.sotlas
.\build\interior-storage\app.exe
$LASTEXITCODE
```

Stage the same files on Linux/Intel macOS and select `--build`/`--build-mac`.
The existing compiler build scripts reconstruct the compiler from Sotlas sources
and enforce strict Stage 2/3 identity before reporting success.
