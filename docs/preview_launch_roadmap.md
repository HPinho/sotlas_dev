# Public preview launch roadmap

**Date:** 2026-11-19
**Repository:** [HPinho/sotlas_dev](https://github.com/HPinho/sotlas_dev)  
**Scope:** a usable native preview for terminal applications, a declarative GUI
calculator and a documented minimal kernel example. This is a release plan;
unchecked items are not implemented or certified by this document.

## Starting point

The bounded Sotlas-written compiler emits and links native programs and
rebuilds its original sources with Stage 2/3 byte identity after receiving a
native seed. Subsequent deliveries added native libraries, independent source
builds and inline record arrays. General frontend/ownership parity and independent
distribution remain open. See the [current checkpoint](native_roadmap_checkpoint.md)
and [sovereignty roadmap](sotlas_sovereignty_roadmap.md) for validation limits.
An initial declarative UI and Windows GUI calculator exist; the complete P2/P3
contracts below remain open.

## Six delivery blocks

### Daily delivery agreement — 2026-11-15, 22:54 America/Sao_Paulo

Deliver one bounded, usable block at a time. A block includes its implementation,
native execution/rejection checks, user instructions and explicit limits. The
owner reports the complete remote matrix result. Green closes that declared
scope; move to the next block rather than repeatedly expanding the same scope.
Later defects remain fixable, and broader features become separate deliveries.
This cadence is a working order, not a claim that all language features can be
completed in one day. No workflow polling or scheduled automation is required.

**2026-11-15 block: installable native terminal SDK.** Includes the compiler seed,
original compiler/runtime sources, terminal calculator, JSON configuration
application, 50 Sotlas contract tests, per-file/archive checksums and fresh-prefix
installation. Installed examples and original-source Stage 2/3 reconstruction
must work with host build tools absent from PATH. Windows and Linux local
execution and Intel macOS/complete remote matrix are recorded separately.
**Closed:** the owner confirmed the full matrix green for `c97c936` on 2026-11-16.
See [SDK instructions](../packaging/SDK_README.md). GUI distribution, package
manager parity, full frontend/ownership parity and kernel release certification
are outside this block. Subsequent P2/P3 GUI deliveries do not reopen the
terminal SDK scope.

**Local evidence (2026-11-15):** Windows and Linux/WSL passed archive extraction,
fresh-prefix installation with spaces in its path, calculator success/error
recovery, JSON configuration and model execution, all 50 installed Sotlas
contract tests, and original-source Stage 2/3 byte identity with host build tools
absent from PATH. Both installers rejected corrupted content before creating
the destination and refused to overwrite an existing installation. Intel macOS
and the complete remote matrix remain pending; CI now exercises this same SDK
path on all three CLI targets and uploads candidate archives and test reports.

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

The hidden-window test closes an active clipped paint session and recreates
the window ten times. It checks GDI and USER object counts and rejects invalid
creation arguments even when the runtime is initialized. The runtime reports
paint cleanup failures while continuing to release the class and DLLs after
the window is destroyed. DPI queries return 0 without a window and use 96
when Windows cannot report the DPI. Display scaling, real focus transitions
and OS allocation failure injection remain open.

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
- [x] Define caller-owned scene/state storage and window cleanup for the bounded single-threaded profile; reject exhausted snapshot storage without changing the previous publication. General compiler borrowing/ARC is separate.

**2026-11-16 delivery — scene ownership and publication:**
[UI snapshots](native_ui_snapshots.md) validate the whole scene and copy its
labels into separate caller-owned storage before publication. The calculator
uses the snapshot for painting. Failed capacity, validation and alias checks
leave the previous scene unchanged; hit testing, keyboard activation and
painting reject invalid views. No heap allocation or new Python implementation
was introduced. The installed SDK now includes the graphical example and UI
fixtures: model/Unicode execution on each CLI target, plus hidden-window
rendering/cleanup and GUI compilation on Windows. Local Windows and Linux/WSL
passed the 53 native contract programs and installed-example checks. Windows
also passed twenty snapshot-backed frames, failed-publication recovery and
three restart/shutdown cycles. Complete matrix/Intel macOS certification was
confirmed by the owner for `c97c936`; this bounded block is closed. Responsive
layout, editing and broader ownership remain separate deliveries.

**Next delivery — keyboard expression editing:**
[Cursor-aware fields](native_ui_editing.md) add insertion, Backspace/Delete,
Home/End, left/right navigation, capacity/error recovery and focused caret
rendering with horizontal scrolling. The native UI record/snapshot validates
UTF-8 scalar boundaries; the calculator grammar remains ASCII. Selection,
clipboard, mouse caret placement, IME and responsive layout are outside this
scope. **Closed:** CI #1393 passed for `7fafb3c`, and CI #1394 also passed with
the editing behavior included in `a7f4ab3`.

**Editing local evidence:** extracted SDK installation passed on Windows
(PowerShell 7) and Linux/WSL: 54 native contracts, calculator editing/model and
Unicode fixtures. Windows also passed posted keydown events through the native
window event queue, focused caret/scroll rendering, active/inactive font-width
measurement, existing resource-count and cleanup checks, and GUI compilation.

**2026-11-17 delivery — adaptive viewport and uniform grids:**
[Grid layout](native_ui_layout.md) supplies balanced tracks with validated
bounds/counts/gaps. The calculator measures its client rectangle before painting
and input dispatch, uses the grid for adaptive controls, and publishes a notice
or empty scene for small/zero viewports without changing model state. Tests
cover geometry, disabled hidden controls and restoring focus, cursor and errors.
Windows exercises actual resize/paint/posted-mouse cycles and steady resource
counts after warm-up. **Closed:** [CI #1394](https://github.com/HPinho/sotlas_dev/actions/runs/44092770531)
completed successfully for `a7f4ab3`, verified directly on GitHub before the
next implementation. The preceding editing and adaptive-grid scopes are closed.

**Adaptive-layout local evidence:** extracted SDK installation passed 56
native contracts plus model/Unicode fixtures on Windows (PowerShell 7) and
Linux/WSL. Windows also passed native resize/paint/posted-mouse sequences,
six steady four-size cycles after warm-up, preserved model state, existing
cleanup checks and compilation of the updated GUI application.

**P3 first application (2026-10-16):** the [graphical calculator](../examples/graphical_calculator/README.md)
now executes through the native Windows backend. Model/layout tests passed on
Windows and Linux/WSL; Windows painting/cleanup tests and a visible click-to-result
check passed locally. Storage/label lifetimes remain explicit caller obligations;
general ownership proof and complete UI ergonomics are still open. The
initial profile had ASCII labels, append/Backspace editing and fixed layout. Remote CI
is pending; the full preview is not certified by this example.

**P3 UTF-8 label delivery (2026-10-16):** labels now accept validated UTF-8 and
the Windows renderer converts them to UTF-16, including surrogate pairs.
The native codec/UI gates passed on Windows and Linux/WSL; Windows also passed
mixed-script drawing and cleanup. Calculator expression input remains ASCII;
IME, shaping and grapheme editing remain open. See the
[text contract](native_unicode_text.md). Remote CI is pending.

Use ordinary Sotlas functions and typed records for the initial declarative
API. No new syntax is promised by this plan. Actions may use explicit IDs and
dispatch; a callback API requires native function-value/lifetime validation.
The first GUI release targets Windows x86-64. Linux and Intel macOS GUI support
requires separate platform implementations and execution gates.

### P4 — applications and kernel documentation

- [x] Publish complete terminal and graphical calculator projects, expected behavior, build commands and troubleshooting instructions for the declared preview profiles.
- [x] Publish a minimal kernel project with documented entry, target, boot environment, memory assumptions and diagnostic output; reproduce it in the selected emulator. See [native boot](native_kernel_boot.md), [interrupts](native_kernel_interrupts.md) and [physical pages](native_kernel_memory.md); local QEMU execution is covered, release certification still requires platform CI.
- [x] Document which compiler, library and ownership contracts each example exercises and automate its build/execution checks. See the [installed kernel SDK guide](native_kernel_sdk.md); new kernel distribution certification awaits its own CI.

**Next delivery — installed kernel SDK:** bundle all seven kernel examples,
their runtime sources, POSIX/Windows image-build scripts and native link
rejection fixtures. Installed SDK gates build all profiles on each CLI host;
Linux QEMU executes the basic and integrated foundation profiles. Entry ABI,
hosted-call boundaries, missing entries, malformed objects and output preservation
are tested before certification. This closes the installed-example path when
its new complete matrix is green; it does not certify a full OS or firmware.

**Kernel SDK local evidence:** extracted installations in paths containing
spaces passed all seven profile builds on Windows/PowerShell 7 and Linux/WSL.
Their seven images and two boot modules are byte-identical across hosts.
PowerShell 5 independently generated the identical foundation image/module.
Both installed verifiers passed deterministic relinking and all four rejection
checks with output preservation. Linux QEMU booted basic/foundation images,
returned guest result 42 / emulator exit 85 and produced every required serial
checkpoint. New native CI steps repeat these installed checks, with image
generation on all three hosts and emulator execution on Linux. The new
delivery is **closed**: [CI #1395](https://github.com/HPinho/sotlas_dev/actions/runs/44134890716)
completed successfully for `e6c36ed`, verified directly on GitHub before the
next block. Installed image generation passed on all three CLI hosts and Linux
boot verification passed for the declared basic/foundation scope.

**Next delivery — native SDK in VS Code:** [native editor commands](native_vscode_sdk.md)
select the installed SDK, create a console project, check/build/run it and
publish compiler locations in Problems. Native builds use the native compiler;
reference commands remain a separate compatible profile. The installed-VSIX
test exercises actual program execution, ownership rejection after Unicode
text, stale-artifact prevention and project preservation. Its new full matrix
certification remains pending.

**Native editor local evidence:** all 16 editor unit tests and TypeScript
compilation passed. On Linux/WSL, the packaged VSIX passed both the reference
diagnostics test and the installed native SDK test in isolated VS Code
profiles. The native test starts with an empty workspace, creates a project,
checks/builds/runs the real executable, maps a Unicode ownership diagnostic,
blocks execution after a failed build and preserves existing project files.
The generated console project also checked, built and ran on Windows using
the installed SDK. Installed-VSIX execution on Windows and Intel macOS remains
for the new three-host CI gate; local Linux results do not certify those hosts.

**2026-11-18 editor repair:** [CI #1397](https://github.com/HPinho/sotlas_dev/actions/runs/44280684297)
failed the installed-VSIX gates on Windows and Intel macOS. Windows compared
equivalent SDK paths with differently cased drive letters; macOS used an older
runner expecting the obsolete application executable name. All other executed
jobs passed, including the Linux native editor gate, native SDK reconstruction,
the reference matrix and C11. The repair normalizes paths through VS Code URIs
and pins the upstream runner with current macOS bundle resolution. Local
installed-VSIX native scenarios now pass on Windows and Linux; 17 editor unit
tests include macOS executable-resolution coverage. Actual macOS execution and
the complete repair matrix still require the new CI run.

**Parallel feature delivery — CPU tensor row operations:** the
[new module](native_tensor_ops.md) implements sum/mean/max by row and
row-vector addition/multiplication with checked ranges, shapes and overlaps.
The [preprocessing example](../examples/native_tensor_rows/README.md) composes
offsets, scales, statistics and matrix-vector projection. Fresh installed SDKs
on Windows and Linux built and executed the example and all 58 native Sotlas
contracts with zero failures. Their native subprocesses ran without host build
tools in PATH. The SDK includes the module, example, documentation and cases;
the installed verifier repeats this coverage on every native CI host. Intel
macOS execution and full CI certification remain pending. This extends the CPU
library; it does not close tensor language types or physical GPU/NPU dispatch.

**2026-11-19 certification:** [CI #1399](https://github.com/HPinho/sotlas_dev/actions/runs/44502271454)
completed successfully for `402e1d0`, following green push run #1398. This
certifies the declared tensor row operations, installed native VSIX scenario
and 58-case SDK scope across Linux, Windows and Intel macOS. Those delivery
blocks are closed; wider frontend, ownership and release gates remain separate.

**Next delivery — native CSV:** caller-backed field iteration, quote decoding
and canonical CRLF writing, with explicit metadata/capacity/alias errors and
output preservation on rejected operations. The installed inventory example
checks the complete read/decode/parse/write/read path. Six original Sotlas
cases extend the native suite to 64. The API operates on byte buffers supplied
by the caller.

**CSV local evidence:** fresh-prefix SDK verification passed all 64 contracts
and the original inventory example on Windows and Linux/WSL, with host build
tools absent from the native subprocess PATH. The installed Windows VSIX
scenario also passed using this SDK before the three-host certification.

**CSV certification:** [CI #1400](https://github.com/HPinho/sotlas_dev/actions/runs/44545711063)
passed for `f0d7fad`, closing the CSV library and inventory example delivery.
[CI #1401](https://github.com/HPinho/sotlas_dev/actions/runs/44623591711)
passed for `1c45008`, including the installed
[CSV terminal utility](../examples/native_csv/README.md#normalize-a-csv-file).
The verifier checks exact output, repeat conversion, empty and maximum-size
input, and zero output on malformed or oversized input.

### P5 — installation

The SDK now records its version, source revision, platform and compiler
fingerprint in `sdk.json`. Installers validate the compiler fingerprint when
present and keep accepting earlier format-1 bundles. The native CI matrix
checks the archive checksum before extraction and verifies the installed
metadata against the build revision. [CI #1403](https://github.com/HPinho/sotlas_dev/actions/runs/44714484483)
passed this packaging gate for Linux, Windows and Intel macOS.

- [x] Package versioned compiler, native libraries, headers/bindings if needed, examples and licenses with checksums.
- [x] Verify clean-prefix install, terminal check/build/run on all three CLI targets, and GUI build and hidden-window rendering on Windows for the `1.0.0rc1` candidate.
- [x] Verify GUI dependency discovery and native self-build from the installed seed without Python, a C compiler or an external linker.

CI #1403 executed the Windows GUI dependency and render checks from the
installed SDK. All three native hosts rebuilt the installed compiler twice
with host build tools outside PATH and compared the resulting executables.
[CI #1422](https://github.com/HPinho/sotlas_dev/actions/runs/45600636812)
repeated the installation, native rebuild, kernel SDK and installed VSIX gates
for `2aff49a9`, the source revision of `1.0.0rc1`.

### P6 — publication gate

The release workflow requires a successful main CI run for the checked-out
commit. It uses that run's three native SDK archives and VSIX, verifies the
SDK archive checksums, and includes the assets in the preview checksum list.
A manual run defaults to `dry_run: true` and uploads
`sotlas-preview-candidate` for review. A manual publish uses the same gates
with `dry_run: false`. The existing tag trigger also requires certified CI.

#### Preview versions

Use `1.0.0rc1`, `1.0.0rc2`, and so on for the preview packages. GitHub
Releases adds a `v` prefix to the corresponding tag. Reserve `1.0.0` for
the stable release. Publish a new candidate when a batch of changes is ready.

1. Update the version in `pyproject.toml`, `setup.py`, both `sotlas/__init__.py`
   files, and `packaging/windows/sotlas.iss`. Add the matching section to
   `CHANGELOG.md` with the user-facing changes and known limits.
2. Push to `main` and confirm that CI passes for that commit. Run **Sotlas
   Release & Packaging** with `dry_run` enabled and download
   `sotlas-preview-candidate` to review the files and release notes. The
   optional `version` field checks that the run uses the intended version.
3. Publish from the certified revision with `dry_run` disabled, or push its
   version tag. Keep published tags and assets intact. Ship fixes under the
   next candidate version.

- [x] Align the README, website setup pages, SDK quickstart and VS Code instructions with the native archives, reference package and supported platforms.
- [x] Run the full CI matrix, clean-install checks and release packaging for `1.0.0rc1` at `2aff49a9`. [Release rehearsal #2](https://github.com/HPinho/sotlas_dev/actions/runs/45606408507) produced the versioned Windows installer, three native SDKs, VSIX and checksum manifest.
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
