# =============================================================
# GC Toxic Shield V2 — Task T5: Admin Dashboard (CustomTkinter)
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
from app._paths import WORDLIST_PATH, CSV_PATH


class AdminDashboard:
    """
    Task T5: Admin Dashboard UI menggunakan CustomTkinter.
    Dilengkapi Audio Control & VU Meter (T7).
    """

    def __init__(
        self,
        logger_service: "LoggerService",
        detector: "ToxicDetector",
        lockdown_mgr=None,
        engine=None,
        auth_service=None,
        on_close: Optional[Callable] = None,
    ):
        self._logger_service = logger_service
        self._detector = detector
        self._lockdown_mgr = lockdown_mgr
        self._engine = engine
        self._auth = auth_service
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

        # ── Header ──
        self._build_header()

        # ── Tabview ──
        self._tabview = ctk.CTkTabview(self._root, corner_radius=10)
        self._tabview.pack(fill="both", expand=True, padx=15, pady=(5, 10))

        # Create tabs
        tab_monitor = self._tabview.add("📡 Monitor")
        tab_wordlist = self._tabview.add("📝 Wordlist")
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
            text="🛡️ GC Toxic Shield V2",
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
        """Same as before."""
        # ── Left: Input ──
        input_frame = ctk.CTkFrame(parent, width=300)
        input_frame.pack(side="left", fill="y", padx=(5, 5), pady=5)
        input_frame.pack_propagate(False)

        ctk.CTkLabel(
            input_frame,
            text="Tambah Kata Toxic",
            font=ctk.CTkFont(size=15, weight="bold"),
        ).pack(pady=(10, 5))

        self._word_entry = ctk.CTkEntry(
            input_frame,
            placeholder_text="Ketik kata baru...",
            height=38,
        )
        self._word_entry.pack(fill="x", padx=10, pady=5)
        self._word_entry.bind("<Return>", lambda e: self._add_word())

        btn_frame = ctk.CTkFrame(input_frame, fg_color="transparent")
        btn_frame.pack(fill="x", padx=10, pady=5)

        ctk.CTkButton(
            btn_frame,
            text="➕ Tambah",
            height=35,
            command=self._add_word,
            fg_color="#2e7d32",
            hover_color="#1b5e20",
        ).pack(fill="x", pady=2)

        ctk.CTkButton(
            btn_frame,
            text="🗑️ Hapus Terpilih",
            height=35,
            command=self._remove_word,
            fg_color="#c62828",
            hover_color="#b71c1c",
        ).pack(fill="x", pady=2)

        ctk.CTkButton(
            btn_frame,
            text="🔄 Reload",
            height=35,
            command=self._reload_wordlist,
        ).pack(fill="x", pady=2)

        self._wordcount_label = ctk.CTkLabel(
            input_frame, text="", font=ctk.CTkFont(size=12), text_color="#aaaaaa"
        )
        self._wordcount_label.pack(pady=(10, 0))

        # ── Right: List ──
        list_frame = ctk.CTkFrame(parent)
        list_frame.pack(side="right", fill="both", expand=True, padx=(0, 5), pady=5)

        ctk.CTkLabel(
            list_frame, text="Daftar Kata Toxic", font=ctk.CTkFont(size=15, weight="bold")
        ).pack(pady=(10, 5))

        listbox_container = ctk.CTkFrame(list_frame)
        listbox_container.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        self._wordlist_listbox = tk.Listbox(
            listbox_container,
            font=("Consolas", 13),
            bg="#2b2b2b", fg="#ffffff",
            selectbackground="#1a73e8", selectforeground="#ffffff",
            borderwidth=0, highlightthickness=0, activestyle="none",
        )
        self._wordlist_listbox.pack(fill="both", expand=True)

        scrollbar = ctk.CTkScrollbar(listbox_container, command=self._wordlist_listbox.yview)
        scrollbar.pack(side="right", fill="y")
        self._wordlist_listbox.configure(yscrollcommand=scrollbar.set)

        self._refresh_wordlist_display()

    def _add_word(self):
        if not self._word_entry: return
        word = self._word_entry.get().strip().lower()
        if not word: return
        
        data = self._load_wordlist_json()
        words = data["toxic_words"]
        
        if word in [w.lower() for w in words]:
            self._word_entry.delete(0, "end")
            return
            
        words.append(word)
        data["toxic_words"] = words # update ref
        self._save_wordlist_json(data)
        
        self._detector.reload_wordlist()
        self._refresh_wordlist_display()
        self._word_entry.delete(0, "end")

    def _remove_word(self):
        if not self._wordlist_listbox: return
        selection = self._wordlist_listbox.curselection()
        if not selection: return
        
        # Get displayed string (contains alias info)
        display_text = self._wordlist_listbox.get(selection[0])
        # Extract word (remove padding match and alias part)
        # Format: "  word  (alias: ...)"
        word_to_remove = display_text.split("(")[0].strip()
        
        data = self._load_wordlist_json()
        words = data["toxic_words"]
        
        # Remove word
        words = [w for w in words if w.lower() != word_to_remove.lower()]
        data["toxic_words"] = words
        
        self._save_wordlist_json(data)
        self._detector.reload_wordlist()
        self._refresh_wordlist_display()

    def _reload_wordlist(self):
        self._detector.reload_wordlist()
        self._refresh_wordlist_display()

    def _refresh_wordlist_display(self):
        if not self._wordlist_listbox: return
        
        data = self._load_wordlist_json()
        toxic_words = data.get("toxic_words", [])
        mapping = data.get("phonetic_mapping", {})
        
        # Sort words
        toxic_words.sort()
        
        self._wordlist_listbox.delete(0, "end")
        
        for word in toxic_words:
            # Find aliases (reverse lookup: keys where value == word)
            aliases = [k for k, v in mapping.items() if v == word]
            
            display_text = f"  {word}"
            if aliases:
                display_text += f"  (alias: {', '.join(aliases)})"
                
            self._wordlist_listbox.insert("end", display_text)
            
        if self._wordcount_label:
            count = len(toxic_words)
            self._wordcount_label.configure(text=f"Total: {count} kata (+{len(mapping)} alias)")

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
        """Tab konfigurasi timer warning/lockdown dan pesan."""

        # Scrollable frame
        scroll = ctk.CTkScrollableFrame(parent)
        scroll.pack(fill="both", expand=True)

        # ── 1. Cycle Timers ──
        ctk.CTkLabel(scroll, text="⏱️ Timer Konfigurasi (Per Cycle)", font=ctk.CTkFont(size=16, weight="bold")).pack(anchor="w", padx=10, pady=(10, 5))

        self._timer_entries = {}

        def add_cycle_row(cycle_name, key_prefix):
            frame = ctk.CTkFrame(scroll)
            frame.pack(fill="x", padx=10, pady=5)
            
            ctk.CTkLabel(frame, text=cycle_name, width=120, anchor="w", font=ctk.CTkFont(weight="bold")).pack(side="left", padx=10)
            
            # Warning Delay
            ctk.CTkLabel(frame, text="Warn Delay (s):").pack(side="left", padx=5)
            w_entry = ctk.CTkEntry(frame, width=60)
            w_entry.pack(side="left", padx=5)
            self._timer_entries[f"{key_prefix}_WarningDelay"] = w_entry

            # Lockdown Duration
            ctk.CTkLabel(frame, text="Lockdown (s):").pack(side="left", padx=5)
            l_entry = ctk.CTkEntry(frame, width=60)
            l_entry.pack(side="left", padx=5)
            self._timer_entries[f"{key_prefix}_LockdownDuration"] = l_entry

        add_cycle_row("Cycle 1 (Viol 1-3)", "Cycle1")
        add_cycle_row("Cycle 2 (Viol 4-6)", "Cycle2")
        add_cycle_row("Cycle 3+ (Viol 7+)", "Cycle3")

        # ── 2. Custom Messages ──
        ctk.CTkLabel(scroll, text="💬 Pesan Peringatan & Hukuman", font=ctk.CTkFont(size=16, weight="bold")).pack(anchor="w", padx=10, pady=(20, 5))

        self._msg_entries = {}

        def add_msg_box(label, key, height=60):
            ctk.CTkLabel(scroll, text=label).pack(anchor="w", padx=20, pady=(5,0))
            box = ctk.CTkTextbox(scroll, height=height) if height > 30 else ctk.CTkEntry(scroll)
            box.pack(fill="x", padx=20, pady=5)
            self._msg_entries[key] = box
        
        add_msg_box("Pesan Warning Level 1:", "WarningMessageLevel1", 80)
        add_msg_box("Pesan Warning Level 2:", "WarningMessageLevel2", 80)
        add_msg_box("Judul Lockdown:", "LockdownTitle", 30)
        add_msg_box("Pesan Lockdown:", "LockdownMessage", 60)

        # ── Action Buttons ──
        btn_frame = ctk.CTkFrame(scroll, fg_color="transparent")
        btn_frame.pack(fill="x", padx=10, pady=20)

        ctk.CTkButton(
            btn_frame, 
            text="💾 Simpan Konfigurasi", 
            fg_color="#2e7d32", hover_color="#1b5e20",
            command=self._save_sanctions_config
        ).pack(side="left", expand=True, fill="x", padx=5)

        ctk.CTkButton(
            btn_frame, 
            text="🔄 Reload Default", 
            fg_color="#455A64", hover_color="#37474F",
            command=self._load_sanctions_config
        ).pack(side="left", expand=True, fill="x", padx=5)

        # Initial Load
        self._load_sanctions_config()

    def _load_sanctions_config(self):
        """Load values from AuthService config to UI."""
        if not self._auth: return
        
        # Load Timers
        for key, entry in self._timer_entries.items():
            val = self._auth.get_config(key)
            if val is not None:
                entry.delete(0, "end")
                entry.insert(0, str(val))

        # Load Messages
        for key, widget in self._msg_entries.items():
            val = self._auth.get_config(key, "")
            if isinstance(widget, ctk.CTkEntry):
                widget.delete(0, "end")
                widget.insert(0, val)
            elif isinstance(widget, ctk.CTkTextbox):
                widget.delete("1.0", "end")
                widget.insert("1.0", val)

    def _save_sanctions_config(self):
        """Save UI values to AuthService config."""
        if not self._auth: return

        try:
            # Save Timers
            for key, entry in self._timer_entries.items():
                try:
                    val = int(entry.get())
                    self._auth.update_config(key, val)
                except ValueError:
                    continue # Skip invalid numbers

            # Save Messages
            for key, widget in self._msg_entries.items():
                if isinstance(widget, ctk.CTkEntry):
                    val = widget.get()
                else:
                    val = widget.get("1.0", "end-1c") # Remove trailing newline
                self._auth.update_config(key, val)

            from tkinter import messagebox
            messagebox.showinfo("Success", "Konfigurasi berhasil disimpan!")
            logger.info("Sanctions config updated via UI")

        except Exception as e:
            logger.error("Failed to save sanctions config: %s", e)

    # ================================================================
    # TAB 5: ADMIN (Audio Controls Added)
    # ================================================================

    def _build_admin_tab(self, parent):
        """Tab Admin: Audio Control, Safety, Auto-Start."""
        from app.system_service import SystemService

        # ── Audio Settings ──
        audio_frame = ctk.CTkFrame(parent)
        audio_frame.pack(fill="x", padx=10, pady=(10, 5))

        ctk.CTkLabel(
            audio_frame,
            text="🎙️ Audio Input Settings",
            font=ctk.CTkFont(size=16, weight="bold"),
        ).pack(anchor="w", padx=15, pady=(10, 5))

        # Device Selection
        ctk.CTkLabel(audio_frame, text="Microphone Device:").pack(anchor="w", padx=15, pady=(5, 0))

        self._device_dropdown = ctk.CTkComboBox(
            audio_frame,
            values=["Default"],
            command=self._on_device_change,
            width=300
        )
        self._device_dropdown.pack(anchor="w", padx=15, pady=5)
        self._populate_devices()

        # Gain Slider
        ctk.CTkLabel(audio_frame, text="Digital Gain (Penguat Suara):").pack(anchor="w", padx=15, pady=(10, 0))

        slider_row = ctk.CTkFrame(audio_frame, fg_color="transparent")
        slider_row.pack(fill="x", padx=15, pady=5)

        self._gain_slider = ctk.CTkSlider(
            slider_row,
            from_=0.0, to=5.0,
            number_of_steps=50,
            command=self._on_gain_change
        )
        self._gain_slider.pack(side="left", fill="x", expand=True)
        self._gain_slider.set(1.0)

        self._gain_label = ctk.CTkLabel(slider_row, text="1.0x", width=40)
        self._gain_label.pack(side="right", padx=5)

        # ── Password Settings ──
        pwd_frame = ctk.CTkFrame(parent)
        pwd_frame.pack(fill="x", padx=10, pady=5)

        ctk.CTkLabel(
            pwd_frame,
            text="🔑 Pengaturan Password",
            font=ctk.CTkFont(size=16, weight="bold"),
        ).pack(anchor="w", padx=15, pady=(10, 5))

        self._old_pwd_entry = ctk.CTkEntry(pwd_frame, placeholder_text="Password Saat Ini", show="*")
        self._old_pwd_entry.pack(fill="x", padx=15, pady=5)

        self._new_pwd_entry = ctk.CTkEntry(pwd_frame, placeholder_text="Password Baru", show="*")
        self._new_pwd_entry.pack(fill="x", padx=15, pady=5)

        ctk.CTkButton(
            pwd_frame,
            text="Ubah Password",
            fg_color="#00BCD4", hover_color="#00ACC1", text_color="black", font=ctk.CTkFont(weight="bold"),
            command=self._change_password_action
        ).pack(anchor="w", padx=15, pady=10)

        # ── Safety Exit (Existing) ──
        safety_frame = ctk.CTkFrame(parent)
        safety_frame.pack(fill="x", padx=10, pady=5)
        # ... (rest same as before)
        ctk.CTkLabel(safety_frame, text="🆘 Safety Exit", font=ctk.CTkFont(size=16, weight="bold"), text_color="#FF4444").pack(anchor="w", padx=15, pady=5)
        ctk.CTkButton(safety_frame, text="Emergency Exit (Release Hooks)", fg_color="#B71C1C", hover_color="#D32F2F", command=self._emergency_exit).pack(fill="x", padx=15, pady=10)

        # ── Auto-Start (Existing) ──
        autostart_frame = ctk.CTkFrame(parent)
        autostart_frame.pack(fill="x", padx=10, pady=5)
        ctk.CTkLabel(autostart_frame, text="🔄 Auto-Start", font=ctk.CTkFont(size=16, weight="bold")).pack(anchor="w", padx=15, pady=5)
        is_enabled = SystemService.is_autostart_enabled()
        self._autostart_var = ctk.StringVar(value="on" if is_enabled else "off")
        ctk.CTkSwitch(autostart_frame, text="Auto-start on Windows boot", variable=self._autostart_var, onvalue="on", offvalue="off", command=self._on_autostart_toggle).pack(anchor="w", padx=15, pady=10)

        # ── Violation Reset (Existing) ──
        violation_frame = ctk.CTkFrame(parent)
        violation_frame.pack(fill="x", padx=10, pady=5)
        ctk.CTkLabel(violation_frame, text="🔄 Reset Violations", font=ctk.CTkFont(size=16, weight="bold")).pack(anchor="w", padx=15, pady=5)
        ctk.CTkButton(violation_frame, text="Reset to 0", fg_color="#1565C0", hover_color="#1976D2", command=self._reset_violations).pack(fill="x", padx=15, pady=10)

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
        if self._lockdown_mgr and hasattr(self._lockdown_mgr, '_overlay'):
            if self._lockdown_mgr._overlay: self._lockdown_mgr._overlay.dismiss()
        SystemService.emergency_release_hooks()

    def _on_autostart_toggle(self):
        from app.system_service import SystemService
        if self._autostart_var.get() == "on": SystemService.enable_autostart()
        else: SystemService.disable_autostart()

    def _reset_violations(self):
        if self._lockdown_mgr: self._lockdown_mgr.reset()

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
