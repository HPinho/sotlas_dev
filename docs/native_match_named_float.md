# Named record and float patterns

Named fields and float patterns complete the pattern forms in the current native
match release profile. The parser, semantic checks, coverage proof and lowering
are written in Sotlas. Resource-bearing payloads and their cleanup runtime are
the next block.

## Named fields

Records use `Point { x: pattern, y: pattern }`. Fields may appear in any order.
`Point { x, .. }` binds `x` and ignores the remaining fields. Without `..`, every
declared field must occur exactly once. The rest marker is unique and last.
Unknown fields, duplicates, incorrect record identities and repeated binding
names are rejected. Shorthand binds the field name even when a module constant
has that name; explicit `x: KEY` retains normal constant-pattern resolution.

Records can be match subjects and appear inside positional enum payloads or
other record patterns. Grouping and `|` alternatives work at each level. Every
alternative retains the same binding-name/type contract; inline array types are
compared by element identity and count, independently of spelling whitespace.
Enum variants retain their existing positional declarations and constructor ABI.

The subject is evaluated and copied once. Scalar, enum and nested record captures
are immutable arm locals. Inline scalar/record arrays can be captured and indexed
through the native array-local contract. Captures receive independent storage;
mutating a captured array through an explicit unsafe pointer in a false guard
does not change the snapshot tested by later arms. General array parameters and
returns still require their separate ABI contract.

Named field constraints participate in the same symbolic Cartesian coverage proof
as positional fields. Declaration order and source pattern order do not change
the physical field identity. A full set of Boolean field marginals does not hide
holes between combinations. Guards contribute no coverage. Returns, exclusive
POD results, ordered fallthrough and LIFO defer use the existing match lowering.

## Float comparisons

F32 and F64 subjects and fields accept numeric literals, typed module constants
and open, closed or half-open numeric ranges. Constants use the native numeric
literal/evaluation contract and are rounded to the selected width before overlap
checks. Typed F64 constants are not silently treated as F32 constants.

- Equality and range comparisons use IEEE numeric comparisons.
- Positive and negative zero match the same equality pattern. Their two bit
  representations form one numeric boundary for inclusive/exclusive endpoints.
- A half-open upper endpoint uses the previous representable value, preserving
  exact F32/F64 boundaries without decimal approximations.
- Open endpoints include the corresponding infinity. NaN matches neither a
  numeric equality pattern nor an ordered interval, including `..`.
- Numeric intervals alone cannot prove complete float coverage. A wildcard or
  capture must cover NaNs and remaining values. A guard such as `n if n != n`
  can select NaNs, with an ordinary fallback for exhaustiveness.
- Overlapping unguarded source arms retain the existing rejection policy.
  Overlap within one `|` group is allowed, and its guard runs once.

Float field coverage partitions monotonic IEEE keys at pattern boundaries. It
includes the otherwise uncovered NaN cells and both signed-zero representations;
it does not enumerate floating-point values. NaN constants are not value patterns.
Invalid/dynamic float bounds and empty/reversed intervals have located errors.

## Profile bounds

The 64 distributed-row, 32 pattern-level and existing AST/CFG/local/frame limits
remain in force. Record subjects are pointer-free POD with padded storage at most
4096 bytes, matching the proof's byte-offset key space and payload layout bound.
Ownership-qualified fields and general resource payloads remain rejected.

The native drivers now collect fewer than 524288 lexer tokens; AST and IR limits
remain separate. This accommodates the larger compiler sources, particularly the
Windows driver. A seed with the earlier 262144-token buffer needs a native seed
refresh before rebuilding the larger source tree. Local validation refreshed that
buffer using the previous Sotlas sources and seed, then rebuilt current Stage 2/3;
the native chain introduced no C/Python step.

## Evidence

- `tests/test_sotlas_native_match_named_float.py`: named fields, rest/shorthand,
  nested records, 20-level bindings, record/array copies, guard ordering, aliases,
  nominal types, both float widths, rounding, signed zeros, infinities, NaNs,
  interval boundaries, coverage and explicit rejections.
- All 512 unions of Boolean record rectangles are checked against an independent
  set oracle, with field order reversed in the generated source.
- `tests/native/match_profile/named_float.sotlas` and paired negatives run through
  the shared rebuilt Stage 3 driver gate, including artifact preservation.
- [Executable public example](../examples/native_match_values/main.sotlas).

The optional C11 user-program backend and full canonical frontend parity keep
their separate gates. Actual Intel macOS execution is certified by its CI runner.

## Local validation

Local validation: 160 match tests and 45 shared Stage 3 cases pass on each
Windows/Linux host, alongside 335 focused frontend, numeric, docs and hosted
bootstrap checks. The exact Windows original-module Stage 2/3 CI test also passes,
including calculator, GUI and UI-model gates. Native Stage 2/3 images are identical
within each host. The example object and ELF/PE/Mach-O outputs match across hosts;
Windows/Linux images execute with exit 42. GitHub CI and Intel macOS execution
remain pending certification gates.
