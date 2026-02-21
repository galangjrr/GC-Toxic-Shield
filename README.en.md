> 🌐 **Language:** [🇮🇩 Indonesia](README.md) | 🇺🇸 English

# 🛡️ GC Toxic Shield
**Brand:** GC Net Security Suite  
**Version:** 1.0 (Google Speech Edition)  
**Target OS:** Windows 10/11 x64  
**Hardware Profile:** Optimized for maximum CPU efficiency (Integrated Graphics friendly)

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.11-blue.svg" alt="Python Version">
  <img src="https://img.shields.io/badge/GUI-CustomTkinter-blueviolet.svg" alt="CustomTkinter">
  <img src="https://img.shields.io/badge/License-Proprietary-red.svg" alt="License">
</p>

## 📌 Project Overview
**GC Toxic Shield** is a *real-time* voice moderation system specifically designed for Internet Cafe (CyberCafe) environments. This application runs quietly in the background, continuously analyzing microphone audio to instantly detect toxic speech or profanity.

Upon detecting a violation, the system enforces gaming discipline by triggering aggressive visual warnings or a full-screen lockdown overlay. This creates a deterrent effect, guaranteeing a peaceful, family-friendly atmosphere within the establishment.

### 🚀 What's New in Edition 1.0?
*GC Toxic Shield* has fully transitioned into a **Cloud-Based Online Engine (Google Speech Recognition)**.
- **⚡ Ultra-lightweight:** Application size has been drastically reduced from `~500MB` down to just `~65MB`.
- **💻 Maximum Performance:** Static memory and CPU footprints are suppressed, ensuring $0$ impact on client PC gaming *Frame Rates (FPS)*.
- **🎙️ Smart Digital Gain:** Dual volume management directly from the Admin Dashboard for low-sensitivity microphones.

---

## 🛠️ Key Features

### 1. 🚨 Extended Penalty System (15-Level Cascade)
The system keeps a strict tally of violations for each computer (until the history is wiped):
- **Dual Strike System (2 Warnings + 1 Lockdown):** For every multiple of 3 violations, the user's screen is fully locked down, disabling PC interactions for durations escalating from 1 Minute up to a peak of **20 Minutes**! (Levels 3, 6, 9, 12, 15).
- **Hardened Admin Override:** The *Lockdown Overlay* features a hidden password prompt. Admins can hit a secret button to bypass the punishment; _however_, this does not reset the violation count back to zero unless deliberately cleared from the Dashboard.
- **Auto-Forgive:** The violation tracker automatically resets to zero if the user maintains clean speech and good behavior for 60 consecutive minutes.

### 2. 🛡️ Surgical Desktop Guard & Settings Block
Locking down the OS without breaking the UX Explorer:
- **Block Editing (Anti-Tampering):** Users can safely refresh the desktop without the "vanishing icons bug," but are strictly prohibited from creating folders, deleting, or pasting foreign files onto the Desktop. (The *Watchdog Engine* instantly deletes alien files in milliseconds and displays a visual reprimand).
- **Settings Lock:** Severs access to the Windows *Settings* app & *Control Panel* to paralyze any tampering attempts.

### 3. 📡 Non-Stop Cloud Detection
- **Cloud STT id-ID:** *Speech-to-Text* sensor piped directly through Google Cloud utilizing Exact Word Boundary Regex.
- **Auto-Recover:** Aggressively recovers and resets the port if the Audio Driver suddenly dies or is unplugged maliciously (*WinError 50* handling).
- **Hot-Reload Wordlist:** Instantly update the list of "Primary Words" and "Alias/Typo Words" from the Admin interface.

### 4. 🔄 GitHub Auto-Updater & One-Click Deploy
- **1-Liner PowerShell Installer:** Simply paste a short *script* into the Administrator PowerShell on each client PC, and GC Toxic Shield will automatically download the latest release from your GitHub repository and drop a shortcut on the Desktop.
- **In-App Updater:** Features a dedicated *Update* button within the *Admin Dashboard*. It asynchronously polls the _latest release_ from GitHub and seamlessly reconstructs the *executable* without destroying the local JSON configurations of the CyberCafe.

---

## 💻 Instant Installation (Client PC)

Deploying to client PCs in the CyberCafe is incredibly easy—no manual *Copy-Paste* required! Follow these steps:
1. Open **PowerShell** on the Client PC *(Must be run as Administrator)*.
2. Copy and Paste the following magic one-liner:
   ```powershell
   iex (irm "https://raw.githubusercontent.com/galangjrr/GC-Toxic-Shield/main/install.ps1")
   ```
3. Press **Enter**. The application will instantly download, extract itself into `C:\GC Net\`, and miraculously drop a shortcut straight onto the Client's *Desktop* in under 5 seconds!

---

## ⚙️ Architecture & Build
The `build.py` module is manually configured. Simply run this command in your primary Terminal/VSCode:
```bash
python build_tools/build.py
```
The application will be packaged into `GCToxicShield.exe` (independent of system bloatware) inside the `dist/GC Toxic Shield` folder.

---

## 🎮 Windows Defender & Anti-Cheat Compatibility
This application enforces UI trapping that utilizes **Win32 API Global Keyboard Hooks** to intercept *Alt+Tab* and *Windows* key actions when a *Lockdown* punishment drops.

- **Windows Defender:** Add the installation path (`C:\GC Net\GC Toxic Shield`) to Defender's exclusion/whitelist to prevent the Desktop Guard feature from being flagged as a *Trojan* or malicious system limiter.
- **Game Anti-Cheat (Vanguard):** Designed to act as passively as possible (only hooks during an active *lockdown*). Disable the hooking manually from the source if clients play strict kernel-level anti-cheat games like Valorant.

---

## 🔒 Security
- **UAC Manifest:** Strictly mandates *Administrator* elevated privileges.
- **Anti-Brute Force:** Entering false *Passwords* at the Lockdown prompt yields forced lockout penalties of up to 30 minutes.
- **Dashboard Authentication:** Can only be accessed or completely terminated via SHA256 Authenticated *Admin Password* (Default `admin123`).

---
*Developed for GC Net.*
