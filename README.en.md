> 🌐 **Language:** [🇮🇩 Indonesia](README.md) | 🇺🇸 English

# 🛡️ GC Toxic Shield
**Brand:** GC Net Security Suite  
**Version:** 2.0.0 (PySide6 Edition)  
**Target OS:** Windows 10/11 x64  
**Hardware Profile:** Optimized for maximum CPU efficiency (Integrated Graphics friendly)

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.11-blue.svg" alt="Python Version">
  <img src="https://img.shields.io/badge/GUI-PySide6-green.svg" alt="PySide6">
  <img src="https://img.shields.io/badge/License-Proprietary-red.svg" alt="License">
</p>

## 📌 Project Overview
**GC Toxic Shield** is a *real-time* voice moderation system specifically designed for Internet Cafe (CyberCafe) environments. This application runs quietly in the background, continuously analyzing microphone audio to instantly detect toxic speech or profanity.

Upon detecting a violation, the system enforces gaming discipline by triggering aggressive visual warnings or a full-screen lockdown overlay. This creates a deterrent effect, guaranteeing a peaceful, family-friendly atmosphere within the establishment.

### 🚀 What's New in Edition 2.0.0?
*GC Toxic Shield* has fully migrated to **PySide6** for both Client & Server, accompanied by audio architecture and system security improvements:
- **🎯 7-Stage Deterministic Audio Pipeline (>95% Accuracy):** Complete overhaul of the cybercafe mic audio capture flow. Features *Noise Floor Auto-Calibration* (`adjust_for_ambient_noise`), *Proximity RMS Gate* discarding neighbor shouts (>1m), *Controlled Soft-Limiter (tanh)* 3x gain cap preventing square-wave clipping, and *Character Deduplication* capturing elongated shouted profanity (e.g. `kontooool`).
- **🛡️ Windows Microphone Privacy Guard (Anti-Sabotage):** Closes the tray icon bypass used by kids to disable the mic. Instantly kills `systemsettings.exe` within 10ms and locks the *Microphone Access* toggle via Group Policy (`LetAppsAccessMicrophone = 1`) to a disabled grey state ("Managed by your organization") with 100% clean rollback.
- **🎨 Modern PySide6 UI:** Complete migration from CustomTkinter to PySide6 featuring GPU acceleration, smooth rendering, and consistent QSS styling.
- **🛡️ InstallerGuard (Process-Level Blocker):** Settings, Control Panel, and unsafe execution files are blocked dynamically at the process level without corrupting the OS registry.
- **🌐 Browser Whitelist & Smart Triangulation:** Prevents false positive alerts by whitelisting major browsers (Chrome, Edge, Firefox, etc.) and separates specific targets (e.g., *TikTok Live Studio*) from generic setups based on safe deployment locations (`Program Files`).
- **🖥️ GC Toxic Shield Center Persistence:** Server PC grid mapping is now fully persistent, stored via MAC Address and IP database inside `server_config.json`. Grid is naturally sorted (`PC-2` before `PC-10`) and supports full CRUD actions from the GUI.
- **🔄 Silent Auto-Update:** Clients perform background updates using a hidden batch script (`CREATE_NO_WINDOW`) with `xcopy` retry logic. Prevents any flashing Command Prompt windows during active gameplay.
- **⚡ Multi-Adapter Wake-On-Lan (WOL):** Relays WOL packets through all active network adapters (multi-broadcast IPs) on ports 7 & 9 using the `psutil` library for ultimate reliability.

---

## 🛠️ Key Features

### 1. 🚨 Extended Penalty System (15-Level Cascade)
The system keeps a strict tally of violations for each computer (until the history is wiped):
- **Dual Strike System (2 Warnings + 1 Lockdown):** For every multiple of 3 violations, the user's screen is fully locked down, disabling PC interactions for durations escalating from 1 Minute up to a peak of **20 Minutes**! (Levels 3, 6, 9, 12, 15).
- **Hardened Admin Override & Password Sync:** The *Lockdown Overlay* features a hidden password prompt. Admins can enter the admin password, synced in real-time from the Server, to bypass the penalty.
- **Auto-Forgive:** The violation tracker automatically resets to zero if the user maintains clean speech and good behavior for 60 consecutive minutes.

### 2. 🛡️ Process-Level InstallerGuard & Windows Anti-Sabotage
Aggressive system defense without altering OS Registry values:
- **Lock Windows Settings & Control Panel:** Instantly terminates `systemsettings.exe` and `control.exe` when enabled, blocking users from tampering with network or system settings.
- **Microphone Privacy Lock:** Locks the *Microphone Access* toggle in Windows Settings to a permanently greyed-out state (*"Managed by your organization"*). Clicks on the blue mic tray icon vanish in milliseconds.
- **Smart Installer Blocker:**
  - **Specific Keywords:** Immediately kills blacklisted apps (e.g. *TikTok Live Studio*, *Bytedance*, *TikTok*) regardless of their folder location.
  - **Generic Keywords:** Blocks executable files matching installer keywords (e.g. `setup`, `install`) only if run inside unsafe environments (e.g. `Downloads` or `Desktop`). Setup files in `Program Files` are allowed.
- **Browser Whitelist:** Bypasses major web browsers to avoid accidental termination while users search for related topics.

### 3. 📡 7-Stage Audio Detection Pipeline (>95% Accuracy)
- **Acoustic Auto-Tune:** Measures room background noise (AC, fans, mechanical keyboards) automatically when the mic first opens.
- **Hardware-Level Noise Gate:** Real-time in-memory linear RMS evaluation; eliminates floor hiss (<0.05) and neighboring PC shouts (0.301–0.450) before sending audio to the cloud.
- **Controlled Soft-Limiter (tanh):** 3x maximum gain cap with natural sine curve shaping to eliminate *square-wave clipping* that degrades Google STT accuracy.
- **Adaptive Duration Ceiling (8s):** Caps sentences at 8 seconds to prevent hanging recordings in noisy cybercafe environments.
- **Vocal Deduplication:** Automatic repeated character collapse (`anjinggg` → `anjing`, `kontooool` → `kontol`).
- **Zero False-Positive Context Guard:** Safe context words (`player`, `dealer honda`, `potato peeler`) are checked against pristine text without string mutation.
- **Auto-Recover:** Aggressively recovers and resets the port if the Audio Driver suddenly dies or is unplugged maliciously (*WinError 50* handling).

### 4. 🔄 Silent Auto-Updater
- **1-Liner PowerShell Installer:** Simply paste a short *script* into the Administrator PowerShell on each client PC to deploy.
- **Silent In-App Updater:** Initiates background updates from the Admin Center. Resolves dependencies, extracts archives, and runs `xcopy` retries silently. Auto-restarts client application without interrupting gameplay.

### 5. 🎚 Dynamic Multi-Zone Proximity Filter
Evaluates energy (RMS) of each *audio chunk* in *real-time* and filters based on user-defined energy zones:
- **Zone Builder UI:** Create multiple energy zones (e.g., *Background Noise* → IGNORE, *User Voice* → PROCESS).
- **Real-time VU Meter:** Displays a visual representation of RMS levels while speaking (green = PROCESS, red = IGNORE).
- **Zero-Latency Sync:** Zone configurations apply instantly to the active audio stream without requiring app restarts.

### 6. 🖥️ GC Toxic Shield Center (Server GUI)
A modern PySide6-powered central command deck to manage all client PCs:
- **CRUD PC Grid:** Add, edit (Name, IP, MAC), or delete PC listings persistently through an intuitive interface.
- **Remote Lock Custom Message:** Send remote lockdown commands with custom admin messages displayed on client screens (e.g., "Please maintain quiet in the room").
- **Natural Sorting:** Organizes the PC grid numerically (`PC-1`, `PC-2`, `PC-10`).
- **Data Export:** Export violation history logs directly to **CSV** or **Markdown** formats.
- **Sanction JSON Sync & Blocker Control:** Graphically edit sanctions configuration and toggle client InstallerGuard flags centrally.

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

The `build.py` module is configured using PyInstaller. Simply run this command in your primary Terminal/VSCode:
```bash
python build_tools/build.py
```
The application will be packaged into `GCToxicShield.exe` inside the `dist/GCToxicShield` folder.

---

## 🎮 Windows Defender & Anti-Cheat Compatibility
This application enforces UI trapping that utilizes **Win32 API Global Keyboard Hooks** to intercept *Alt+Tab* and *Windows* key actions when a *Lockdown* punishment drops.

- **Windows Defender:** Add the installation path (`C:\GC Net\GC Toxic Shield`) to Defender's exclusion list to prevent background monitoring from triggering false positive antivirus blocks.
- **Game Anti-Cheat (Vanguard):** Designed to act as passively as possible (only hooks during an active *lockdown*). Disable the hooking manually from the source if clients play strict kernel-level anti-cheat games like Valorant.

---

## 🔒 Security
- **UAC Manifest:** Strictly mandates *Administrator* elevated privileges.
- **Anti-Brute Force:** Entering false *Passwords* at the Lockdown prompt yields forced lockout penalties of up to 30 minutes.
- **Dashboard Authentication:** Can only be accessed or completely terminated via SHA256 Authenticated *Admin Password* (Default `admin123`).

---
*Developed for GC Net.*
