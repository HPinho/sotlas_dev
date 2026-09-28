#!/usr/bin/env bash
# ==============================================================================
# Sotlas preview installer for Linux and macOS.
# ==============================================================================
# Usage from a source checkout:
#   bash packaging/install.sh
# ==============================================================================

set -euo pipefail

INSTALL_DIR="${SOTLAS_INSTALL_DIR:-$HOME/.sotlas}"
BIN_DIR="$INSTALL_DIR/bin"

echo ""
echo "==================================================================="
echo "                  SOTLAS PREVIEW INSTALLER                         "
echo "==================================================================="
echo ""

echo "-> Install directory: $INSTALL_DIR"
mkdir -p "$INSTALL_DIR"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

ARCH="$(uname -m)"
case "$ARCH" in
    x86_64|amd64)
        ;;
    *)
        echo "Unsupported preview architecture: $ARCH. Current portable bundles are x86_64 only." >&2
        exit 2
        ;;
esac

OS_NAME="$(uname -s)"
case "$OS_NAME" in
    Linux)
        PACKAGE_TARGET="linux"
        PACKAGE_SUFFIX="linux-x64"
        ;;
    Darwin)
        PACKAGE_TARGET="darwin"
        PACKAGE_SUFFIX="macos-x64"
        ;;
    *)
        echo "Unsupported preview operating system: $OS_NAME" >&2
        exit 2
        ;;
esac

if command -v python3 >/dev/null 2>&1; then
    PYTHON_BIN="python3"
elif command -v python >/dev/null 2>&1; then
    PYTHON_BIN="python"
else
    echo "Python 3.10 or newer is required to install the Sotlas preview." >&2
    exit 3
fi

VERSION="$(sed -n 's/^SOTLAS_VERSION = "\(.*\)"$/\1/p' "$REPO_ROOT/compiler/sotlas/__init__.py")"
if [ -z "$VERSION" ]; then
    echo "Unable to determine the current Sotlas version." >&2
    exit 1
fi

BUNDLE_PATH="$REPO_ROOT/dist/sotlas-v${VERSION}-${PACKAGE_SUFFIX}"
if [ ! -d "$BUNDLE_PATH" ]; then
    echo "-> Building the current local ${PACKAGE_SUFFIX} preview bundle..."
    "$PYTHON_BIN" "$SCRIPT_DIR/package.py" --target "$PACKAGE_TARGET" --dist-dir "$REPO_ROOT/dist"
fi
if [ ! -d "$BUNDLE_PATH" ]; then
    echo "The packager did not produce the expected bundle for version $VERSION: $BUNDLE_PATH" >&2
    exit 1
fi

echo "-> Installing $BUNDLE_PATH..."
cp -R "$BUNDLE_PATH/"* "$INSTALL_DIR/"

chmod +x "$BIN_DIR"/* 2>/dev/null || true

# Configurar PATH em ~/.bashrc e ~/.zshrc
PATH_LINE="export PATH=\"$BIN_DIR:\$PATH\""
SOTLAS_HOME_LINE="export SOTLAS_HOME=\"$INSTALL_DIR\""

for RC in "$HOME/.bashrc" "$HOME/.zshrc" "$HOME/.profile"; do
    if [ -f "$RC" ]; then
        if ! grep -q "SOTLAS_HOME" "$RC"; then
            echo "" >> "$RC"
            echo "# Sotlas Toolchain" >> "$RC"
            echo "$SOTLAS_HOME_LINE" >> "$RC"
            echo "$PATH_LINE" >> "$RC"
            echo "-> Updated: $RC"
        fi
    fi
done

echo ""
echo "==================================================================="
echo "              SOTLAS PREVIEW INSTALLED                             "
echo "==================================================================="
echo ""
echo "Try these verified preview commands:"
echo "  sotlas version"
echo "  $PYTHON_BIN -m sotlas.doctor"
echo "  sotlas check examples/01_hello_systems/main.sotlas"
echo ""
echo "Restart your terminal or update PATH for this session:"
echo "  export PATH=\"$BIN_DIR:\$PATH\""
echo "  sotlas version"
echo ""
