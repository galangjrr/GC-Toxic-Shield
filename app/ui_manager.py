# =============================================================
# GC Toxic Shield — Task T5: Admin Dashboard (CustomTkinter)
# =============================================================
# Module ini bertanggung jawab untuk:
# 1. Tab Live Monitor: Transkripsi real-time + VU Meter
# 2. Tab Wordlist: Tambah/hapus kata + hot-reload detector
# 3. Tab Logs: Viewer toxic_incidents.csv
# 4. Tab Admin: Audio Controls (Gain/Device), Safety Exit, Auto-Start
# =============================================================

import os
import csv
import json
import threading
import time
import logging
import tkinter as tk

try:
    import customtkinter as ctk
except ImportError:
    ctk = None

from typing import Optional, Callable, TYPE_CHECKING

if TYPE_CHECKING:
    from app.detector import ToxicDetector
    from app.logger_service import LoggerService

# ── Logging ────────────────────────────────────────────────────
logger = logging.getLogger("GCToxicShield.UI")

# ── Constants ──────────────────────────────────────────────────
REFRESH_INTERVAL_MS = 2000    # Refresh Logs/Stats setiap 2 detik
VU_METER_INTERVAL_MS = 50     # Refresh VU Meter setiap 50ms (smooth)
WINDOW_WIDTH = 900
WINDOW_HEIGHT = 800  # Diperbesar agar semua menu admin muat

# ── Paths (PyInstaller-compatible) ─────────────────────────────
from app._paths import WORDLIST_PATH, CSV_PATH, ICON_ICO_PATH


class AdminDashboard:
    """
    Task T5: Admin Dashboard UI menggunakan CustomTkinter.
    Dilengkapi Audio Control & VU Meter (T7).
    """

    def __init__(
        self,
        logger_service: "LoggerService",
        detector: "ToxicDetector",
        penalty_mgr=None,
        engine=None,
        auth_service=None,
        app_version: str = "1.0.0",
        github_repo: str = "",
        on_close: Optional[Callable] = None,
    ):
        self._logger_service = logger_service
        self._detector = detector
        self._penalty_mgr = penalty_mgr
        self._engine = engine
        self._auth = auth_service
        self._app_version = app_version
        self._github_repo = github_repo
        self._desktop_guard = None  # Akan diset dari main.py
        self._on_close = on_close
        self._root: Optional[ctk.CTk] = None
        self._timers = []

        # UI Components
        self._monitor_textbox = None
        self._vu_progress = None
        self._wordlist_listbox = None
        self._word_entry = None
        self._logs_textbox = None
        self._status_label = None
        self._stats_label = None

        # Audio Controls
        self._device_dropdown = None
        self._gain_slider = None
        self._gain_label = None

    @property
    def root(self) -> Optional[ctk.CTk]:
        return self._root

    def build(self) -> ctk.CTk:
        """Membangun UI dan mengembalikan root window."""
        if ctk is None:
            raise ImportError(
                "customtkinter is required. Install via: pip install customtkinter"
            )

        # ── Theme Setup ──
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        # ── Root Window ──
        self._root = ctk.CTk()
        self._root.title("🛡️ GC Toxic Shield — Admin Dashboard")
        
        # Center Window
        self._root.update_idletasks()
        ws = self._root.winfo_screenwidth()
        hs = self._root.winfo_screenheight()
        x = (ws // 2) - (WINDOW_WIDTH // 2)
        y = (hs // 2) - (WINDOW_HEIGHT // 2)
        self._root.geometry(f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}+{x}+{y}")
        
        self._root.minsize(800, 500)
        self._root.protocol("WM_DELETE_WINDOW", self._handle_close)
        
        # Set Icon
        try:
            if os.path.exists(ICON_ICO_PATH):
                self._root.iconbitmap(ICON_ICO_PATH)
        except Exception as e:
            logger.warning("Failed to set window icon: %s", e)

        # ── Header ──
        self._build_header()

        # ── Tabview ──
        self._tabview = ctk.CTkTabview(self._root, corner_radius=10)
        self._tabview.pack(fill="both", expand=True, padx=15, pady=(5, 10))

        # Create tabs
        tab_monitor = self._tabview.add("📡 Monitor")
        tab_wordlist = self._tabview.add("📝 Daftar Kata")
        tab_logs = self._tabview.add("📊 Logs")
        tab_sanctions = self._tabview.add("📜 Sanksi & Pesan")
        tab_admin = self._tabview.add("⚙ Admin")

        self._build_monitor_tab(tab_monitor)
        self._build_wordlist_tab(tab_wordlist)
        self._build_logs_tab(tab_logs)
        self._build_sanctions_tab(tab_sanctions)
        self._build_admin_tab(tab_admin)

        # ── Global Emergency Hotkey: Ctrl+Shift+Q ──
        self._root.bind_all(
            "<Control-Shift-Q>",
            lambda e: self._emergency_exit()
        )

        # ── Status Bar ──
        self._build_status_bar()

        # ── Start Timers ──
        self._schedule_refresh()      # Logs/Text (slow)
        self._schedule_vu_meter()     # VU Meter (fast)

        logger.info("✓ Admin Dashboard built (%dx%d)", WINDOW_WIDTH, WINDOW_HEIGHT)
        return self._root

    # ================================================================
    # HEADER
    # ================================================================

    def _build_header(self):
        header = ctk.CTkFrame(self._root, height=60, corner_radius=0)
        header.pack(fill="x", padx=15, pady=(10, 5))
        header.pack_propagate(False)

        title = ctk.CTkLabel(
            header,
            text="🛡️ GC Toxic Shield",
            font=ctk.CTkFont(size=22, weight="bold"),
        )
        title.pack(side="left", padx=15)

        self._stats_label = ctk.CTkLabel(
            header,
            text="",
            font=ctk.CTkFont(size=13),
            text_color="#aaaaaa",
        )
        self._stats_label.pack(side="right", padx=15)

    # ================================================================
    # TAB 1: LIVE MONITOR (with VU Meter)
    # ================================================================

    def _build_monitor_tab(self, parent):
        """Tab Live Monitor: Transkripsi + VU Meter."""

        # ── VU Meter Bar (Top) ──
        vu_frame = ctk.CTkFrame(parent, height=40, fg_color="transparent")
        vu_frame.pack(fill="x", pady=(5, 10))

        ctk.CTkLabel(
            vu_frame,
            text="🔊 Mic Level:",
            font=ctk.CTkFont(size=12, weight="bold"),
        ).pack(side="left", padx=(5, 10))

        self._vu_progress = ctk.CTkProgressBar(
            vu_frame,
            height=15,
            corner_radius=8,
            mode="determinate",
        )
        self._vu_progress.pack(side="left", fill="x", expand=True, padx=5)
        self._vu_progress.set(0.0)

        # ── Controls bar ──
        controls = ctk.CTkFrame(parent, height=40)
        controls.pack(fill="x", pady=(0, 5))

        ctk.CTkLabel(
            controls,
            text="Live Transcription (Real-time)",
            font=ctk.CTkFont(size=13),
            text_color="#aaaaaa",
        ).pack(side="left", padx=10)

        ctk.CTkButton(
            controls,
            text="🔄 Refresh Text",
            width=100,
            height=32,
            command=self._refresh_monitor,
        ).pack(side="right", padx=5)

        # ── Text display ──
        self._monitor_textbox = ctk.CTkTextbox(
            parent,
            font=ctk.CTkFont(family="Consolas", size=13),
            corner_radius=8,
            state="disabled",
        )
        self._monitor_textbox.pack(fill="both", expand=True, pady=(0, 5))

    def _refresh_monitor(self):
        """Refresh teks transkripsi (slow update)."""
        if not self._monitor_textbox or not self._logger_service:
            return

        buffer = self._logger_service.get_buffer()

        self._monitor_textbox.configure(state="normal")
        self._monitor_textbox.delete("1.0", "end")
        
        # Tambahkan indikator waktu agar user tahu tombol refresh bekerja
        current_time = time.strftime("%H:%M:%S")
        self._monitor_textbox.insert("end", f"  [Live Monitor — Diperbarui: {current_time}]\n")
        self._monitor_textbox.insert("end", "  " + "━" * 80 + "\n\n")

        if not buffer:
            self._monitor_textbox.insert("end", "  (Belum ada transkripsi... bicara sekarang!)\n")
        else:
            for entry in buffer:
                icon = "🚨" if entry.is_toxic else "✅"
                tag = "TOXIC" if entry.is_toxic else "SAFE"
                words_str = ""
                if entry.matched_words:
                    words_str = f" [{', '.join(entry.matched_words)}]"
                
                # Highlight toxic lines logic could be added here
                line = f"  {icon} [{entry.timestamp}] [{tag}] {entry.text}{words_str}\n"
                self._monitor_textbox.insert("end", line)

        self._monitor_textbox.configure(state="disabled")
        self._monitor_textbox.see("end")  # Auto-scroll

        # Update stats header
        if self._stats_label:
            stats = self._logger_service.stats
            self._stats_label.configure(
                text=(
                    f"Logged: {stats['total_logged']} | "
                    f"Toxic: {stats['total_toxic']} | "
                    f"Buffer: {stats['buffer_size']}"
                )
            )

    def _update_vu_meter(self):
        """Update progress bar dari RMS audio engine (fast update)."""
        if self._engine and self._vu_progress:
            level = self._engine.get_vu_level()
            self._vu_progress.set(level)

            # Change color based on level (optional visual enhancement)
            # CustomTkinter progress bar color change is tricky dynamically,
            # so we stick to default color for now.

    # ================================================================
    # TAB 2: WORDLIST
    # ================================================================

    def _build_wordlist_tab(self, parent):
        """Tab Daftar Kata: 2 Kolom (Kata Utama vs Variasi/Alias)."""

        main_frame = ctk.CTkFrame(parent, fg_color="transparent")
        main_frame.pack(fill="both", expand=True, padx=10, pady=10)
        main_frame.grid_columnconfigure((0, 1), weight=1)

        # ── Kolom Kiri: Kata Terlarang (Blocked Words) ──
        left_col = ctk.CTkFrame(main_frame)
        left_col.grid(row=0, column=0, sticky="nsew", padx=(0, 5))

        ctk.CTkLabel(
            left_col, text="🚫 Daftar Kata Terlarang", font=ctk.CTkFont(size=16, weight="bold")
        ).pack(pady=(10, 5))

        listbox_frame_l = ctk.CTkFrame(left_col)
        listbox_frame_l.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        self._wordlist_listbox = tk.Listbox(
            listbox_frame_l, font=("Consolas", 13),
            bg="#2b2b2b", fg="#ffffff", selectbackground="#c62828",
            borderwidth=0, highlightthickness=0, activestyle="none"
        )
        self._wordlist_listbox.pack(side="left", fill="both", expand=True)
        scroll_l = ctk.CTkScrollbar(listbox_frame_l, command=self._wordlist_listbox.yview)
        scroll_l.pack(side="right", fill="y")
        self._wordlist_listbox.configure(yscrollcommand=scroll_l.set)

        self._wordlist_listbox.bind("<<ListboxSelect>>", self._on_word_select)

        # Input & Tombol Kiri
        input_frame_l = ctk.CTkFrame(left_col, fg_color="transparent")
        input_frame_l.pack(fill="x", padx=10, pady=(0, 10))

        self._word_entry = ctk.CTkEntry(input_frame_l, placeholder_text="Tambah kata utama baru...", height=35)
        self._word_entry.pack(fill="x", pady=(0, 5))
        self._word_entry.bind("<Return>", lambda e: self._add_word())

        btn_row_l = ctk.CTkFrame(input_frame_l, fg_color="transparent")
        btn_row_l.pack(fill="x")
        ctk.CTkButton(
            btn_row_l, text="➕ Tambah", width=100, fg_color="#2e7d32", hover_color="#1b5e20", command=self._add_word
        ).pack(side="left", expand=True, fill="x", padx=(0, 5))
        ctk.CTkButton(
            btn_row_l, text="🗑️ Hapus", width=100, fg_color="#c62828", hover_color="#b71c1c", command=self._remove_word
        ).pack(side="left", expand=True, fill="x")

        # ── Kolom Kanan: Variasi / Alias (Mirip / Typo) ──
        right_col = ctk.CTkFrame(main_frame)
        right_col.grid(row=0, column=1, sticky="nsew", padx=(5, 0))

        ctk.CTkLabel(
            right_col, text="🔠 Variasi / Alias Kata (Diizinkan jika ada typo)", font=ctk.CTkFont(size=16, weight="bold")
        ).pack(pady=(10, 5))
        
        self._alias_subtitle = ctk.CTkLabel(
            right_col, text="Pilih kata di kolom kiri terlebih dahulu.", font=ctk.CTkFont(size=12), text_color="#aaaaaa"
        )
        self._alias_subtitle.pack(pady=(0, 5))

        listbox_frame_r = ctk.CTkFrame(right_col)
        listbox_frame_r.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        self._alias_listbox = tk.Listbox(
            listbox_frame_r, font=("Consolas", 13),
            bg="#2b2b2b", fg="#ffffff", selectbackground="#1a73e8",
            borderwidth=0, highlightthickness=0, activestyle="none",
            state="disabled"
        )
        self._alias_listbox.pack(side="left", fill="both", expand=True)
        scroll_r = ctk.CTkScrollbar(listbox_frame_r, command=self._alias_listbox.yview)
        scroll_r.pack(side="right", fill="y")
        self._alias_listbox.configure(yscrollcommand=scroll_r.set)

        # Input & Tombol Kanan
        input_frame_r = ctk.CTkFrame(right_col, fg_color="transparent")
        input_frame_r.pack(fill="x", padx=10, pady=(0, 10))

        self._alias_entry = ctk.CTkEntry(input_frame_r, placeholder_text="Tambah variasi / typo...", height=35, state="disabled")
        self._alias_entry.pack(fill="x", pady=(0, 5))
        self._alias_entry.bind("<Return>", lambda e: self._add_alias())

        btn_row_r = ctk.CTkFrame(input_frame_r, fg_color="transparent")
        btn_row_r.pack(fill="x")
        self._btn_add_alias = ctk.CTkButton(
            btn_row_r, text="➕ Tambah", width=100, fg_color="#2e7d32", hover_color="#1b5e20", command=self._add_alias, state="disabled"
        )
        self._btn_add_alias.pack(side="left", expand=True, fill="x", padx=(0, 5))
        self._btn_add_alias_del = ctk.CTkButton(
            btn_row_r, text="🗑️ Hapus", width=100, fg_color="#c62828", hover_color="#b71c1c", command=self._remove_alias, state="disabled"
        )
        self._btn_add_alias_del.pack(side="left", expand=True, fill="x")

        # Reload Button (Global)
        ctk.CTkButton(
            parent, text="🔄 Segarkan (Reload Detector)", height=35, command=self._reload_wordlist
        ).pack(fill="x", padx=10, pady=(0, 10))

        # Initial Load
        self._selected_word = None
        self._refresh_words_display()

    # ── Callbacks Kiri (Words) ──
    def _refresh_words_display(self):
        if not self._wordlist_listbox: return
        data = self._load_wordlist_json()
        toxic_words = sorted(set(data.get("toxic_words", [])))
        
        self._wordlist_listbox.delete(0, "end")
        for word in toxic_words:
            self._wordlist_listbox.insert("end", f"  {word}")
            
        # Reset selection state
        self._selected_word = None
        self._refresh_aliases_display()

    def _on_word_select(self, event=None):
        sel = self._wordlist_listbox.curselection()
        if not sel:
            self._selected_word = None
        else:
            self._selected_word = self._wordlist_listbox.get(sel[0]).strip()
        self._refresh_aliases_display()

    def _add_word(self):
        word = self._word_entry.get().strip().lower()
        if not word: return
        
        data = self._load_wordlist_json()
        words = data.get("toxic_words", [])
        
        if word in [w.lower() for w in words]:
            self._word_entry.delete(0, "end")
            return
            
        words.append(word)
        data["toxic_words"] = words
        self._save_wordlist_json(data)
        
        self._detector.reload_wordlist()
        self._refresh_words_display()
        self._word_entry.delete(0, "end")

    def _remove_word(self):
        if not self._selected_word: return
        
        data = self._load_wordlist_json()
        words = data.get("toxic_words", [])
        mapping = data.get("phonetic_mapping", {})
        
        # Hapus kata
        words = [w for w in words if w.lower() != self._selected_word.lower()]
        data["toxic_words"] = words
        
        # Hapus semua alias yang merujuk ke kata tersebut
        keys_to_delete = [k for k, v in mapping.items() if v.lower() == self._selected_word.lower()]
        for k in keys_to_delete:
            del mapping[k]
        data["phonetic_mapping"] = mapping
        
        self._save_wordlist_json(data)
        self._detector.reload_wordlist()
        self._refresh_words_display()

    # ── Callbacks Kanan (Aliases) ──
    def _refresh_aliases_display(self):
        if not self._alias_listbox: return
        
        self._alias_listbox.configure(state="normal")
        self._alias_listbox.delete(0, "end")
        
        if not self._selected_word:
            self._alias_subtitle.configure(text="Pilih kata di kolom kiri terlebih dahulu.")
            self._alias_entry.configure(state="disabled")
            self._btn_add_alias.configure(state="disabled")
            self._btn_add_alias_del.configure(state="disabled")
            self._alias_listbox.configure(state="disabled")
            return
            
        self._alias_subtitle.configure(text=f"Alias untuk: '{self._selected_word}'")
        self._alias_entry.configure(state="normal")
        self._btn_add_alias.configure(state="normal")
        self._btn_add_alias_del.configure(state="normal")
        
        data = self._load_wordlist_json()
        mapping = data.get("phonetic_mapping", {})
        
        # Cari semua key (alias) yang valuenya adalah word yang terpilih
        aliases = sorted([k for k, v in mapping.items() if v.lower() == self._selected_word.lower()])
        for alias in aliases:
            self._alias_listbox.insert("end", f"  {alias}")

    def _add_alias(self):
        if not self._selected_word: return
        alias = self._alias_entry.get().strip().lower()
        if not alias: return
        
        data = self._load_wordlist_json()
        mapping = data.get("phonetic_mapping", {})
        
        mapping[alias] = self._selected_word.lower()
        data["phonetic_mapping"] = mapping
        
        self._save_wordlist_json(data)
        self._detector.reload_wordlist()
        self._refresh_aliases_display()
        self._alias_entry.delete(0, "end")

    def _remove_alias(self):
        if not self._selected_word: return
        sel = self._alias_listbox.curselection()
        if not sel: return
        alias_to_remove = self._alias_listbox.get(sel[0]).strip()
        
        data = self._load_wordlist_json()
        mapping = data.get("phonetic_mapping", {})
        
        if alias_to_remove in mapping:
            del mapping[alias_to_remove]
            
        data["phonetic_mapping"] = mapping
        
        self._save_wordlist_json(data)
        self._detector.reload_wordlist()
        self._refresh_aliases_display()

    def _reload_wordlist(self):
        self._detector.reload_wordlist()
        self._refresh_words_display()

    def _load_wordlist_json(self) -> dict:
        """
        Loads wordlist.json which is now a DICT (T12):
        {
            "toxic_words": ["word1", ...],
            "phonetic_mapping": {"peeler": "peler", ...}
        }
        Returns default dict if error or old format.
        """
        default_data = {"toxic_words": [], "phonetic_mapping": {}}
        try:
            with open(WORDLIST_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                
            # Handle backward compatibility (if it was a list)
            if isinstance(data, list):
                return {"toxic_words": data, "phonetic_mapping": {}}
            
            # Ensure keys exist
            if "toxic_words" not in data: data["toxic_words"] = []
            if "phonetic_mapping" not in data: data["phonetic_mapping"] = {}
            
            return data
        except Exception:
            return default_data

    def _save_wordlist_json(self, data: dict):
        try:
            with open(WORDLIST_PATH, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=4)
        except Exception as e:
            logger.error("Failed to save wordlist: %s", e)

    # ================================================================
    # TAB 3: LOGS
    # ================================================================

    def _build_logs_tab(self, parent):
        controls = ctk.CTkFrame(parent, height=40)
        controls.pack(fill="x", pady=(5, 5))

        ctk.CTkLabel(
            controls, text="Toxic Incident Log (CSV)",
            font=ctk.CTkFont(size=13), text_color="#aaaaaa"
        ).pack(side="left", padx=10)

        ctk.CTkButton(
            controls, text="🔄 Refresh", width=100, height=32,
            command=self._refresh_logs
        ).pack(side="right", padx=5)

        self._logs_textbox = ctk.CTkTextbox(
            parent, font=ctk.CTkFont(family="Consolas", size=12),
            corner_radius=8, state="disabled"
        )
        self._logs_textbox.pack(fill="both", expand=True, pady=(0, 5))
        self._refresh_logs()

    def _refresh_logs(self):
        if not self._logs_textbox: return
        self._logs_textbox.configure(state="normal")
        self._logs_textbox.delete("1.0", "end")
        
        current_time = time.strftime("%H:%M:%S")
        self._logs_textbox.insert("end", f"  [Log Insiden — Diperbarui: {current_time}]\n")
        self._logs_textbox.insert("end", "  " + "━" * 80 + "\n\n")
        
        try:
            if not os.path.exists(CSV_PATH):
                self._logs_textbox.insert("end", "  (Belum ada log pelanggaran yang tercatat)\n")
            else:
                with open(CSV_PATH, "r", encoding="utf-8") as f:
                    reader = csv.reader(f)
                    header = next(reader, None)
                    if header:
                        self._logs_textbox.insert("end", f"  {'Timestamp':<22} {'Text':<35} {'Words':<20} {'Severity':<10}\n")
                        self._logs_textbox.insert("end", "  " + "─" * 85 + "\n")
                    for row in reader:
                        if len(row) >= 4:
                            ts, text, words, severity = row
                            display_text = text[:32] + "..." if len(text) > 35 else text
                            sev_icon = {"HIGH":"🔴","MEDIUM":"🟡","LOW":"🟢"}.get(severity, "⚪")
                            self._logs_textbox.insert("end", f"  {ts:<22} {display_text:<35} {words:<20} {sev_icon} {severity:<10}\n")
        except Exception as e:
            self._logs_textbox.insert("end", f"Error: {e}\n")
            
        self._logs_textbox.configure(state="disabled")
        try:
            self._root.update_idletasks()
        except: pass

    # ================================================================
    # TAB 4: SANKSI & PESAN (Timers & Messages)
    # ================================================================

    def _build_sanctions_tab(self, parent):
        """Tab konfigurasi sanction_list (config-driven)."""

        scroll = ctk.CTkScrollableFrame(parent)
        scroll.pack(fill="both", expand=True)

        # ── Header ──
        ctk.CTkLabel(
            scroll, text="📜 Daftar Sanksi (Urutan Eksekusi)",
            font=ctk.CTkFont(size=16, weight="bold"),
        ).pack(anchor="w", padx=10, pady=(10, 5))

        ctk.CTkLabel(
            scroll,
            text="Sanksi dieksekusi berurutan dari atas ke bawah. Item terakhir akan diulang jika level melebihi jumlah list.",
            font=ctk.CTkFont(size=12), text_color="#aaaaaa", wraplength=800,
        ).pack(anchor="w", padx=10, pady=(0, 10))

        # ── Sanction List Display ──
        list_frame = ctk.CTkFrame(scroll)
        list_frame.pack(fill="x", padx=10, pady=5)

        self._sanction_listbox = tk.Listbox(
            list_frame,
            font=("Consolas", 12),
            bg="#2b2b2b", fg="#ffffff",
            selectbackground="#1a73e8", selectforeground="#ffffff",
            borderwidth=0, highlightthickness=0, activestyle="none",
            exportselection=False,
            height=10,
        )
        self._sanction_listbox.pack(fill="x", expand=True, padx=5, pady=5)
        self._sanction_listbox.bind("<<ListboxSelect>>", self._on_sanction_select)

        # ── Edit Fields ──
        edit_frame = ctk.CTkFrame(scroll)
        edit_frame.pack(fill="x", padx=10, pady=5)

        ctk.CTkLabel(edit_frame, text="Type:", font=ctk.CTkFont(weight="bold")).grid(row=0, column=0, padx=10, pady=5, sticky="w")
        self._sanction_type_var = ctk.StringVar(value="WARNING")
        ctk.CTkSegmentedButton(
            edit_frame, values=["WARNING", "LOCKDOWN"],
            variable=self._sanction_type_var,
        ).grid(row=0, column=1, padx=10, pady=5, sticky="w")

        ctk.CTkLabel(edit_frame, text="Warning Delay (s):", font=ctk.CTkFont(weight="bold")).grid(row=1, column=0, padx=10, pady=5, sticky="w")
        self._sanction_delay_entry = ctk.CTkEntry(edit_frame, width=80)
        self._sanction_delay_entry.grid(row=1, column=1, padx=10, pady=5, sticky="w")
        self._sanction_delay_entry.insert(0, "5")

        ctk.CTkLabel(edit_frame, text="Duration (s):", font=ctk.CTkFont(weight="bold")).grid(row=2, column=0, padx=10, pady=5, sticky="w")
        self._sanction_duration_entry = ctk.CTkEntry(edit_frame, width=80)
        self._sanction_duration_entry.grid(row=2, column=1, padx=10, pady=5, sticky="w")
        self._sanction_duration_entry.insert(0, "60")

        ctk.CTkLabel(edit_frame, text="Message:", font=ctk.CTkFont(weight="bold")).grid(row=3, column=0, padx=10, pady=5, sticky="nw")
        self._sanction_msg_textbox = ctk.CTkTextbox(edit_frame, height=80, width=500)
        self._sanction_msg_textbox.grid(row=3, column=1, padx=10, pady=5, sticky="w")

        # ── Buttons ──
        btn_frame = ctk.CTkFrame(scroll, fg_color="transparent")
        btn_frame.pack(fill="x", padx=10, pady=10)

        ctk.CTkButton(
            btn_frame, text="➕ Tambah Sanksi",
            fg_color="#2e7d32", hover_color="#1b5e20",
            command=self._add_sanction,
        ).pack(side="left", expand=True, fill="x", padx=3)

        ctk.CTkButton(
            btn_frame, text="✏️ Update Terpilih",
            fg_color="#1565C0", hover_color="#0D47A1",
            command=self._update_sanction,
        ).pack(side="left", expand=True, fill="x", padx=3)

        ctk.CTkButton(
            btn_frame, text="🗑️ Hapus Terpilih",
            fg_color="#c62828", hover_color="#b71c1c",
            command=self._remove_sanction,
        ).pack(side="left", expand=True, fill="x", padx=3)

        ctk.CTkButton(
            btn_frame, text="💾 Simpan ke Config",
            fg_color="#FF6F00", hover_color="#E65100",
            command=self._save_sanctions_config,
        ).pack(side="left", expand=True, fill="x", padx=3)

        # ── Penalty Reset Minutes ──
        reset_frame = ctk.CTkFrame(scroll)
        reset_frame.pack(fill="x", padx=10, pady=(10, 5))
        ctk.CTkLabel(reset_frame, text="⏱️ Penalty Reset (menit):", font=ctk.CTkFont(weight="bold")).pack(side="left", padx=10)
        self._penalty_reset_entry = ctk.CTkEntry(reset_frame, width=80)
        self._penalty_reset_entry.pack(side="left", padx=5)

        # ── Load ──
        self._sanctions_data = []
        self._load_sanctions_config()

    def _load_sanctions_config(self):
        """Load sanction_list from config to UI."""
        if not self._auth:
            return
        self._sanctions_data = self._auth.get_config("sanction_list", [])
        if not isinstance(self._sanctions_data, list):
            self._sanctions_data = []
        self._refresh_sanction_listbox()

        # Load penalty reset
        reset_min = self._auth.get_config("PenaltyResetMinutes", 60)
        self._penalty_reset_entry.delete(0, "end")
        self._penalty_reset_entry.insert(0, str(reset_min))

    def _refresh_sanction_listbox(self):
        """Refresh listbox display from _sanctions_data."""
        self._sanction_listbox.delete(0, "end")
        for i, s in enumerate(self._sanctions_data):
            stype = s.get("type", "WARNING")
            icon = "🔒" if stype == "LOCKDOWN" else "⚠️"
            msg_preview = s.get("message", "")[:50].replace("\n", " ")
            delay = s.get("warning_delay", 0)
            dur = s.get("duration", 0)
            display = f"  {i+1}. {icon} {stype}  |  delay={delay}s  dur={dur}s  |  {msg_preview}"
            self._sanction_listbox.insert("end", display)

    def _on_sanction_select(self, event=None):
        """Populate edit fields when a sanction is selected."""
        sel = self._sanction_listbox.curselection()
        if not sel:
            return
        idx = sel[0]
        if idx >= len(self._sanctions_data):
            return
        s = self._sanctions_data[idx]
        self._sanction_type_var.set(s.get("type", "WARNING"))
        self._sanction_delay_entry.delete(0, "end")
        self._sanction_delay_entry.insert(0, str(s.get("warning_delay", 5)))
        self._sanction_duration_entry.delete(0, "end")
        self._sanction_duration_entry.insert(0, str(s.get("duration", 0)))
        self._sanction_msg_textbox.delete("1.0", "end")
        self._sanction_msg_textbox.insert("1.0", s.get("message", ""))

    def _get_edit_fields(self) -> dict:
        """Read current edit fields into a sanction dict."""
        try:
            delay = int(self._sanction_delay_entry.get())
        except ValueError:
            delay = 5
        try:
            dur = int(self._sanction_duration_entry.get())
        except ValueError:
            dur = 0
        return {
            "type": self._sanction_type_var.get(),
            "message": self._sanction_msg_textbox.get("1.0", "end-1c"),
            "duration": dur,
            "warning_delay": delay,
        }

    def _add_sanction(self):
        """Add new sanction from edit fields."""
        self._sanctions_data.append(self._get_edit_fields())
        self._refresh_sanction_listbox()

    def _update_sanction(self):
        """Update selected sanction from edit fields."""
        sel = self._sanction_listbox.curselection()
        if not sel:
            return
        idx = sel[0]
        if idx >= len(self._sanctions_data):
            return
        self._sanctions_data[idx] = self._get_edit_fields()
        self._refresh_sanction_listbox()

    def _remove_sanction(self):
        """Remove selected sanction."""
        sel = self._sanction_listbox.curselection()
        if not sel:
            return
        idx = sel[0]
        if idx < len(self._sanctions_data):
            self._sanctions_data.pop(idx)
        self._refresh_sanction_listbox()

    def _reset_penalty_action(self):
        """Bypass password and forcefully reset the violation count (Admin usage)."""
        if self._penalty_mgr: 
            self._penalty_mgr.reset()
            messagebox.showinfo("Berhasil", "Riwayat pelanggaran seluruh pengguna telah dialihkan menjadi 0.")

    # ================================================================
    # AUTO-UPDATER
    # ================================================================

    def _check_update_action(self):
        """Memeriksa API GitHub secara asinkronus untuk mencari rilis terbaru."""
        import threading
        from app.updater import GithubUpdater
        from tkinter import messagebox

        if not self._github_repo or self._github_repo == "USERNAME/REPO_NAME":
            messagebox.showinfo("Informasi Update", "Repositori GitHub belum dikonfigurasi. Silakan ubah variabel GITHUB_REPO di 'main.py' terlebih dahulu.")
            return

        messagebox.showinfo("Memeriksa Pembaruan", "Sistem sedang memeriksa pembaruan di latar belakang.\nHarap tunggu sebentar...")

        def _check():
            updater = GithubUpdater(self._github_repo, self._app_version)
            has_update, latest_version, zip_url, notes = updater.check_for_updates()

            def _on_ui():
                if has_update:
                    ans = messagebox.askyesno(
                        "Update Ditemukan!",
                        f"GC Toxic Shield V{latest_version.replace('v', '')} tersedia!\n\nCatatan Rilis:\n{notes[:300]}...\n\nApakah Anda ingin mengunduh dan memasangnya sekarang?"
                    )
                    if ans:
                        self._start_download_update(updater, zip_url)
                else:
                    if "Gagal" in notes:
                        messagebox.showerror("Gagal Memeriksa", notes)
                    else:
                        messagebox.showinfo("Update Selesai", "Aplikasi Anda sudah versi yang paling terbaru!")

            if self._root:
                self._root.after(0, _on_ui)

        threading.Thread(target=_check, daemon=True).start()

    def _start_download_update(self, updater, zip_url):
        """Membuka dialog progres bar asinkronus untuk proses pengunduhan ZIP."""
        from tkinter import messagebox
        
        dl_win = ctk.CTkToplevel(self._root)
        dl_win.title("Mengunduh Pembaruan...")
        dl_win.geometry("400x120")
        dl_win.resizable(False, False)
        dl_win.attributes("-topmost", True)
        
        # Center the download window
        dl_win.update_idletasks()
        x = (self._root.winfo_screenwidth() // 2) - 200
        y = (self._root.winfo_screenheight() // 2) - 60
        dl_win.geometry(f"+{x}+{y}")
        
        lbl = ctk.CTkLabel(dl_win, text="Memulai koneksi ke server...", font=ctk.CTkFont(size=14))
        lbl.pack(expand=True, padx=20, pady=20)
        
        # Modal
        dl_win.focus_force()
        dl_win.grab_set()

        def _on_progress(msg):
            lbl.configure(text=msg)

        def _on_complete(msg):
            lbl.configure(text=msg, text_color="#4CAF50")
            dl_win.after(2500, lambda: dl_win.destroy())

        def _on_error(msg):
            lbl.configure(text=f"Error: {msg}", text_color="#FF5252")
            messagebox.showerror("Update Gagal", f"Terdapat kesalahan saat mengunduh:\n{msg}")

        updater.download_and_install_async(zip_url, on_progress=_on_progress, on_complete=_on_complete, on_error=_on_error)
        
    def _save_sanctions_config(self):
        """Save sanction_list and PenaltyResetMinutes to config."""
        if not self._auth:
            return
        try:
            self._auth.update_config("sanction_list", self._sanctions_data)
            try:
                reset_min = int(self._penalty_reset_entry.get())
                self._auth.update_config("PenaltyResetMinutes", reset_min)
            except ValueError:
                pass

            # Reload penalty manager if available
            if hasattr(self, '_penalty_mgr') and self._penalty_mgr:
                self._penalty_mgr.reload_config()

            from tkinter import messagebox
            messagebox.showinfo("Success", "Konfigurasi sanksi berhasil disimpan!")
            logger.info("Sanction config saved via UI (%d items)", len(self._sanctions_data))
        except Exception as e:
            logger.error("Failed to save sanctions config: %s", e)

    # ================================================================
    # TAB 5: ADMIN (Audio Controls Added)
    # ================================================================

    def _build_admin_tab(self, parent):
        """Tab Admin: Audio Control, Safety, Auto-Start."""
        from app.system_service import SystemService

        # Gunakan scrollable frame agar responsif dan muat di layar kecil
        scroll = ctk.CTkScrollableFrame(parent)
        scroll.pack(fill="both", expand=True)

        # Container utama dengan 2 kolom untuk merapikan layout
        content_frame = ctk.CTkFrame(scroll, fg_color="transparent")
        content_frame.pack(fill="both", expand=True, padx=10, pady=10)
        content_frame.grid_columnconfigure((0, 1), weight=1)

        # ── Kolom Kiri: Audio & System ──
        left_col = ctk.CTkFrame(content_frame, fg_color="transparent")
        left_col.grid(row=0, column=0, sticky="nsew", padx=(0, 10))

        # 1. Audio Settings
        audio_frame = ctk.CTkFrame(left_col)
        audio_frame.pack(fill="x", pady=(0, 15))
        ctk.CTkLabel(audio_frame, text="🎙️ Audio Input", font=ctk.CTkFont(size=16, weight="bold")).pack(anchor="w", padx=15, pady=(10, 5))
        
        ctk.CTkLabel(audio_frame, text="Microphone Device:").pack(anchor="w", padx=15, pady=(5, 0))
        self._device_dropdown = ctk.CTkComboBox(audio_frame, values=["Default"], command=self._on_device_change, width=300)
        self._device_dropdown.pack(anchor="w", padx=15, pady=5)
        self._populate_devices()

        ctk.CTkLabel(audio_frame, text="Digital Gain (Penguat Suara):").pack(anchor="w", padx=15, pady=(10, 0))
        slider_row = ctk.CTkFrame(audio_frame, fg_color="transparent")
        slider_row.pack(fill="x", padx=15, pady=5)
        self._gain_slider = ctk.CTkSlider(slider_row, from_=0.0, to=5.0, number_of_steps=50, command=self._on_gain_change)
        self._gain_slider.pack(side="left", fill="x", expand=True)
        self._gain_slider.set(1.0)
        self._gain_label = ctk.CTkLabel(slider_row, text="1.0x", width=40)
        self._gain_label.pack(side="right", padx=5)

        # 2. System Settings
        system_frame = ctk.CTkFrame(left_col)
        system_frame.pack(fill="x", pady=(0, 15))
        ctk.CTkLabel(system_frame, text="⚙️ Windows Integration", font=ctk.CTkFont(size=16, weight="bold")).pack(anchor="w", padx=15, pady=(10, 5))

        # Auto-start
        is_enabled = SystemService.is_autostart_enabled()
        self._autostart_var = ctk.StringVar(value="on" if is_enabled else "off")
        ctk.CTkSwitch(
            system_frame, text="Auto-start saat Windows boot", variable=self._autostart_var, 
            onvalue="on", offvalue="off", command=self._on_autostart_toggle
        ).pack(anchor="w", padx=15, pady=(10, 5))

        # Settings Lock
        self._settings_lock_var = ctk.StringVar(value="off")
        ctk.CTkSwitch(
            system_frame, text="Kunci Windows Settings & Control Panel", variable=self._settings_lock_var,
            onvalue="on", offvalue="off", command=self._on_settings_lock_toggle
        ).pack(anchor="w", padx=15, pady=(10, 5))

        # Desktop Guard
        self._desktop_guard_var = ctk.StringVar(value="off") # Secara default OFF pada first-run
        self._guard_switch = ctk.CTkSwitch(
            system_frame, text="Surgical Desktop Guard (Blokir Edit)", variable=self._desktop_guard_var,
            onvalue="on", offvalue="off", command=self._on_desktop_guard_toggle
        )
        self._guard_switch.pack(anchor="w", padx=15, pady=(10, 15))

        # Pembaruan Jaringan (Updater)
        update_frame = ctk.CTkFrame(left_col)
        update_frame.pack(fill="x", pady=(0, 15))
        ctk.CTkLabel(update_frame, text="🔄 Pembaruan Sistem", font=ctk.CTkFont(size=16, weight="bold")).pack(anchor="w", padx=15, pady=(10, 5))
        ctk.CTkLabel(update_frame, text=f"Versi Saat Ini: v{self._app_version}").pack(anchor="w", padx=15, pady=(0, 5))
        
        ctk.CTkButton(
            update_frame, text="Periksa Pembaruan", fg_color="#4CAF50", hover_color="#45a049", 
            text_color="white", font=ctk.CTkFont(weight="bold"), command=self._check_update_action
        ).pack(anchor="w", padx=15, pady=(5, 15))


        # ── Kolom Kanan: Keamanan & Admin ──
        right_col = ctk.CTkFrame(content_frame, fg_color="transparent")
        right_col.grid(row=0, column=1, sticky="nsew", padx=(10, 0))

        # 3. Mode Admin & Password
        pwd_frame = ctk.CTkFrame(right_col)
        pwd_frame.pack(fill="x", pady=(0, 15))
        ctk.CTkLabel(pwd_frame, text="🔑 Keamanan Dashboard", font=ctk.CTkFont(size=16, weight="bold")).pack(anchor="w", padx=15, pady=(10, 5))
        
        self._old_pwd_entry = ctk.CTkEntry(pwd_frame, placeholder_text="Password Saat Ini", show="*")
        self._old_pwd_entry.pack(fill="x", padx=15, pady=5)
        self._new_pwd_entry = ctk.CTkEntry(pwd_frame, placeholder_text="Password Baru", show="*")
        self._new_pwd_entry.pack(fill="x", padx=15, pady=5)
        
        ctk.CTkButton(
            pwd_frame, text="Ubah Password", fg_color="#00BCD4", hover_color="#00ACC1", text_color="black", 
            font=ctk.CTkFont(weight="bold"), command=self._change_password_action
        ).pack(anchor="w", padx=15, pady=(10, 15))

        # 4. Modul Admin / Reset
        action_frame = ctk.CTkFrame(right_col)
        action_frame.pack(fill="x", pady=(0, 15))
        ctk.CTkLabel(action_frame, text="🛠️ Modul Operasional", font=ctk.CTkFont(size=16, weight="bold")).pack(anchor="w", padx=15, pady=(10, 5))

        ctk.CTkButton(
            action_frame, text="🔄 Reset Status Peringatan", fg_color="#1565C0", hover_color="#1976D2", 
            command=self._reset_violations, height=35
        ).pack(fill="x", padx=15, pady=(10, 5))

        ctk.CTkButton(
            action_frame, text="🆘 Emergency Exit (Matikan Aplikasi)", fg_color="#B71C1C", hover_color="#D32F2F", 
            command=self._emergency_exit, height=35
        ).pack(fill="x", padx=15, pady=(10, 15))

    # ── Audio Callbacks ──

    def _populate_devices(self):
        """Isi dropdown dengan list device dari AudioEngine."""
        if not self._engine or not self._device_dropdown: return
        devices = self._engine.list_devices()
        if devices:
            # Format: "Index: Name"
            values = [f"{idx}: {name}" for idx, name in devices]
            self._device_dropdown.configure(values=values)
            self._device_dropdown.set(values[0])
        else:
            self._device_dropdown.configure(values=["No devices found"])

    def _on_device_change(self, choice):
        """Callback saat device dipilih."""
        if not self._engine: return
        try:
            # Parse index dari string "0: Microphone (Realtek...)"
            device_index = int(choice.split(":")[0])
            self._engine.set_input_device(device_index)
        except Exception as e:
            logger.error("Failed to set device: %s", e)

    def _on_gain_change(self, value):
        """Callback slider gain."""
        if not self._engine: return
        self._engine.set_gain(value)
        if self._gain_label:
            self._gain_label.configure(text=f"{value:.1f}x")

    # ── Existing Admin Callbacks ──

    def _emergency_exit(self):
        from app.system_service import SystemService
        logger.warning("🆘 EMERGENCY EXIT triggered UI")
        if self._penalty_mgr and hasattr(self._penalty_mgr, '_overlay'):
            if self._penalty_mgr._overlay: self._penalty_mgr._overlay.dismiss()
        SystemService.emergency_release_hooks()

    def _on_autostart_toggle(self):
        from app.system_service import SystemService
        if self._autostart_var.get() == "on": SystemService.enable_autostart()
        else: SystemService.disable_autostart()

    def _on_desktop_guard_toggle(self):
        if not self._desktop_guard:
            return
        if self._desktop_guard_var.get() == "on":
            self._desktop_guard.enable()
        else:
            self._desktop_guard.disable()

    def _on_settings_lock_toggle(self):
        from app.system_service import SystemService
        from tkinter import messagebox
        enable = self._settings_lock_var.get() == "on"
        success = SystemService.toggle_windows_settings(enable)
        if success:
            state = "TERKUNCI" if enable else "TERBUKA"
            messagebox.showinfo(
                "Windows Settings",
                f"Settings & Control Panel: {state}"
            )
        else:
            messagebox.showerror(
                "Error",
                "Gagal mengubah pengaturan.\n"
                "Pastikan aplikasi berjalan sebagai Administrator."
            )
            # Revert toggle
            self._settings_lock_var.set("off" if enable else "on")

    def _reset_violations(self):
        if self._penalty_mgr: self._penalty_mgr.reset()

    def _change_password_action(self):
        if not self._auth: return
        from tkinter import messagebox
        old_pwd = self._old_pwd_entry.get()
        new_pwd = self._new_pwd_entry.get()

        if not old_pwd or not new_pwd:
            messagebox.showwarning("Peringatan", "Harap isi kedua kolom password!")
            return

        if not self._auth.verify_password(old_pwd):
            messagebox.showerror("Error", "Password Saat Ini salah!")
            return

        if self._auth.change_password(new_pwd):
            messagebox.showinfo("Sukses", "Password berhasil diubah!")
            self._old_pwd_entry.delete(0, "end")
            self._new_pwd_entry.delete(0, "end")
        else:
            messagebox.showerror("Error", "Gagal mengubah password. Cek log untuk detail.")

    # ================================================================
    # TIMERS & CLEANUP
    # ================================================================

    def _build_status_bar(self):
        status_frame = ctk.CTkFrame(self._root, height=30, corner_radius=0)
        status_frame.pack(fill="x", side="bottom")
        self._status_label = ctk.CTkLabel(status_frame, text="🟢 System Active", text_color="gray")
        self._status_label.pack(side="left", padx=10)

    def _schedule_refresh(self):
        """Slow timer (Log/Text update)."""
        if not self._root: return
        self._refresh_monitor()
        t = self._root.after(REFRESH_INTERVAL_MS, self._schedule_refresh)
        self._timers.append(t)

    def _schedule_vu_meter(self):
        """Fast timer (VU Meter)."""
        if not self._root: return
        self._update_vu_meter()
        t = self._root.after(VU_METER_INTERVAL_MS, self._schedule_vu_meter)
        self._timers.append(t)

    def _handle_close(self):
        for t in self._timers:
            try: self._root.after_cancel(t)
            except: pass
        if self._on_close: self._on_close()
        self._root.destroy()

    def destroy(self):
        self._handle_close()
