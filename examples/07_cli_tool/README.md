# Command dispatch example

This standalone example checks enum-based command selection and dispatch. Its
`main` exercises Build, Test, Help, and an unknown command and returns zero only
when every result matches the expected status. CI checks, emits, and runs it
with the C11 backend:

```sh
sotlas check examples/07_cli_tool/main.sotlas
sotlas compile examples/07_cli_tool/main.sotlas --backend c11 --emit-c -o cli_dispatch.c
sotlas run examples/07_cli_tool/main.sotlas
```

It demonstrates the dispatch logic only. Reading process arguments and writing
terminal output are outside the current preview contract.
