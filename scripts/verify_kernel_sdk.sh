#!/usr/bin/env bash
set -euo pipefail
[[ $# -ge 2 && $# -le 3 && ( $# -eq 2 || "$3" == --boot ) ]] || { echo 'Usage: bash scripts/verify_kernel_sdk.sh NATIVE_SEED FRESH_OUTPUT [--boot]' >&2; exit 2; }
sdk="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
compiler="$(cd "$(dirname "$1")" && pwd)/$(basename "$1")"
[[ -x "$compiler" && ! -e "$2" ]] || { echo 'Require an executable native seed and fresh output.' >&2; exit 2; }
if [[ "${3:-}" == --boot ]]; then
    [[ "$(uname -s)" == Linux ]] || { echo 'SDK boot certification requires Linux QEMU.' >&2; exit 2; }
    command -v qemu-system-x86_64 >/dev/null; command -v timeout >/dev/null
fi
mkdir -p "$2";output="$(cd "$2" && pwd)"
profiles=(boot interrupts memory heap collections vm foundation)
for profile in "${profiles[@]}"; do
    if [[ "$profile" == boot ]]; then
        if [[ "${3:-}" == --boot ]]; then bash "$sdk/scripts/build_kernel.sh" "$compiler" "$output/$profile" --run
        else bash "$sdk/scripts/build_kernel.sh" "$compiler" "$output/$profile"; fi
    elif [[ "$profile" == foundation && "${3:-}" == --boot ]]; then
        bash "$sdk/scripts/build_kernel.sh" "$compiler" "$output/$profile" --foundation --run
    else
        bash "$sdk/scripts/build_kernel.sh" "$compiler" "$output/$profile" "--$profile"
    fi
done
environment="$(command -v env)"
native() { "$environment" -i PATH="$output/no-host-tools" "$@"; }
image="$output/boot/kernel.elf"
cp "$image" "$output/preserved.elf"
native "$compiler" --link-kernel "$output/boot/kernel.o" "$output/relinked.elf" kernel_main
cmp "$image" "$output/relinked.elf"
reject() {
    local expected="$1";shift
    set +e
    native "$compiler" "$@" >> "$output/rejections.log" 2>&1
    local status=$?
    set -e
    [[ $status -eq $expected ]] || { echo "Kernel rejection returned $status; expected $expected." >&2; exit 1; }
    cmp "$image" "$output/preserved.elf"
}
mkdir -p "$output/invalid"
for case_name in bad_abi hosted; do
    entry="$output/invalid/$case_name.sotlas"
    cp "$sdk/tests/native/kernel_sdk/$case_name.sotlas" "$entry"
    native "$compiler" --check-build "$output/invalid" "$entry"
    native "$compiler" --build-obj "$output/$case_name.o" "$output/invalid" "$entry"
    reject 9 --link-kernel "$output/$case_name.o" "$image" kernel_main
done
reject 9 --link-kernel "$output/boot/kernel.o" "$image" missing_entry
printf 'not an object\n' > "$output/malformed.o"
reject 8 --link-kernel "$output/malformed.o" "$image" kernel_main
digest() { if command -v sha256sum >/dev/null; then sha256sum "$1" | cut -d ' ' -f 1; else shasum -a 256 "$1" | cut -d ' ' -f 1; fi; }
: > "$output/images.sha256"
for profile in "${profiles[@]}"; do printf '%s  %s/kernel.elf\n' "$(digest "$output/$profile/kernel.elf")" "$profile" >> "$output/images.sha256"; done
printf '# Installed kernel SDK verification\n\nSeven kernel profiles checked, compiled and linked with the native seed.\nFour invalid links rejected without changing the valid image. Repeated linking is byte-identical.\n' > "$output/summary.md"
if [[ "${3:-}" == --boot ]]; then printf '\nBasic and foundation profiles booted in Linux QEMU TCG: guest 42 / QEMU 85 and all required serial checkpoints.\n' >> "$output/summary.md"; fi
echo "Installed kernel SDK verified: $output"
