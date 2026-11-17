# Native calculator keyboard editing

The calculator supports insertion and deletion at a keyboard-controlled cursor.
The reusable UI field stores a UTF-8 byte offset in `UiItem.caret`; scene
validation and snapshot publication preserve and validate this position.

## Calculator behavior

| Input | Behavior |
|---|---|
| Arithmetic character or calculator button | Insert at the cursor; advance one ASCII byte |
| Left / Right | Move by one ASCII byte, stopping at the ends |
| Home / End | Move to the beginning/end |
| Backspace | Remove the byte before the cursor |
| Delete | Remove the byte at the cursor |
| Enter or `=` | Evaluate without changing the expression or cursor |
| Clear | Reset expression, cursor and error state |

Navigation and Delete apply while the expression field has focus. Clicking the
field focuses it; keyboard navigation positions the cursor. Clicking buttons
still applies their actions at the current cursor. Tab and button activation
retain their previous behavior. Backspace is handled through the character
event, so the preceding keydown does not delete a second byte. A character `.`
is distinct from the Delete virtual key despite their equal numeric code.

The model stores at most 128 ASCII expression bytes. Inserting into a full
buffer reports error 9 and preserves both bytes and cursor. A successful edit
clears the old evaluator/capacity error and returns the result display to
`Ready`. Moving the cursor alone preserves the previous result/error.
Deletion at a boundary is a no-op. Invalid seeks or characters preserve the
expression and cursor. Division-by-zero and syntax errors remain editable.

`calculator_ui_cursor()` reads the position; `calculator_ui_seek(position)`
rejects positions beyond the expression. `calculator_ui_delete()` removes at
the position. `calculator_ui_key(key)` accepts the navigation/Delete virtual
keys used by the dispatcher. The example owns one model session; the shared
calculator evaluator remains reentrant.

## Reusable field and rendering

`ui_text_field_at(view, id, bounds, label, length, caret)` accepts only a valid
UTF-8 label and a caret at a scalar boundary or the end. A continuation-byte
position is rejected with view error 5 before adding an item. Existing
`ui_text_field` places its caret at the end. Manually constructed `UiItem`
records must initialize `caret`: zero for labels/buttons and a valid byte
position for fields. Recompile applications against the matching runtime
sources; this preview does not promise binary layout compatibility with older
UI records.

The focused Windows field draws a steady vertical caret. Text width is
measured with the selected font, and long input scrolls horizontally by whole
UTF-16 scalars until the caret fits the available field width. Per-item clipping
and paint cleanup still apply. Unfocused fields show the beginning of the text.
Snapshot storage owns its copied labels and caret independently of the model.

`native_window_text_width` measures UTF-16 text inside an active paint session.
It returns zero for empty text, minus one for invalid state/input or OS failure,
and otherwise the measured pixel width. It uses existing drawing resources;
no application font, bitmap, timer or caret handle is allocated.

## Verification and scope

The Sotlas model fixture covers middle insertion, both deletion directions,
empty/end boundaries, navigation, failed seeks, capacity rejection/recovery,
error correction, focus and keydown/character separation. `ui_caret` covers
ASCII/BMP/supplementary scalar boundaries, invalid positions, legacy defaults,
snapshot preservation and invalid-scene rejection. The Windows renderer fixture
adds full-length input, Home/End/middle positions and active/inactive measurement
checks to the existing snapshot, resource-count and shutdown tests. These run
through the installed native SDK, with no Python/C invocation in that path.
Windows additionally posts real keydown messages through the window queue for
Home, Right, Delete and End before dispatching them to the model.

This block is keyboard editing of the bounded calculator plus scalar-boundary
field carets. Selection, clipboard, mouse hit-to-caret placement, undo/redo,
grapheme editing, bidirectional shaping, IME, caret blinking, responsive layout
and non-Windows renderers are separate work. The calculator grammar remains
ASCII even though the generic field accepts validated UTF-8 labels.

Local execution and owner-reported CI certification are recorded in the
[preview roadmap](preview_launch_roadmap.md). The current editing delivery
closes after its complete matrix is reported green.
