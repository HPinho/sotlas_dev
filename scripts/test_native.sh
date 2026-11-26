#!/usr/bin/env bash
# Compile original .sotlas contracts and run them with a native seed only.
set -euo pipefail
if [[ $# -lt 2 || $# -gt 3 ]]; then
    echo 'Usage: bash scripts/test_native.sh NATIVE_COMPILER FRESH_OUTPUT [MANIFEST]' >&2
    exit 2
fi
repository="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
compiler="$(cd "$(dirname "$1")" && pwd)/$(basename "$1")"
manifest="${3:-$repository/tests/native/contracts/manifest.txt}"
suite="$(cd "$(dirname "$manifest")" && pwd)"
manifest="$suite/$(basename "$manifest")"
[[ -x "$compiler" && -f "$manifest" && ! -e "$2" ]] || { echo 'Require a native compiler, manifest and fresh output.' >&2; exit 2; }
case "$(uname -s):$(uname -m)" in
    Linux:x86_64) build=--build ;;
    Darwin:x86_64) build=--build-mac ;;
    *) echo 'Native tests require Linux x86-64 or Intel macOS.' >&2; exit 2 ;;
esac
mkdir -p "$2/src/sotlas/runtime" "$2/logs"
output="$(cd "$2" && pwd)"
cp "$repository"/runtime/native/*.sotlas "$output/src/sotlas/runtime/"
environment="$(command -v env)"
ulimit -c 0
native() { "$environment" -i PATH="$output/no-host-tools" "$@"; }
total=0; failures=0; seen='|'
: > "$output/cases.xml"
printf '# Sotlas native contracts\n\n| Case | Result |\n| --- | --- |\n' > "$output/summary.md"
while read -r mode name source extra; do
    [[ -z "${mode:-}" || "$mode" == \#* ]] && continue
    [[ -z "${extra:-}" && "$name" =~ ^[a-z0-9_]+$ && "$source" == "cases/$name.sotlas" ]] || { echo 'Invalid native test manifest row.' >&2; exit 2; }
    case "$seen" in *"|$name|"*) echo "Duplicate test: $name" >&2; exit 2 ;; esac
    seen="$seen$name|"
    case "$mode" in pass|reject|syntax|fault|trap) ;; *) echo "Unknown test mode: $mode" >&2; exit 2 ;; esac
    [[ -f "$suite/$source" ]] || { echo "Missing Sotlas test: $source" >&2; exit 2; }
    cp "$suite/$source" "$output/src/$name.sotlas"
    entry="$output/src/$name.sotlas"; image="$output/$name"
    log="$output/logs/$name.log"; failed=''; total=$((total+1))
    set +e
    native "$compiler" --check-build "$output/src" "$entry" > "$log" 2>&1
    checked=$?
    set -e
    if [[ "$mode" == reject || "$mode" == syntax ]]; then
        case "$mode:$checked" in
            syntax:5|reject:6|reject:7) ;;
            *) failed="check returned $checked; expected $mode";;
        esac
        cp "$compiler" "$image"
    elif [[ $checked -ne 0 ]]; then failed="check returned $checked"; fi
    if [[ -z "$failed" ]]; then
        set +e
        native "$compiler" "$build" "$image" "$output/src" "$entry" >> "$log" 2>&1
        compiled=$?
        set -e
        if [[ "$mode" == reject || "$mode" == syntax ]]; then
            case "$mode:$compiled" in
                syntax:5|reject:6|reject:7)
                    if ! cmp -s "$compiler" "$image"; then failed='rejected build changed existing output'; fi;;
                *) failed="build returned $compiled; expected $mode";;
            esac
        elif [[ $compiled -ne 0 ]]; then failed="build returned $compiled"
        else
            set +e
            native "$image" >> "$log" 2>&1
            actual=$?
            set -e
            case "$mode" in
                fault) expected=136 ;;
                trap) expected=132 ;;
                *) expected=0 ;;
            esac
            if [[ $actual -ne $expected ]]; then failed="execution returned $actual; expected $expected"; fi
        fi
    fi
    printf '<testcase classname="Sotlas.Native" name="%s" file="tests/native/contracts/%s">' "$name" "$source" >> "$output/cases.xml"
    if [[ -n "$failed" ]]; then
        failures=$((failures+1))
        printf '<failure message="%s"/>' "$failed" >> "$output/cases.xml"
        printf '::error file=tests/native/contracts/%s,title=Sotlas %s::%s\n' "$source" "$name" "$failed"
        cat "$log"
        printf '| `%s` | FAIL: %s |\n' "$name" "$failed" >> "$output/summary.md"
    else
        printf 'PASS %s (%s)\n' "$name" "$mode"
        printf '| `%s` | PASS (%s) |\n' "$name" "$mode" >> "$output/summary.md"
    fi
    printf '</testcase>\n' >> "$output/cases.xml"
done < "$manifest"
[[ $total -gt 0 ]] || { echo 'An empty Sotlas suite cannot pass.' >&2; exit 2; }
{
    printf '<?xml version="1.0" encoding="UTF-8"?>\n<testsuite name="Sotlas native contracts" tests="%s" failures="%s">\n' "$total" "$failures"
    cat "$output/cases.xml"
    printf '</testsuite>\n'
} > "$output/junit.xml"
printf '\n**%s Sotlas tests, %s failures.** Compiler and programs ran with host tools absent from PATH.\n' "$total" "$failures" >> "$output/summary.md"
if [[ -n "${GITHUB_STEP_SUMMARY:-}" ]]; then cat "$output/summary.md" >> "$GITHUB_STEP_SUMMARY"; fi
printf 'Sotlas tests: %s total, %s failures. Reports: %s\n' "$total" "$failures" "$output"
[[ $failures -eq 0 ]]
