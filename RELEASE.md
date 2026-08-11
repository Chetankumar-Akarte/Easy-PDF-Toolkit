# Release Pipeline

This repository uses a manual GitHub Actions workflow to build platform binaries on demand.

## Workflow

- Workflow file: `.github/workflows/release.yml`
- Trigger: `workflow_dispatch` only
- Inputs:
  - `version`: release version without `v` prefix
  - `prerelease`: mark release as prerelease
  - `targets`: `all`, `windows-x64`, `macos-x64`, `macos-arm64`, `linux-x64`
  - `artifacts`: `portable`, `installer`, `both`
  - `publish`: publish a GitHub release

## Outputs

- Portable bundles:
  - Windows: zip
  - macOS/Linux: tar.gz
- Installers:
  - Windows: MSI (WiX)
  - macOS: DMG + PKG
  - Linux: AppImage
- `SHA256SUMS.txt` is generated for release assets.
- Packaged smoke test is required before artifact upload for each selected target.

## Local Build

### macOS/Linux

```bash
bash scripts/release/build_local.sh 1.0.0 both
```

### Windows PowerShell

```powershell
./scripts/release/build_local.ps1 -Version 1.0.0 -ArtifactKind both
```

## Signing and Notarization

Signing/notarization is enforced as a fail-fast gate in release workflow.

### Required Secrets

- Windows
  - `WIN_CERT_PFX_BASE64`
  - `WIN_CERT_PASSWORD`
  - `WIN_TIMESTAMP_URL`
- macOS
  - `MACOS_CERT_P12_BASE64`
  - `MACOS_CERT_PASSWORD`
  - `MACOS_TEAM_ID`
  - `MACOS_SIGNING_IDENTITY`
  - `MACOS_NOTARY_APPLE_ID`
  - `MACOS_NOTARY_TEAM_ID`
  - `MACOS_NOTARY_APP_PASSWORD`
- Linux
  - `LINUX_GPG_PRIVATE_KEY` (ASCII-armored private key)
  - `LINUX_GPG_PASSPHRASE`

If required secrets are missing for a selected signed platform target, the workflow fails and release publication is blocked.

### Secret Value Preparation (Windows and macOS)

Use these commands locally to prepare the values for GitHub repository secrets.

#### Windows Secrets

- `WIN_CERT_PFX_BASE64`
  - Value: base64 contents of your `.pfx` file on one line.
  - macOS/Linux:

```bash
base64 -i /path/to/codesign.pfx | tr -d '\n'
```

  - Windows PowerShell:

```powershell
[Convert]::ToBase64String([IO.File]::ReadAllBytes("C:\path\to\codesign.pfx"))
```

- `WIN_CERT_PASSWORD`
  - Value: password used when exporting the `.pfx`.

- `WIN_TIMESTAMP_URL`
  - Value: RFC3161 timestamp server URL.
  - Examples:
    - `http://timestamp.digicert.com`
    - `http://timestamp.sectigo.com`
    - `http://rfc3161timestamp.globalsign.com/advanced`

#### macOS Secrets

- `MACOS_CERT_P12_BASE64`
  - Value: base64 contents of your `.p12` certificate on one line.

```bash
base64 -i /path/to/developerid.p12 | tr -d '\n'
```

- `MACOS_CERT_PASSWORD`
  - Value: password used when exporting the `.p12`.

- `MACOS_TEAM_ID`
  - Value: Apple Team ID (10 characters), for example `AB12C34DEF`.

- `MACOS_SIGNING_IDENTITY`
  - Value: exact identity string from this command:

```bash
security find-identity -v -p codesigning
```

  - Example value: `Developer ID Application: Your Name (TEAMID)`.

- `MACOS_NOTARY_APPLE_ID`
  - Value: Apple ID email used for notarization.

- `MACOS_NOTARY_TEAM_ID`
  - Value: usually same as `MACOS_TEAM_ID`.

- `MACOS_NOTARY_APP_PASSWORD`
  - Value: Apple app-specific password from Apple ID account.

#### Safety Checklist

- Keep base64 values as a single line (no extra spaces/newlines).
- Make sure certificates include private keys.
- Paste secret values, not file paths.
- Never commit key/certificate exports into the repository.

### Linux Secret Preparation (Copy-Paste)

```bash
# 1) List your secret keys and pick KEY_ID for:
#    Chetankumar Akarte <chetan.akarte@gmail.com>
gpg --list-secret-keys --keyid-format LONG "Chetankumar Akarte <chetan.akarte@gmail.com>"

# 2) Set your key id (replace with actual value from the command above)
KEY_ID="YOUR_KEY_ID"

# 3) Export private key (ASCII armored)
gpg --armor --export-secret-keys "$KEY_ID" > private.key.asc

# 4) Copy private key to clipboard
# macOS:
pbcopy < private.key.asc
# Linux (xclip):
xclip -selection clipboard < private.key.asc
# Linux fallback (xsel):
xsel --clipboard --input < private.key.asc

# 5) Optional: export public key (for sharing/verification)
gpg --armor --export "$KEY_ID" > public.key.asc

# 6) Cleanup local private key export when done
rm -f private.key.asc
```

- Secret mapping:
  - `LINUX_GPG_PRIVATE_KEY`: contents of `private.key.asc`
  - `LINUX_GPG_PASSPHRASE`: passphrase used for this GPG key
- Warning: never commit exported private key files or passphrases to the repository.

### Linux Signature Outputs

- `Easy-PDF-Toolkit-<version>-linux-x64.tar.gz.asc`
- `Easy-PDF-Toolkit-<version>-linux-x64.AppImage.asc`
- `linux-signing-public-key.asc`

Both are detached armored GPG signatures.

### Linux Verification (End Users)

```bash
gpg --import linux-signing-public-key.asc
gpg --verify Easy-PDF-Toolkit-<version>-linux-x64.AppImage.asc Easy-PDF-Toolkit-<version>-linux-x64.AppImage
gpg --verify Easy-PDF-Toolkit-<version>-linux-x64.tar.gz.asc Easy-PDF-Toolkit-<version>-linux-x64.tar.gz
```

## OCR Dependency Policy

OCR is external. Tesseract is not bundled into release binaries.

- The app now auto-detects common binary locations and PATH.
- Users can still provide explicit path in settings.
