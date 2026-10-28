# Persistent UTF-8 key/value parsing and composition

The executable creates independent persistent text slots, recycles an earlier
allocation, splits a key/value record (`answer=42`) using checked views,
parses the numeric field, clones the key into a separate allocation and releases
the original without invalidating the clone. It then builds a report by
composing two stored texts and performs checked Unicode scalar edits.

Expected process exit code: **42**. No text is printed. All backing storage
is caller-owned and managed by the Sotlas-native reusable pool. Success verifies
that every live handle is explicitly released and the pool closes.

See [persistent text composition](../../docs/native_pool_text_composition.md)
for the full API and limitations, and [native pools](../../docs/native_pool.md)
for lifetime and allocation identity contracts.

A current native Stage 3 compiler can check and build the example using the
existing source-list build/test gate. All three Linux/Windows/Intel macOS Stage 3
CI gates execute this example with Python and host C tools absent from the
native child process PATH. The initial seed and test harness still use Python.
