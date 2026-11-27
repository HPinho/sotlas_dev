# Native discern statements

Use `discern value { ... }` to dispatch on an enum. Each arm has the form
`case pattern => { ... }`, with an optional `case` prefix. Write a variant
as `.Ready`, `Ready` or `Status::Ready`. Payload patterns can bind fields,
as in `case .Data(code) => { ... }`. Use qualified variant names for enum
patterns nested inside payload fields.

The selector is evaluated once. The compiler verifies that the unguarded
patterns cover every variant and payload value. A final `case else` or `_`
covers the remaining values. Guards and alternatives use the same checking
and lowering as native `match`.

The [native contract suite](../tests/native/contracts/manifest.txt) exercises
successful dispatch and rejects incomplete coverage, foreign and unknown
variants, and non-enum selectors.
