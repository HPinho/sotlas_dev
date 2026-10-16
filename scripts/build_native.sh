#!/usr/bin/env bash
set -euo pipefail

# Shell orchestration only. No Python/C bootstrap fallback is permitted here.
if [[ $# -lt 1 || $# -gt 2 ]]; then
    echo 'Usage: bash scripts/build_native.sh NATIVE_SEED [FRESH_OUTPUT_DIRECTORY]' >&2
    exit 1
fi
repository="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
seed="$(cd "$(dirname "$1")" && pwd)/$(basename "$1")"
[[ -x "$seed" ]] || { echo 'An executable native seed is required.' >&2; exit 1; }
case "$(uname -s):$(uname -m)" in
    Linux:x86_64) driver=linux; build=--build ;;
    Darwin:x86_64) driver=darwin; build=--build-mac ;;
    *) echo 'This workflow requires Linux x86-64 or Intel macOS.' >&2; exit 1 ;;
esac
output="${2:-$repository/build/native-selfhost}"
[[ ! -e "$output" ]] || { echo 'Choose a fresh output directory; existing builds are preserved.' >&2; exit 1; }
mkdir -p "$output/src/sotlas/compiler/backend" "$output/src/sotlas/runtime"
output="$(cd "$output" && pwd)"
namespace="$output/src/sotlas/compiler"
for name in token ast lexer parser sema backend/target_ir backend/lower_scalar backend/x86_64_scalar; do
    cp "$repository/bootstrap/sotlas/native_compiler/$name.sotlas" "$namespace/$name.sotlas"
done
cp "$repository/bootstrap/sotlas/native_driver/$driver.sotlas" "$namespace/${driver}_driver.sotlas"
cp "$repository"/runtime/native/*.sotlas "$output/src/sotlas/runtime/"
cp "$repository/examples/native_config.sotlas" "$output/src/native_config.sotlas"
cp "$repository/tests/native/use_after_move.sotlas" "$output/use_after_move.sotlas"
environment="$(command -v env)"
native() { "$environment" PATH="$output/no-host-tools" "$@"; }
entry="$namespace/${driver}_driver.sotlas"
native "$seed" --build-cc "$output/stage2" "$output/src" "$entry"
native "$output/stage2" --build-cc "$output/sotlas-native" "$output/src" "$entry"
cmp "$output/stage2" "$output/sotlas-native"
native "$output/sotlas-native" --self-test
native "$output/sotlas-native" --check-build "$output/src" "$output/src/native_config.sotlas"
native "$output/sotlas-native" "$build" "$output/native-config" "$output/src" "$output/src/native_config.sotlas"
set +e
native "$output/native-config"
status=$?
set -e
[[ $status -eq 42 ]] || { echo "Application returned $status; expected 42." >&2; exit 1; }
cp "$output/native-config" "$output/preserved-image"
for mode in check compile; do
    set +e
    if [[ "$mode" == check ]]; then
        native "$output/sotlas-native" --check "$output/use_after_move.sotlas"
    else
        native "$output/sotlas-native" "$output/use_after_move.sotlas" "$output/native-config"
    fi
    status=$?
    set -e
    [[ $status -eq 6 ]] || { echo "Rejection returned $status; expected 6." >&2; exit 1; }
done
cmp "$output/native-config" "$output/preserved-image"
echo "Native self-build verified. Compiler: $output/sotlas-native"
