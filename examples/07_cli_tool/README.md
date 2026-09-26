# Command dispatch example

This example verifies enum-based command selection and dispatch through the
canonical frontend and C11 backend:

```sh
sotlas check examples/07_cli_tool/main.sotlas
sotlas compile examples/07_cli_tool/main.sotlas --backend c11 --emit-c -o cli_dispatch.c
```

It is a command-dispatch example, not a complete operating-system CLI. Reading
process arguments, strings from `argv`, and writing terminal output are outside
the current preview contract. The selected `Build` command returns status `0`;
the `Test` branch returns `10`, and unknown values return `1`.
