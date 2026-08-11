#!/usr/bin/env bash
set -euo pipefail

VERSION="$1"
SOURCE_DIR="$2"
OUTPUT_DIR="$3"

if [[ -z "$VERSION" || -z "$SOURCE_DIR" || -z "$OUTPUT_DIR" ]]; then
  echo "Usage: $0 <version> <source_dir> <output_dir>"
  exit 2
fi

mkdir -p "$OUTPUT_DIR"
APPDIR="$OUTPUT_DIR/AppDir"
rm -rf "$APPDIR"
mkdir -p "$APPDIR/usr/bin" "$APPDIR/usr/share/applications" "$APPDIR/usr/share/icons/hicolor/256x256/apps"

cp -R "$SOURCE_DIR" "$APPDIR/usr/bin/Easy-PDF-Toolkit"

cat > "$APPDIR/AppRun" <<'EOF'
#!/usr/bin/env bash
HERE="$(dirname "$(readlink -f "$0")")"
exec "$HERE/usr/bin/Easy-PDF-Toolkit/Easy-PDF-Toolkit" "$@"
EOF
chmod +x "$APPDIR/AppRun"

cat > "$APPDIR/usr/share/applications/easy-pdf-toolkit.desktop" <<'EOF'
[Desktop Entry]
Type=Application
Name=Easy PDF Tool Kit
Exec=Easy-PDF-Toolkit
Icon=easy-pdf-toolkit
Categories=Office;
Terminal=false
EOF

if [[ -f "$SOURCE_DIR/_internal/app/resources/icons/tool_logo.svg" ]]; then
  cp "$SOURCE_DIR/_internal/app/resources/icons/tool_logo.svg" "$APPDIR/usr/share/icons/hicolor/256x256/apps/easy-pdf-toolkit.svg"
fi

curl -fsSL -o "$OUTPUT_DIR/appimagetool" https://github.com/AppImage/AppImageKit/releases/download/continuous/appimagetool-x86_64.AppImage
chmod +x "$OUTPUT_DIR/appimagetool"
ARCH=x86_64 "$OUTPUT_DIR/appimagetool" "$APPDIR" "$OUTPUT_DIR/Easy-PDF-Toolkit-${VERSION}-linux-x64.AppImage"
