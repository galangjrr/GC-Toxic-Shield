<#
.SYNOPSIS
Memperbaiki Control Panel dan Group Policy yang terkunci atau error (Corrupted Registry/Policies).

.DESCRIPTION
Script ini menghapus kunci registry "NoControlPanel" dan membersihkan pengaturan lokal
Group Policy yang kemungkinan bertabrakan / corrupt akibat bug toggle versi sebelumnya.
Jalankan script ini sebagai Administrator.
#>

Write-Host "===================================================" -ForegroundColor Cyan
Write-Host "    GC Toxic Shield - Emergency Repair Tool" -ForegroundColor Cyan
Write-Host "===================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Memulai perbaikan Control Panel dan Group Policy..."
Write-Host ""

try {
    # 1. Menghapus key NoControlPanel dari CurrentUser (HKCU)
    Write-Host "[1/4] Membersihkan pembatasan Control Panel di HKCU..."
    $pathHKCU = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Policies\Explorer"
    if (Test-Path $pathHKCU) {
        Remove-ItemProperty -Path $pathHKCU -Name "NoControlPanel" -ErrorAction SilentlyContinue
        Write-Host "  -> Berhasil." -ForegroundColor Green
    }
    else {
        Write-Host "  -> Key tidak ditemukan (Aman)." -ForegroundColor Yellow
    }

    # 2. Menghapus key NoControlPanel dari LocalMachine (HKLM) (Untuk jaga-jaga)
    Write-Host "[2/4] Membersihkan pembatasan Control Panel di HKLM..."
    $pathHKLM = "HKLM:\Software\Microsoft\Windows\CurrentVersion\Policies\Explorer"
    if (Test-Path $pathHKLM) {
        Remove-ItemProperty -Path $pathHKLM -Name "NoControlPanel" -ErrorAction SilentlyContinue
        Write-Host "  -> Berhasil." -ForegroundColor Green
    }
    else {
        Write-Host "  -> Key tidak ditemukan (Aman)." -ForegroundColor Yellow
    }

    # 3. Menghapus folder Machine dan User dari System32\GroupPolicy yang corrupt
    Write-Host "[3/4] Me-reset file Group Policy (gpedit) lokal yang error..."
    $gpDir = "$env:windir\System32\GroupPolicy"
    
    if (Test-Path "$gpDir\Machine") {
        Remove-Item -Path "$gpDir\Machine" -Recurse -Force -ErrorAction SilentlyContinue
    }
    if (Test-Path "$gpDir\User") {
        Remove-Item -Path "$gpDir\User" -Recurse -Force -ErrorAction SilentlyContinue
    }
    Write-Host "  -> Berhasil dihapus." -ForegroundColor Green

    # 4. Melakukan pemaksaan update Group Policy
    Write-Host "[4/4] Memperbarui Group Policy secara paksa..."
    gpupdate /force
    Write-Host "  -> Berhasil diupdate." -ForegroundColor Green

    Write-Host ""
    Write-Host "===================================================" -ForegroundColor Cyan
    Write-Host "    PERBAIKAN SELESAI!" -ForegroundColor Green
    Write-Host "===================================================" -ForegroundColor Cyan
    Write-Host "Silahkan coba buka kembali Control Panel atau gpedit.msc."
    Write-Host ""
}
catch {
    Write-Host "Error saat mengeksekusi perbaikan: $_" -ForegroundColor Red
}

Write-Host "Tekan Enter untuk keluar..."
Read-Host
