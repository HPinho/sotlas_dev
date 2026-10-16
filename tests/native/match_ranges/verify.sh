#!/usr/bin/env bash
set -euo pipefail
[[ $# -eq 2 ]] || { echo 'Usage: verify.sh NATIVE_COMPILER OUTPUT_DIRECTORY' >&2; exit 1; }
compiler="$(cd "$(dirname "$1")" && pwd)/$(basename "$1")"
fixtures="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
mkdir -p "$2"
output="$(cd "$2" && pwd)"
environment="$(command -v env)"
image="$output/match-ranges"
invoke() {
    local expected="$1"; shift
    local status=0
    "$environment" PATH="$output/no-host-tools" "$@" >"$output/stdout" 2>"$output/stderr" || status=$?
    if [[ $status -ne $expected ]]; then
        cat "$output/stderr" >&2
        echo "Exit $status; expected $expected: $*" >&2
        exit 1
    fi
}
while IFS='|' read -r filename expected message || [[ -n "$filename" ]]; do
    [[ -n "$filename" ]] || continue
    message="${message%$'\r'}"
    source="$fixtures/$filename"
    if [[ "$expected" == 42 ]]; then
        invoke 0 "$compiler" --check "$source"
        invoke 0 "$compiler" "$source" "$image"
        invoke 42 "$image"
    else
        cp "$image" "$output/preserved"
        invoke "$expected" "$compiler" --check "$source"
        grep -F -- "$message" "$output/stderr" >/dev/null
        grep -F '.sotlas:' "$output/stderr" >/dev/null
        invoke "$expected" "$compiler" "$source" "$image"
        grep -F -- "$message" "$output/stderr" >/dev/null
        grep -F '.sotlas:' "$output/stderr" >/dev/null
        cmp "$image" "$output/preserved"
    fi
    echo "Passed: $filename"
done <"$fixtures/cases.txt"
