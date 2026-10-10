<#
.SYNOPSIS
    Lumina Player PyInstaller derleme ve Inno Setup installer üretme betiği.
#>
param(
    [switch]$SkipInstaller
)
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Lumina Player - Derleme Başlatılıyor  " -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

# 1. vendor\vlc kontrolü
$vlcDir = Join-Path $root "vendor\vlc"
if (-not (Test-Path (Join-Path $vlcDir "libvlc.dll"))) {
    Write-Host "[1/4] vendor\vlc bulunamadı, hazırlanıyor..." -ForegroundColor Yellow
    & powershell -ExecutionPolicy Bypass -File (Join-Path $root "tools\fetch_vlc.ps1")
} else {
    Write-Host "[1/4] vendor\vlc hazır." -ForegroundColor Green
}

# 2. PyInstaller ile .exe derleme
Write-Host "[2/4] PyInstaller ile paketleniyor..." -ForegroundColor Yellow
$py = Join-Path $root ".venv\Scripts\pyinstaller.exe"
if (-not (Test-Path $py)) {
    $py = "pyinstaller"
}
& $py --clean --noconfirm (Join-Path $root "packaging\lumina.spec")

$distDir = Join-Path $root "dist\LuminaPlayer"
if (Test-Path (Join-Path $distDir "LuminaPlayer.exe")) {
    $size = [math]::Round(((Get-ChildItem $distDir -Recurse | Measure-Object Length -Sum).Sum / 1MB), 1)
    Write-Host "[2/4] PyInstaller derlemesi başarılı! ($size MB): $distDir" -ForegroundColor Green
} else {
    Write-Error "PyInstaller derlemesi başarısız oldu!"
}

# 3. Inno Setup ile Installer Üretimi
if (-not $SkipInstaller) {
    Write-Host "[3/4] Inno Setup denetleniyor..." -ForegroundColor Yellow
    $isccCandidates = @(
        "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe",
        "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
        "$env:ProgramFiles\Inno Setup 6\ISCC.exe"
    )
    $iscc = $null
    foreach ($cand in $isccCandidates) {
        if ($cand -and (Test-Path $cand)) { $iscc = $cand; break }
    }

    if ($iscc -and (Test-Path $iscc)) {
        Write-Host "Inno Setup bulundu: $iscc. Installer derleniyor..." -ForegroundColor Yellow
        & $iscc (Join-Path $root "packaging\installer.iss")
        Write-Host "[3/4] Installer başarıyla üretildi! (dist/ klasöründe)" -ForegroundColor Green
    } else {
        Write-Host "[3/4] Inno Setup (ISCC.exe) bulunamadı. Kurucu üretimi atlandı." -ForegroundColor DarkYellow
        Write-Host "      (Installer üretmek için Inno Setup 6 kurabilirsiniz: winget install JRSoftware.InnoSetup)" -ForegroundColor DarkGray
    }
}

Write-Host "========================================" -ForegroundColor Green
Write-Host "  Lumina Player Derleme Tamamlandı!     " -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
