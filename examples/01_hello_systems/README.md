# Hello Systems

A small native program that computes a factorial and checks the result. It is
kept intentionally small so it can serve as an installation and compiler smoke
test.

```sh
sotlas check examples/01_hello_systems/main.sotlas
sotlas compile examples/01_hello_systems/main.sotlas --backend c11 --emit-c -o hello.c
sotlas run examples/01_hello_systems/main.sotlas
```

The program returns exit status `0` when `5!` evaluates to `120`.
