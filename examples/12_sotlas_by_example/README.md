# Sotlas by Example

These examples are small, runnable programs that exercise the compiler's
current native contract. `05_native_control_flow.sotlas` combines an early
return, a conditional expression, a loop, `continue`, `break`, and conditional
branches in one program. Its `main` checks multiple input paths and returns a
nonzero status if a result is wrong.

From the repository root, run the native example with:

```sh
sotlas check examples/12_sotlas_by_example/05_native_control_flow.sotlas
sotlas compile examples/12_sotlas_by_example/05_native_control_flow.sotlas \
  --backend c11 --emit-c -o build/native_control_flow.c
sotlas run examples/12_sotlas_by_example/05_native_control_flow.sotlas
```

Native compilation and execution require a configured Clang installation.
The example returns a nonzero exit code if either the zero-limit early return
or the loop's expected sum is wrong.
