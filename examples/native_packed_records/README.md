# Packed records on the native x86-64 path

This program verifies a 14-byte packed packet layout, unaligned scalar access,
array stride, independent copies, and by-value function arguments and returns.
It uses ordinary memory and exits with 42 on success. It performs no hardware I/O.

Use a native seed rebuilt from sources containing packed-record support:

```sh
sotlas-native --check examples/native_packed_records/main.sotlas
sotlas-native examples/native_packed_records/main.sotlas packet
./packet
```

On Windows use an `.exe` output name. The native compiler selects its host
executable format. The cross-platform test also emits ELF, PE and Mach-O images.

See [the layout contract](../../docs/native_layout_queries.md). Packing removes
padding between fields; it does not repack nested records or provide volatile,
atomic, endian-conversion or general foreign ABI guarantees.
