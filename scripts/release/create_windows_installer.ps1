param(
    [Parameter(Mandatory = $true)]
    [string]$Version,
    [Parameter(Mandatory = $true)]
    [string]$SourceDir,
    [Parameter(Mandatory = $true)]
    [string]$OutputDir
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path $SourceDir)) {
    throw "SourceDir not found: $SourceDir"
}

$wixObjDir = Join-Path $OutputDir "wix"
New-Item -ItemType Directory -Path $wixObjDir -Force | Out-Null

$wxsPath = Join-Path $wixObjDir "easy-pdf-toolkit.wxs"
$wixSource = @"
<?xml version="1.0" encoding="UTF-8"?>
<Wix xmlns="http://wixtoolset.org/schemas/v4/wxs">
  <Package Name="Easy PDF Tool Kit" Language="1033" Version="$Version" Manufacturer="EasyPDF" UpgradeCode="f44eb2f4-8ca9-4f4a-9f70-d2eaad8438e1" Scope="perMachine">
    <MajorUpgrade DowngradeErrorMessage="A newer version is already installed." />
    <MediaTemplate EmbedCab="yes" />

    <StandardDirectory Id="ProgramFiles64Folder">
      <Directory Id="INSTALLFOLDER" Name="Easy PDF Tool Kit" />
    </StandardDirectory>

    <Feature Id="MainFeature" Title="Easy PDF Tool Kit" Level="1">
      <ComponentGroupRef Id="AppFiles" />
    </Feature>
  </Package>

  <Fragment>
    <ComponentGroup Id="AppFiles" Directory="INSTALLFOLDER">
      <Files Include="$SourceDir\**" />
    </ComponentGroup>
  </Fragment>
</Wix>
"@

$wixSource | Out-File -FilePath $wxsPath -Encoding utf8

Push-Location $wixObjDir
wix build "$wxsPath" -arch x64 -o (Join-Path $OutputDir "Easy-PDF-Toolkit-$Version-windows-x64.msi")
Pop-Location
