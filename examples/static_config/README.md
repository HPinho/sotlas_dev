# Native static configuration

This example stores a configuration and its channel table in initialized native
data. No function constructs the global value at startup. A returned snapshot
has independent inline storage; editing it leaves the global configuration intact.
The process exits with status 42 and prints no text.

Using an already built native compiler on Linux x86-64:

```sh
build/native-selfhost/sotlas-native --check examples/static_config/main.sotlas
build/native-selfhost/sotlas-native examples/static_config/main.sotlas build/static-config
./build/static-config
```

On Windows, use the Windows native compiler and an `.exe` output path. A shell
may display exit 42 as an unsuccessful command; 42 is the expected program result.

See [the native static record contract](../../docs/native_static_records.md) for
constant evaluation, storage limits and excluded resource/pointer initializers.
