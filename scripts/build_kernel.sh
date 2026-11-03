#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 1 || $# -gt 3 || ( $# -eq 3 && "$3" != --run ) ]]; then
    echo 'Usage: bash scripts/build_kernel.sh NATIVE_COMPILER [FRESH_OUTPUT_DIRECTORY] [--run]' >&2
    exit 1
fi
repository="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
compiler="$(cd "$(dirname "$1")" && pwd)/$(basename "$1")"
[[ -x "$compiler" ]] || { echo 'An executable native compiler is required.' >&2; exit 1; }
output="${2:-$repository/build/kernel-boot}"
[[ ! -e "$output" ]] || { echo 'Choose a fresh output directory; existing builds are preserved.' >&2; exit 1; }
qemu=''
if [[ ${3:-} == --run ]]; then
    qemu="$(command -v qemu-system-x86_64)"
    timeout_tool="$(command -v timeout)"
    [[ -n "$qemu" && -n "$timeout_tool" ]] || { echo 'QEMU x86-64 and timeout are required for --run.' >&2; exit 1; }
fi
mkdir -p "$output/src/sotlas/runtime"
output="$(cd "$output" && pwd)"
cp "$repository/examples/native_kernel_boot/main.sotlas" "$output/src/main.sotlas"
cp "$repository/runtime/native/kernel_x86.sotlas" "$output/src/sotlas/runtime/kernel_x86.sotlas"
environment="$(command -v env)"
native() { "$environment" PATH="$output/no-host-tools" "$@"; }
native "$compiler" --check-build "$output/src" "$output/src/main.sotlas"
native "$compiler" --build-obj "$output/kernel.o" "$output/src" "$output/src/main.sotlas"
native "$compiler" --link-kernel "$output/kernel.o" "$output/kernel.elf" kernel_main
echo "Kernel image: $output/kernel.elf"
if [[ -n "$qemu" ]]; then
    set +e
    # Do not use -no-shutdown: QEMU 10.2 implements debug-exit as shutdown.
    "$timeout_tool" 15s "$qemu" -machine pc -accel tcg -cpu qemu64 -m 64M \
        -kernel "$output/kernel.elf" -display none -serial stdio -monitor none \
        -no-reboot -device isa-debug-exit,iobase=0xf4,iosize=0x04 \
        > "$output/serial.log" 2>&1
    status=$?
    set -e
    cat "$output/serial.log"
    [[ $status -eq 85 ]] || { echo "Kernel boot failed: QEMU exit $status, expected 85." >&2; exit 1; }
    grep -Fxq 'SOTLAS: kernel entered' "$output/serial.log"
    grep -Fxq 'SOTLAS: memory, stack, data, SSE OK' "$output/serial.log"
    grep -Fxq 'SOTLAS: VGA OK' "$output/serial.log"
    echo 'Kernel boot verified: Multiboot handoff, native x86-64, BSS/data, stack, SSE and VGA.'
fi
