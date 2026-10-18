# Inline inventory table

This native example stores two records directly inside an `Inventory`, returns
the container by value, borrows it through `whisper`, loops over its elements
and edits an independent copy. The original inventory total remains 42.

With a native compiler built from SV8.76 sources:

```sh
sotlas-native --check examples/record_table/main.sotlas
sotlas-native examples/record_table/main.sotlas inventory
```

The native host driver selects its normal executable format. On Windows, name
the output `inventory.exe`. Run the executable on the corresponding operating
system; exit status 42 confirms the checks. This is an execution example rather
than a terminal UI: it intentionally communicates its result through exit status.

See the [record-array field contract](../../docs/native_record_array_fields.md)
for storage, bounds, ownership and unsupported element types.
