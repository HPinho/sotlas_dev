# Graphical calculator

A Windows x64 application written in Sotlas, using the reusable calculator
evaluator and a first declarative UI library. The native seed compiles the
original modules and links the executable with no generated C, Python process
or external linker in the build path. Windows system drawing services remain
platform dependencies.

## Build and run

Use a native seed containing the P2 Win64 bridge, on Windows 10/11 x64:

```powershell
powershell -NoProfile -File examples/graphical_calculator/build.ps1 build/native/sotlas-native.exe build/gui-calculator
./build/gui-calculator/calculator.exe
```

Choose a fresh output directory. Click numbers and operations, then `=`. The
expression remains visible for correction or continued editing. `C` clears;
`←` deletes the last character; `×` and `÷` select multiplication and division.
The keyboard accepts the same arithmetic
characters, Backspace and Enter. Tab moves focus in declaration order; Enter
or Space activates a focused button. Escape closes the application.

The expression buffer holds 128 ASCII bytes. Full input is rejected without
modifying the expression. Invalid expressions display the evaluator's error
and remain editable. Arithmetic follows the [terminal calculator contract](../calculator/README.md):
precedence, parentheses, decimals, `f64`, bounded magnitude and six-place display.
It is not exact financial decimal arithmetic.

## UI library contract

`runtime/native/ui.sotlas` is independent of the platform renderer. A `UiView`
borrows caller-owned item storage; item labels borrow stable UTF-8 storage.
The example model keeps its expression/result buffers stable through painting.
This is an explicit lifetime precondition, not a new compiler borrow proof.

| Component/API | Behavior in this profile |
|---|---|
| `ui_text` | Read-only label |
| `ui_button` | Label, focus and one action ID per activation |
| `ui_text_field` | Focusable value display; this application implements append/Backspace editing |
| `ui_row`, `ui_column`, `ui_cell` | Fixed extents, spacing and checked container bounds |
| `ui_click` | Hit testing with half-open bounds; gaps do not activate controls |
| `ui_key` | Tab focus cycling; Enter/Space button activation |
| `ui_windows_paint` | Event-driven Windows drawing and per-item clipping |

The view supports at most 64 items, each with a unique nonzero ID and up to
128 UTF-8 label bytes. Geometry must fit the 4096-unit coordinate profile.
Invalid geometry, labels, duplicate IDs or exhausted item storage set a view
error and preserve previously inserted items/count. Recreate a view to clear
an error. Raw view/item pointers must remain valid; fabricating pointers is
outside the safe contract. A renderer failure always attempts to close its
clip/paint scope and restore the previous font.

The calculator declares 23 items using these functions: title, input, result
and twenty buttons. Its model owns one session. State changes rebuild the
view and request repaint; button activation and translated character events
are handled separately so Enter/Space do not apply an action twice.

## Verification

- The original UI/calculator model passed native execution on Windows and
  Linux/WSL: layout bounds, hit tests, focus, arithmetic, invalid expressions,
  input capacity, duplicate IDs, invalid labels and exhausted storage.
- The Windows renderer passed twenty frames without growing measured GDI/USER
  object counts. Tests exercise rejected frames, failure during a paint,
  restoration of clip state and shutdown with an active paint session.
- A local visible application check clicked `7`, `+`, `8`, `=` and displayed
  `7+8` and `15`. This is visual local evidence, not an automated screenshot gate.
- Build scripts invoke checking and compilation with host tools absent from PATH.
  Existing Stage 3 gates reuse their rebuilt compiler for the model; Windows
  additionally runs rendering. Remote CI and Intel macOS model execution are pending.

The UTF-8/UTF-16 gate also passed on Windows and Linux/WSL; Windows drew a
mixed-script label containing BMP and supplementary scalars. Font coverage
and shaping are not certified by a successful drawing call.

Tests: `tests/native/ui/model.sotlas`, `tests/native/ui/unicode.sotlas`,
`tests/native/ui/render.sotlas` and the
process adapter `tests/native_ui_gate.py`. UI implementation and tests of its
semantics are Sotlas; Python only orchestrates processes in the test harness.

## Remaining scope

This first UI profile uses fixed layout and validated UTF-8 labels. The
[encoding contract](../../docs/native_unicode_text.md) defines conversion,
controls and capacity rules. It does not provide
responsive reflow, general text selection/caret editing, complex text shaping/IME,
accessibility, clipboard support, multiple windows, touch, animations, GPU
rendering, a visual editor or hot reload. Narrow windows clip the fixed scene.
These limits must remain visible in preview documentation. Linux/macOS
renderer ports and full language/ownership parity are separate work.
