#!/usr/bin/env bash
# midiplayer — one-shot install + run script for Debian / Ubuntu / derivatives.
#
# Unlike the original MidiSheetMusic build.sh (which compiled the C# source
# with `xbuild` and spawned `timidity` for playback), this port is pure
# Python, so "building" just means installing the runtime dependencies.
#
# Usage:
#   ./build.sh          # install deps if missing, then run the app
#   ./build.sh --deps   # only install deps, don't launch
#   ./build.sh --run    # only launch, skip the dep check
#   ./build.sh file.mid # install deps if missing, then open file.mid

set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &>/dev/null && pwd)"
cd "$SCRIPT_DIR"

PYTHON=${PYTHON:-python3}

APT_PACKAGES=(
    python3
    python3-gi
    python3-gi-cairo
    python3-cairo
    gir1.2-gtk-4.0
    fluidsynth
    python3-fluidsynth
    fluid-soundfont-gm
)

have_apt_packages() {
    dpkg -s "$@" >/dev/null 2>&1
}

install_deps() {
    if ! command -v apt-get >/dev/null 2>&1; then
        echo "warning: apt-get not found; skipping automatic dependency install." >&2
        echo "Please install the following manually: ${APT_PACKAGES[*]}" >&2
        return
    fi

    # Only run sudo apt if something is actually missing, so repeat runs are quiet.
    local missing=()
    for pkg in "${APT_PACKAGES[@]}"; do
        if ! dpkg -s "$pkg" >/dev/null 2>&1; then
            missing+=("$pkg")
        fi
    done

    if [ ${#missing[@]} -eq 0 ]; then
        return
    fi

    echo "Installing missing packages: ${missing[*]}"
    if [ "$(id -u)" -eq 0 ]; then
        apt-get update
        apt-get install -y "${missing[@]}"
    else
        sudo apt-get update
        sudo apt-get install -y "${missing[@]}"
    fi
}

run_app() {
    PYTHONPATH="$SCRIPT_DIR" exec "$PYTHON" -m midiplayer "$@"
}

case "${1:-}" in
    --deps)
        install_deps
        ;;
    --run)
        shift || true
        run_app "$@"
        ;;
    --help|-h)
        sed -n '2,12p' "$0"
        ;;
    *)
        install_deps
        run_app "$@"
        ;;
esac
