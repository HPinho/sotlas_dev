#!/usr/bin/env bash
# ==============================================================================
# Sotlas preview installer for Linux and macOS.
# ==============================================================================
# Usage from a source checkout:
#   bash packaging/install.sh
# Or with a downloaded release archive:
#   bash install.sh --source-archive ./sotlas-v1.0.0rc1-linux-x64.tar.gz
# ==============================================================================

set -euo pipefail

INSTALL_DIR="${SOTLAS_INSTALL_DIR:-$HOME/.sotlas}"
BIN_DIR="$INSTALL_DIR/bin"
SOURCE_ARCHIVE=""

while [ "$#" -gt 0 ]; do
    case "$1" in
        --source-archive)
            if [ "$#" -lt 2 ] || [ -z "$2" ]; then
                echo "--source-archive requires a .tar.gz path." >&2
                exit 2
            fi
            SOURCE_ARCHIVE="$2"
            shift 2
            ;;
        -h|--help)
            echo "Usage: $0 [--source-archive PATH]"
            echo "Without --source-archive, the installer builds from the current source checkout."
            exit 0
            ;;
        *)
            echo "Unknown installer argument: $1" >&2
            exit 2
            ;;
    esac
done

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

install_archive() {
    archive="$1"
    if [ ! -f "$archive" ]; then
        echo "Source archive does not exist: $archive" >&2
        exit 2
    fi
    case "$(basename "$archive")" in
        *-"$PACKAGE_SUFFIX".tar.gz)
            ;;
        *)
            echo "Archive does not match this host ($PACKAGE_SUFFIX): $archive" >&2
            exit 2
            ;;
    esac

    extract_root="$(mktemp -d "${TMPDIR:-/tmp}/sotlas-preview.XXXXXX")"
    trap 'rm -rf "$extract_root"' EXIT

    # Reject absolute and parent-traversal archive entries before extraction.
    while IFS= read -r entry; do
        case "$entry" in
            /*|../*|*/../*|*/..)
                echo "Unsafe path in preview archive: $entry" >&2
                exit 2
                ;;
        esac
    done < <(tar -tzf "$archive")

    tar -xzf "$archive" -C "$extract_root"

    payload_root=""
    payload_count=0
    if [ -f "$extract_root/bin/sotlas" ] && [ -d "$extract_root/compiler" ]; then
        payload_root="$extract_root"
        payload_count=1
    fi
    for candidate in "$extract_root"/*; do
        [ -d "$candidate" ] || continue
        if [ -f "$candidate/bin/sotlas" ] && [ -d "$candidate/compiler" ]; then
            payload_root="$candidate"
            payload_count=$((payload_count + 1))
        fi
    done

    if [ "$payload_count" -ne 1 ]; then
        echo "Portable archive must contain exactly one Sotlas toolchain root; found $payload_count." >&2
        exit 2
    fi

    echo "-> Installing release archive $archive..."
    cp -R "$payload_root/"* "$INSTALL_DIR/"
    rm -rf "$extract_root"
    trap - EXIT
}

if [ -n "$SOURCE_ARCHIVE" ]; then
    install_archive "$SOURCE_ARCHIVE"
else
    VERSION_FILE="$REPO_ROOT/compiler/sotlas/__init__.py"
    if [ ! -f "$VERSION_FILE" ]; then
        echo "Source checkout not found. Use --source-archive when running install.sh from a GitHub Release." >&2
        exit 1
    fi

    VERSION="$(sed -n 's/^SOTLAS_VERSION = "\(.*\)"$/\1/p' "$VERSION_FILE")"
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
fi

if [ ! -f "$BIN_DIR/sotlas" ]; then
    echo "Installation is incomplete: missing $BIN_DIR/sotlas" >&2
    exit 1
fi
chmod +x "$BIN_DIR"/* 2>/dev/null || true

# Verify the canonical installed frontend before mutating shell startup files.
INSTALL_PYTHONPATH="$INSTALL_DIR/compiler:$INSTALL_DIR/tools"
if [ -n "${PYTHONPATH:-}" ]; then
    INSTALL_PYTHONPATH="$INSTALL_PYTHONPATH:$PYTHONPATH"
fi
echo "-> Running Sotlas preview doctor..."
PYTHONPATH="$INSTALL_PYTHONPATH" "$PYTHON_BIN" -m sotlas.doctor

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
