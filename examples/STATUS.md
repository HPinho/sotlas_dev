# Official example status

`examples/manifest.json` is the machine-readable source of truth.

- **SUPPORTED** requires the complete project support contract: specification, parser, typed AST, semantic verification, lowering/backend, positive tests, negative tests, and end-to-end tests.
- **EXPERIMENTAL** means implementation exists, but the complete support contract has not yet been proven.
- **backend_contract: true** selects an example for the CI smoke `sotlas check -> C11 lowering -> host C syntax validation`.

Passing the backend-contract smoke does **not** promote an example or language feature to **SUPPORTED**.

At the current Reality Reset baseline, the numbered examples remain **EXPERIMENTAL** until the master-spec support gate is satisfied end to end.
