# Native static dispatch table

The program declares an immutable command table as initialized native data,
looks up command codes with checked indexing and exits with status 42. It prints
no text. This is a data-driven lookup example, not indirect function-pointer dispatch.
The same fixed-layout table mechanism can describe application settings or
kernel metadata without a C initializer or a startup constructor.

With an already built Linux x86-64 native compiler:

```sh
build/native-selfhost/sotlas-native --check examples/static_dispatch/main.sotlas
build/native-selfhost/sotlas-native examples/static_dispatch/main.sotlas build/static-dispatch
./build/static-dispatch
```

On Windows use a Windows native seed and an `.exe` output name. Status 42 is
expected even when a shell displays a nonzero status as a failed command.

See [the table contract](../../docs/native_static_tables.md) for supported
initializers, mutation rules, bounds traps and capacity limits.
