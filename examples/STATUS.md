# Official example status

`examples/manifest.json` is the machine-readable source of truth.

- **SUPPORTED** examples must satisfy the canonical `sotlas check` contract, C11 lowering, and host C syntax validation in CI.
- **EXPERIMENTAL** examples may exercise syntax or semantics still being migrated into the canonical frontend.

Promotion to **SUPPORTED** requires the complete project support contract: specification, parser, semantic verification, lowering/backend, positive tests, negative tests, and end-to-end tests.
