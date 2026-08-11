#!/usr/bin/env bash
set -euo pipefail

VERSION="${1:-dev}"
ARTIFACT_KIND="${2:-portable}" # portable|installer|both

if [[ "$ARTIFACT_KIND" != "portable" && "$ARTIFACT_KIND" != "installer" && "$ARTIFACT_KIND" != "both" ]]; then
  echo "Invalid artifact kind: $ARTIFACT_KIND"
  exit 2
fi

if [[ ! -d .venv ]]; then
  python3 -m venv .venv
fi
source .venv/bin/activate

python -m pip install --upgrade pip
pip install -r requirements.txt
python -m pytest -q

python - <<'PY'
import fitz
doc = fitz.open()
page = doc.new_page()
page.insert_text((72, 72), "Easy PDF Toolkit smoke test")
doc.save("smoke.pdf")
doc.close()
PY

if [[ "$ARTIFACT_KIND" == "portable" || "$ARTIFACT_KIND" == "both" ]]; then
  pyinstaller --clean --noconfirm easy-pdf-toolkit.spec
  if [[ "$(uname -s)" == "Linux" ]]; then
    xvfb-run -a dist/Easy-PDF-Toolkit/Easy-PDF-Toolkit --smoke-open smoke.pdf
    tar -czf "dist/Easy-PDF-Toolkit-${VERSION}-linux-x64.tar.gz" -C dist Easy-PDF-Toolkit
  else
    dist/Easy-PDF-Toolkit.app/Contents/MacOS/Easy-PDF-Toolkit --smoke-open smoke.pdf
    tar -czf "dist/Easy-PDF-Toolkit-${VERSION}-macos-$(uname -m).tar.gz" -C dist Easy-PDF-Toolkit.app
  fi
fi

if [[ "$ARTIFACT_KIND" == "installer" || "$ARTIFACT_KIND" == "both" ]]; then
  if [[ "$(uname -s)" == "Linux" ]]; then
    chmod +x scripts/release/create_linux_appimage.sh
    ./scripts/release/create_linux_appimage.sh "$VERSION" "dist/Easy-PDF-Toolkit" "dist"
  else
    chmod +x scripts/release/create_macos_installers.sh
    ./scripts/release/create_macos_installers.sh "$VERSION" "dist/Easy-PDF-Toolkit.app" "dist"
  fi
fi

echo "Done. Artifacts are in dist/."
