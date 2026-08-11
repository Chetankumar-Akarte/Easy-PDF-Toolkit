param(
    [string]$Version = "dev",
    [ValidateSet("portable", "installer", "both")]
    [string]$ArtifactKind = "portable"
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path ".venv")) {
    python -m venv .venv
}

. .venv\Scripts\Activate.ps1

python -m pip install --upgrade pip
pip install -r requirements.txt
python -m pytest -q

python -c "import fitz; d=fitz.open(); p=d.new_page(); p.insert_text((72,72), 'Easy PDF Toolkit smoke test'); d.save('smoke.pdf'); d.close()"

if ($ArtifactKind -eq "portable" -or $ArtifactKind -eq "both") {
    pyinstaller --clean --noconfirm easy-pdf-toolkit.spec
    dist\Easy-PDF-Toolkit\Easy-PDF-Toolkit.exe --smoke-open smoke.pdf
    Compress-Archive -Path dist\Easy-PDF-Toolkit\* -DestinationPath "dist\Easy-PDF-Toolkit-$Version-windows-x64.zip" -Force
}

if ($ArtifactKind -eq "installer" -or $ArtifactKind -eq "both") {
    if (-not (Get-Command wix -ErrorAction SilentlyContinue)) {
        dotnet tool install --global wix --version 5.*
        $env:Path += ";$env:USERPROFILE\.dotnet\tools"
    }
    ./scripts/release/create_windows_installer.ps1 -Version $Version -SourceDir "dist\Easy-PDF-Toolkit" -OutputDir "dist"
}

Write-Host "Done. Artifacts are in dist/."
