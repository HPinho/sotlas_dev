#!/usr/bin/env bash
set -euo pipefail
[[ $# -ge 1 && $# -le 2 && ( $# -eq 1 || "$2" == --rebuild ) ]] || { echo 'Usage: bash scripts/verify_sdk.sh FRESH_OUTPUT_DIRECTORY [--rebuild]' >&2; exit 2; }
sdk="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
case "$(uname -s):$(uname -m)" in
    Linux:x86_64) platform=linux; build=--build ;;
    Darwin:x86_64) platform=darwin; build=--build-mac ;;
    *) echo 'Unsupported SDK host.' >&2; exit 2 ;;
esac
[[ ! -e "$1" ]] || { echo 'Choose a fresh verification output directory.' >&2; exit 2; }
mkdir -p "$1/src/sotlas/runtime" "$1/src/calculator" "$1/src/configuration" "$1/src/calculator_app"
output="$(cd "$1" && pwd)"
cp "$sdk"/runtime/native/*.sotlas "$output/src/sotlas/runtime/"
cp "$sdk/examples/calculator/src/calculator/main.sotlas" "$output/src/calculator/"
cp "$sdk/examples/calculator/platform/$platform.sotlas" "$output/src/calculator/platform.sotlas"
cp "$sdk/examples/native_config_map/main.sotlas" "$output/src/configuration/main.sotlas"
mkdir -p "$output/src/tensor_rows"
cp "$sdk/examples/native_tensor_rows/main.sotlas" "$output/src/tensor_rows/main.sotlas"
mkdir -p "$output/src/csv_app"
cp "$sdk/examples/native_csv/main.sotlas" "$output/src/csv_app/main.sotlas"
cp "$sdk/tests/native/calculator/model.sotlas" "$output/src/calculator_model.sotlas"
cp "$sdk"/examples/graphical_calculator/src/calculator_app/*.sotlas "$output/src/calculator_app/"
cp "$sdk/tests/native/ui/model.sotlas" "$output/src/calculator_app/tests.sotlas"
cp "$sdk/tests/native/ui/unicode.sotlas" "$output/src/calculator_app/unicode_tests.sotlas"
environment="$(command -v env)"
native() { "$environment" -i PATH="$output/no-host-tools" "$@"; }
compiler="$sdk/bin/sotlas-native"
native "$compiler" --self-test
for name in calculator configuration tensor_rows csv_app; do
    native "$compiler" --check-build "$output/src" "$output/src/$name/main.sotlas"
    native "$compiler" "$build" "$output/$name" "$output/src" "$output/src/$name/main.sotlas"
done
printf '6*7\n' | native "$output/calculator" > "$output/calculator.out"
printf '42\n' > "$output/expected.out"
cmp "$output/expected.out" "$output/calculator.out"
set +e
printf '1/0\n42\n' | native "$output/calculator" > "$output/calculator-error.out"
status=$?
set -e
[[ $status -eq 2 ]] || { echo 'Calculator did not report the input error.' >&2; exit 1; }
printf 'error: division by zero at byte 1\n42\n' > "$output/expected-error.out"
cmp "$output/expected-error.out" "$output/calculator-error.out"
native "$compiler" "$build" "$output/model" "$output/src" "$output/src/calculator_model.sotlas"
for program in configuration model; do
    set +e
    native "$output/$program"
    status=$?
    set -e
    [[ $status -eq 42 ]] || { echo "$program returned $status; expected 42." >&2; exit 1; }
done
native "$output/tensor_rows"
native "$output/csv_app"
for name in tests unicode_tests; do
    native "$compiler" --check-build "$output/src" "$output/src/calculator_app/$name.sotlas"
    native "$compiler" "$build" "$output/ui-$name" "$output/src" "$output/src/calculator_app/$name.sotlas"
    set +e
    native "$output/ui-$name"
    status=$?
    set -e
    [[ $status -eq 42 ]] || { echo "UI $name returned $status; expected 42." >&2; exit 1; }
done
bash "$sdk/scripts/test_native.sh" "$compiler" "$output/contracts"
if [[ "${2:-}" == --rebuild ]]; then
    bash "$sdk/scripts/build_native.sh" "$compiler" "$output/rebuild"
fi
printf '# Installed native SDK verification\n\nCalculator, error recovery, JSON configuration, CSV round trip, tensor row preprocessing, UI model/Unicode and installed Sotlas contracts passed.\n' > "$output/summary.md"
if [[ "${2:-}" == --rebuild ]]; then printf '\nOriginal compiler sources rebuilt with Stage 2/3 byte identity.\n' >> "$output/summary.md"; fi
echo "Installed SDK verified: $output"
