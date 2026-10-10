#!/usr/bin/env bash
# Install an extracted native Linux bundle without Python or a C toolchain.
set -euo pipefail
if [ "$#" -ne 2 ]; then
    echo "Usage: install-native.sh BUNDLE_DIRECTORY DESTINATION_DIRECTORY" >&2
    exit 2
fi
bundle="$1"
destination="$2"
if [ "$(uname -s)" != Linux ] || [ "$(uname -m)" != x86_64 ]; then
    echo "This native bundle requires Linux x86-64." >&2
    exit 2
fi
if [ -e "$destination" ]; then
    echo "Installation destination already exists; choose an empty destination." >&2
    exit 2
fi
if [ ! -f "$bundle/SHA256SUMS" ] || [ ! -f "$bundle/bin/sotlas-native" ]; then
    echo "Incomplete native bundle." >&2
    exit 2
fi
if [ -n "$(find "$bundle" -type l -print -quit)" ]; then
    echo "Native bundles must not contain symlinks." >&2
    exit 2
fi
while read -r digest relative; do
    if [[ ! "$digest" =~ ^[0-9a-f]{64}$ ]]; then exit 2; fi
    case "$relative" in
        bin/sotlas-native|manifest.json|install-native.sh|src/sotlas/compiler/*.sotlas|docs/native-driver.md) ;;
        *) echo "Unsupported checksum path: $relative" >&2; exit 2 ;;
    esac
    case "$relative" in /*|*..*|*\\*) exit 2 ;; esac
done < "$bundle/SHA256SUMS"
while IFS= read -r file; do
    relative="${file#"$bundle"/}"
    [ "$relative" = SHA256SUMS ] && continue
    if ! grep -F "  $relative" "$bundle/SHA256SUMS" | grep -Fqx "$(sha256sum "$file" | cut -d ' ' -f 1)  $relative"; then
        echo "Unverified native bundle file: $relative" >&2
        exit 2
    fi
done < <(find "$bundle" -type f -print)
for name in token ast lexer parser sema; do
    test -f "$bundle/src/sotlas/compiler/$name.sotlas"
done
for name in target_ir lower_scalar x86_64_scalar; do
    test -f "$bundle/src/sotlas/compiler/backend/$name.sotlas"
done
test -f "$bundle/src/sotlas/compiler/linux_driver.sotlas"
(cd "$bundle" && sha256sum --strict -c SHA256SUMS)
mkdir -p "$destination"
cp -R "$bundle/bin" "$destination/bin"
cp -R "$bundle/src" "$destination/src"
cp -R "$bundle/docs" "$destination/docs"
cp "$bundle/manifest.json" "$bundle/SHA256SUMS" "$destination/"
chmod 755 "$destination/bin/sotlas-native"
echo "Installed native compiler: $destination/bin/sotlas-native"
