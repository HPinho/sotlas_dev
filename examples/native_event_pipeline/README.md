# Native event pipeline

A small typed data pipeline combines settings, heterogeneous readings, explicit
success/error values and a report. It uses nested payload enums inside structs,
arrays of those values, named/array patterns, static startup data and the internal
owned-value ABI. Settings are deliberately declared before their dependencies.

The executable checks valid input, an offline source and an error payload, then
exits with status **42**. It prints no output. Returning an error enum here is an
ordinary explicit value; it does not introduce automatic error propagation.

With a native compiler rebuilt from sources containing SV8.96:

```sh
sotlas-native --check examples/native_event_pipeline/main.sotlas
sotlas-native examples/native_event_pipeline/main.sotlas build/event-pipeline
./build/event-pipeline
```

On Windows, use the native Windows compiler and an `.exe` output name. Exit 42 is
the expected result. The native compiler emits its own machine code and links
the program without launching Python, a C compiler or an external linker.

This is the bounded native preview profile. The aggregates are pointer-free POD;
their ownership checks do not synthesize resource destruction or ARC. See
[composed native values](../../docs/native_composed_values.md) for layouts,
limits, static storage and validation boundaries.
