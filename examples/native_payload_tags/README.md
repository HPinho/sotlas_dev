# Explicit payload tags

This program decodes a bounded byte protocol into a tagged enum with declared
IDs, matches nested payloads, and propagates decoding errors through a second
explicitly tagged `Ok/Err` enum. It verifies valid input, truncated data and an
unknown wire tag. Success exits with 42.

Copy `runtime/native/binary.sotlas` to `src/sotlas/runtime/binary.sotlas`
and this program to `src/main.sotlas`. Use a rebuilt native compiler:

```sh
sotlas-native --check-build src src/main.sotlas
sotlas-native --build payload-tags src src/main.sotlas
./payload-tags
```

Use `--build-win payload-tags.exe` on Windows or `--build-mac payload-tags` on
Intel macOS. The wire format is decoded explicitly; it is not a raw enum memory
image. See the [contract](../../docs/native_payload_tags.md).
