#!/usr/bin/env bash
set -euo pipefail
[[ $# -eq 2 ]] || { echo 'Usage: build.sh NATIVE_COMPILER FRESH_OUTPUT_DIRECTORY' >&2; exit 1; }
compiler="$(cd "$(dirname "$1")" && pwd)/$(basename "$1")"
[[ ! -e "$2" ]] || { echo 'Choose a fresh output directory.' >&2; exit 1; }
example="$(cd "$(dirname "$0")" && pwd)"
repository="$(cd "$example/../.." && pwd)"
case "$(uname -s)" in
    Linux) platform=linux; build=--build ;;
    Darwin) platform=darwin; build=--build-mac ;;
    *) echo 'Linux or Intel macOS required.' >&2; exit 1 ;;
esac
mkdir -p "$2/src/calculator" "$2/src/sotlas/runtime"
output="$(cd "$2" && pwd)"
cp "$example/src/calculator/main.sotlas" "$output/src/calculator/main.sotlas"
cp "$example/platform/$platform.sotlas" "$output/src/calculator/platform.sotlas"
cp "$repository/runtime/native/calculator.sotlas" "$output/src/sotlas/runtime/calculator.sotlas"
env PATH="$output/no-host-tools" "$compiler" --check-build "$output/src" "$output/src/calculator/main.sotlas"
env PATH="$output/no-host-tools" "$compiler" "$build" "$output/calculator" "$output/src" "$output/src/calculator/main.sotlas"
echo "Calculator: $output/calculator"
