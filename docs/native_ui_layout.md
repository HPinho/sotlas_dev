# Native grid layout and calculator resizing

The UI library includes a checked grid primitive. The Windows calculator uses
it to rebuild its controls from the current client rectangle before painting
or handling input. A resize therefore changes hit-testing geometry as well as
the rendered scene, including when a mouse event arrives before repaint.

## Reusable grid

`ui_grid_cell(bounds, columns, rows, gap, column, row)` returns a `UiRect` for
one track intersection. Rows and columns range from 1 to 64, coordinates use
the existing 4096-unit geometry profile, and every cell must have positive
width and height. Invalid bounds, indices, counts, gaps or insufficient space
produce an invalid rectangle. Validation precedes subtraction and division.

The grid distributes leftover width/height units from the leading edge. Cell
sizes differ by at most one unit, adjacent tracks have the requested gap, and
the final track ends exactly at the supplied bounds. The function does not
allocate, mutate layout cursors or retain pointers. This is a uniform grid,
not weighted tracks, spanning or content-based measurement.

## Calculator viewport

`calculator_ui_viewport(view, width, height)` uses Win32 client coordinates:

| Client size | Scene |
|---|---|
| At least 280 × 420 | Title, expression, result and the 4 × 5 button grid; controls fill the available area with fixed margins/gaps |
| Smaller positive size | A noninteractive `Enlarge window to continue` label; clipping applies when even the message cannot fit |
| Either dimension zero | Empty scene |
| Dimension above 4096 | Layout extent clamped to 4096 on that axis |
| Missing item storage or invalid capacity | Rejected without clearing the existing error |

The application owns 32 item slots and separate snapshot label storage. Item
IDs remain stable across sizes. Compact/empty views do not process calculator
clicks, character input or key activation. Expression bytes, cursor, result,
error and saved focus survive compact/empty transitions; normal layout restores
the controls without resetting the model. Escape still closes the application.

The original `calculator_ui_view` remains the reference geometry API used by
existing callers/tests. Both entry points share the same control construction.
The actual application measures its client rectangle for each received event,
then publishes a validated snapshot before painting or hit testing. Win32
window messages and client-coordinate measurements remain platform services;
no C compiler, Python process or external linker participates in this path.

## Evidence and limits

`ui_grid_layout` exercises partition bounds, gaps, coverage, balanced remainders
and the 4096-unit edge across multiple row/column/gap combinations.
`ui_grid_reject` covers zero/oversized counts, bad indices, excessive gaps,
empty tracks, forged bounds and overflow-sized values.

The model fixture covers minimum, odd, reference, larger, maximum and clamped
viewports; button centers/gaps; compact/zero views; disabled hidden controls;
and restoration of focus, expression, cursor and evaluator errors. These tests
run through the installed SDK on the advertised CLI targets.

Windows additionally resizes a hidden native window through small, normal and
larger outer sizes, measures the actual client rectangle, paints published
scenes and posts mouse messages at the new button centers. After one full
resize warm-up, six further four-size cycles require stable GDI/USER counts
and unchanged model data. Existing frame/resource/cleanup checks remain.
The portable zero-sized layout test does not certify an OS minimize/restore
sequence. CI certification is recorded in the preview roadmap.

This block covers adaptive calculator geometry using reusable uniform grids.
Per-monitor DPI transitions, scalable fonts, weighted/flex layouts, custom
widgets, accessibility and non-Windows renderers remain separate work. Text
uses the existing system font and field caret-scrolling contract.
