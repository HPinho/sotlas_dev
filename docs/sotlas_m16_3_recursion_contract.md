# M16.3e — Native Recursion Contract

**Status:** IMPLEMENTED — PENDING CI CERTIFICATION  
**Track:** R-SYS / M16.3 Calls & ABI  
**Authority:** machine-call recursion semantics for the current scalar direct-call slice

This document is intentionally narrow. It does not redefine the language as a whole. For broader semantics and restrictions, consult the canonical documentation network in [`README.md`](./README.md).

## Cross-references

- [`sotlas_master_roadmap.md`](./sotlas_master_roadmap.md) — language architecture and profile-specific restrictions such as environments that disallow unbounded recursion;
- [`sotlas_development_blueprint.md`](./sotlas_development_blueprint.md) — ordering/dependencies of backend, kernel, application, realtime and other tracks;
- [`sotlas_full_implementation_plan.md`](./sotlas_full_implementation_plan.md) — M16.3 backlog, including the recursion-contract milestone;
- [`sotlas_implementation_status.md`](./sotlas_implementation_status.md) — certification reality; this document must not be interpreted as `CERTIFIED` until the corresponding baseline is green;
- [`sotlas_release_roadmap.md`](./sotlas_release_roadmap.md) — rules for milestone closure and public release claims.

If any of these documents appears to conflict with this contract, follow the authority routing rules in [`README.md`](./README.md) and repair the documentation gap instead of guessing.

---

## 1. Contract

Within the current M16.3 scalar direct-call subset, Sotlas permits:

- direct self recursion;
- direct mutual recursion among module functions;
- recursion through the same scalar SysV ABI already used by non-recursive calls;
- recursive calls to internal or external module symbols, subject to the normal linkage contract.

Recursion does **not** receive a private or special calling convention.

Each recursive edge uses the ordinary call path:

```text
caller frame
    ↓
validated scalar arguments
    ↓
SysV register arguments 1..6
stack arguments 7+
    ↓
16-byte-aligned outgoing call area
    ↓
r10/r11 caller-saved preservation
    ↓
call callee
    ↓
RAX return transport
    ↓
caller frame restored
```

Therefore self recursion and mutual recursion exercise the same ABI rules as every other M16.3 direct call.

---

## 2. What this layer guarantees

The native backend continues to validate every recursive call exactly as a non-recursive direct call:

- callee must be a valid module function symbol;
- system/foreign calls do not become legal merely because they are recursive;
- argument count must match;
- scalar argument types must match exactly;
- return shape/type must match exactly;
- the normal linkage contract remains in force;
- ordinary stack-frame construction and teardown remain in force;
- register and stack-passed arguments keep their existing SysV rules.

A call graph cycle never bypasses ABI validation.

---

## 3. What this layer does not guarantee

M16.3e does **not** promise:

- a maximum recursion depth;
- compile-time termination proof for arbitrary recursion;
- tail-call optimization;
- tail-recursion elimination;
- stack-overflow recovery;
- recursive aggregate ABI support beyond the currently supported scalar call contract;
- indirect/foreign/system recursion outside already supported call forms.

The generic native ABI must not invent a global recursion-depth restriction merely because a stricter vertical track needs one.

Profiles that require deterministic stack usage, bounded execution or restricted call graphs — for example specific realtime, interrupt, barecore or kernel-critical contexts — must impose and prove those constraints in the appropriate semantic/profile layer before machine ABI lowering.

---

## 4. Source lowering boundary

M16.3e removes the artificial self-call prohibition from the existing narrow scalar source lowering.

The source subset remains deliberately unchanged otherwise:

```sotlas
fn repeat(value: u32) -> u32 {
    return repeat(value);
}
```

is structurally lowerable because it already fits the M16.3b direct-call shape.

The milestone does **not** generalize calls to arbitrary locals, literals, nested call expressions, implicit conversions or aggregates. Those remain separate language/backend work.

Mutual recursion is likewise legal when every edge independently satisfies the normal direct-call contract.

---

## 5. Evidence gates

The M16.3e gate must prove at least:

1. source self recursion survives checked source → canonical SIR → typed Target IR;
2. source self recursion reaches x86-64 assembly through the normal call ABI;
3. synthetic finite self recursion executes natively;
4. synthetic finite mutual recursion executes natively;
5. caller-saved preservation remains active on recursive edges;
6. compiler/tools mirrors remain byte-identical for the touched call/lowering layers;
7. existing non-recursive direct-call gates remain green.

Primary gate:

```text
tests/test_sotlas_machine_x86_64_recursion.py
```

The existing direct-call gate is also updated so a recursive cycle is a positive ABI case rather than an expected rejection.

---

## 6. Certification rule

Until the repository baseline is green after this implementation, the status is:

```text
IMPLEMENTED — PENDING CI CERTIFICATION
```

Only after the user-observed CI baseline is green may the Implementation Status / milestone records be promoted to `CERTIFIED` or equivalent.

This follows [`sotlas_release_roadmap.md`](./sotlas_release_roadmap.md): implementation evidence precedes milestone closure, and milestone closure precedes a public release claim.
