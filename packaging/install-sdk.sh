#!/usr/bin/env bash
set -euo pipefail
[[ $# -eq 2 ]] || { echo 'Usage: bash packaging/install-sdk.sh EXTRACTED_BUNDLE FRESH_DESTINATION' >&2; exit 2; }
bundle="$(cd "$1" && pwd)"; destination="$2"
[[ ! -e "$destination" && -f "$bundle/SHA256SUMS" && -f "$bundle/sdk.json" ]] || { echo 'Require a complete bundle and fresh destination.' >&2; exit 2; }
case "$(uname -s):$(uname -m)" in
    Linux:x86_64) target=linux-x64 ;;
    Darwin:x86_64) target=macos-x64 ;;
    *) echo 'Unsupported SDK host.' >&2; exit 2 ;;
esac
grep -Fq '"format":1' "$bundle/sdk.json"
grep -Fq "\"target\":\"$target\"" "$bundle/sdk.json" || { echo 'SDK target does not match this host.' >&2; exit 2; }
[[ -z "$(find "$bundle" -type l -print -quit)" ]] || { echo 'SDK symlinks are not accepted.' >&2; exit 2; }
digest() { if command -v sha256sum >/dev/null; then sha256sum "$1" | cut -d ' ' -f 1; else shasum -a 256 "$1" | cut -d ' ' -f 1; fi; }
seen='|'; count=0
while read -r hash path extra; do
    [[ "$hash" =~ ^[0-9a-f]{64}$ && -z "${extra:-}" && "$path" =~ ^[a-zA-Z0-9_./-]+$ ]] || { echo 'Invalid SDK checksum row.' >&2; exit 2; }
    case "$path" in /*|*..*|*\\*|SHA256SUMS) echo 'Unsafe SDK checksum path.' >&2; exit 2 ;; esac
    case "$path" in bin/*|runtime/native/*|bootstrap/sotlas/*|scripts/*|packaging/*|docs/*|examples/*|tests/native/*|LICENSE|README.md|sdk.json) ;; *) echo 'Unexpected SDK path.' >&2; exit 2 ;; esac
    case "$seen" in *"|$path|"*) echo 'Duplicate checksum path.' >&2; exit 2 ;; esac
    seen="$seen$path|"; count=$((count+1))
    [[ -f "$bundle/$path" && "$(digest "$bundle/$path")" == "$hash" ]] || { echo "SDK integrity failure: $path" >&2; exit 2; }
done < "$bundle/SHA256SUMS"
[[ $count -gt 0 ]] || { echo 'Empty SDK checksum list.' >&2; exit 2; }
while IFS= read -r file; do
    path="${file#"$bundle"/}"; [[ "$path" == SHA256SUMS ]] && continue
    case "$seen" in *"|$path|"*) ;; *) echo "Unverified SDK file: $path" >&2; exit 2 ;; esac
done < <(find "$bundle" -type f)
for required in bin/sotlas-native runtime/native/json.sotlas scripts/build_native.sh scripts/test_native.sh scripts/verify_sdk.sh tests/native/contracts/manifest.txt examples/calculator/src/calculator/main.sotlas examples/native_config_map/main.sotlas LICENSE; do
    [[ -f "$bundle/$required" ]] || { echo "Incomplete SDK: $required" >&2; exit 2; }
done
if grep -Eq '"(sdk_version|compiler_sha256)"[[:space:]]*:' "$bundle/sdk.json"; then
    version="$(sed -n 's/.*"sdk_version":"\([^"]*\)".*/\1/p' "$bundle/sdk.json")"
    compiler_hash="$(sed -n 's/.*"compiler_sha256":"\([^"]*\)".*/\1/p' "$bundle/sdk.json")"
    if [[ ! "$version" =~ ^[0-9]+\.[0-9]+\.[0-9]+(rc[0-9]+)?$ ||
          ! "$compiler_hash" =~ ^[0-9a-f]{64}$ ||
          "$(digest "$bundle/bin/sotlas-native")" != "$compiler_hash" ]]; then
        echo 'SDK version or compiler identity verification failed.' >&2
        exit 2
    fi
fi
mkdir -p "$destination"
cp -R "$bundle/." "$destination/"
chmod 755 "$destination/bin/sotlas-native"
echo "Installed native SDK: $destination"
