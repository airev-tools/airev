#!/usr/bin/env bash
# install.sh — install airev from GitHub Releases with checksum verification.
#
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/airev-tools/airev/main/build/install.sh | bash
#
# Override version:
#   AIREV_VERSION=v0.2.0 bash install.sh
#
# If your platform has no native binary, use pip instead:
#   pip install airev

set -euo pipefail

REPO="airev-tools/airev"
INSTALL_DIR="${AIREV_INSTALL_DIR:-/usr/local/bin}"

# ---- Platform detection ----

detect_platform() {
    local os arch
    os="$(uname -s | tr '[:upper:]' '[:lower:]')"
    arch="$(uname -m)"

    case "$os" in
        linux)  os="linux" ;;
        darwin) os="darwin" ;;
        *)
            echo "Error: Unsupported OS '$os'."
            echo ""
            echo "Install via pip instead:"
            echo "  pip install airev"
            exit 1
            ;;
    esac

    case "$arch" in
        x86_64|amd64) arch="x86_64" ;;
        arm64|aarch64) arch="arm64" ;;
        *)
            echo "Error: Unsupported architecture '$arch'."
            echo ""
            echo "Install via pip instead:"
            echo "  pip install airev"
            exit 1
            ;;
    esac

    echo "${os}-${arch}"
}

# ---- Version resolution ----

resolve_version() {
    if [ -n "${AIREV_VERSION:-}" ]; then
        echo "$AIREV_VERSION"
        return
    fi

    local latest
    latest="$(curl -fsSL "https://api.github.com/repos/${REPO}/releases/latest" \
        | grep '"tag_name"' \
        | head -1 \
        | sed 's/.*"tag_name": *"\([^"]*\)".*/\1/')" || true

    if [ -z "$latest" ]; then
        echo "Error: Could not determine latest version."
        echo "GitHub API may be rate-limited. Set AIREV_VERSION manually:"
        echo "  AIREV_VERSION=v0.2.0 bash install.sh"
        echo ""
        echo "Or install via pip:"
        echo "  pip install airev"
        exit 1
    fi

    echo "$latest"
}

# ---- Download and verify ----

download_and_verify() {
    local version="$1"
    local platform="$2"
    local binary_name="airev-${version}-${platform}"
    local base_url="https://github.com/${REPO}/releases/download/${version}"

    local tmpdir
    tmpdir="$(mktemp -d)"
    trap 'rm -rf "$tmpdir"' EXIT

    echo "Downloading ${binary_name}..."
    if ! curl -fsSL -o "${tmpdir}/${binary_name}" "${base_url}/${binary_name}"; then
        echo "Error: Binary not available for ${platform}."
        echo ""
        echo "Available platforms: linux-x86_64, darwin-x86_64, darwin-arm64"
        echo ""
        echo "Install via pip instead:"
        echo "  pip install airev"
        exit 1
    fi

    echo "Downloading checksum..."
    if curl -fsSL -o "${tmpdir}/${binary_name}.sha256" "${base_url}/${binary_name}.sha256" 2>/dev/null; then
        echo "Verifying checksum..."
        (cd "$tmpdir" && sha256sum -c "${binary_name}.sha256")
        if [ $? -ne 0 ]; then
            echo "Error: Checksum verification failed. The download may be corrupted."
            exit 1
        fi
        echo "Checksum verified."
    else
        echo "Warning: Checksum file not available. Skipping verification."
    fi

    chmod +x "${tmpdir}/${binary_name}"

    echo "Installing to ${INSTALL_DIR}/airev..."
    if [ -w "$INSTALL_DIR" ]; then
        mv "${tmpdir}/${binary_name}" "${INSTALL_DIR}/airev"
    else
        sudo mv "${tmpdir}/${binary_name}" "${INSTALL_DIR}/airev"
    fi

    echo ""
    echo "airev installed successfully!"
    echo ""
    airev --version 2>/dev/null || true
}

# ---- Main ----

main() {
    local platform version
    platform="$(detect_platform)"
    version="$(resolve_version)"

    echo "Platform: ${platform}"
    echo "Version:  ${version}"
    echo ""

    download_and_verify "$version" "$platform"
}

main
