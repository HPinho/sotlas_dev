# Phase Gate Evidence Matrix

This matrix is generated from `phase_gate_matrix.json`. The Python test suite
checks that every listed gate exists; CI runs that suite and the dedicated
phase subsets listed in `.github/workflows/ci.yml`. Evidence and boundaries
describe the tested 1.0 subset. They are not claims of full language support.

| Phase | Area | Gate files | Evidence exercised | Known boundary |
|---:|---|---|---|---|
| 0 | Reality reset | `test_sotlas_reality_gate.py` | Repository metadata, public claims, examples, and canonical CLI smoke checks. | Documentation and acceptance claims; it does not certify every language feature. |
| 1 | Typed semantic core | `test_sotlas_phase1_pipeline.py`, `test_sotlas_typed_ast_foundation.py` | Canonical check pipeline and typed AST semantic cases. | Most semantic cases are checker tests; native execution is limited to explicit fixtures. |
| 2 | Ownership domains | `test_phase2_regression_guard.py`, `test_sotlas_phase2_v1_region_release_gate.py`, `test_sotlas_phase2_v1_borrow_release_gate.py`, `test_sotlas_sole_ownership.py`, `test_sotlas_ownership_soundness.py` | Canonical ownership/SIR placement, static rejection, and selected native ownership runs. | The supported structured subset is tested; arbitrary CFG and full runtime ARC remain outside the contract. |
| 3 | Authority domains | `test_sotlas_authority_phase1.py`, `test_sotlas_authority_checked_sir.py`, `test_sotlas_authority_sir_abi.py` | Canonical authority checks, typed SIR facts, and ABI contract validation. | Reference ABI tests do not imply vendor GPU/NPU execution. |
| 4 | State spaces | `test_sotlas_state_frontend.py`, `test_sotlas_state_phase1.py` | Canonical state typing and transition validation. | Only declared state-transition forms are accepted. |
| 5 | Effects | `test_sotlas_source_effects.py`, `test_sotlas_backend_effect_contract.py` | Effect inference and backend rejection contracts. | Effect checking does not sandbox external side effects. |
| 6 | Flow | `test_sotlas_flow_frontend.py`, `test_sotlas_flow_cfg.py`, `test_sotlas_flow_cfg_runtime.py`, `test_sotlas_flow_runtime.py`, `test_sotlas_flow_native.py` | Canonical typed plans/SIR and reference interpretation for integer and boolean CFGs; native C11 entrypoints for serial pure signed/unsigned integer, f32/f64, and bool plans. C and Sotlas callers can invoke the generated entrypoint through its checked C ABI declaration. | The SIR interpreter and native backend cover different scalar/CFG subsets; native signed overflow is not defined by the language. Source calls require the exact generated symbol and an @system function; there is no dedicated Flow invocation syntax. Native callers receive only the final stage result. Parallel plans, ownership payloads, stage errors/cancellation, and GPU/NPU dispatch remain unsupported. |
| 7 | Execution domains | `test_sotlas_llvm.py` | Target normalization, feature contracts, and LLVM emission checks. | This is not a complete platform ABI or a Sotlas machine-code backend. |
| 8 | Heterogeneous compute | `test_sotlas_device_reference_runtime.py`, `test_sotlas_device_checked_c11_pipeline.py`, `test_sotlas_device_reference_abi_link.py` | Checked DEVICE lifecycle and reference C11 provider integration. | No physical GPU/NPU, vendor driver, DMA, or hardware completion is implemented. |
| 9 | Trust domains | `test_sotlas_source_effects.py`, `test_sotlas_unsafe_ffi.py` | Foreign boundary classification, explicit unsafe checks, and fail-closed validation. | Trust labels do not create process isolation or a sandbox. |
| 10 | Guarantees | `test_sotlas_contract_frontend.py`, `test_sotlas_contract_report_cli.py` | Supported preconditions, refinements, and deterministic reports. | Only the documented predicate subset is proved. |
| 11 | Causality | `test_sotlas_flow_frontend.py` | Source and checked Flow call/dependency explanations. | Ambiguous mutation and unresolved control flow remain fail-closed. |
| 12 | Counterfactuals | `test_sotlas_flow_frontend.py` | Certified graph recovery and selected pure SIR equivalence cases. | Proof is limited to the tested normalization and scalar subset. |
| 13 | Transactions | `test_sotlas_flow_frontend.py` | Effect policy checks and sequential compensation behavior. | Parallel transactional execution and arbitrary rollback semantics are rejected. |
| 14 | Intent | `test_sotlas_flow_frontend.py` | Selection among checked eligible Flow alternatives, fallback reports, and explicit provider availability requirements. | Provider availability is supplied by the caller; intent does not discover or dispatch physical hardware. |
| 15 | Canonical SIR | `test_sotlas_sir.py`, `test_sotlas_sir_report_cli.py` | Canonical SIR facts, validation, and reports. | SIR body lowering remains a certified subset, not complete lowering for the language. |
| 16 | Native machine backend | `test_sotlas_llvm_direct_emission.py` | Direct LLVM subset emission, native execution, and C11/LLVM differential checks for tested unsigned parameter and literal arithmetic. | Parity covers only tested forms. LLVM provides target code generation; Sotlas does not yet own register allocation or a machine backend. |
| 17 | Advanced tooling | `test_sotlas_contract_report_cli.py`, `test_sotlas_flow_report_cli.py`, `test_sotlas_sir_report_cli.py` | Deterministic report CLI contracts. | Reports describe only facts represented by the checked subset. |

## Cross-cutting validation

The CI workflow also checks canonical `check` → C11 emission for every
example marked `backend_contract`, runs native examples marked `native_run`,
builds and installs the Python wheel, installs the packaged VS Code extension
in a clean profile, and tests/lints/builds the website.

The matrix intentionally calls out reference runtimes and prototype subsets.
A passing test for one of those paths does not promote it to native, device,
or general-purpose support.
