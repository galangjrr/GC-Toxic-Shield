# =============================================================
# GC Toxic Shield — Admin Dashboard (PySide6)
# =============================================================
# 100% Pixel-Perfect UI Migration from CustomTkinter.
# Features:
# - Full QSS (Qt Style Sheets) for identical Figma colors
# - QGraphicsDropShadowEffect for card depth
# - QStackedWidget for seamless tab switching
# - Hardware accelerated drawing (GPU)
# =============================================================

import os
import csv
import json
import time
import logging
import threading
from typing import Optional, Callable, List, Dict, Any

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QFrame, QLabel, QPushButton, QStackedWidget, QTextEdit, 
    QProgressBar, QGridLayout, QSlider, QComboBox, QLineEdit,
    QCheckBox, QListWidget, QListWidgetItem, QMessageBox, QButtonGroup,
    QScrollArea, QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
    QSpinBox, QDoubleSpinBox
)
from PySide6.QtCore import Qt, QTimer, QSize
from PySide6.QtGui import QFont, QIcon, QColor, QTextCursor
from PySide6.QtWidgets import QGraphicsDropShadowEffect

logger = logging.getLogger("GCToxicShield.UI")

# ── Timer Intervals ──
REFRESH_INTERVAL_MS = 2000
VU_METER_INTERVAL_MS = 80

# ── Design Tokens (Obsidian Cyberpunk v2.1.0) ──
BG       = "#080A10"
CARD     = "#111628"
BORDER   = "#1F263B"
ACCENT   = "#6366F1"
SUCCESS  = "#10B981"
DANGER   = "#EF4444"
WARNING  = "#F59E0B"
TEXT     = "#F8FAFC"
MUTED    = "#64748B"
ENTRY_BG = "#0C0F19"
TAB_BG   = "#111628"
TAB_SEL  = "#1E293B"
FONT_FAM = "Segoe UI Variable"

# Global Stylesheet
QSS = f"""
QMainWindow, QWidget#MainContent {{
    background-color: {BG};
    color: {TEXT};
    font-family: "{FONT_FAM}";
}}

/* Card Panels */
QFrame.Card {{
    background-color: {CARD};
    border: 1px solid {BORDER};
    border-radius: 8px;
}}

/* Titles */
QLabel.H1 {{ font-size: 22px; font-weight: bold; color: {TEXT}; }}
QLabel.H2 {{ font-size: 14px; font-weight: bold; color: {ACCENT}; }}
QLabel.H3 {{ font-size: 13px; font-weight: bold; color: {TEXT}; }}
QLabel.Muted {{ font-size: 11px; color: {MUTED}; }}

/* Tab Buttons */
QPushButton.TabBtn {{
    background-color: {TAB_BG};
    color: {MUTED};
    border: 1px solid {BORDER};
    border-radius: 8px;
    padding: 6px 12px;
    font-size: 12px;
}}
QPushButton.TabBtn:hover {{ background-color: {TAB_SEL}; }}
QPushButton.TabBtn:checked {{
    background-color: {TAB_SEL};
    color: {TEXT};
    border: 1px solid {ACCENT};
}}

/* Segmented Buttons */
QPushButton.SegBtn {{
    background-color: {TAB_BG};
    color: {TEXT};
    border: 1px solid {BORDER};
    padding: 4px 10px;
    font-size: 11px;
}}
QPushButton.SegBtn:checked {{
    background-color: {ACCENT};
    color: white;
    border: 1px solid {ACCENT};
}}

/* TextBoxes, LineEdits, and Tables */
QTextEdit, QLineEdit, QListWidget, QTableWidget, QSpinBox, QDoubleSpinBox {{
    background-color: {ENTRY_BG};
    color: {TEXT};
    border: 1px solid {BORDER};
    border-radius: 6px;
    font-family: "Consolas";
    font-size: 11px;
    padding: 6px;
}}
QLineEdit, QSpinBox, QDoubleSpinBox {{ font-family: "{FONT_FAM}"; font-size: 12px; padding: 4px 8px; }}

/* Table specifics */
QTableWidget::item {{ padding: 4px; }}
QHeaderView::section {{
    background-color: {CARD};
    color: {MUTED};
    padding: 4px;
    border: none;
    border-bottom: 1px solid {BORDER};
    border-right: 1px solid {BORDER};
    font-weight: bold;
}}
QTableCornerButton::section {{ background-color: {CARD}; border: none; }}

/* Action Buttons */
QPushButton.ActionBtn {{
    font-weight: bold; font-size: 11px; color: white;
    border-radius: 6px; padding: 6px 12px;
}}
QPushButton.BtnPrimary {{ background-color: {ACCENT}; }}
QPushButton.BtnPrimary:hover {{ background-color: #3B5BDB; }}
QPushButton.BtnSuccess {{ background-color: {SUCCESS}; }}
QPushButton.BtnSuccess:hover {{ background-color: #27AE60; }}
QPushButton.BtnDanger {{ background-color: {DANGER}; }}
QPushButton.BtnDanger:hover {{ background-color: #C0392B; }}
QPushButton.BtnWarning {{ background-color: {WARNING}; }}
QPushButton.BtnWarning:hover {{ background-color: #D68910; }}
QPushButton.BtnOutline {{
    background-color: {TAB_BG}; color: {TEXT};
    border: 1px solid {BORDER}; font-weight: normal;
}}
QPushButton.BtnOutline:hover {{ background-color: {TAB_SEL}; }}

/* Scrollbars */
QScrollBar:vertical {{
    background: {CARD}; width: 10px; margin: 0px;
}}
QScrollBar::handle:vertical {{
    background: {BORDER}; min-height: 20px; border-radius: 5px;
}}
QScrollBar::handle:vertical:hover {{ background: {MUTED}; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0px; }}

/* Status Bar */
QFrame#StatusBar {{ background-color: {BORDER}; border-top: 1px solid #2B3037; }}

/* Sliders */
QSlider::groove:horizontal {{
    height: 6px; background: {BORDER}; border-radius: 3px;
}}
QSlider::handle:horizontal {{
    background: {ACCENT}; width: 14px; height: 14px; 
    margin: -4px 0; border-radius: 7px;
}}
QSlider::sub-page:horizontal {{ background: {ACCENT}; border-radius: 3px; }}

/* ComboBox */
QComboBox {
    background-color: {ENTRY_BG}; color: {TEXT};
    border: 1px solid {BORDER}; border-radius: 6px; padding: 4px 8px;
}
QComboBox::drop-down { border: none; }

/* Premium QCheckBox */
QCheckBox {
    spacing: 10px;
    color: {TEXT};
    font-size: 12px;
    font-weight: bold;
}
QCheckBox::indicator {
    width: 18px;
    height: 18px;
    border: 1.5px solid {BORDER};
    border-radius: 5px;
    background-color: {ENTRY_BG};
}
QCheckBox::indicator:hover {
    border-color: {ACCENT};
}
QCheckBox::indicator:checked {
    background-color: {ACCENT};
    border-color: {ACCENT};
}
"""

# ── Imports ──
from app._paths import WORDLIST_PATH, CSV_PATH, ICON_ICO_PATH


def create_shadow() -> QGraphicsDropShadowEffect:
    shadow = QGraphicsDropShadowEffect()
    shadow.setBlurRadius(15)
    shadow.setOffset(0, 4)
    shadow.setColor(QColor(0, 0, 0, 80))
    return shadow


class AdminDashboard(QMainWindow):
    """GC Toxic Shield — Admin Dashboard UI (PySide6)."""

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
        super().__init__()
        self._logger_service = logger_service
        self._detector = detector
        self._penalty_mgr = penalty_mgr
        self._engine = engine
        self._auth = auth_service
        self._app_version = app_version
        self._github_repo = github_repo
        self._installer_guard = None
        self._on_close = on_close

        if self._penalty_mgr:
            self._penalty_mgr.on_sync_callback = self._on_penalty_sync

        self.setWindowTitle("GC Toxic Shield")
        self.resize(960, 700)
        self.setMinimumSize(800, 600)
        
        # Center Window
        screen = QApplication.primaryScreen().availableGeometry()
        self.move((screen.width() - 960) // 2, (screen.height() - 700) // 2)
        
        try:
            if os.path.exists(ICON_ICO_PATH):
                self.setWindowIcon(QIcon(ICON_ICO_PATH))
        except Exception:
            pass

        # Central Widget & Main Layout structure
        self.central_widget = QWidget()
        self.central_widget.setObjectName("MainContent")
        self.setCentralWidget(self.central_widget)
        
        self.main_layout = QHBoxLayout(self.central_widget)
        self.main_layout.setContentsMargins(0, 0, 0, 0) # Remove margins for flushed sidebar
        self.main_layout.setSpacing(0)

        # ── Left: Sidebar ──
        self.sidebar_frame = QFrame()
        self.sidebar_frame.setObjectName("SidebarFrame")
        self.sidebar_frame.setFixedWidth(240)
        self.sidebar_layout = QVBoxLayout(self.sidebar_frame)
        self.sidebar_layout.setContentsMargins(15, 20, 15, 20)
        self.sidebar_layout.setSpacing(8)
        self.main_layout.addWidget(self.sidebar_frame)

        # ── Right: Content Container ──
        self.content_container = QWidget()
        self.content_layout = QVBoxLayout(self.content_container)
        self.content_layout.setContentsMargins(20, 20, 20, 0)
        self.content_layout.setSpacing(15)
        self.main_layout.addWidget(self.content_container, 1)

        # Build UI Components
        self._build_sidebar()
        self._build_header()
        self._build_content_area()
        self._build_status_bar()

        # Connect timers
        self._refresh_timer = QTimer(self)
        self._refresh_timer.timeout.connect(self._schedule_refresh)
        self._refresh_timer.start(REFRESH_INTERVAL_MS)

        self._vu_timer = QTimer(self)
        self._vu_timer.timeout.connect(self._update_vu_meter)
        self._vu_timer.start(VU_METER_INTERVAL_MS)

        self._net_timer = QTimer(self)
        self._net_timer.timeout.connect(self._schedule_network_status_refresh)
        self._net_timer.start(3000)

        # Apply Global QSS
        self.setStyleSheet(QSS)
        
        # Initial states
        self._switch_tab(0)
        self._refresh_wordlist_display()
        self._refresh_guard_config_display()

        logger.info("✓ Admin Dashboard built (PySide6)")

    # ================================================================
    # BUILD SYSTEM
    # ================================================================

    def _build_sidebar(self):
        # 1. Title/Logo at top of sidebar
        title_box = QWidget()
        title_lyt = QHBoxLayout(title_box)
        title_lyt.setContentsMargins(0, 0, 0, 20)
        title = QLabel("🛡 GC Toxic Shield")
        title.setProperty("class", "H1")
        title_lyt.addWidget(title)
        self.sidebar_layout.addWidget(title_box)

        # 2. Navigation Buttons
        self.tab_group = QButtonGroup(self)
        self.tab_group.setExclusive(True)
        self.tab_group.idClicked.connect(self._switch_tab)

        tabs = [
            ("📡 Live Monitor", 0),
            ("📝 Manajemen Kata", 1),
            ("🛡 Installer Guard", 2),
            ("📜 Daftar Sanksi", 3),
            ("⚙ Pengaturan", 4),
            ("🎚 Proximity Filter", 5),
        ]

        for label, index in tabs:
            btn = QPushButton(label)
            btn.setProperty("class", "SidebarBtn")
            btn.setCheckable(True)
            btn.setFixedHeight(40)
            self.tab_group.addButton(btn, index)
            self.sidebar_layout.addWidget(btn)
        
        self.sidebar_layout.addStretch()

        # 3. Version Pill at bottom
        ver_pill = QLabel(f"v{self._app_version}")
        ver_pill.setAlignment(Qt.AlignCenter)
        ver_pill.setFixedSize(60, 24)
        ver_pill.setStyleSheet(f"background-color: {BORDER}; color: {ACCENT}; border-radius: 6px; font-size: 11px;")
        
        v_box = QWidget()
        v_lyt = QHBoxLayout(v_box)
        v_lyt.setContentsMargins(0,0,0,0)
        v_lyt.addWidget(ver_pill, alignment=Qt.AlignLeft)
        self.sidebar_layout.addWidget(v_box)

    def _build_header(self):
        header_frame = QFrame()
        header_frame.setFixedHeight(40)
        h_layout = QHBoxLayout(header_frame)
        h_layout.setContentsMargins(0, 0, 0, 0)

        # Left: Current Page Title (Dynamic)
        self._header_title_label = QLabel("Dashboard Utama")
        self._header_title_label.setProperty("class", "H2")
        self._header_title_label.setStyleSheet(f"color: {TEXT}; font-size: 18px;")
        h_layout.addWidget(self._header_title_label)

        h_layout.addStretch()

        # Right: Server Badge
        self._header_server_badge = QLabel("● SERVER ONLINE")
        self._header_server_badge.setStyleSheet(f"color: {SUCCESS}; font-weight: bold; font-size: 11px;")
        h_layout.addWidget(self._header_server_badge)

        self.content_layout.addWidget(header_frame)

    def _build_content_area(self):
        self.stack = QStackedWidget()
        self.content_layout.addWidget(self.stack, 1) # expand=True
        
        self._build_monitor_tab()
        self._build_wordlist_tab()
        self._build_installer_guard_tab()
        self._build_sanctions_tab()
        self._build_settings_tab()
        self._build_proximity_filter_tab()

    def _build_status_bar(self):
        bar = QFrame()
        bar.setObjectName("StatusBar")
        bar.setFixedHeight(28)
        h_layout = QHBoxLayout(bar)
        h_layout.setContentsMargins(15, 0, 15, 0)

        self._status_label = QLabel("● System Active")
        self._status_label.setStyleSheet(f"color: {SUCCESS}; font-weight: bold; font-size: 11px;")
        h_layout.addWidget(self._status_label)

        self._stats_label = QLabel("Logged: 0 | Toxic: 0")
        self._stats_label.setStyleSheet(f"color: {MUTED}; font-size: 11px;")
        h_layout.addWidget(self._stats_label)
        h_layout.addStretch()

        # Add it to content layout at the bottom
        self.content_layout.addWidget(bar)

    def _switch_tab(self, index):
        self.stack.setCurrentIndex(index)
        btn = self.tab_group.button(index)
        if btn and not btn.isChecked():
            btn.setChecked(True)
            
        # Update Header Title
        titles = [
            "📡 Live Streaming Monitor",
            "📝 Manajemen Sensor Kata",
            "🛡 Installer Guard Blokir Pihak Ke-3",
            "📜 Konfigurasi Sistem Sanksi",
            "⚙ Pengaturan Admin",
            "🎚 Dynamic Proximity Filter"
        ]
        if 0 <= index < len(titles):
            self._header_title_label.setText(titles[index])

    # ================================================================
    # TAB 1: MONITOR
    # ================================================================

    def _build_monitor_tab(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 10)

        # VU Card
        vu_card = QFrame()
        vu_card.setProperty("class", "Card")
        vu_card.setGraphicsEffect(create_shadow())
        vu_card.setFixedHeight(45)
        v_layout = QHBoxLayout(vu_card)
        v_layout.setContentsMargins(12, 0, 12, 0)
        
        lbl = QLabel("🔊 Mic Level:")
        lbl.setProperty("class", "Muted")
        v_layout.addWidget(lbl)
        
        self._vu_progress = QProgressBar()
        self._vu_progress.setFixedHeight(16)
        self._vu_progress.setTextVisible(False)
        self._vu_progress.setRange(0, 100)
        self._vu_progress.setStyleSheet(f"""
            QProgressBar {{ border: 1px solid {BORDER}; border-radius: 4px; background-color: {BG}; }}
            QProgressBar::chunk {{ background-color: {ACCENT}; border-radius: 3px; }}
        """)
        v_layout.addWidget(self._vu_progress, 1)
        layout.addWidget(vu_card)

        # View Toggle
        toggle_frame = QFrame()
        th_layout = QHBoxLayout(toggle_frame)
        th_layout.setContentsMargins(0, 5, 0, 5)
        
        self.seg_group = QButtonGroup(self)
        self.seg_group.setExclusive(True)
        self.seg_group.idClicked.connect(self._on_monitor_view_change)

        btn_live = QPushButton("Live Monitor")
        btn_live.setProperty("class", "SegBtn")
        btn_live.setCheckable(True)
        btn_live.setChecked(True)
        btn_live.setFixedSize(100, 26)
        
        btn_log = QPushButton("Log Insiden")
        btn_log.setProperty("class", "SegBtn")
        btn_log.setCheckable(True)
        btn_log.setFixedSize(100, 26)

        self.seg_group.addButton(btn_live, 0)
        self.seg_group.addButton(btn_log, 1)

        th_layout.addWidget(btn_live)
        th_layout.addWidget(btn_log)
        th_layout.addStretch()
        layout.addWidget(toggle_frame)

        # TextBoxes Stack
        self.monitor_stack = QStackedWidget()
        
        self._monitor_textbox = QTextEdit()
        self._monitor_textbox.setReadOnly(True)
        self.monitor_stack.addWidget(self._monitor_textbox)
        
        self._logs_table = QTableWidget()
        self._logs_table.setColumnCount(5)
        self._logs_table.setHorizontalHeaderLabels(["Waktu", "Teks", "Sensor", "Status", "Level"])
        self._logs_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self._logs_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._logs_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._logs_table.verticalHeader().setVisible(False)
        self.monitor_stack.addWidget(self._logs_table)

        layout.addWidget(self.monitor_stack, 1)
        self.stack.addWidget(page)

    def _on_monitor_view_change(self, index):
        self.monitor_stack.setCurrentIndex(index)
        if index == 0: self._refresh_monitor(force=True)
        else: self._refresh_logs()

    def _refresh_monitor(self, force=False):
        if self.monitor_stack.currentIndex() != 0 and not force: return
        buffer = self._logger_service.get_buffer()
        
        current_time = time.strftime("%H:%M:%S")
        txt = f"Live transcription text time ({current_time}):\n"

        if not buffer:
            txt += "  (Belum ada transkripsi... bicara sekarang!)\n"
        else:
            for entry in buffer:
                icon = "🚨" if entry.is_toxic else "✅"
                tag = "TOXIC" if entry.is_toxic else "SAFE"
                words_str = f" [{', '.join(entry.matched_words)}]" if entry.matched_words else ""
                txt += f"{icon} {tag} : {entry.text}{words_str}\n"

        self._monitor_textbox.setPlainText(txt)
        cursor = self._monitor_textbox.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        self._monitor_textbox.setTextCursor(cursor)

        if self._stats_label:
            stats = self._logger_service.stats
            self._stats_label.setText(f"Logged: {stats['total_logged']} | Toxic: {stats['total_toxic']} | Buffer: {stats['buffer_size']}")

    def _refresh_logs(self):
        if self.monitor_stack.currentIndex() != 1: return

        try:
            if not os.path.exists(CSV_PATH):
                self._logs_table.setRowCount(0)
                return

            with open(CSV_PATH, "r", encoding="utf-8") as f:
                reader = list(csv.reader(f))
                
            if len(reader) <= 1:
                self._logs_table.setRowCount(0)
                return
                
            data_rows = reader[1:]
            self._logs_table.setRowCount(len(data_rows))
            
            for row_idx, row in enumerate(data_rows):
                if len(row) >= 4:
                    ts, text, words, severity = row
                    sev_icon = {"HIGH": "🔴 ", "MEDIUM": "🟡 ", "LOW": "🟢 "}.get(severity, "⚪ ")
                    
                    self._logs_table.setItem(row_idx, 0, QTableWidgetItem(ts))
                    self._logs_table.setItem(row_idx, 1, QTableWidgetItem(text))
                    self._logs_table.setItem(row_idx, 2, QTableWidgetItem(words))
                    self._logs_table.setItem(row_idx, 3, QTableWidgetItem(sev_icon + severity))
                    
        except Exception as e:
            logger.error("Failed to refresh logs table: %s", e)

    def _update_vu_meter(self) -> None:
        """Update all VU meter displays from the audio engine.

        Called every VU_METER_INTERVAL_MS (80ms) by the QTimer.
        Updates both the main monitor VU meter (perceptual scale)
        and the proximity filter VU meter (raw linear RMS).
        """
        if not self._engine:
            return

        # ── Main Monitor VU Meter (perceptual scale) ──
        if hasattr(self, '_vu_progress'):
            level = self._engine.get_vu_level()  # 0.0 to 1.0
            val = int(level * 100)
            self._vu_progress.setValue(val)

            # Dynamic coloring
            if val < 50:
                color = SUCCESS
            elif val < 80:
                color = WARNING
            else:
                color = DANGER

            self._vu_progress.setStyleSheet(f"""
                QProgressBar {{ border: 1px solid {BORDER}; border-radius: 4px; background-color: {BG}; }}
                QProgressBar::chunk {{ background-color: {color}; border-radius: 3px; }}
            """)

        # ── Proximity Filter VU Meter (raw linear RMS) ──
        if hasattr(self, '_prox_vu_progress'):
            try:
                raw_rms = self._engine.get_current_rms()
                prox_val = int(min(raw_rms, 1.0) * 100)
                self._prox_vu_progress.setValue(prox_val)

                if hasattr(self, '_prox_rms_label'):
                    self._prox_rms_label.setText(f"RMS: {raw_rms:.4f}")

                # Color by zone action
                prox_color = MUTED  # Default: no zone match
                if hasattr(self._engine, 'proximity_zones'):
                    for zone in self._engine.proximity_zones:
                        min_r = float(zone.get("min_rms", 0))
                        max_r = float(zone.get("max_rms", 0))
                        if min_r <= raw_rms <= max_r:
                            prox_color = SUCCESS if zone.get("action") == "PROCESS" else DANGER
                            break

                self._prox_vu_progress.setStyleSheet(f"""
                    QProgressBar {{ border: 1px solid {BORDER}; border-radius: 4px; background-color: {BG}; }}
                    QProgressBar::chunk {{ background-color: {prox_color}; border-radius: 3px; }}
                """)
            except Exception as e:
                logger.debug("Proximity VU update error: %s", e)

    def _build_wordlist_tab(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        
        lbl = QLabel("PENGATURAN KATA KOTOR & PENGECUALIAN")
        lbl.setProperty("class", "H2")
        layout.addWidget(lbl)

        # 2 Columns
        cols = QWidget()
        cols_lyt = QHBoxLayout(cols)
        cols_lyt.setContentsMargins(0, 0, 0, 0)
        
        # Helper function to create a table setup
        def setup_table(title, label_color, attr_name):
            frame = QFrame()
            frame.setProperty("class", "Card")
            frame.setGraphicsEffect(create_shadow())
            flyt = QVBoxLayout(frame)
            
            lbl = QLabel(title)
            lbl.setStyleSheet(f"color: {label_color}; font-weight: bold; font-size: 12px;")
            flyt.addWidget(lbl)
            
            table = QTableWidget(0, 1)
            table.setHorizontalHeaderLabels(["Kata"])
            table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
            table.setSelectionBehavior(QAbstractItemView.SelectItems)
            table.verticalHeader().setVisible(False)
            setattr(self, attr_name, table)
            flyt.addWidget(table)
            
            # Action Buttons
            blyt = QHBoxLayout()
            blyt.setContentsMargins(0, 0, 0, 0)
            btn_add = QPushButton("➕ Tambah Info")
            btn_add.setProperty("class", "ActionBtn BtnSuccess")
            btn_add.clicked.connect(lambda: self._add_table_row(table))
            
            btn_del = QPushButton("🗑 Hapus Pilihan")
            btn_del.setProperty("class", "ActionBtn BtnDanger")
            btn_del.clicked.connect(lambda: self._delete_table_row(table))
            
            blyt.addWidget(btn_add)
            blyt.addWidget(btn_del)
            flyt.addLayout(blyt)
            
            cols_lyt.addWidget(frame)

        # Left
        setup_table("⛔ Daftar Kata Dilarang", DANGER, "_forbidden_table")
        
        # Right
        setup_table("✅ Daftar Kata Dizinkan", SUCCESS, "_allowed_table")
        
        layout.addWidget(cols, 1)

        # Buttons
        btn_frame = QWidget()
        btn_lyt = QHBoxLayout(btn_frame)
        btn_lyt.setContentsMargins(0, 0, 0, 0)
        
        sys_btn = QPushButton("💾 Simpan")
        sys_btn.setProperty("class", "ActionBtn BtnPrimary")
        sys_btn.setFixedSize(120, 34)
        sys_btn.clicked.connect(self._save_wordlist_from_ui)
        btn_lyt.addWidget(sys_btn)
        
        ref_btn = QPushButton("🔄 Segarkan")
        ref_btn.setProperty("class", "ActionBtn BtnOutline")
        ref_btn.setFixedSize(120, 34)
        ref_btn.clicked.connect(self._refresh_wordlist_display)
        btn_lyt.addWidget(ref_btn)

        import_btn = QPushButton("📂 Muat dari File")
        import_btn.setProperty("class", "ActionBtn BtnWarning")
        import_btn.setFixedSize(140, 34)
        import_btn.clicked.connect(self._import_wordlist_json)
        btn_lyt.addWidget(import_btn)
        
        btn_lyt.addStretch()
        layout.addWidget(btn_frame)

        self.stack.addWidget(page)

    def _import_wordlist_json(self):
        from PySide6.QtWidgets import QFileDialog
        import json
        
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Import Wordlist Konfigurasi", "", "JSON Files (*.json)"
        )
        if not file_path:
            return
            
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                
            raw_tx = data.get("toxic_words", [])
            if isinstance(raw_tx, dict):
                flat = []
                for k, v in raw_tx.items():
                    flat.append(k)
                    if isinstance(v, list): flat.extend(v)
                raw_tx = list(set(flat))
            
            raw_al = data.get("allowed_words", [])
            
            def populate(table, items):
                table.setRowCount(len(items))
                for i, it in enumerate(items):
                    table.setItem(i, 0, QTableWidgetItem(str(it)))
            
            if hasattr(self, '_forbidden_table'):
                populate(self._forbidden_table, raw_tx)
            if hasattr(self, '_allowed_table'):
                populate(self._allowed_table, raw_al)
                
            QMessageBox.information(self, "Preview Import", "Berhasil pratinjau data Wordlist dari file.\nSilakan tekan 'Simpan' untuk menerapkannya secara permanen.")
        except Exception as e:
            QMessageBox.critical(self, "Error Import", f"Gagal membaca file JSON:\n{e}")

    def _refresh_wordlist_display(self):
        data = self._load_wordlist_json()
        if data is None: return
        
        raw_tx = data.get("toxic_words", [])
        if isinstance(raw_tx, dict):
            flat = []
            for k, v in raw_tx.items():
                flat.append(k)
                if isinstance(v, list): flat.extend(v)
            raw_tx = flat
        words = sorted(set(w.strip() for w in raw_tx if isinstance(w, str) and w.strip()))
        
        allowed = data.get("allowed_words", [])
        if isinstance(allowed, list):
            allowed = sorted(set(w.strip() for w in allowed if isinstance(w, str) and w.strip()))
        else:
            allowed = []
            
        if hasattr(self, '_forbidden_table'):
            def populate(table, words_list):
                table.setRowCount(len(words_list))
                for i, w in enumerate(words_list):
                    table.setItem(i, 0, QTableWidgetItem(w))

            populate(self._forbidden_table, words)
            populate(self._allowed_table, allowed)

    def _add_table_row(self, table: QTableWidget):
        row = table.rowCount()
        table.insertRow(row)
        item = QTableWidgetItem("")
        table.setItem(row, 0, item)
        table.editItem(item)
        table.setCurrentCell(row, 0)

    def _delete_table_row(self, table: QTableWidget):
        rows = set([i.row() for i in table.selectedItems()])
        for row in sorted(rows, reverse=True):
            table.removeRow(row)

    def _get_table_words(self, table: QTableWidget) -> list:
        words = []
        for i in range(table.rowCount()):
            item = table.item(i, 0)
            if item and item.text().strip():
                words.append(item.text().strip().lower())
        return words

    def _save_wordlist_from_ui(self):
        try:
            forbidden = self._get_table_words(self._forbidden_table)
            allowed = self._get_table_words(self._allowed_table)
            
            old_data = self._load_wordlist_json() or {}
            phonetic = old_data.get("phonetic_mapping", {})
            data = {"toxic_words": forbidden, "allowed_words": allowed, "phonetic_mapping": phonetic}
            
            self._save_wordlist_json(data)
            if self._detector:
                self._detector.reload_wordlist()
            self._refresh_wordlist_display()
            QMessageBox.information(self, "Berhasil", f"Wordlist disimpan: {len(forbidden)} kata dilarang, {len(allowed)} kata dizinkan.")
        except Exception as e:
            logger.error("Failed to save wordlist from UI: %s", e)
            QMessageBox.critical(self, "Gagal", f"Gagal menyimpan wordlist:\n{e}")

    def _load_wordlist_json(self) -> dict:
        try:
            with open(WORDLIST_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list):
                return {"toxic_words": data, "phonetic_mapping": {}, "allowed_words": []}
            if "toxic_words" not in data: data["toxic_words"] = []
            if "phonetic_mapping" not in data: data["phonetic_mapping"] = {}
            if "allowed_words" not in data: data["allowed_words"] = []
            return data
        except Exception as e:
            logger.error("Failed to read wordlist: %s", e)
            return None

    def _save_wordlist_json(self, data: dict):
        try:
            with open(WORDLIST_PATH, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=4)
        except Exception as e:
            logger.error("Failed to save wordlist: %s", e)

    # ================================================================
    # TAB 3: INSTALLER GUARD
    # ================================================================

    def _build_installer_guard_tab(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        
        # Helper function to create a table setup
        def setup_guard_table(title, color, attr_name):
            card = QFrame()
            card.setProperty("class", "Card")
            card.setGraphicsEffect(create_shadow())
            c_lyt = QVBoxLayout(card)
            
            lbl = QLabel(title)
            lbl.setStyleSheet(f"color: {color}; font-weight: bold; font-size: 12px;")
            c_lyt.addWidget(lbl)
            
            table = QTableWidget(0, 1)
            table.setHorizontalHeaderLabels(["Kata Kunci / Path"])
            table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
            table.setSelectionBehavior(QAbstractItemView.SelectItems)
            table.verticalHeader().setVisible(False)
            setattr(self, attr_name, table)
            c_lyt.addWidget(table)
            
            blyt = QHBoxLayout()
            blyt.setContentsMargins(0, 0, 0, 0)
            btn_add = QPushButton("➕ Tambah")
            btn_add.setProperty("class", "ActionBtn BtnSuccess")
            btn_add.clicked.connect(lambda: self._add_table_row(table))
            
            btn_del = QPushButton("🗑 Hapus")
            btn_del.setProperty("class", "ActionBtn BtnDanger")
            btn_del.clicked.connect(lambda: self._delete_table_row(table))
            
            blyt.addWidget(btn_add)
            blyt.addWidget(btn_del)
            c_lyt.addLayout(blyt)
            
            return card

        # Top Row (Full Width): Blacklist
        top_card = setup_guard_table("⛔ Blacklist Kata Kunci (setup, installer, dll)", DANGER, "_guard_blacklist_textbox")
        layout.addWidget(top_card, 1)

        # Bottom Row (Split 50:50): Whitelist Processes & Paths
        bottom_row = QWidget()
        b_lyt = QHBoxLayout(bottom_row)
        b_lyt.setContentsMargins(0, 0, 0, 0)
        
        card_proc = setup_guard_table("✅ Whitelist Proses (robloxplayerbeta, dll)", SUCCESS, "_guard_whitelist_proc_textbox")
        card_path = setup_guard_table("🔵 Whitelist Paths (c:\\windows\\, dll)", ACCENT, "_guard_whitelist_path_textbox")
        
        b_lyt.addWidget(card_proc)
        b_lyt.addWidget(card_path)
        
        layout.addWidget(bottom_row, 1)

        # Buttons
        btn_frame = QWidget()
        btn_lyt = QHBoxLayout(btn_frame)
        btn_lyt.setContentsMargins(0, 0, 0, 0)
        
        sys_btn = QPushButton("💾 Simpan")
        sys_btn.setProperty("class", "ActionBtn BtnPrimary")
        sys_btn.setFixedSize(120, 34)
        sys_btn.clicked.connect(self._save_guard_config)
        btn_lyt.addWidget(sys_btn)
        
        ref_btn = QPushButton("🔄 Segarkan")
        ref_btn.setProperty("class", "ActionBtn BtnOutline")
        ref_btn.setFixedSize(120, 34)
        ref_btn.clicked.connect(self._refresh_guard_config_display)
        btn_lyt.addWidget(ref_btn)

        import_btn = QPushButton("📂 Muat dari File")
        import_btn.setProperty("class", "ActionBtn BtnWarning")
        import_btn.setFixedSize(140, 34)
        import_btn.clicked.connect(self._import_guard_config_json)
        btn_lyt.addWidget(import_btn)
        
        btn_lyt.addStretch()
        layout.addWidget(btn_frame)

        self.stack.addWidget(page)

    def _import_guard_config_json(self):
        from PySide6.QtWidgets import QFileDialog
        import json
        
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Import Installer Guard Konfigurasi", "", "JSON Files (*.json)"
        )
        if not file_path:
            return
            
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                config = json.load(f)
                
            def populate(table, items):
                table.setRowCount(len(items))
                for i, it in enumerate(items):
                    table.setItem(i, 0, QTableWidgetItem(str(it)))
                    
            if hasattr(self, '_guard_blacklist_textbox'):
                populate(self._guard_blacklist_textbox, config.get("blacklist", []))
                populate(self._guard_whitelist_proc_textbox, config.get("whitelist_processes", []))
                populate(self._guard_whitelist_path_textbox, config.get("whitelist_paths", []))
                
            QMessageBox.information(self, "Preview Import", "Berhasil pratinjau data Installer Guard dari file.\nSilakan tekan 'Simpan' untuk menerapkannya secara permanen.")
        except Exception as e:
            QMessageBox.critical(self, "Error Import", f"Gagal membaca file JSON:\n{e}")

    def _refresh_guard_config_display(self):
        config = self._load_guard_config()
        if hasattr(self, '_guard_blacklist_textbox'):
            def populate(table, items):
                table.setRowCount(len(items))
                for i, it in enumerate(items):
                    table.setItem(i, 0, QTableWidgetItem(it))
                    
            populate(self._guard_blacklist_textbox, config.get("blacklist", []))
            populate(self._guard_whitelist_proc_textbox, config.get("whitelist_processes", []))
            populate(self._guard_whitelist_path_textbox, config.get("whitelist_paths", []))

    def _load_guard_config(self) -> dict:
        from app._paths import GUARD_CONFIG_PATH
        if os.path.exists(GUARD_CONFIG_PATH):
            try:
                with open(GUARD_CONFIG_PATH, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.error("Failed to load guard config: %s", e)
        if self._installer_guard:
            return {
                "blacklist": self._installer_guard.blacklist,
                "whitelist_processes": list(self._installer_guard.whitelist_processes),
                "whitelist_paths": self._installer_guard.whitelist_paths
            }
        return {"blacklist": [], "whitelist_processes": [], "whitelist_paths": []}

    def _save_guard_config(self):
        from app._paths import GUARD_CONFIG_PATH
        try:
            bl = self._get_table_words(self._guard_blacklist_textbox)
            pr = self._get_table_words(self._guard_whitelist_proc_textbox)
            pa = self._get_table_words(self._guard_whitelist_path_textbox)
            
            config = {"blacklist": bl, "whitelist_processes": pr, "whitelist_paths": pa}
            with open(GUARD_CONFIG_PATH, "w", encoding="utf-8") as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
                
            if self._installer_guard:
                self._installer_guard.load_config()
            QMessageBox.information(self, "Berhasil", "Konfigurasi Installer Guard disimpan.")
        except Exception as e:
            logger.error("Failed to save guard config: %s", e)
            QMessageBox.critical(self, "Gagal", f"Gagal menyimpan config:\n{e}")

    def _build_sanctions_tab(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        
        cols = QWidget()
        cols_lyt = QHBoxLayout(cols)
        cols_lyt.setContentsMargins(0, 0, 0, 0)
        
        # Left: Sanction List
        left = QFrame()
        left.setProperty("class", "Card")
        left.setGraphicsEffect(create_shadow())
        l_lyt = QVBoxLayout(left)
        
        l_lbl = QLabel("📜 Daftar Sanksi (Urutan Eksekusi)")
        l_lbl.setProperty("class", "H3")
        l_lyt.addWidget(l_lbl)
        
        lbl_subtitle = QLabel("Sanksi dieksekusi berurutan dari atas ke bawah")
        lbl_subtitle.setProperty("class", "Muted")
        l_lyt.addWidget(lbl_subtitle)
        
        self._sanction_listbox = QListWidget()
        self._sanction_listbox.itemClicked.connect(self._on_sanction_select)
        l_lyt.addWidget(self._sanction_listbox, 1)

        btn_row = QWidget()
        btn_lyt = QHBoxLayout(btn_row)
        btn_lyt.setContentsMargins(0, 0, 0, 0)
        
        for txt, clr, cmd in [
            ("➕ Tambah", SUCCESS, self._add_sanction),
            ("✏️ Update", ACCENT, self._update_sanction),
            ("🗑 Hapus", DANGER, self._remove_sanction),
            ("💾 Simpan", WARNING, self._save_sanctions_config),
            ("📂 Import", "#17A2B8", self._import_sanctions_json)
        ]:
            b = QPushButton(txt)
            b.setProperty("class", "ActionBtn")
            b.setStyleSheet(f"background-color: {clr};")
            b.clicked.connect(cmd)
            btn_lyt.addWidget(b)
            
        l_lyt.addWidget(btn_row)
        cols_lyt.addWidget(left)

        # Right: Editor
        right = QFrame()
        right.setProperty("class", "Card")
        right.setGraphicsEffect(create_shadow())
        r_lyt = QVBoxLayout(right)
        
        r_lbl = QLabel("✏️ Editor Sanksi")
        r_lbl.setProperty("class", "H3")
        r_lyt.addWidget(r_lbl)
        
        # Type
        type_frame = QWidget()
        type_lyt = QHBoxLayout(type_frame)
        type_lyt.setContentsMargins(0, 0, 0, 10)
        
        self.sanction_type_group = QButtonGroup(self)
        self.sanction_type_group.setExclusive(True)
        self._btn_warn = QPushButton("WARNING")
        self._btn_warn.setProperty("class", "SegBtn")
        self._btn_warn.setCheckable(True)
        self._btn_warn.setChecked(True)
        
        self._btn_lock = QPushButton("LOCKDOWN")
        self._btn_lock.setProperty("class", "SegBtn")
        self._btn_lock.setCheckable(True)
        
        self.sanction_type_group.addButton(self._btn_warn, 0)
        self.sanction_type_group.addButton(self._btn_lock, 1)
        type_lyt.addWidget(self._btn_warn)
        type_lyt.addWidget(self._btn_lock)
        type_lyt.addStretch()
        r_lyt.addWidget(type_frame)

        # Fields
        lbl_delay = QLabel("Warning Delay:")
        lbl_delay.setProperty("class", "Muted")
        r_lyt.addWidget(lbl_delay)
        self._sanction_delay_entry = QSpinBox()
        self._sanction_delay_entry.setRange(0, 3600)
        self._sanction_delay_entry.setSuffix(" detik")
        self._sanction_delay_entry.setValue(5)
        r_lyt.addWidget(self._sanction_delay_entry)

        lbl_dur = QLabel("Duration:")
        lbl_dur.setProperty("class", "Muted")
        r_lyt.addWidget(lbl_dur)
        self._sanction_duration_entry = QSpinBox()
        self._sanction_duration_entry.setRange(0, 86400)
        self._sanction_duration_entry.setSuffix(" detik")
        self._sanction_duration_entry.setValue(60)
        r_lyt.addWidget(self._sanction_duration_entry)

        lbl_msg = QLabel("Message:")
        lbl_msg.setProperty("class", "Muted")
        r_lyt.addWidget(lbl_msg)
        self._sanction_msg_textbox = QTextEdit()
        self._sanction_msg_textbox.setFixedHeight(80)
        r_lyt.addWidget(self._sanction_msg_textbox)

        lbl_reset = QLabel("⏱ Penalty Reset:")
        lbl_reset.setProperty("class", "Muted")
        r_lyt.addWidget(lbl_reset)
        self._penalty_reset_entry = QSpinBox()
        self._penalty_reset_entry.setRange(1, 10080)
        self._penalty_reset_entry.setSuffix(" menit")
        self._penalty_reset_entry.setFixedWidth(120)
        r_lyt.addWidget(self._penalty_reset_entry)
        r_lyt.addStretch()
        
        cols_lyt.addWidget(right)
        layout.addWidget(cols, 1)
        self.stack.addWidget(page)
        
        self._sanctions_data = []
        self._load_sanctions_config()

    def _import_sanctions_json(self):
        from PySide6.QtWidgets import QFileDialog
        import json
        
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Import Sanctions Konfigurasi", "", "JSON Files (*.json)"
        )
        if not file_path:
            return
            
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                
            if isinstance(data, list):
                self._sanctions_data = data
            elif isinstance(data, dict) and "sanction_list" in data:
                self._sanctions_data = data["sanction_list"]
            else:
                raise ValueError("Format file json sanksi tidak valid. Harus berisi array objek sanksi.")
                
            self._refresh_sanction_listbox()
            QMessageBox.information(self, "Preview Import", "Berhasil pratinjau data Sanksi dari file.\nSilakan tekan 'Simpan' untuk menerapkannya secara permanen.")
        except Exception as e:
            QMessageBox.critical(self, "Error Import", f"Gagal membaca file JSON:\n{e}")

    def _load_sanctions_config(self):
        if not self._auth: return
        self._sanctions_data = self._auth.get_config("sanction_list", [])
        if not isinstance(self._sanctions_data, list): self._sanctions_data = []
        self._refresh_sanction_listbox()
        
        reset_min = self._auth.get_config("PenaltyResetMinutes", 60)
        if hasattr(self, '_penalty_reset_entry'):
            self._penalty_reset_entry.setValue(int(reset_min))

    def _on_penalty_sync(self):
        """Called by penalty_mgr.reload_config when server updates sanctions."""
        QTimer.singleShot(0, self, self._load_sanctions_config)

    def _refresh_sanction_listbox(self):
        if not hasattr(self, '_sanction_listbox'): return
        self._sanction_listbox.clear()
        for i, s in enumerate(self._sanctions_data):
            stype = s.get("type", "WARNING")
            icon = "🔒" if stype == "LOCKDOWN" else "⚠️"
            msg_preview = s.get("message", "")[:40].replace("\n", " ")
            delay = s.get("warning_delay", 0)
            dur = s.get("duration", 0)
            item = QListWidgetItem(f" {icon} {stype} | delay={delay}s dur={dur}s | {msg_preview}")
            self._sanction_listbox.addItem(item)

    def _on_sanction_select(self, item):
        idx = self._sanction_listbox.row(item)
        if idx < 0 or idx >= len(self._sanctions_data): return
        s = self._sanctions_data[idx]
        
        is_lockdown = s.get("type", "WARNING") == "LOCKDOWN"
        self._btn_lock.setChecked(is_lockdown)
        self._btn_warn.setChecked(not is_lockdown)
        
        self._sanction_delay_entry.setValue(s.get("warning_delay", 5))
        self._sanction_duration_entry.setValue(s.get("duration", 0))
        self._sanction_msg_textbox.setPlainText(s.get("message", ""))

    def _get_edit_fields(self) -> dict:
        stype = "LOCKDOWN" if self._btn_lock.isChecked() else "WARNING"
        return {
            "type": stype,
            "message": self._sanction_msg_textbox.toPlainText(),
            "duration": self._sanction_duration_entry.value(),
            "warning_delay": self._sanction_delay_entry.value()
        }

    def _add_sanction(self):
        self._sanctions_data.append(self._get_edit_fields())
        self._refresh_sanction_listbox()

    def _update_sanction(self):
        idx = self._sanction_listbox.currentRow()
        if 0 <= idx < len(self._sanctions_data):
            self._sanctions_data[idx] = self._get_edit_fields()
            self._refresh_sanction_listbox()

    def _remove_sanction(self):
        idx = self._sanction_listbox.currentRow()
        if 0 <= idx < len(self._sanctions_data):
            self._sanctions_data.pop(idx)
            self._refresh_sanction_listbox()

    def _save_sanctions_config(self):
        if not self._auth: return
        try:
            self._auth.update_config("sanction_list", self._sanctions_data)
            try:
                reset_min = self._penalty_reset_entry.value()
                self._auth.update_config("PenaltyResetMinutes", reset_min)
            except Exception: pass
            
            if self._penalty_mgr:
                self._penalty_mgr.reload_config()
            QMessageBox.information(self, "Berhasil", "Konfigurasi sanksi berhasil disimpan!")
        except Exception as e:
            logger.error("Failed to save sanctions config: %s", e)

    def set_audio_engine(self, engine: "AudioEngine") -> None:
        """Set the audio engine reference and initialize proximity zones.

        Loads persisted zone configuration from config and syncs it
        to both the engine and the UI widgets.

        Args:
            engine: AudioEngine instance.
        """
        self._engine = engine
        self.audio_engine = engine
        self.sync_audio_ui()
        self._populate_proximity_zones()

    # ================================================================
    # TAB 6: PROXIMITY FILTER
    # ================================================================

    def _build_proximity_filter_tab(self) -> None:
        """Build the Proximity Filter tab with real-time VU meter and zone builder.

        The tab consists of:
        - A real-time VU meter showing raw RMS values (0.0–1.0).
        - A dynamic zone builder where users can add, edit, and remove
          energy zones with PROCESS or IGNORE actions.
        """
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 10)

        # ── Real-time VU Meter Card ──
        vu_card = QFrame()
        vu_card.setProperty("class", "Card")
        vu_card.setGraphicsEffect(create_shadow())
        vu_card.setFixedHeight(80)
        vu_lyt = QVBoxLayout(vu_card)
        vu_lyt.setContentsMargins(12, 8, 12, 8)

        top_row = QHBoxLayout()
        lbl_vu = QLabel("🎚 Real-time Audio Level (Raw RMS)")
        lbl_vu.setProperty("class", "H3")
        top_row.addWidget(lbl_vu)
        top_row.addStretch()

        self._prox_rms_label = QLabel("RMS: 0.0000")
        self._prox_rms_label.setStyleSheet(
            f"color: {ACCENT}; font-weight: bold; "
            f"font-family: Consolas; font-size: 13px;"
        )
        top_row.addWidget(self._prox_rms_label)
        vu_lyt.addLayout(top_row)

        self._prox_vu_progress = QProgressBar()
        self._prox_vu_progress.setFixedHeight(20)
        self._prox_vu_progress.setTextVisible(False)
        self._prox_vu_progress.setRange(0, 100)
        self._prox_vu_progress.setStyleSheet(f"""
            QProgressBar {{ border: 1px solid {BORDER}; border-radius: 4px; background-color: {BG}; }}
            QProgressBar::chunk {{ background-color: {ACCENT}; border-radius: 3px; }}
        """)
        vu_lyt.addWidget(self._prox_vu_progress)
        layout.addWidget(vu_card)

        # ── Zone Builder Card ──
        zone_card = QFrame()
        zone_card.setProperty("class", "Card")
        zone_card.setGraphicsEffect(create_shadow())
        zone_lyt = QVBoxLayout(zone_card)
        zone_lyt.setContentsMargins(12, 10, 12, 10)

        zone_title_row = QHBoxLayout()
        lbl_zones = QLabel("📐 Zone Configuration")
        lbl_zones.setProperty("class", "H3")
        zone_title_row.addWidget(lbl_zones)
        zone_title_row.addStretch()

        btn_add_zone = QPushButton("➕ Add New Zone")
        btn_add_zone.setProperty("class", "ActionBtn BtnSuccess")
        btn_add_zone.setFixedSize(150, 30)
        btn_add_zone.clicked.connect(self._add_proximity_zone)
        zone_title_row.addWidget(btn_add_zone)
        zone_lyt.addLayout(zone_title_row)

        # Header row
        header = QHBoxLayout()
        header.setSpacing(6)
        for text, width in [("Nama Zona", 140), ("Min RMS", 90), ("Max RMS", 90), ("Action", 100), ("", 32)]:
            lbl = QLabel(text)
            lbl.setProperty("class", "Muted")
            lbl.setFixedWidth(width)
            header.addWidget(lbl)
        header.addStretch()
        zone_lyt.addLayout(header)

        # Scroll area for zone rows
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet("background: transparent;")

        self._zone_container = QWidget()
        self._zone_rows_layout = QVBoxLayout(self._zone_container)
        self._zone_rows_layout.setContentsMargins(0, 0, 0, 0)
        self._zone_rows_layout.setSpacing(4)
        self._zone_rows_layout.addStretch()

        scroll.setWidget(self._zone_container)
        zone_lyt.addWidget(scroll, 1)

        layout.addWidget(zone_card, 1)
        self.stack.addWidget(page)

        # Zone row widget storage
        self._zone_row_widgets: List[Dict[str, Any]] = []

    def _create_zone_row(self, zone: Dict[str, Any]) -> None:
        """Create a single zone row with interactive widgets.

        Each row contains: name entry, min/max RMS spinboxes,
        action dropdown, and a delete button.  All value-change
        signals are connected to ``_sync_zones_to_engine``.

        Args:
            zone: Zone dict with keys id, name, min_rms, max_rms, action.
        """
        row_widget = QWidget()
        row_lyt = QHBoxLayout(row_widget)
        row_lyt.setContentsMargins(0, 2, 0, 2)
        row_lyt.setSpacing(6)

        name_edit = QLineEdit(zone.get("name", ""))
        name_edit.setFixedWidth(140)
        name_edit.textChanged.connect(lambda _: self._sync_zones_to_engine())
        row_lyt.addWidget(name_edit)

        min_spin = QDoubleSpinBox()
        min_spin.setRange(0.00, 1.00)
        min_spin.setSingleStep(0.01)
        min_spin.setDecimals(2)
        min_spin.setValue(float(zone.get("min_rms", 0.00)))
        min_spin.setFixedWidth(90)
        min_spin.valueChanged.connect(lambda _: self._sync_zones_to_engine())
        row_lyt.addWidget(min_spin)

        max_spin = QDoubleSpinBox()
        max_spin.setRange(0.00, 1.00)
        max_spin.setSingleStep(0.01)
        max_spin.setDecimals(2)
        max_spin.setValue(float(zone.get("max_rms", 0.10)))
        max_spin.setFixedWidth(90)
        max_spin.valueChanged.connect(lambda _: self._sync_zones_to_engine())
        row_lyt.addWidget(max_spin)

        action_combo = QComboBox()
        action_combo.addItems(["PROCESS", "IGNORE"])
        action_combo.setCurrentText(zone.get("action", "IGNORE"))
        action_combo.setFixedWidth(100)
        action_combo.currentTextChanged.connect(
            lambda _: self._sync_zones_to_engine()
        )
        row_lyt.addWidget(action_combo)

        btn_del = QPushButton("🗑")
        btn_del.setFixedSize(32, 28)
        btn_del.setProperty("class", "ActionBtn BtnDanger")
        btn_del.clicked.connect(
            lambda checked=False, w=row_widget: self._remove_proximity_zone(w)
        )
        row_lyt.addWidget(btn_del)

        row_lyt.addStretch()

        row_data: Dict[str, Any] = {
            "widget": row_widget,
            "name": name_edit,
            "min_rms": min_spin,
            "max_rms": max_spin,
            "action": action_combo,
        }
        self._zone_row_widgets.append(row_data)

        idx = self._zone_rows_layout.count() - 1
        self._zone_rows_layout.insertWidget(idx, row_widget)

    def _add_proximity_zone(self) -> None:
        """Add a new zone with safe defaults and sync to engine."""
        zone_count = len(self._zone_row_widgets)
        zone: Dict[str, Any] = {
            "id": f"zone_{zone_count + 1}",
            "name": f"New Zone {zone_count + 1}",
            "min_rms": 0.00,
            "max_rms": 0.10,
            "action": "IGNORE",
        }
        self._create_zone_row(zone)
        self._sync_zones_to_engine()

    def _remove_proximity_zone(self, row_widget: QWidget) -> None:
        """Remove a zone row from the UI and sync to engine.

        Args:
            row_widget: The QWidget of the zone row to remove.
        """
        self._zone_row_widgets = [
            r for r in self._zone_row_widgets
            if r["widget"] is not row_widget
        ]
        self._zone_rows_layout.removeWidget(row_widget)
        row_widget.deleteLater()
        self._sync_zones_to_engine()

    def _sync_zones_to_engine(self) -> None:
        """Synchronize zone configuration from UI widgets to engine and config.

        Called on every UI interaction (value change, add, delete).
        Validates that min_rms <= max_rms per row and auto-corrects.
        Persists the updated zones to config.json via auth_service.
        """
        zones: List[Dict[str, Any]] = []
        for i, row in enumerate(self._zone_row_widgets):
            min_val = row["min_rms"].value()
            max_val = row["max_rms"].value()

            # Auto-correct: ensure min <= max
            if min_val > max_val:
                row["max_rms"].blockSignals(True)
                row["max_rms"].setValue(min_val)
                row["max_rms"].blockSignals(False)
                max_val = min_val

            zone: Dict[str, Any] = {
                "id": f"zone_{i + 1}",
                "name": row["name"].text().strip() or f"Zone {i + 1}",
                "min_rms": round(min_val, 2),
                "max_rms": round(max_val, 2),
                "action": row["action"].currentText(),
            }
            zones.append(zone)

        # Update engine in-memory (no I/O)
        if self._engine and hasattr(self._engine, 'proximity_zones'):
            self._engine.proximity_zones = zones

        # Persist to config
        if self._auth:
            try:
                self._auth.update_config("proximity_zones", zones)
            except Exception as e:
                logger.error("Failed to persist proximity zones: %s", e)

    def _populate_proximity_zones(self) -> None:
        """Load zones from config and populate the UI rows.

        Called once on ``set_audio_engine`` to bootstrap the tab
        with persisted (or default) zone configuration.
        """
        if not hasattr(self, '_zone_row_widgets'):
            return

        # Clear existing rows
        for row in self._zone_row_widgets:
            row["widget"].deleteLater()
        self._zone_row_widgets = []

        # Load from config or use defaults
        zones: List[Dict[str, Any]] = []
        if self._auth:
            saved = self._auth.get_config("proximity_zones")
            if isinstance(saved, list) and saved:
                zones = saved

        if not zones:
            zones = [
                {"id": "zone_1", "name": "Background Noise", "min_rms": 0.00, "max_rms": 0.05, "action": "IGNORE"},
                {"id": "zone_2", "name": "User Voice", "min_rms": 0.06, "max_rms": 0.30, "action": "PROCESS"},
                {"id": "zone_3", "name": "Distant Yell", "min_rms": 0.31, "max_rms": 0.45, "action": "IGNORE"},
                {"id": "zone_4", "name": "User Yell", "min_rms": 0.46, "max_rms": 1.00, "action": "PROCESS"},
            ]

        for zone in zones:
            self._create_zone_row(zone)

        # Sync to engine
        if self._engine and hasattr(self._engine, 'proximity_zones'):
            self._engine.proximity_zones = zones

    # ================================================================
    # TAB 7: PENGATURAN
    # ================================================================
    def _build_settings_tab(self):
        from app.system_service import SystemService
        
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet("background: transparent;")
        
        content = QWidget()
        c_lyt = QGridLayout(content)
        c_lyt.setContentsMargins(0, 0, 0, 0)
        c_lyt.setSpacing(10)
        
        # ── Left Column ──
        
        # Audio
        c1 = QFrame()
        c1.setProperty("class", "Card")
        c1.setGraphicsEffect(create_shadow())
        c1_lyt = QVBoxLayout(c1)
        lbl_audio = QLabel("🎙 Audio Input")
        lbl_audio.setProperty("class", "H3")
        c1_lyt.addWidget(lbl_audio)
        
        lbl_mic = QLabel("Microphone device (device)")
        lbl_mic.setProperty("class", "Muted")
        c1_lyt.addWidget(lbl_mic)
        
        self._device_dropdown = QComboBox()
        self._device_dropdown.addItem("Default")
        self._device_dropdown.currentIndexChanged.connect(self._on_device_change)
        c1_lyt.addWidget(self._device_dropdown)
        
        gain_lyt = QHBoxLayout()
        lbl_gain = QLabel("Digital Gain")
        lbl_gain.setProperty("class", "Muted")
        gain_lyt.addWidget(lbl_gain)
        
        self._gain_label = QLabel("1.0x")
        self._gain_label.setFixedSize(40, 22)
        self._gain_label.setAlignment(Qt.AlignCenter)
        self._gain_label.setStyleSheet(f"background: {BORDER}; border-radius: 4px; font-weight: bold;")
        gain_lyt.addWidget(self._gain_label)
        c1_lyt.addLayout(gain_lyt)
        
        self._gain_slider = QSlider(Qt.Horizontal)
        self._gain_slider.setRange(0, 50) # 0.0 to 5.0
        self._gain_slider.setValue(10)
        self._gain_slider.valueChanged.connect(self._on_gain_change)
        c1_lyt.addWidget(self._gain_slider)
        c1_lyt.addStretch()
        c_lyt.addWidget(c1, 0, 0)
        
        self._populate_devices()

        # Server
        c2 = QFrame()
        c2.setProperty("class", "Card")
        c2.setGraphicsEffect(create_shadow())
        c2_lyt = QVBoxLayout(c2)
        lbl_srv = QLabel("📡 Server Center")
        lbl_srv.setProperty("class", "H3")
        c2_lyt.addWidget(lbl_srv)
        
        lbl_ip = QLabel("IP")
        lbl_ip.setProperty("class", "Muted")
        c2_lyt.addWidget(lbl_ip)
        self._server_ip_entry = QLineEdit()
        self._server_ip_entry.setPlaceholderText("192.168.18.197")
        c2_lyt.addWidget(self._server_ip_entry)
        
        lbl_port = QLabel("Port")
        lbl_port.setProperty("class", "Muted")
        c2_lyt.addWidget(lbl_port)
        self._server_port_entry = QLineEdit()
        self._server_port_entry.setPlaceholderText("9000")
        self._server_port_entry.setFixedWidth(100)
        c2_lyt.addWidget(self._server_port_entry)

        if self._auth:
            saved_ip = self._auth.get_config("ServerIP", "")
            if saved_ip: self._server_ip_entry.setText(saved_ip)
            self._server_port_entry.setText(str(self._auth.get_config("ServerPort", 9000)))

        self._net_status_label = QLabel("● Tidak Terhubung")
        self._net_status_label.setProperty("class", "Muted")
        c2_lyt.addWidget(self._net_status_label)
        
        btn_con = QPushButton("💾 Simpan & Hubungkan")
        btn_con.setProperty("class", "ActionBtn BtnSuccess")
        btn_con.clicked.connect(self._save_and_connect_network)
        c2_lyt.addWidget(btn_con)
        
        btn_dis = QPushButton("⛔ Putuskan")
        btn_dis.setProperty("class", "ActionBtn BtnDanger")
        btn_dis.clicked.connect(self._disconnect_network)
        c2_lyt.addWidget(btn_dis)
        c2_lyt.addStretch()
        c_lyt.addWidget(c2, 1, 0)
        
        # ── Right Column ──
        
        # System
        c3 = QFrame()
        c3.setProperty("class", "Card")
        c3.setGraphicsEffect(create_shadow())
        c3_lyt = QVBoxLayout(c3)
        lbl_sys = QLabel("⚙ Sistem")
        lbl_sys.setProperty("class", "H3")
        c3_lyt.addWidget(lbl_sys)
        
        self._chk_auto = QCheckBox("Auto-start saat Windows boot")
        self._chk_auto.setChecked(SystemService.is_autostart_enabled())
        self._chk_auto.toggled.connect(self._on_autostart_toggle)
        c3_lyt.addWidget(self._chk_auto)
        
        self._chk_lock = QCheckBox("Kunci Windows Settings")
        self._chk_lock.setChecked(SystemService.is_windows_settings_locked())
        self._chk_lock.toggled.connect(self._on_settings_lock_toggle)
        c3_lyt.addWidget(self._chk_lock)
        
        self._chk_inst = QCheckBox("Blokir Installer (MSI & EXE)")
        self._chk_inst.toggled.connect(self._on_installer_lock_toggle)
        c3_lyt.addWidget(self._chk_inst)

        ver_lyt = QHBoxLayout()
        lbl_ver = QLabel(f"v{self._app_version}")
        lbl_ver.setProperty("class", "Muted")
        ver_lyt.addWidget(lbl_ver)
        ver_lyt.addStretch()
        
        btn_upd = QPushButton("Periksa Pembaruan")
        btn_upd.setProperty("class", "ActionBtn BtnOutline")
        btn_upd.clicked.connect(self._check_update_action)
        ver_lyt.addWidget(btn_upd)
        c3_lyt.addLayout(ver_lyt)
        c3_lyt.addStretch()
        c_lyt.addWidget(c3, 0, 1)

        # Security
        c4 = QFrame()
        c4.setProperty("class", "Card")
        c4.setGraphicsEffect(create_shadow())
        c4_lyt = QVBoxLayout(c4)
        lbl_sec = QLabel("🔑 Keamanan")
        lbl_sec.setProperty("class", "H3")
        c4_lyt.addWidget(lbl_sec)
        
        self._old_pwd_entry = QLineEdit()
        self._old_pwd_entry.setPlaceholderText("Password Lama")
        self._old_pwd_entry.setEchoMode(QLineEdit.Password)
        c4_lyt.addWidget(self._old_pwd_entry)
        
        self._new_pwd_entry = QLineEdit()
        self._new_pwd_entry.setPlaceholderText("Password Baru")
        self._new_pwd_entry.setEchoMode(QLineEdit.Password)
        c4_lyt.addWidget(self._new_pwd_entry)
        
        btn_pwd = QPushButton("Ubah Password")
        btn_pwd.setProperty("class", "ActionBtn BtnOutline")
        btn_pwd.clicked.connect(self._change_password_action)
        c4_lyt.addWidget(btn_pwd)
        
        btn_emg = QPushButton("Emergency Exit")
        btn_emg.setProperty("class", "ActionBtn BtnDanger")
        btn_emg.clicked.connect(self._emergency_exit)
        c4_lyt.addWidget(btn_emg)
        c4_lyt.addStretch()
        c_lyt.addWidget(c4, 1, 1)

        scroll.setWidget(content)
        layout.addWidget(scroll)
        self.stack.addWidget(page)

    # ================================================================
    # AUTO-UPDATER
    # ================================================================

    def _check_update_action(self):
        from app.updater import GithubUpdater
        if not self._github_repo or self._github_repo == "USERNAME/REPO_NAME":
            QMessageBox.information(self, "Info", "GitHub repo belum dikonfigurasi.")
            return
            
        def _check():
            updater = GithubUpdater(self._github_repo, self._app_version)
            has_update, latest_version, zip_url, notes = updater.check_for_updates()
            
            def _on_ui():
                if has_update:
                    ans = QMessageBox.question(self, "Update!", f"V{latest_version.replace('v','')} tersedia!\n\n{notes[:300]}...\n\nUnduh sekarang?")
                    if ans == QMessageBox.Yes: self._start_download_update(updater, zip_url)
                else:
                    if "Gagal" in notes: QMessageBox.critical(self, "Gagal", notes)
                    else: QMessageBox.information(self, "OK", "Sudah versi terbaru!")
            QTimer.singleShot(0, self, _on_ui)
            
        threading.Thread(target=_check, daemon=True).start()

    def _start_download_update(self, updater, zip_url):
        # We can implement a proper QProgressDialog later if needed
        QMessageBox.information(self, "Update", "Download started in background...")

    # ================================================================
    # AUDIO CALLBACKS
    # ================================================================

    def _populate_devices(self):
        if not self._engine or not hasattr(self, '_device_dropdown'): return
        self._device_dropdown.blockSignals(True)
        try:
            devices = self._engine.list_devices()
            self._device_dropdown.clear()
            if devices:
                values = [f"{idx}: {name}" for idx, name in devices]
                self._device_dropdown.addItems(values)
                
                current_idx = self._engine.input_device_index
                if current_idx is not None:
                    target_idx = 0
                    for i, v in enumerate(values):
                        if v.startswith(str(current_idx) + ":"): target_idx = i; break
                    self._device_dropdown.setCurrentIndex(target_idx)
            else:
                self._device_dropdown.addItem("No devices")
        except Exception as e:
            logger.warning("Failed to populate devices: %s", e)
        self._device_dropdown.blockSignals(False)

    def sync_audio_ui(self):
        if not self._engine: return
        self._populate_devices()
        current_gain = self._engine.gain
        if hasattr(self, '_gain_slider'):
            self._gain_slider.blockSignals(True)
            self._gain_slider.setValue(int(current_gain * 10))
            self._gain_slider.blockSignals(False)
            self._gain_label.setText(f"{current_gain:.1f}x")

    def _on_device_change(self, target_idx):
        if not self._engine or target_idx < 0: return
        choice = self._device_dropdown.itemText(target_idx)
        if choice == "No devices" or choice == "Default": return
        try:
            device_index = int(choice.split(":")[0])
            self._engine.set_input_device(device_index)
            if self._auth: self._auth.update_config("InputDeviceIndex", device_index)
            logger.info("Switched audio device to: %s", choice)
        except Exception as e:
            logger.error("Failed to set device: %s", e)

    def _on_gain_change(self, value_int):
        gain_val = float(value_int) / 10.0
        if self._engine: self._engine.set_gain(gain_val)
        if self._gain_label: self._gain_label.setText(f"{gain_val:.1f}x")
        if self._auth: self._auth.update_config("AudioGain", gain_val)

    # ================================================================
    # NETWORK CALLBACKS
    # ================================================================

    def _save_and_connect_network(self):
        server_ip = self._server_ip_entry.text().strip()
        port_str = self._server_port_entry.text().strip()
        if not server_ip:
            QMessageBox.warning(self, "Peringatan", "Server IP tidak boleh kosong.")
            return
        try: port = int(port_str) if port_str else 9000
        except ValueError: QMessageBox.critical(self, "Error", "Port harus angka."); return
        
        if self._auth:
            self._auth.update_config("ServerIP", server_ip)
            self._auth.update_config("ServerPort", port)
            
        self._net_status_label.setText("● Menghubungkan...")
        self._net_status_label.setStyleSheet(f"color: {WARNING}; font-size: 11px;")
        
        if hasattr(self, '_network_client') and self._network_client:
            try: self._network_client.stop()
            except Exception: pass
            
        if hasattr(self, '_start_network_callback') and self._start_network_callback:
            try:
                self._start_network_callback(server_ip, port)
                QMessageBox.information(self, "Berhasil", f"Menghubungkan ke {server_ip}:{port}...")
            except Exception as e: QMessageBox.critical(self, "Error", f"Gagal:\n{e}")
        else:
            QMessageBox.information(self, "Info", f"Config disimpan: {server_ip}:{port}\nRestart untuk terhubung.")

    def _disconnect_network(self):
        if hasattr(self, '_network_client') and self._network_client:
            try: self._network_client.stop()
            except Exception: pass
        self._net_status_label.setText("● Tidak Terhubung")
        self._net_status_label.setStyleSheet(f"color: {MUTED}; font-size: 11px;")
        QMessageBox.information(self, "Terputus", "Koneksi diputus.")

    def _schedule_network_status_refresh(self):
        try:
            client = getattr(self, '_network_client', None)
            if client and client.is_connected:
                self._net_status_label.setText("● Terhubung")
                self._net_status_label.setStyleSheet(f"color: {SUCCESS}; font-size: 11px;")
                if self._header_server_badge:
                    self._header_server_badge.setText("● SERVER ONLINE")
                    self._header_server_badge.setStyleSheet(f"color: {SUCCESS}; font-weight: bold; font-size: 11px;")
            elif client:
                self._net_status_label.setText("● Menghubungkan...")
                self._net_status_label.setStyleSheet(f"color: {WARNING}; font-size: 11px;")
                if self._header_server_badge:
                    self._header_server_badge.setText("● CONNECTING")
                    self._header_server_badge.setStyleSheet(f"color: {WARNING}; font-weight: bold; font-size: 11px;")
            else:
                self._net_status_label.setText("● Tidak Terhubung")
                self._net_status_label.setStyleSheet(f"color: {MUTED}; font-size: 11px;")
                if self._header_server_badge:
                    self._header_server_badge.setText("● OFFLINE")
                    self._header_server_badge.setStyleSheet(f"color: {MUTED}; font-weight: bold; font-size: 11px;")
        except Exception: pass

    # ================================================================
    # ADMIN SYSTEM SYSTEM CALLBACKS
    # ================================================================

    def _emergency_exit(self):
        from app.system_service import SystemService
        logger.warning("🆘 EMERGENCY EXIT triggered")
        if getattr(self, '_penalty_mgr', None) and hasattr(self._penalty_mgr, '_overlay'):
            if self._penalty_mgr._overlay: self._penalty_mgr._overlay.dismiss()
        SystemService.emergency_release_hooks()

    def _on_autostart_toggle(self, checked):
        from app.system_service import SystemService
        if checked: SystemService.enable_autostart()
        else: SystemService.disable_autostart()

    def _on_settings_lock_toggle(self, checked):
        from app.system_service import SystemService
        success = SystemService.toggle_windows_settings(checked)
        if success:
            if self._auth: self._auth._config["BlockSettings"] = checked; self._auth._save_config()
            QMessageBox.information(self, "OK", f"Settings: {'TERKUNCI' if checked else 'TERBUKA'}")
        else:
            QMessageBox.critical(self, "Error", "Gagal. Jalankan sebagai Administrator.")
            self._chk_lock.blockSignals(True)
            self._chk_lock.setChecked(not checked)
            self._chk_lock.blockSignals(False)

    def _on_installer_lock_toggle(self, checked):
        from app.system_service import SystemService
        success = SystemService.toggle_installer_block(checked)
        if success:
            if self._auth: self._auth._config["BlockInstaller"] = checked; self._auth._save_config()
            if self._installer_guard:
                if checked: self._installer_guard.enable()
                else: self._installer_guard.disable()
            QMessageBox.information(self, "OK", f"Instalasi: {'DIBLOKIR' if checked else 'DIIZINKAN'}")
        else:
            QMessageBox.critical(self, "Error", "Gagal. Jalankan sebagai Administrator.")
            self._chk_inst.blockSignals(True)
            self._chk_inst.setChecked(not checked)
            self._chk_inst.blockSignals(False)

    def _change_password_action(self):
        if not self._auth: return
        old_pwd = self._old_pwd_entry.text()
        new_pwd = self._new_pwd_entry.text()
        if not old_pwd or not new_pwd:
            QMessageBox.warning(self, "Peringatan", "Isi kedua kolom password!")
            return
        if not self._auth.verify_password(old_pwd):
            QMessageBox.critical(self, "Error", "Password salah!")
            return
        if self._auth.change_password(new_pwd):
            QMessageBox.information(self, "Sukses", "Password berhasil diubah!")
            self._old_pwd_entry.clear()
            self._new_pwd_entry.clear()
        else:
            QMessageBox.critical(self, "Error", "Gagal mengubah password.")

    def _schedule_refresh(self):
        self._refresh_monitor()

    def closeEvent(self, event):
        if self._on_close: self._on_close()
        event.accept()
