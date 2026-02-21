# =============================================================
# GC Toxic Shield — Runtime Path Resolver
# =============================================================
# Modul ini menyediakan path resolution yang kompatibel dengan:
# - Mode development (python main.py)
# - Mode bundled (PyInstaller .exe)
#
# PyInstaller mengekstrak file ke sys._MEIPASS (temp dir),
# tetapi data/model/assets harus dicari di folder .exe berada.
# =============================================================

import os
import sys


def get_app_root() -> str:
    """
    Mendapatkan root directory aplikasi yang benar
    baik di mode development maupun PyInstaller bundle.

    - Development: folder tempat main.py berada
    - PyInstaller:  folder tempat .exe berada
    """
    if getattr(sys, 'frozen', False):
        # PyInstaller bundle → folder tempat .exe berada
        return os.path.dirname(sys.executable)
    else:
        # Development → folder project root (parent dari app/)
        return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def get_bundle_root() -> str:
    """
    Mendapatkan root untuk bundled resources (internal PyInstaller).

    - Development: sama dengan app_root
    - PyInstaller:  sys._MEIPASS (temp extraction dir)
    """
    if getattr(sys, 'frozen', False):
        return sys._MEIPASS
    else:
        return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# ── Pre-resolved paths ──────────────────────────────────────
APP_ROOT = get_app_root()
MODELS_DIR = os.path.join(APP_ROOT, "models")
ASSETS_DIR = os.path.join(APP_ROOT, "assets")
LOGS_DIR = os.path.join(APP_ROOT, "logs")
WORDLIST_PATH = os.path.join(ASSETS_DIR, "word_list.json")
CSV_PATH = os.path.join(LOGS_DIR, "toxic_incidents.csv")
CONFIG_PATH = os.path.join(ASSETS_DIR, "config.json")
ICON_PNG_PATH = os.path.join(ASSETS_DIR, "icon.png")
ICON_ICO_PATH = os.path.join(ASSETS_DIR, "icon.ico")
