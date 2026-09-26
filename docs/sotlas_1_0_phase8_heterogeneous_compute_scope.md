# Sotlas 1.0 — Phase 8 Heterogeneous Compute Scope

**Updated:** 2026-09-26  
**Status:** COMPLETE for the DEVICE reference-runtime contract

## Certified contract

The checked source pipeline composes a verified lifecycle with canonical SIR,
logical and physical runtime ABI plans, and a C11 artifact for the reference
DEVICE runtime. Source identities for submit, completion, synchronization, and
reacquisition survive the pipeline. Runtime owner bindings must match the
certified owners exactly; omissions, extras, or incompatible plans fail
closed. The generated declarations link to the repository's C reference
provider, and a native test executes a complete transfer, completion, sync,
reacquisition, and fence-consumption cycle. A two-owner lifecycle is also
covered end to end and batches its synchronization.

## Release boundary

The runtime is a deterministic single-threaded reference provider. Sotlas 1.0
does not claim GPU/NPU execution, hardware discovery, DMA, driver integration,
physical completion, target synchronization, device failure recovery, or
timeouts. Those require a concrete provider and hardware-specific lowering.
The reference ABI is an integration contract for those future providers, not a
hardware implementation.

## CI gate

CI runs the reference runtime tests, checked-source-to-C11 lifecycle tests, and
the generated-ABI native link-and-run test. These gates cover the full
reference path and do not imply physical device coverage.
