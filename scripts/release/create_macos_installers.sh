#!/usr/bin/env bash
set -euo pipefail

VERSION="$1"
APP_BUNDLE_PATH="$2"
OUTPUT_DIR="$3"

if [[ -z "$VERSION" || -z "$APP_BUNDLE_PATH" || -z "$OUTPUT_DIR" ]]; then
  echo "Usage: $0 <version> <app_bundle_path> <output_dir>"
  exit 2
fi

mkdir -p "$OUTPUT_DIR"

APP_NAME="Easy-PDF-Toolkit.app"
DMG_PATH="$OUTPUT_DIR/Easy-PDF-Toolkit-${VERSION}-macos.dmg"
PKG_PATH="$OUTPUT_DIR/Easy-PDF-Toolkit-${VERSION}-macos.pkg"

TMP_DMG_DIR="$OUTPUT_DIR/dmg-root"
rm -rf "$TMP_DMG_DIR"
mkdir -p "$TMP_DMG_DIR"
cp -R "$APP_BUNDLE_PATH" "$TMP_DMG_DIR/$APP_NAME"

hdiutil create -volname "Easy PDF Tool Kit" -srcfolder "$TMP_DMG_DIR" -ov -format UDZO "$DMG_PATH"

pkgbuild \
  --root "$APP_BUNDLE_PATH" \
  --identifier com.easypdf.toolkit \
  --version "$VERSION" \
  --install-location "/Applications/$APP_NAME" \
  "$PKG_PATH"
