# Native optional values and checked lookup

Concrete POD enums with exactly `Some(T)` and unit `None` support postfix `?`:

```sotlas
enum Maybe { None, Some(u32) }

fn increment(input: Maybe) -> Maybe {
    let value: u32 = input?;
    return Maybe::Some(value + 1);
}
```

## Language contract

The operand is evaluated once and snapshotted. `Some` yields its payload;
`None` copies the complete nominal enum to the enclosing return destination
before active lexical defers execute in reverse order. Later operands and
arguments do not execute. The enclosing function must return the same plain
nominal enum. Both variant orders and the existing explicit-tag syntax work;
success is selected by the actual `Some` discriminant, not by a zero sentinel.

Payloads follow the current POD scalar, record, nested-enum and bounded-array
rules. Array success values can feed the native `for` snapshot path. Stored,
call, conditional and compatible match operands retain existing inference rules.
A direct `Maybe::None?` is a valid early return inside the matching result type.

Mixed schemas such as `Some/Err` or `Ok/None`, extra variants, non-unit None,
missing/multiple Some payloads, nominal return mismatches, qualified result
bindings and pointer/resource payloads fail closed. `?` remains forbidden inside
defer. Unsafe fabrication of an invalid tag is outside the contract. This does
not add generic `Option<T>`, implicit conversion to Result, nullable pointers,
resource-bearing options, automatic ARC/drop or foreign aggregate ABI support.
The optional legacy C11 emitter retains its narrower supported Result forms.

## Native library

`runtime/native/optional.sotlas` imports the existing text and numeric-result
modules and adds these concrete types:

- `NativeIndexOption { None, Some(usize) }` carries an index without reserving
  any usize value as an absence sentinel.
- `NativeIndexResult { status:u32, value:NativeIndexOption,
  error:NativeNumericError }` separates checked lookup failure from absence.

| API | Contract |
| --- | --- |
| `native_index_some/none` | Construct a concrete optional index |
| `native_index_or` | Return the present index or caller-selected fallback |
| `native_index_add` | Propagate None; return None on usize overflow; otherwise Some(sum) |
| `native_text_find_option` | First byte offset, successful None when not found, error on invalid input shape |
| `native_text_find_option_from` | Search from an inclusive byte offset and return an offset in the original slice |
| `native_index_result/error` | Construct success or kind-7 invalid-shape/range results |

Lookup status zero means the search was valid; its value may still be None.
Invalid source/needle shape or `start > length` returns status/error kind 7,
None and the requested start offset. Position zero is a valid Some. An empty
needle returns Some(start), including at the end of the input. A valid longer
needle or missing byte pattern returns successful None. Embedded NUL bytes
remain part of the search; offsets are bytes, not Unicode scalar indices.

The search implementation reuses `native_text_find` and `native_text_sub`.
There is no parallel search algorithm or allocator. Borrowed ranges must retain
readable caller-owned storage for the call. Shape/null/address checks do not
prove pointer provenance or accessible memory; no borrowed pointer escapes in
the returned index. A search position is not necessarily a readable byte when
it equals the length for an empty needle.

## Example and gates

The [configuration lookup example](../examples/native_optional/main.sotlas)
finds the separator in `answer=42`, advances a present index, propagates a
missing separator through None, distinguishes invalid input and verifies cleanup
on both optional paths. It parses 42 using the existing checked numeric API.
Native rebuild gates include imported check/build, execution and ELF/PE/Mach-O
emission for this source.

`tests/test_sotlas_native_optional.py` covers schema/tag orders, direct None,
snapshots, cleanup, scalar/record/array payloads, argument evaluation and nominal/
ownership rejection. Library cases cover zero/max indices, overflow, missing vs
invalid, start/end bounds, empty needles, embedded zero bytes and checked record
propagation carrying an optional value. Full CI certification remains pending.

### Local validation

The candidate passed 146 focused native tests on each of Windows and Linux,
including existing Result propagation, numeric results, array iteration and
array payload/ABI cases. The imported example passed check, object generation,
direct build and execution with exit 42 on both hosts with host tools absent
from PATH. Both producers emitted byte-identical object, ELF, PE and Mach-O
artifacts. Mach-O emission was checked locally; execution awaits macOS CI.

Original-source rebuilds produced identical Stage 2 and Stage 3 compilers on
each host. Stage 3 SHA-256 values:

- Windows: `703a0c69158a823ab475daf91a79185568fb6443e55379df40ddf04425f8cf6c`
- Linux: `e9f299172c885d29687df819e6d221e2db11b7b9e067d40c88bf0ff8cfcb38a7`

An additional 124 focused checks passed for structured CFG, AST self-hosting,
Target IR, phase gates, examples and public snippet inventory. These checks
validate this concrete native profile, not full frontend or ownership parity.
