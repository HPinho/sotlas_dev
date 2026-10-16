# Public preview launch roadmap

**Date:** 2026-10-16  
**Repository:** [HPinho/sotlas_dev](https://github.com/HPinho/sotlas_dev)  
**Scope:** a usable native preview for terminal applications, a declarative GUI
calculator and a documented minimal kernel example. This is a release plan;
unchecked items are not implemented or certified by this document.

## Starting point

The bounded Sotlas-written compiler emits and links native programs and
rebuilds its original sources with Stage 2/3 byte identity after receiving a
native seed. SV8.64 passed focused Windows and Linux/WSL capacity tests locally;
its remote CI is pending. General frontend/ownership parity and independent
distribution remain open. See the [sovereignty roadmap](sotlas_sovereignty_roadmap.md).
The declarative GUI described here is planned, not an existing toolkit.

## Six delivery blocks

| Block | Deliverable | Completion gate |
|---|---|---|
| P1 | Calculator core and native application APIs | Original Sotlas sources check, compile and execute; arithmetic and error cases pass |
| P2 | Native window, drawing, text and input | Native executable opens, paints, resizes and closes; input and resource cleanup work |
| P3 | Declarative Sotlas UI library | Calculator runs with reusable components, state updates, layout and keyboard navigation |
| P4 | Three documented example projects | Terminal calculator, GUI calculator and minimal kernel reproduce from instructions |
| P5 | Installable native preview | Clean installation builds and runs examples without Python or a C compiler |
| P6 | Release candidate certification | Advertised platform gates, support matrix, extension and packaged examples agree |

**P1 local completion (2026-10-16):** the [terminal calculator](../examples/calculator/README.md)
passes its Sotlas-native model gate and 12 CLI scenarios on Windows and
Linux/WSL. The original example builds with native seeds and host tools absent
from PATH. Existing Stage 3 gates now cover it. Intel macOS execution and
remote CI are pending; P2–P6 remain open.

### P1 — language and library path

- [x] Implement the calculator model in Sotlas: precedence, parentheses, decimals, invalid input and division by zero.
- [x] Provide the text buffers, numeric parsing/formatting, collections, error values and I/O used by this application; document capacity and lifetime limits.
- [x] Check and compile these original sources through the native compiler; no compiler extension was required for this bounded application.

The terminal and graphical applications must reuse this same model. Caller-backed
buffers and explicit cleanup are acceptable when their lifetimes are enforced
or documented as unsafe preconditions. General generics and automatic ARC are
tracked separately; completion of this block does not certify them.

### P2 — platform proof

- [x] Implement a Windows platform probe through the native backend: window lifecycle, event dispatch, drawing, fonts and UTF-16 unit input.
- [x] Validate required scalar Win64 calls, record layouts and handles; the probe uses the OS procedure rather than Sotlas callbacks.
- [ ] Exercise resize, display scaling, focus, Unicode input, allocation/initialization failures and repeated open/close without resource leaks.

**P2 first delivery (2026-10-16):** the [Windows window probe](../examples/native_window/README.md)
passed local hidden-window lifecycle/input/resource gates and a visible drawing
and text-update check. Resize, basic DPI queries and invalid-input rejection
are covered; per-monitor scale/focus transitions, complete Unicode editing and
injected OS allocation failures remain unvalidated. Remote CI is pending.

The concrete OS rendering/text adapters are selected by this probe. The UI API
and application logic are Sotlas code; platform bindings may call OS services.
The packaged build must not require a C compiler or generated C glue. Window
system services remain runtime dependencies and must be listed.

### P3 — declarative UI in Sotlas

- [x] Implement the first bounded `Text`, `Button`, `TextField`, `Row` and `Column` profile, with IDs, fixed sizing/spacing and Tab focus order.
- [x] Implement state-to-view updates, action dispatch and event-driven repaint in the graphical calculator, with separate key/character activation paths.
- [ ] Define component/state/resource ownership and cleanup; reject or diagnose exhausted UI storage and preserve valid state on failure.

**P3 first application (2026-10-16):** the [graphical calculator](../examples/graphical_calculator/README.md)
now executes through the native Windows backend. Model/layout tests passed on
Windows and Linux/WSL; Windows painting/cleanup tests and a visible click-to-result
check passed locally. Storage/label lifetimes remain explicit caller obligations;
general ownership proof and complete UI ergonomics are still open. The initial
profile has ASCII labels, append/Backspace editing and fixed layout. Remote CI
is pending; the full preview is not certified by this example.

Use ordinary Sotlas functions and typed records for the initial declarative
API. No new syntax is promised by this plan. Actions may use explicit IDs and
dispatch; a callback API requires native function-value/lifetime validation.
The first GUI release targets Windows x86-64. Linux and Intel macOS GUI support
requires separate platform implementations and execution gates.

### P4 — applications and kernel documentation

- [ ] Publish complete terminal and graphical calculator projects, expected behavior, build commands and troubleshooting instructions.
- [ ] Publish a minimal kernel project with documented entry, target, boot environment, memory assumptions and diagnostic output; reproduce it in the selected emulator.
- [ ] Document which compiler, library and ownership contracts each example exercises and automate its build/execution checks.

### P5 — installation

- [ ] Package versioned compiler, native libraries, headers/bindings if needed, examples and licenses with checksums.
- [ ] Install on a clean machine, then check, build and run the terminal example on every advertised CLI target and the GUI on Windows.
- [ ] Verify GUI dependency discovery and native self-build from the installed seed without Python, a C compiler or an external linker.

### P6 — publication gate

- [ ] Align README, website, quickstart and VS Code package with the actual preview commands and supported platforms.
- [ ] Run focused gates per delivery block; run the full release matrix and clean-install checks for the candidate.
- [ ] Resolve crashes, incorrect generated code, resource lifetime bugs and broken installation; publish known feature limits and reporting instructions.

## Working order and release rule

Implement P1, then P2 and P3, complete P4/P5, and certify P6. Each block should
deliver executable behavior and its focused regression checks in one reviewable
commit. Reuse existing native seeds and Stage 3 gates. Remote CI is reported by
the owner; do not wait for or monitor it between independent work.

The preview ships when all six gates pass for the declared targets. Full
Flutter feature parity, hot reload, a visual editor, mobile targets, GPU UI
acceleration and complete Python/C bootstrap removal are separate milestones.
They must not appear as supported preview features without their own evidence.
