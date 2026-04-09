#!/usr/bin/env bash
# Build a .deb package for midiplayer.
#
# Usage:
#   ./build-deb.sh
#
# Produces: midiplayer_0.1.0_all.deb
# Install:  sudo dpkg -i midiplayer_0.1.0_all.deb && sudo apt-get install -f

set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &>/dev/null && pwd)"
cd "$SCRIPT_DIR"

PKG_NAME="midiplayer"
PKG_VERSION="0.1.1"
DEB_DIR="$SCRIPT_DIR/deb-build"
INSTALL_ROOT="$DEB_DIR/${PKG_NAME}_${PKG_VERSION}_all"

echo "==> Building ${PKG_NAME} ${PKG_VERSION} .deb package..."

# Clean previous build
rm -rf "$DEB_DIR"
mkdir -p "$INSTALL_ROOT/DEBIAN"

# ---- DEBIAN control files ----
cp "$SCRIPT_DIR/debian/control"   "$INSTALL_ROOT/DEBIAN/control"
cp "$SCRIPT_DIR/debian/postinst"  "$INSTALL_ROOT/DEBIAN/postinst"
cp "$SCRIPT_DIR/debian/copyright" "$INSTALL_ROOT/DEBIAN/copyright"
chmod 755 "$INSTALL_ROOT/DEBIAN/postinst"

# ---- Application files ----
APP_DIR="$INSTALL_ROOT/usr/lib/midiplayer"
mkdir -p "$APP_DIR"

# Copy the Python package
cp -r "$SCRIPT_DIR/midiplayer" "$APP_DIR/midiplayer"

# Remove __pycache__ and .pyc
find "$APP_DIR" -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find "$APP_DIR" -name "*.pyc" -delete 2>/dev/null || true

# ---- Launcher script ----
# Use a Python script (not bash) with a different name than the package
# to avoid import confusion. The shebang uses the absolute python3 path.
BIN_DIR="$INSTALL_ROOT/usr/bin"
mkdir -p "$BIN_DIR"
cat > "$BIN_DIR/midiplayer" << 'LAUNCHER'
#!/usr/bin/python3
import sys
import os
import site

# Add our package to the path
sys.path.insert(0, "/usr/lib/midiplayer")

# Add user site-packages (pip --user installs like pyfluidsynth)
user_site = site.getusersitepackages()
if os.path.isdir(user_site) and user_site not in sys.path:
    sys.path.append(user_site)

# Redirect stderr to a log file for debugging desktop launches
_log_dir = os.path.join(
    os.environ.get("XDG_STATE_HOME", os.path.expanduser("~/.local/state")),
    "midiplayer",
)
try:
    os.makedirs(_log_dir, exist_ok=True)
    _log = open(os.path.join(_log_dir, "launch.log"), "w")
    sys.stderr = _log
except Exception:
    pass

from midiplayer.app import main
sys.exit(main())
LAUNCHER
chmod 755 "$BIN_DIR/midiplayer"

# ---- Desktop entry ----
DESKTOP_DIR="$INSTALL_ROOT/usr/share/applications"
mkdir -p "$DESKTOP_DIR"
cat > "$DESKTOP_DIR/com.pulpoff.midiplayer.desktop" << 'DESKTOP'
[Desktop Entry]
Type=Application
Name=MIDI player
GenericName=MIDI Player
Comment=MIDI sheet music player with piano and FluidSynth audio
Exec=/usr/bin/midiplayer %U
Icon=midiplayer
Terminal=false
Categories=Audio;Music;Player;
MimeType=audio/midi;audio/x-midi;application/x-midi;audio/mid;
StartupWMClass=com.pulpoff.midiplayer
StartupNotify=true
DESKTOP

# ---- MIME type registration ----
MIME_DIR="$INSTALL_ROOT/usr/share/mime/packages"
mkdir -p "$MIME_DIR"
cat > "$MIME_DIR/com.pulpoff.midiplayer.xml" << 'MIME'
<?xml version="1.0" encoding="UTF-8"?>
<mime-info xmlns="http://www.freedesktop.org/standards/shared-mime-info">
  <mime-type type="audio/midi">
    <comment>MIDI audio</comment>
    <glob pattern="*.mid"/>
    <glob pattern="*.midi"/>
  </mime-type>
  <mime-type type="audio/x-midi">
    <comment>MIDI audio</comment>
    <glob pattern="*.mid"/>
    <glob pattern="*.midi"/>
  </mime-type>
  <mime-type type="application/x-midi">
    <comment>MIDI audio</comment>
    <glob pattern="*.mid"/>
    <glob pattern="*.midi"/>
  </mime-type>
</mime-info>
MIME

# ---- Icon ----
ICON_DIR="$INSTALL_ROOT/usr/share/icons/hicolor/scalable/apps"
mkdir -p "$ICON_DIR"
cp "$SCRIPT_DIR/midiplayer/resources/midiplayer.svg" "$ICON_DIR/midiplayer.svg"

# ---- Sample MIDI files ----
SAMPLE_DIR="$INSTALL_ROOT/usr/share/midiplayer/samples"
mkdir -p "$SAMPLE_DIR"
for midi in "$SCRIPT_DIR"/*.mid; do
    [ -f "$midi" ] && cp "$midi" "$SAMPLE_DIR/"
done

# ---- Doc ----
DOC_DIR="$INSTALL_ROOT/usr/share/doc/midiplayer"
mkdir -p "$DOC_DIR"
cp "$SCRIPT_DIR/README.md" "$DOC_DIR/"
cp "$SCRIPT_DIR/debian/copyright" "$DOC_DIR/"

# ---- Calculate installed size ----
INSTALLED_SIZE=$(du -sk "$INSTALL_ROOT" | cut -f1)
sed -i "/^Architecture:/a Installed-Size: ${INSTALLED_SIZE}" "$INSTALL_ROOT/DEBIAN/control"

# ---- Build the .deb ----
dpkg-deb --build --root-owner-group "$INSTALL_ROOT"
mv "$INSTALL_ROOT.deb" "$SCRIPT_DIR/${PKG_NAME}_${PKG_VERSION}_all.deb"

# Clean up build directory
rm -rf "$DEB_DIR"

echo ""
echo "==> Built: ${PKG_NAME}_${PKG_VERSION}_all.deb"
echo ""
echo "Install with:"
echo "  sudo dpkg -i ${PKG_NAME}_${PKG_VERSION}_all.deb"
echo "  sudo apt-get install -f    # to resolve any missing dependencies"
echo ""
echo "Run with:"
echo "  midiplayer [file.mid]"
