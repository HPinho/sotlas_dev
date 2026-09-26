# Sotlas Preview Website

This directory contains the development copy of the Sotlas website. Its content is being reviewed
against the compiler and tests in the parent repository. The live organization site is maintained
separately and is not updated by changes here.

## Run locally

From the repository root:

```sh
cd web
npm ci
npm run dev
```

## Validate a change

```sh
npm test
npm run lint
npm run build
```

The examples page imports source files from `../examples`; the Vite development server is configured
to serve files from the repository root. Public support statements should match `docs/sotlas_1_0_release_scope.md`
and the compiler gates before this copy is transferred to the organization website.
