# Composed native data values

The native compiler resolves aggregate storage dependencies before emitting code.
Records, payload enums and bounded arrays can now form finite, mixed data models
without requiring declarations to appear in dependency order.

```sotlas
struct Envelope{pub event:Event;}
enum Event{None,Value(Reading),}
struct Reading{pub number:u32;}

static startup:Envelope=Envelope{event:Event::Value(Reading{number:42})};

pub fn main_entry()->u32{
    return match startup.event{Event::None=>0,Event::Value(reading)=>reading.number};
}
```

This delivery covers five connected paths: declaration/layout resolution,
composed runtime values, internal calls and ownership, recursive static data,
and an executable event-pipeline example. The implementation is in Sotlas;
Python remains a test/bootstrap harness, not part of emitted program execution.

## Layout resolution

All enum discriminants are registered before any aggregate fields are laid out.
The compiler then completes ready records and payload enums in bounded passes.
An aggregate becomes ready only when its by-value dependencies have complete
layouts. This handles forward records, forward/nested payload enums, enums in
record fields and chains alternating between records, enums and array elements.

Raw pointer edges retain pointer size and do not require an inline pointee layout.
Direct and indirect cycles through by-value fields or arrays are rejected before
emission. Unknown by-value types, duplicate type names, overflow and capacity exhaustion
also fail closed. The completed graph is cross-checked against field metadata,
preventing a payload enum from silently retaining a provisional U32 field layout.

## Runtime values and the private ABI

- Pointer-free records can contain payload enums, including enum arrays. Payloads
  can contain those records and bounded arrays of other payload enums.
- Constructors, local copies, field replacement, checked indexing and whole-array
  assignment preserve the complete nested storage and nominal payload types.
- Positional, named-record and array patterns can destructure the combined model.
  Guard fallthrough keeps an independent snapshot; guards cannot alter the value
  inspected by a later arm through a copied capture.
- Internal parameters and hidden returns reuse the existing aggregate ABI,
  including stack arguments and conditional/match results. Copies are independent.
- `sole`/`exclusive` transfers and internal `whisper`/`direct` borrows apply when
  the complete graph is POD. Moved-value checks, deferred borrow reservations and
  capture of return values before LIFO cleanup remain in force.

The tagged layout remains private: a U32 tag and aligned, non-overlapping slots
for the declared payload fields. It is not a C union or an exported ABI. Scalar
enums retain their existing U32 conversion contract; this delivery does not
introduce a new nominal scalar-enum ABI.

## Static data

`static` and `static mut` declarations can use payload constructors directly or
inside records/arrays. The compiler serializes the selected tag and active fields
recursively. Padding and inactive payload slots are zero. A wholly zero value
uses BSS; other values use initialized object data. Integer, Boolean and F32/F64
payloads use the existing constant evaluator and target byte representation.

There are no runtime startup constructors for this storage. Runtime function
calls, pointer/resource initializers, string relocations and general aggregate
module constants remain outside the static contract. Global mutability and unsafe
access rules are unchanged. This is independent of C11 initializer support.

## Bounds and remaining work

The shared capacities remain 32 aggregate layouts, 32 enum tables, 256 variant
records and 256 field slots. Each payload enum consumes an aggregate layout and a
tag field. Array elements are bounded to 1–256; the relevant array-value and
payload storage budgets still apply. A payload enum's complete padded storage
must fit within 4096 bytes. Static initialization uses the existing 4096-entry
pool; aggregates consume one entry per byte, including inactive storage.

Recursive copying/serialization, pattern depth, stack/local/CFG budgets and the
existing limits on large record arrays remain checked. Layout dependency passes
do not implement recursive by-value types or resource graphs. Pointer-bearing
payloads, ownership-qualified fields, automatic ARC/drop, general slices, foreign
aggregate signatures and cross-object semantic interfaces remain separate work.
Canonical Stage-0/C11 parity and release-platform certification are separate gates.

## Example and evidence

[The event pipeline](../examples/native_event_pipeline/README.md) uses statically
configured heterogeneous readings, an explicit success/error enum, a report,
ownership transfer and replacement of the input source. It checks successful,
offline and error paths, then exits with status 42 on the native host.

`tests/test_sotlas_native_composed_values.py` covers declaration permutations,
mixed dependency chains, scalar widths, calls/stack returns, ownership, guards,
static object bytes/BSS, exact capacity boundaries and negative cases. The shared
rebuilt Stage 3 fixtures exercise check/compile/run and preserve existing output
on located failures. Existing match, array, ownership, runtime and static-storage
suites remain enabled.


## Local validation

Local validation: 382 native match, array/ABI, ownership, runtime and composed-
value tests pass on each Windows/Linux host, plus 83 shared rebuilt Stage 3 driver
cases per host. All 31 new composed-value tests also pass through the hosted seed
route; another 269 focused parser, semantic, numeric, storage, frontend, bootstrap
and documentation tests pass. Native Stage 2/3 images are identical within each
host. The exact Windows original-module CI gate passes with calculator, GUI and
UI-model checks. Both public examples produce byte-identical objects and ELF/PE/
Mach-O images across hosts; Windows/Linux images run with exit 42 with host tools
absent from PATH. New GitHub CI and actual Intel macOS execution remain pending.

