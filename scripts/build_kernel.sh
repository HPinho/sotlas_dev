#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 1 || $# -gt 4 ]]; then
    echo 'Usage: bash scripts/build_kernel.sh NATIVE_COMPILER [FRESH_OUTPUT_DIRECTORY] [--run] [--interrupts|--memory|--heap|--collections]' >&2
    exit 1
fi
run=false
interrupts=false
memory=false
heap=false
collections=false
for option in "${@:3}"; do
    case "$option" in
        --run) [[ $run == false ]] || exit 1; run=true ;;
        --interrupts) [[ $interrupts == false ]] || exit 1; interrupts=true ;;
        --memory) [[ $memory == false ]] || exit 1; memory=true ;;
        --heap) [[ $heap == false ]] || exit 1; heap=true ;;
        --collections) [[ $collections == false ]] || exit 1; collections=true ;;
        *) echo "Unknown kernel option: $option" >&2; exit 1 ;;
    esac
done
[[ $memory == false || $interrupts == false ]] || { echo 'Choose one kernel profile.' >&2; exit 1; }
[[ $heap == false || ( $memory == false && $interrupts == false ) ]] || { echo 'Choose one kernel profile.' >&2; exit 1; }
[[ $collections == false || ( $heap == false && $memory == false && $interrupts == false ) ]] || { echo 'Choose one kernel profile.' >&2; exit 1; }
if [[ $collections == true ]]; then heap=true; fi
repository="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
compiler="$(cd "$(dirname "$1")" && pwd)/$(basename "$1")"
[[ -x "$compiler" ]] || { echo 'An executable native compiler is required.' >&2; exit 1; }
output="${2:-$repository/build/kernel-boot}"
[[ ! -e "$output" ]] || { echo 'Choose a fresh output directory; existing builds are preserved.' >&2; exit 1; }
qemu=''
if [[ $run == true ]]; then
    qemu="$(command -v qemu-system-x86_64)"
    timeout_tool="$(command -v timeout)"
    [[ -n "$qemu" && -n "$timeout_tool" ]] || { echo 'QEMU x86-64 and timeout are required for --run.' >&2; exit 1; }
fi
mkdir -p "$output/src/sotlas/runtime"
output="$(cd "$output" && pwd)"
example=native_kernel_boot
if [[ $interrupts == true ]]; then example=native_kernel_interrupts; fi
if [[ $memory == true ]]; then example=native_kernel_memory; fi
if [[ $heap == true ]]; then example=native_kernel_heap; fi
if [[ $collections == true ]]; then example=native_kernel_collections; fi
cp "$repository/examples/$example/main.sotlas" "$output/src/main.sotlas"
cp "$repository/runtime/native/kernel_x86.sotlas" "$output/src/sotlas/runtime/kernel_x86.sotlas"
if [[ $memory == true || $heap == true ]]; then
    cp "$repository/runtime/native/pages.sotlas" "$output/src/sotlas/runtime/pages.sotlas"
    cp "$repository/runtime/native/kernel_memory.sotlas" "$output/src/sotlas/runtime/kernel_memory.sotlas"
fi
if [[ $heap == true ]]; then
    for module in managed heap kernel_heap; do
        cp "$repository/runtime/native/$module.sotlas" "$output/src/sotlas/runtime/$module.sotlas"
    done
fi
if [[ $collections == true ]]; then
    cp "$repository/runtime/native/vector.sotlas" "$output/src/sotlas/runtime/vector.sotlas"
fi
if [[ $memory == true ]]; then
    printf 'SOTLAS-MODULE-RESERVED\n42' > "$output/boot-module.bin"
fi
environment="$(command -v env)"
native() { "$environment" PATH="$output/no-host-tools" "$@"; }
native "$compiler" --check-build "$output/src" "$output/src/main.sotlas"
native "$compiler" --build-obj "$output/kernel.o" "$output/src" "$output/src/main.sotlas"
native "$compiler" --link-kernel "$output/kernel.o" "$output/kernel.elf" kernel_main
echo "Kernel image: $output/kernel.elf"
if [[ -n "$qemu" ]]; then
    module_args=()
    if [[ $memory == true ]]; then module_args=(-initrd "$output/boot-module.bin"); fi
    set +e
    # Do not use -no-shutdown: QEMU 10.2 implements debug-exit as shutdown.
    "$timeout_tool" 15s "$qemu" -machine pc -accel tcg -cpu qemu64 -m 64M \
        -kernel "$output/kernel.elf" "${module_args[@]}" -display none -serial stdio -monitor none \
        -no-reboot -device isa-debug-exit,iobase=0xf4,iosize=0x04 \
        > "$output/serial.log" 2>&1
    status=$?
    set -e
    cat "$output/serial.log"
    [[ $status -eq 85 ]] || { echo "Kernel boot failed: QEMU exit $status, expected 85." >&2; exit 1; }
    if [[ $collections == true ]]; then
        grep -Fxq 'SOTLAS: dynamic words and checked views OK' "$output/serial.log"
        grep -Fxq 'SOTLAS: collections IRQ and heap reclamation OK' "$output/serial.log"
        echo 'Kernel collections verified: growing POD vector, checked views, interrupt serialization and reclamation.'
    elif [[ $heap == true ]]; then
        grep -Fxq 'SOTLAS: heap resize and failure preservation OK' "$output/serial.log"
        grep -Fxq 'SOTLAS: heap IRQ allocation and exhaustion OK' "$output/serial.log"
        grep -Fxq 'SOTLAS: heap pages returned and stale handles rejected' "$output/serial.log"
        echo 'Kernel heap verified: variable buffers, resize, interrupt allocation and page reclamation.'
    elif [[ $memory == true ]]; then
        grep -Fxq 'SOTLAS: page allocation and reuse OK' "$output/serial.log"
        grep -Fxq 'SOTLAS: memory map and exhaustion OK' "$output/serial.log"
        grep -Fxq 'SOTLAS: boot module preserved' "$output/serial.log"
        grep -Fxq 'SOTLAS: IRQ-safe page metadata OK' "$output/serial.log"
        echo 'Kernel memory verified: aligned spans, zeroing, stale handles, exhaustion and boot module preservation.'
    elif [[ $interrupts == true ]]; then
        grep -Fxq 'SOTLAS: breakpoint and error frame OK' "$output/serial.log"
        grep -Fxq 'SOTLAS: timer and SSE preservation OK' "$output/serial.log"
        echo 'Kernel interrupts verified: trap/error frames, PIC/PIT timer, IRETQ and SSE preservation.'
    else
        grep -Fxq 'SOTLAS: kernel entered' "$output/serial.log"
        grep -Fxq 'SOTLAS: memory, stack, data, SSE OK' "$output/serial.log"
        grep -Fxq 'SOTLAS: VGA OK' "$output/serial.log"
        echo 'Kernel boot verified: Multiboot handoff, native x86-64, BSS/data, stack, SSE and VGA.'
    fi
fi
