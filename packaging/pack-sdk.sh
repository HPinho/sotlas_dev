#!/usr/bin/env bash
set -euo pipefail
[[ $# -eq 2 ]] || { echo 'Usage: bash packaging/pack-sdk.sh NATIVE_SEED FRESH_BUNDLE_DIRECTORY' >&2; exit 2; }
repository="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
seed="$(cd "$(dirname "$1")" && pwd)/$(basename "$1")"
case "$(uname -s):$(uname -m)" in
    Linux:x86_64) target=linux-x64 ;;
    Darwin:x86_64) target=macos-x64 ;;
    *) echo 'This SDK supports Linux x86-64 and Intel macOS.' >&2; exit 2 ;;
esac
[[ -x "$seed" && ! -e "$2" && ! -e "$2.tar.gz" ]] || { echo 'Require an executable seed and fresh bundle/archive paths.' >&2; exit 2; }
environment="$(command -v env)"
"$environment" -i PATH=/no-host-tools "$seed" --self-test
mkdir -p "$2/bin"
bundle="$(cd "$2" && pwd)"
cp "$seed" "$bundle/bin/sotlas-native"
chmod 755 "$bundle/bin/sotlas-native"
for directory in runtime/native bootstrap/sotlas/native_compiler/backend bootstrap/sotlas/native_driver \
    scripts packaging docs examples/calculator/src/calculator examples/calculator/platform examples/native_config_map \
    tests/native/contracts tests/native/calculator tests/native/ui examples/graphical_calculator/src/calculator_app; do mkdir -p "$bundle/$directory"; done
cp "$repository"/runtime/native/*.sotlas "$bundle/runtime/native/"
for name in token ast lexer parser sema; do cp "$repository/bootstrap/sotlas/native_compiler/$name.sotlas" "$bundle/bootstrap/sotlas/native_compiler/"; done
cp "$repository"/bootstrap/sotlas/native_compiler/backend/*.sotlas "$bundle/bootstrap/sotlas/native_compiler/backend/"
cp "$repository"/bootstrap/sotlas/native_driver/{linux,windows,darwin}.sotlas "$bundle/bootstrap/sotlas/native_driver/"
for name in build_native.sh build_native.ps1 test_native.sh test_native.ps1 verify_sdk.sh verify_sdk.ps1 build_kernel.sh build_kernel.ps1 verify_kernel_sdk.sh verify_kernel_sdk.ps1; do cp "$repository/scripts/$name" "$bundle/scripts/"; done
cp "$repository"/packaging/install-sdk.{sh,ps1} "$bundle/packaging/"
for name in native_json.md native_narrow_division.md native_seed_workflow.md native_ui_snapshots.md native_ui_editing.md native_ui_layout.md native_vscode_sdk.md native_tensor_ops.md native_csv.md; do cp "$repository/docs/$name" "$bundle/docs/"; done
cp "$repository"/docs/native_kernel*.md "$bundle/docs/"
for profile in boot interrupts memory heap collections vm foundation; do
    mkdir -p "$bundle/examples/native_kernel_$profile"
    cp "$repository/examples/native_kernel_$profile/"{main.sotlas,README.md} "$bundle/examples/native_kernel_$profile/"
done
mkdir -p "$bundle/tests/native/kernel_sdk"
cp "$repository"/tests/native/kernel_sdk/*.sotlas "$bundle/tests/native/kernel_sdk/"
cp "$repository/examples/calculator/src/calculator/main.sotlas" "$bundle/examples/calculator/src/calculator/"
cp "$repository"/examples/calculator/platform/*.sotlas "$bundle/examples/calculator/platform/"
cp "$repository"/examples/native_config_map/{main.sotlas,README.md} "$bundle/examples/native_config_map/"
mkdir -p "$bundle/examples/native_tensor_rows"
cp "$repository"/examples/native_tensor_rows/{main.sotlas,README.md} "$bundle/examples/native_tensor_rows/"
mkdir -p "$bundle/examples/native_csv"
cp "$repository"/examples/native_csv/{main.sotlas,README.md} "$bundle/examples/native_csv/"
cp "$repository/examples/native_config.sotlas" "$bundle/examples/"
cp -R "$repository/tests/native/contracts/." "$bundle/tests/native/contracts/"
cp "$repository/tests/native/use_after_move.sotlas" "$bundle/tests/native/"
cp "$repository/tests/native/calculator/model.sotlas" "$bundle/tests/native/calculator/"
cp "$repository"/tests/native/ui/*.sotlas "$bundle/tests/native/ui/"
cp "$repository"/examples/graphical_calculator/src/calculator_app/*.sotlas "$bundle/examples/graphical_calculator/src/calculator_app/"
cp "$repository"/examples/graphical_calculator/{README.md,build.ps1} "$bundle/examples/graphical_calculator/"
cp "$repository/LICENSE" "$bundle/LICENSE"
cp "$repository/packaging/SDK_README.md" "$bundle/README.md"
revision="${GITHUB_SHA:-local}"
[[ "$revision" =~ ^[a-zA-Z0-9_-]+$ ]] || { echo 'Invalid source revision.' >&2; exit 2; }
printf '{"format":1,"target":"%s","source_revision":"%s","channel":"preview"}\n' "$target" "$revision" > "$bundle/sdk.json"
digest() { if command -v sha256sum >/dev/null; then sha256sum "$1" | cut -d ' ' -f 1; else shasum -a 256 "$1" | cut -d ' ' -f 1; fi; }
(cd "$bundle"; find . -type f ! -name SHA256SUMS | LC_ALL=C sort | while IFS= read -r path; do printf '%s  %s\n' "$(digest "$path")" "${path#./}"; done) > "$bundle/SHA256SUMS"
tar -czf "$bundle.tar.gz" -C "$(dirname "$bundle")" "$(basename "$bundle")"
printf '%s  %s\n' "$(digest "$bundle.tar.gz")" "$(basename "$bundle").tar.gz" > "$bundle.tar.gz.sha256"
echo "Native SDK candidate: $bundle.tar.gz"
