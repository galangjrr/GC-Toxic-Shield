# ==============================================================================
# GC Toxic Shield - GitHub Auto Installer (One-Liner)
# ==============================================================================
# Skrip ini digunakan untuk mengunduh, mengekstrak, dan membuat Shortcut 
# dari rilis GitHub terbaru ke dalam direktori instalasi Warnet Anda secara otomatis.
#
# CARA PENGGUNAAN (Buka PowerShell sebagai Administrator):
# iex (irm "https://raw.githubusercontent.com/USERNAME/REPO_NAME/main/install.ps1")
# ==============================================================================

$ErrorActionPreference = "Stop"

# ⚠️ UBAH REPOSITORY INI SESUAI DENGAN AKUN GITHUB ANDA NANTI ⚠️
$githubRepo = "galangjrr/GC-Toxic-Shield" 
# =================================================================

$installDir = "C:\GC Net\GC Toxic Shield"
$exeName = "GC Toxic Shield.exe"
$releaseApiUrl = "https://api.github.com/repos/$githubRepo/releases/latest"

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host " GC Toxic Shield - Auto Installer " -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan

# 1. Pastikan berjalan sebagai Administrator
$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Write-Warning "Skrip ini WAJIB dijalankan dengan akses Administrator!"
    Write-Warning "Silakan buka PowerShell -> Klik kanan -> Run as Administrator."
    Exit
}

# 2. Hentikan aplikasi jika sedang berjalan (agar file bisa ditimpa)
if (Get-Process $exeName.Replace(".exe", "") -ErrorAction SilentlyContinue) {
    Write-Host "=> Mematikan GC Toxic Shield yang sedang berjalan..." -ForegroundColor Yellow
    Stop-Process -Name $exeName.Replace(".exe", "") -Force -ErrorAction SilentlyContinue
    Start-Sleep -Seconds 3
}

# 3. Buat Folder Instalasi
if (-not (Test-Path $installDir)) {
    Write-Host "=> Membuat direktori $installDir..."
    New-Item -ItemType Directory -Force -Path $installDir | Out-Null
}

# 4. Ambil Info Rilis Terbaru via GitHub API
Write-Host "=> Memeriksa GitHub untuk versi terbaru ($githubRepo)..."
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

try {
    $releaseInfo = Invoke-RestMethod -Uri $releaseApiUrl
    $version = $releaseInfo.tag_name
    Write-Host "- Versi ditemukan: $version" -ForegroundColor Green
    
    # Cari di Assets yang bereksistensi .zip
    $downloadUrl = $releaseInfo.assets | Where-Object { $_.name -like "*.zip" } | Select-Object -ExpandProperty browser_download_url -First 1
    
    if (-not $downloadUrl) {
        throw "File berekstensi .zip tidak ditemukan di daftar Assets Release ini."
    }
}
catch {
    if ($_.Exception.Message -match "404") {
        Write-Error "API GitHub mengembalikan error 404 (Not Found)."
        Write-Error "🚨 PENTING: Anda belum membuat 'Release' publik di repository GitHub Anda!"
        Write-Error "🚨 Silakan buka GitHub -> Releases -> Draft a new release -> Unggah GC Toxic Shield.zip."
    }
    else {
        Write-Error "GAGAL mengakses GitHub API. Pastikan nama repository benar dan publik."
        Write-Error $_.Exception.Message
    }
    Exit
}

# 5. Mulai Mengunduh
$tempZipPath = Join-Path $env:TEMP "GC_Toxic_Shield_Install.zip"
Write-Host "=> Mengunduh file dari GitHub..."
Write-Host "- URL: $downloadUrl"
Invoke-WebRequest -Uri $downloadUrl -OutFile $tempZipPath

# 6. Ekstrak Berkas Zip
Write-Host "=> Mengekstrak file ke $installDir..."
$tempExt = Join-Path $env:TEMP 'GCT_Install_Ext'
if (Test-Path $tempExt) { Remove-Item -Recurse -Force $tempExt }
Expand-Archive -Path $tempZipPath -DestinationPath $tempExt -Force

# Cari exe untuk mengetahui di mana persisnya letak root folder dari aplikasi di dalam zip
$exePath = Get-ChildItem -Path $tempExt -Filter $exeName -Recurse | Select-Object -First 1
if (-not $exePath) {
    throw "Gagal menemukan '$exeName' di dalam file unduhan zip."
}

$sourceDir = $exePath.Directory.FullName
Copy-Item -Path "$sourceDir\*" -Destination $installDir -Recurse -Force

Remove-Item -Recurse -Force $tempExt
Remove-Item $tempZipPath -Force

# 7. Membuat Shortcut di Desktop
Write-Host "=> Membuat Shortcut di Desktop..."
$WshShell = New-Object -comObject WScript.Shell
$desktopPath = [Environment]::GetFolderPath("Desktop")
$shortcut = $WshShell.CreateShortcut("$desktopPath\GC Toxic Shield.lnk")
$shortcut.TargetPath = "$installDir\$exeName"
$shortcut.WorkingDirectory = $installDir
# Kalau icon ada di dalam sub-folder assets
$iconPath = "$installDir\assets\icon.ico"
if (Test-Path $iconPath) {
    $shortcut.IconLocation = $iconPath
}
$shortcut.Save()

Write-Host "==========================================" -ForegroundColor Green
Write-Host " INSTALASI BERHASIL! " -ForegroundColor Green
Write-Host " Aplikasi terpasang di: $installDir" -ForegroundColor Green
Write-Host "==========================================" -ForegroundColor Green

# 8. Otomatis Menjalankan Aplikasi
Write-Host "=> Menjalankan Aplikasi..."
Start-Process -FilePath "$installDir\$exeName" -WorkingDirectory $installDir
