# Inspect native layout and verify real storage

The example calculates a descriptor's size, stride, alignment and address-field
offset, checks those results against real generated storage, and allocates/releases
a native pool slot. Pool metadata checks derive their layout from the compiler.
Expected process exit: **42**, without output or physical hardware access.
See [native layout queries](../../docs/native_layout_queries.md).

After rebuilding a native compiler named `sotlas-native.exe`, PowerShell can
stage and build the example without Python or a C compiler:

```powershell
$runtime = 'build/layout-query/src/sotlas/runtime'
New-Item -ItemType Directory -Force $runtime
'managed','pool' | ForEach-Object { Copy-Item "runtime/native/$_.sotlas" $runtime }
Copy-Item examples/native_layout_queries/main.sotlas build/layout-query/src/main.sotlas
.\sotlas-native.exe --check-build build/layout-query/src build/layout-query/src/main.sotlas
.\sotlas-native.exe --build-win build/layout-query/app.exe build/layout-query/src build/layout-query/src/main.sotlas
.\build\layout-query\app.exe
$LASTEXITCODE
```

On Linux or Intel macOS, stage the same files and choose `--build` or `--build-mac`.
Runtime modules using the new queries need a rebuilt compiler. Older seeds can
reconstruct it from the updated compiler sources; they cannot directly compile
new runtime sources that use query syntax they do not yet understand.
