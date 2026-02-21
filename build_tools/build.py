# =============================================================
# GC Toxic Shield — PyInstaller Build Script
# =============================================================
# Engine Swap T9: Sekarang pakai Google Speech (online).
# Build jadi JAUH lebih kecil (~20MB vs ~500MB+)
# karena tidak perlu bundle torch, faster-whisper, ctranslate2.
#
# Usage:
#   python build_tools/build.py
#
# Output:
#   dist/GCToxicShield/
#   ├── GCToxicShield.exe    (executable + admin manifest)
#   ├── assets/              (word_list.json)
#   └── logs/                (auto-created)
# =============================================================

import os
import sys
import subprocess
import shutil

# ── Paths ──
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BUILD_TOOLS = os.path.join(PROJECT_ROOT, "build_tools")
DIST_DIR = os.path.join(PROJECT_ROOT, "dist", "GCToxicShield")
MANIFEST_PATH = os.path.join(BUILD_TOOLS, "gc_toxic_shield.manifest")
MAIN_PY = os.path.join(PROJECT_ROOT, "main.py")


def check_pyinstaller():
    try:
        import PyInstaller
        print(f"  ✓ PyInstaller {PyInstaller.__version__} found")
        return True
    except ImportError:
        print("  ✗ PyInstaller not found! Run: pip install pyinstaller")
        return False


def build():
    print("\n" + "━" * 60)
    print("  GC Toxic Shield — Build Script (Google Speech Edition)")
    print("━" * 60 + "\n")

    if not check_pyinstaller():
        sys.exit(1)

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm",
        "--name", "GCToxicShield",
        "--onedir",                # Startup lebih cepat di PC klien
        "--windowed",              # Produksi: sembunyikan terminal agar lebih aman dari heuristik AV
        "--manifest", MANIFEST_PATH,  # UAC admin prompt → keyboard hook stabil

        # ── Collect-all (UI + Tray + Pillow) ──
        "--collect-all", "customtkinter",   # UI framework — wajib agar tema tidak pecah
        "--collect-all", "pillow",          # Fix 'No module named PIL' di .exe
        "--collect-all", "PIL",             # Explicitly collect PIL namespace
        "--collect-all", "pystray",         # System Tray — ikon + menu

        # ── Hidden imports ──
        "--hidden-import", "speech_recognition",
        "--hidden-import", "pyaudio",
        "--hidden-import", "pystray",
        "--hidden-import", "PIL",
        "--hidden-import", "PIL._tkinter_finder",
        "--hidden-import", "PIL._imagingtk",   # Ikon tray muncul sempurna
        "--hidden-import", "sounddevice",
        "--hidden-import", "customtkinter",
        "--hidden-import", "numpy",            # Dibutuhkan untuk gain audio
        "--hidden-import", "ctypes",
        "--hidden-import", "requests",
        "--hidden-import", "pkg_resources.extern",
        "--hidden-import", "watchdog",

        # App modules
        "--hidden-import", "app._paths",
        "--hidden-import", "app.audio_engine",
        "--hidden-import", "app.detector",
        "--hidden-import", "app.logger_service",
        "--hidden-import", "app.overlay",
        "--hidden-import", "app.penalty_manager",
        "--hidden-import", "app.desktop_guard",
        "--hidden-import", "app.ui_manager",
        "--hidden-import", "app.system_service",
        "--hidden-import", "app.auth_service",
        "--hidden-import", "app.login_dialog",
        "--hidden-import", "app.static_data",

        # ── Exclude bloat (AI offline + lib tidak terpakai) ──
        "--exclude-module", "torch",
        "--exclude-module", "torchaudio",
        "--exclude-module", "faster_whisper",
        "--exclude-module", "ctranslate2",
        "--exclude-module", "scipy",
        "--exclude-module", "matplotlib",
        "--exclude-module", "notebook",
        "--exclude-module", "cv2",
        "--exclude-module", "pytest",
        "--exclude-module", "test",
        "--exclude-module", "unittest",
        "--exclude-module", "numba",
        "--exclude-module", "llvmlite",
        "--exclude-module", "librosa",
        "--exclude-module", "pandas",
        "--exclude-module", "pocketsphinx",
        "--exclude-module", "sphinx",
        "--exclude-module", "lxml",
        "--exclude-module", "h5py",
        "--exclude-module", "sklearn",
        "--exclude-module", "tkinter.test",

        # Icon
        "--icon", os.path.join(PROJECT_ROOT, "assets", "icon.ico"),

        # Output
        "--distpath", os.path.join(PROJECT_ROOT, "dist"),
        "--workpath", os.path.join(PROJECT_ROOT, "build"),
        "--specpath", BUILD_TOOLS,

        MAIN_PY,
    ]

    print("  Building (much smaller now — no torch/whisper!)...")
    print()

    result = subprocess.run(cmd, cwd=PROJECT_ROOT)

    if result.returncode != 0:
        print("\n  ✗ Build FAILED!")
        sys.exit(1)

    print("\n  ✓ Build completed!")

    # ── Copy Assets ──
    print("\n  Copying assets...")

    assets_src = os.path.join(PROJECT_ROOT, "assets")
    assets_dst = os.path.join(DIST_DIR, "assets")
    if os.path.isdir(assets_src):
        shutil.copytree(assets_src, assets_dst, dirs_exist_ok=True)
        print(f"  ✓ assets/ → {assets_dst}")

    logs_dst = os.path.join(DIST_DIR, "logs")
    os.makedirs(logs_dst, exist_ok=True)
    print(f"  ✓ logs/ created")

    # ── Post-Build Cleanup (Crucial for <30MB size) ──
    print("\n  Cleaning up offline AI bloat...")
    bloat_files = [
        "language-model.lm.bin",
        "pronounciation-dictionary.dict",
        "mdef",
        "sendump",
        "logdists",
        "feat.params",
        "variances",
        "transition_matrices",
        "means",
        "mixture_weights",
        "noisedict",
        "feature_transform",
    ]
    
    # Remove files
    cleanup_count = 0
    for root, dirs, files in os.walk(DIST_DIR):
        for name in files:
            if name in bloat_files or name.startswith("mfc140"):
                try:
                    os.remove(os.path.join(root, name))
                    print(f"    - Removed: {name}")
                    cleanup_count += 1
                except Exception as e:
                    print(f"    ! Failed to remove {name}: {e}")
            elif name.endswith(".pyd") and ("scipy" in name or "sklearn" in name):
                 try:
                    os.remove(os.path.join(root, name))
                    print(f"    - Removed: {name}")
                    cleanup_count += 1
                 except Exception:
                    pass
            elif "linux" in name or "darwin" in name or "macos" in name:
                try:
                    os.remove(os.path.join(root, name))
                    print(f"    - Removed OS bloat: {name}")
                    cleanup_count += 1
                except Exception:
                    pass

    print(f"  ✓ Cleanup finished ({cleanup_count} files removed)")

    # ── Summary ──
    print("\n" + "━" * 60)
    print("  ✅ BUILD SUCCESSFUL!")
    print(f"  Output: {DIST_DIR}")
    print()
    print("  Isi distribusi:")
    print("    GCToxicShield.exe  ← Jalankan (auto UAC prompt)")
    print("    _internal/         ← Runtime + DLLs")
    print("    assets/            ← word_list.json")
    print("    logs/              ← CSV output")
    print()
    print("  ⚠ PENTING: PC klien HARUS punya koneksi internet!")
    print("    Engine sekarang menggunakan Google Speech (online).")
    print()
    print("  Deploy:")
    print("    1. Copy dist/GCToxicShield/ ke target PC")
    print("    2. Pastikan internet aktif")
    print("    3. Jalankan GCToxicShield.exe")
    print("━" * 60 + "\n")


if __name__ == "__main__":
    build()
