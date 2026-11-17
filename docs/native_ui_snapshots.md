# Native UI scene publication

The fixed-layout UI can publish a validated snapshot whose label bytes reside
in caller-owned scene storage. The calculator keeps model/draft storage separate
from its published item/text buffers; modifying the model no longer changes the
currently published scene through borrowed labels.

## Contract

`ui_view_valid` validates the whole bounded scene: storage shape/alignment,
count/capacity, unique nonzero IDs, component kinds, geometry and UTF-8 labels.
Hit testing, keyboard activation and Windows painting reject invalid scenes.
The renderer validates before acquiring a paint session.

`ui_snapshot(source, destination, items, capacity, labels, label_capacity)`
validates the complete source and destination before writing. On success it
copies items and all label bytes, redirects copied label pointers into the
destination text storage, and publishes count, focus and clean error metadata.
No NUL terminators are added; item lengths remain UTF-8 byte counts.

| Condition | Behavior |
|---|---|
| Items | 1–64 slots; at most 64 published components |
| Text storage | 1–8192 bytes; each label remains limited to 128 bytes |
| Exact capacity | Accepted, including 64 labels of 128 bytes each |
| Empty scene/empty label | Accepted with valid destination storage |
| Invalid source or insufficient capacity | Returns false; destination metadata, items and text remain unchanged |
| Destination regions overlap each other | Rejected before writes |
| Source view/items/labels overlap any destination region | Rejected before writes |
| Successful source mutation after publication | Published items/text stay independent |
| Repair and retry after rejection | Allowed; no sticky error is introduced in the destination |

The API allocates nothing. The application owns storage and keeps it live until
the scene is no longer used. Overwriting that storage replaces the scene; old
copies of its pointers must not be retained across replacement. Source input
must remain stable for both validation and copying. A valid pointer shape does
not prove accessibility, lifetime or exclusivity. Fabricated/dangling pointers
and concurrent mutation remain outside this single-threaded profile.

These are runtime checks and explicit storage responsibilities, not a claim of
general compiler-enforced UI borrowing or automatic ARC. No OS resources are
acquired by scene publication. The Windows application closes its window and
paint resources on a failed build/publication or rendering operation.

## Evidence and closure

The Sotlas contracts `ui_snapshot_values`, `ui_snapshot_reject` and
`ui_invalid_views` run through the native contract runner, including the
installed SDK gate. They test maximum and exact capacities, empty scenes,
Unicode, independent copies, duplicate IDs, malformed labels, pointer range
overflow, invalid geometry/kinds/counts, aliasing, unchanged output and retry.

The UI model and Unicode fixtures execute from the installed SDK on every CLI
target. Windows additionally compiles the graphical calculator and executes
the hidden-window renderer fixture: twenty snapshot-backed frames, resource
counts, failed publication followed by painting the previous scene, rejected
painting, scope cleanup and three shutdown/restart cycles. The generated
application is `ui-main.exe` in the SDK verification output. These checks do not
open a visible test window.

Local Windows and Linux/WSL execution is recorded in the preview roadmap.
The owner reported the full matrix green for `c97c936` on 2026-11-16, closing
the bounded scene-storage/publication block, including Intel macOS. Subsequent
[keyboard editing](native_ui_editing.md) is a separate delivery. General responsive layout, selection editing, IME,
accessibility, multiple windows, GPU rendering, Linux/macOS renderers and full
language ownership parity are separate blocks.
