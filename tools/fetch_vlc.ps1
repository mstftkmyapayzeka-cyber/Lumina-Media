<#
.SYNOPSIS
    libVLC çalışma zamanını (libvlc.dll, libvlccore.dll, plugins/) vendor\vlc klasörüne hazırlar.
.DESCRIPTION
    1) Sistemde kurulu 64-bit VLC 3.x varsa oradan kopyalar.
    2) Yoksa videolan.org'dan resmî win64 zip arşivini indirip çıkarır.
    Uygulama geliştirme sırasında ve PyInstaller paketlemesinde bu klasörü kullanır;
    son kullanıcının ayrıca VLC kurmasına gerek kalmaz.
#>
param(
    [string]$VlcVersion = "3.0.21",
    [switch]$Force
)
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$dest = Join-Path $root "vendor\vlc"

if ((Test-Path (Join-Path $dest "libvlc.dll")) -and -not $Force) {
    Write-Host "vendor\vlc zaten hazır (yenilemek için -Force)." -ForegroundColor Green
    exit 0
}
if (Test-Path $dest) { Remove-Item $dest -Recurse -Force }
New-Item -ItemType Directory -Force -Path $dest | Out-Null

function Find-SystemVlc {
    $candidates = @()
    foreach ($key in @("HKLM:\SOFTWARE\VideoLAN\VLC", "HKLM:\SOFTWARE\WOW6432Node\VideoLAN\VLC")) {
        try { $candidates += (Get-ItemProperty $key -ErrorAction Stop).InstallDir } catch {}
    }
    $candidates += "$env:ProgramFiles\VideoLAN\VLC"
    foreach ($c in $candidates) {
        if ($c -and (Test-Path (Join-Path $c "libvlc.dll")) -and (Test-Path (Join-Path $c "plugins"))) { return $c }
    }
    return $null
}

$src = Find-SystemVlc
if ($src) {
    Write-Host "Kurulu VLC bulundu: $src"
} else {
    $zipUrl = "https://download.videolan.org/pub/videolan/vlc/$VlcVersion/win64/vlc-$VlcVersion-win64.zip"
    $tmp = Join-Path $env:TEMP "lumina-vlc"
    New-Item -ItemType Directory -Force -Path $tmp | Out-Null
    $zip = Join-Path $tmp "vlc.zip"
    Write-Host "İndiriliyor: $zipUrl"
    Invoke-WebRequest -Uri $zipUrl -OutFile $zip
    Expand-Archive -Path $zip -DestinationPath $tmp -Force
    $src = Join-Path $tmp "vlc-$VlcVersion"
}

Copy-Item (Join-Path $src "libvlc.dll") $dest
Copy-Item (Join-Path $src "libvlccore.dll") $dest
Copy-Item (Join-Path $src "plugins") (Join-Path $dest "plugins") -Recurse
if (Test-Path (Join-Path $src "hrtfs")) { Copy-Item (Join-Path $src "hrtfs") (Join-Path $dest "hrtfs") -Recurse }
foreach ($f in @("COPYING.txt", "AUTHORS.txt", "README.txt")) {
    if (Test-Path (Join-Path $src $f)) { Copy-Item (Join-Path $src $f) (Join-Path $dest "VLC-$f") }
}

# Eklenti önbelleğini (plugins.dat) yeniden üret: ilk açılış hızlanır.
$cacheGen = Join-Path $src "vlc-cache-gen.exe"
if (Test-Path $cacheGen) {
    & $cacheGen (Join-Path $dest "plugins") | Out-Null
}
$size = [math]::Round(((Get-ChildItem $dest -Recurse | Measure-Object Length -Sum).Sum / 1MB), 1)
Write-Host "libVLC hazır: $dest ($size MB)" -ForegroundColor Green
