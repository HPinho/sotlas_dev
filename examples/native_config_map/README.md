# Native configuration collection

The program stores text and numeric settings, imports `increment=22` from a
checked field split, releases the source, updates existing values, removes and
reinserts an entry, and iterates checked keys and values. It computes 42, releases
the map through `defer` and verifies that its pool closes without live slots.
Expected exit code: **42**. It does not print output or write a configuration file.

It first reads a nested JSON configuration, selects `base` and
`options.increment`, decodes a Unicode label and copies those values into the
map. The [native JSON reader](../../docs/native_json.md) validates source syntax
and offsets; the map owns its copied keys and values after insertion.
After updating those values, the program builds a nested JSON document using
the native writer, reparses it and verifies the numeric and Unicode round trip
before deferred map cleanup. Output remains in a caller-owned memory buffer.

Production collection code is [Sotlas](../../runtime/native/text_map.sotlas).
See [the collection contract](../../docs/native_text_map.md) for capacity,
ownership, alias and error behavior. The storage is bounded and caller-owned;
this example does not promise a generic map, automatic ARC or a disk database.

With a native seed named `sotlas-native.exe` in the repository root, stage and
build on Windows using PowerShell:

```powershell
$runtime = 'build/config-map/src/sotlas/runtime'
New-Item -ItemType Directory -Force $runtime
'results','managed','text','unicode','utf8_buffer','pool','pool_text','text_map','json','json_writer' |
    ForEach-Object { Copy-Item "runtime/native/$_.sotlas" $runtime }
Copy-Item examples/native_config_map/main.sotlas build/config-map/src/main.sotlas
.\sotlas-native.exe --check-build build/config-map/src build/config-map/src/main.sotlas
.\sotlas-native.exe --build-win build/config-map/config.exe build/config-map/src build/config-map/src/main.sotlas
.\build\config-map\config.exe
$LASTEXITCODE
```

On Linux/Intel macOS, stage the same ten runtime modules under
`build/config-map/src/sotlas/runtime` and the example as `src/main.sotlas`.
Use `--build` on Linux or `--build-mac` on Intel macOS. After obtaining the seed,
these native build and execution commands do not launch Python or a C compiler.
The separate CI test harness still uses Python to stage sources and assert results.
