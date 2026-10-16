# Native Windows window probe

This P2 delivery opens a resizable Windows x64 window, paints UTF-16 text and
updates it from keyboard input. Escape or the close button ends the application.
The application, resource lifecycle and platform adapter are Sotlas code.
The native compiler emits machine code and links the PE without generated C,
a C compiler, application C runtime glue or an external linker after receiving
a native seed.

This is a platform probe. Declarative components and the graphical calculator
remain in P3. The [preview roadmap](../../docs/preview_launch_roadmap.md) tracks
the remaining release gates.

## Build and use

Use a native compiler containing the P2 Win64 scalar bridge. An older seed can
build that compiler from its Sotlas sources, but cannot directly link this
example's new imports. `scripts/build_native.ps1` verifies Stage 2/3 identity;
when upgrading across the PE layout change, first generate a transitional
compiler and use it as the seed for a fresh verification directory. Do not
disable the identity check. The new PE's startup section is 4 KiB.

From the repository root on Windows:

```powershell
powershell -NoProfile -File examples/native_window/build.ps1 build/native/sotlas-native.exe build/window-example
./build/window-example/sotlas-window.exe
```

Choose a fresh output directory. A Windows 10/11 x64 interactive desktop is
required; CLI support on Linux or Intel macOS does not imply a GUI port.
The visible example displays an instruction and Omega, appends UTF-16 units,
supports Backspace, repaints after edits and closes with Escape. It has a
128-unit text buffer. The probe is not an IME, grapheme-aware editor or an
accessibility implementation.

## Architecture and lifetime

`runtime/native/window_windows.sotlas` loads Windows system DLLs and resolves
the adapter's fixed API set. It registers a 72-byte `WNDCLASSW` with the OS's
`DefWindowProcW`, creates a window with the 12-argument `CreateWindowExW`, and
polls 48-byte `MSG` records. No Sotlas function is exposed as a Win64 callback.
Queued paint, keyboard, UTF-16 character and mouse-button events reach the
Sotlas application. Synchronous messages use OS default handling; this is not
a complete custom window-procedure implementation.

Drawing uses `BeginPaint`/`EndPaint`, a system background brush, a borrowed stock
font and `TextOutW`. The previous font is restored before ending the paint.
The adapter owns its window, registered class and DLL references; stock GDI
objects are borrowed. `native_window_stop` closes the window, unregisters its
class and releases DLL references. Stop/close are idempotent after success.
Use a single owning thread and one active window. Pointer arguments must refer
to stable, accessible storage for the duration of each synchronous call.

`native_window_next` reports kinds 0 ignored, 1 paint, 2 UTF-16 unit, 3 mouse
down, 4 close and 5 key down. Paint must be completed before polling again.
Mouse coordinates are signed client coordinates. The caller stops on close;
it must not dispatch the same handled input again. Blocking mode waits for a
message when the queue is empty. The default window procedure handles resize
and focus; a repaint reads the current client rectangle.

The platform dependencies are KERNEL32, USER32 and GDI32 supplied by Windows.
The user-facing UI library planned for P3 will hide these raw handles and call
packets behind ordinary Sotlas types and functions.

## Raw Win64 bridge contract

The PE backend adds these reserved declarations with checked machine types:

| Name | Parameters | Result |
|---|---|---|
| `sotlas_windows_load_library` | pointer to NUL-terminated UTF-16 | `u64` module handle |
| `sotlas_windows_get_proc_address` | `u64` module, pointer to NUL-terminated ASCII export | `u64` address |
| `sotlas_windows_call_scalar` | `u64` address, pointer to twelve initialized `u64` slots | `u64` raw return |

The scalar bridge reserves shadow space and aligns the stack, maps the first
four slots to RCX/RDX/R8/R9, and copies eight further slots onto the stack.
It changes no SysV callee-saved register. Every packet must contain twelve
readable slots even when the actual function takes fewer arguments. The caller
must supply a nonzero live function address and match its true Win64 signature.
The compiler checks the bridge declaration, not the dynamically resolved target.

This is an unsafe scalar/pointer FFI boundary. Floating arguments/results,
varargs, aggregate-by-value ABI, Sotlas callbacks and exception unwinding are
outside its contract. Narrow signed/unsigned OS results must be interpreted
at their declared width; unused high return bits are not a language value.
Raw pointer casts and invalid call packets do not acquire lifetime guarantees.
Unknown static foreign imports and non-Windows linking still fail closed.

## Evidence and remaining work

- The native smoke gate creates/resizes/draws/closes a real hidden window,
  checks DPI availability, posts and reads keyboard/Unicode/mouse events,
  and repeats lifecycle checks without growth in measured GDI/USER counts.
- Invalid state, null text/title, oversized text, duplicate create and invalid
  dimensions are rejected. Shutdown and restart succeed.
- A visible local execution rendered Omega and updated text; it exited through
  the keyboard event path. This is a local visual check, not a CI screenshot gate.
- Windows and Linux native compiler sources rebuilt with Stage 2/3 byte identity.
  Both hosts emitted byte-identical PE images for this application.
- Four focused PE regressions passed, including old file/console bridges,
  deterministic images, new signature rejection and unsupported targets. The
  calculator model and twelve CLI scenarios still pass on the changed Windows PE.

The existing Windows Stage 3 gate runs `tests/native_window_gate.py` and the
Sotlas smoke fixture without another bootstrap. Remote CI is pending. Do not
infer certification for per-monitor DPI changes, IME/surrogate editing,
accessibility, device loss or injected OS allocation failures from these tests.
Those remain in P2/P3. General native frontend/ownership parity remains open.

## Platform references

Layouts and calling rules follow Microsoft's [x64 ABI](https://learn.microsoft.com/en-us/cpp/build/x64-calling-convention),
[WNDCLASSW](https://learn.microsoft.com/en-us/windows/win32/api/winuser/ns-winuser-wndclassw),
[MSG](https://learn.microsoft.com/en-us/windows/win32/api/winuser/ns-winuser-msg),
[CreateWindowExW](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-createwindowexw),
[PeekMessageW](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-peekmessagew)
and [BeginPaint](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-beginpaint)
contracts. Windows services are optional platform dependencies of this example.
