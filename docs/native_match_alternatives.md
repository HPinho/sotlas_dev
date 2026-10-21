# Native match alternatives

The Sotlas-written parser and lowering support `|` alternatives in statement and
expression patterns. This extends the existing native scalar and POD payload
contract. It does not add resource payloads or change the optional C11 backend's
supported user programs.

## Syntax and binding contract

- Alternatives work at the root, inside positional variant fields and inside
  named record fields.
- Parentheses group alternatives; `|` has lower precedence than an integer range.
  Parenthesized expressions directly before a range delimiter keep their
  existing constant-bound interpretation, including arithmetic and bitwise bounds.
- Literals, module constants, enum paths, ranges, wildcards, bindings and nested
  positional variants retain their existing types and bounds.
- Every alternative binds exactly the same names with the same declared types.
  Names may occur in different field positions. Missing names and differing
  nominal/scalar types are rejected even when the body does not use the binding.
- Bindings are immutable and local to their source arm and guard. Duplicate names
  inside a single distributed pattern remain invalid.
- The first matching alternative supplies bindings. The source guard runs once.
  A false guard proceeds to the next **source arm**, without retrying another
  alternative in the same arm. Only the selected body runs.

For example, `Value::Left(n,_) | Value::Right(_,n)` shares one body when both
positions declare the same type. A field can use `true | false`, and grouping
supports forms such as `Outer::Wrap((Inner::A | Inner::B))`.

## Lowering, coverage and cleanup

The parser distributes nested choices into decision rows. Rows keep their source
spans and source-arm group, including when an enclosing arm body is cloned.
The lowering reserves a shared guard-failure target for the whole group. This
preserves source semantics for overlapping patterns and different binding orders.

Coverage uses the union of unguarded distributed patterns. Integer prefix coverage
handles overlapping alternatives without enumerating values. Payload coverage
continues to use the symbolic product proof. Guarded alternatives cannot fill a
coverage hole. Existing cross-arm overlap/reachability rules are preserved;
overlap within an alternative group is allowed.

The subject is evaluated and snapshotted once. Existing per-row ownership joins,
record copies, early returns, loop exits and LIFO defer cleanup apply. Parser AST
rewiring snapshots the original arm before changing sibling links; Stage 3
fixtures exercise this through the compiler's actual native memory semantics.

## Bounds and remaining pattern work

A match has at most **64 distributed decision rows**, including ordinary arms.
Nested choices share that budget: seven independent Boolean alternatives require
128 rows and are rejected. Six require 64 rows and are covered by execution tests.
Existing AST node, 32-level pattern, CFG, local/frame and layout bounds still
apply. Cloning an arm body is bounded to 128 AST levels and the shared node buffer.
No limit failure silently drops an alternative or emits a partial artifact.

[Named-field/record destructuring and float patterns](native_match_named_float.md)
are implemented, including alternatives inside named fields. General resource
payloads and ARC/drop integration remain the next runtime block.

## Evidence

- `tests/test_sotlas_native_match_alternatives.py`: scalar and nested choices,
  grouping, independent Boolean-union oracle, overlapping intervals, binding
  identity, guard counters/permutations, one-time subject evaluation, record
  results, exclusive moves, defer, loop exits, syntax and exact row limits.
- `tests/native/match_profile/alternatives.sotlas`: executable Stage 3 fixture;
  paired negatives check mismatched bindings and Cartesian coverage holes.
- `tests/native/match_ranges/cases.txt`: shared Windows/Linux/Intel macOS driver
  gate, including located diagnostics and preservation of existing output.
- [Public example](../examples/native_match_values/main.sotlas).
