#!/usr/bin/env bash
set -euo pipefail
[[ $# -eq 2 ]] || { echo 'Usage: verify.sh NATIVE_COMPILER OUTPUT_DIRECTORY' >&2; exit 1; }
compiler="$(cd "$(dirname "$1")" && pwd)/$(basename "$1")"
mkdir -p "$2"
output="$(cd "$2" && pwd)"
environment="$(command -v env)"
image="$output/large-program"
case "$(uname -s)" in
    Linux) build=--build ;;
    Darwin) build=--build-mac ;;
    *) echo 'Linux or Intel macOS required.' >&2; exit 1 ;;
esac

# Generate source fixtures; the native compiler owns all compilation stages.
for limit in 1024 1025; do
    mkdir -p "$output/functions-$limit/app"
    {
        echo 'module app::main; import app::library::*; pub fn main_entry()->u32{let mut total:u32=0;'
        for ((index=0;index<1023;index++)); do printf 'total += f%04d(1);\n' "$index"; done
        echo 'if total!=523776 || f0511(1)!=512 || f0512(1)!=513 || f1022(1)!=1023{return 1;}return 42;}'
    } >"$output/functions-$limit/app/main.sotlas"
    {
        echo 'module app::library;'
        for ((index=0;index<1023;index++)); do printf 'pub fn f%04d(value:u32)->u32{return value+%d;}\n' "$index" "$index"; done
        if [[ "$limit" == 1025 ]]; then echo 'pub fn extra()->u32{return 0;}'; fi
    } >"$output/functions-$limit/app/library.sotlas"
done
for limit in 2048 2049; do
    {
        echo 'module strings; fn digit(data:*const u8)->u32{return unsafe{*(data+4)} as u32;}'
        for ((chunk=0;chunk<32;chunk++)); do
            printf 'fn chunk%d()->u32{let mut total:u32=0;\n' "$chunk"
            for ((offset=0;offset<64;offset++)); do printf 'total += digit("s%04d");\n' "$((chunk*64+offset))"; done
            echo 'return total;}'
        done
        echo 'pub fn main_entry()->u32{let mut total:u32=0;'
        for ((chunk=0;chunk<32;chunk++)); do printf 'total += chunk%d();\n' "$chunk"; done
        if [[ "$limit" == 2049 ]]; then echo 'total += digit("s2048");'; fi
        echo 'if total!=107512{return 1;}return 42;}'
    } >"$output/strings-$limit.sotlas"
done
for length in 65535 65536; do
    {
        printf 'module bytes; pub fn main_entry()->u32{let data:*const u8="'
        for ((index=0;index<length;index++)); do printf a; done
        echo '";if unsafe{*data}!=97{return 1;}return 42;}'
    } >"$output/bytes-$length.sotlas"
done
invoke() {
    local expected="$1"; shift
    local status=0
    "$environment" PATH="$output/no-host-tools" "$compiler" "$@" >"$output/stdout" 2>"$output/stderr" || status=$?
    if [[ $status -ne $expected ]]; then cat "$output/stderr" >&2; echo "Exit $status; expected $expected: $*" >&2; exit 1; fi
}
verify() {
    local source="$1" expected="$2" root="${3:-}" status=0
    if [[ "$expected" != 0 ]]; then cp "$image" "$output/preserved"; fi
    if [[ -n "$root" ]]; then
        invoke "$expected" --check-build "$root" "$source"
        invoke "$expected" "$build" "$image" "$root" "$source"
    else
        invoke "$expected" --check "$source"
        invoke "$expected" "$source" "$image"
    fi
    if [[ "$expected" == 0 ]]; then
        "$environment" PATH="$output/no-host-tools" "$image" || status=$?
        [[ $status == 42 ]] || { echo "Program returned $status; expected 42." >&2; exit 1; }
    else
        cmp "$image" "$output/preserved"
    fi
    echo "Passed: $source (compiler exit $expected)"
}
verify "$output/functions-1024/app/main.sotlas" 0 "$output/functions-1024"
verify "$output/functions-1025/app/main.sotlas" 8 "$output/functions-1025"
verify "$output/strings-2048.sotlas" 0
verify "$output/strings-2049.sotlas" 7
verify "$output/bytes-65535.sotlas" 0
verify "$output/bytes-65536.sotlas" 7
