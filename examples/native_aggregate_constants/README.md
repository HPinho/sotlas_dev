# Immutable native profile table

The program defines a constant table of records with weights and tagged
policies. It changes an independent local copy, verifies the original remains
intact, reads a default profile and sums enabled entries to 42.

Copy `main.sotlas` to `src/main.sotlas` and use a native compiler rebuilt with
aggregate constants:

```sh
sotlas-native --check-build src src/main.sotlas
sotlas-native --build profiles src src/main.sotlas
./profiles
```

Success exits 42. Use `--build-win profiles.exe` on Windows or `--build-mac profiles`
on Intel macOS, with the same `src src/main.sotlas` arguments. No runtime modules or host
compiler/linker are required for this example after obtaining the native seed.
See [the contract](../../docs/native_aggregate_constants.md) for initializer,
immutability, storage and platform limits.
