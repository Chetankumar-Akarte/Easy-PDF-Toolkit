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

If required secrets are missing for a selected signed platform target, the workflow fails and release publication is blocked.

## OCR Dependency Policy

OCR is external. Tesseract is not bundled into release binaries.

- The app now auto-detects common binary locations and PATH.
- Users can still provide explicit path in settings.
