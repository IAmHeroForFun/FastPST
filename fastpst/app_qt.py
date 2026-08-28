"""
FastPST - PySide6 (Qt) Desktop Application
Provides high-performance email browsing, Outlook 3-pane folder hierarchy navigation,
Outlook 2-line message card list, adaptive reading pane, search, Dark/Light theme switching, and offline licensing.
"""

import os
import sys
import time
import threading
import logging
from typing import List, Dict, Any, Optional

from PySide6.QtCore import Qt, Signal, QObject, QTimer, QRect, QSize
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLineEdit, QPushButton, QLabel, QSplitter, QTextBrowser, QTextEdit,
    QComboBox, QCheckBox, QProgressBar, QFileDialog, QMessageBox, QFrame,
    QDialog, QTreeWidget, QTreeWidgetItem, QListWidget, QListWidgetItem,
    QStyledItemDelegate, QStyle
)
from PySide6.QtGui import QFont, QIcon, QPainter, QColor, QFontMetrics, QPen

from fastpst.utils import get_app_directory, get_database_path
from fastpst.scanner import scan_directory_for_psts
from fastpst.parser import PSTParser, PYPFF_AVAILABLE, get_mail_parser
from fastpst.db import DatabaseManager
from fastpst.exporter import EmailExporter, cleanup_temp_files
from fastpst.launcher import MailLauncher
from fastpst.license import verify_license_token, save_license, load_saved_license
from fastpst.theme import (
    apply_theme, save_theme_preference, load_theme_preference,
    format_email_body_html
)

logger = logging.getLogger("fastpst.app_qt")


class WorkerSignals(QObject):
    status_updated = Signal(str)
    progress_updated = Signal(int, int, str, float, int, int)
    no_files_found = Signal(str)
    error_dialog = Signal(str)
    indexing_complete = Signal(int, float)


class EmailCardDelegate(QStyledItemDelegate):
    """
    Renders each email in Outlook's clean message card format:
    Line 1: SENDER (Bold)                      [📎] Date & Time
    Line 2: Subject (Medium)
    Line 3: Preview Snippet (Muted, smaller)
    """

    def __init__(self, parent=None, theme_getter=None):
        super().__init__(parent)
        self.theme_getter = theme_getter

    def sizeHint(self, option, index):
        return QSize(option.rect.width(), 70)

    def paint(self, painter: QPainter, option, index):
        email_data = index.data(Qt.UserRole + 1)
        if not email_data:
            super().paint(painter, option, index)
            return

        painter.save()
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setRenderHint(QPainter.TextAntialiasing, True)

        rect = option.rect
        is_selected = bool(option.state & QStyle.State_Selected)
        is_dark = self.theme_getter() == "dark" if self.theme_getter else False

        # 1. Background fill
        if is_selected:
            painter.fillRect(rect, QColor("#2563eb"))
        else:
            bg_color = QColor("#18181b") if is_dark else QColor("#ffffff")
            painter.fillRect(rect, bg_color)

        # 2. Text colors
        if is_selected:
            sender_color = QColor("#ffffff")
            date_color = QColor("#dbeafe")
            subject_color = QColor("#ffffff")
            snippet_color = QColor("#bfdbfe")
            divider_color = QColor("#1d4ed8")
        else:
            sender_color = QColor("#f8fafc") if is_dark else QColor("#0f172a")
            date_color = QColor("#94a3b8") if is_dark else QColor("#64748b")
            subject_color = QColor("#e2e8f0") if is_dark else QColor("#1e293b")
            snippet_color = QColor("#71717a") if is_dark else QColor("#64748b")
            divider_color = QColor("#27272a") if is_dark else QColor("#f1f5f9")

        # 3. Data fields
        raw_sender = email_data.get("sender") or email_data.get("sender_name") or "Unknown"
        if "<" in raw_sender:
            sender = raw_sender.split("<")[0].strip().strip('"').strip("'")
            if not sender:
                sender = raw_sender
        else:
            sender = raw_sender

        subject = email_data.get("subject") or "(No Subject)"
        date_sent = email_data.get("date_sent") or ""
        has_att = bool(email_data.get("has_attachments"))
        snippet = (email_data.get("body_snippet") or "").strip().replace("\n", " ")

        att_prefix = "📎 " if has_att else ""
        date_text = f"{att_prefix}{date_sent}".strip()

        margin_x = rect.left() + 10
        margin_right = rect.right() - 10
        content_width = rect.width() - 20

        # --- LINE 1: Sender (Bold) + Date/Time (Right aligned) ---
        date_font = QFont("-apple-system", 8)
        painter.setFont(date_font)
        painter.setPen(date_color)
        fm_date = QFontMetrics(date_font)
        date_width = fm_date.horizontalAdvance(date_text)
        date_rect = QRect(margin_right - date_width, rect.top() + 6, date_width, 18)
        painter.drawText(date_rect, Qt.AlignRight | Qt.AlignVCenter, date_text)

        # Sender (Bold)
        sender_font = QFont("-apple-system", 10, QFont.Bold)
        painter.setFont(sender_font)
        painter.setPen(sender_color)
        sender_max_width = max(40, content_width - date_width - 12)
        fm_sender = QFontMetrics(sender_font)
        elided_sender = fm_sender.elidedText(sender, Qt.ElideRight, sender_max_width)
        sender_rect = QRect(margin_x, rect.top() + 6, sender_max_width, 18)
        painter.drawText(sender_rect, Qt.AlignLeft | Qt.AlignVCenter, elided_sender)

        # --- LINE 2: Subject (Medium, 9.5pt) ---
        subj_font = QFont("-apple-system", 9)
        painter.setFont(subj_font)
        painter.setPen(subject_color)
        fm_subj = QFontMetrics(subj_font)
        elided_subj = fm_subj.elidedText(subject, Qt.ElideRight, content_width)
        subj_rect = QRect(margin_x, rect.top() + 26, content_width, 18)
        painter.drawText(subj_rect, Qt.AlignLeft | Qt.AlignVCenter, elided_subj)

        # --- LINE 3: Snippet Preview (8pt, Muted) ---
        if snippet:
            snip_font = QFont("-apple-system", 8)
            painter.setFont(snip_font)
            painter.setPen(snippet_color)
            fm_snip = QFontMetrics(snip_font)
            elided_snip = fm_snip.elidedText(snippet, Qt.ElideRight, content_width)
            snip_rect = QRect(margin_x, rect.top() + 46, content_width, 16)
            painter.drawText(snip_rect, Qt.AlignLeft | Qt.AlignVCenter, elided_snip)

        # Bottom Divider line
        painter.setPen(QPen(divider_color, 1))
        painter.drawLine(rect.left(), rect.bottom(), rect.right(), rect.bottom())

        painter.restore()


class LicenseDialog(QDialog):
    """Modal dialog for viewing license status and activating/renewing offline keys."""

    def __init__(self, parent=None, db_manager=None, mandatory: bool = False, theme: str = "light"):
        super().__init__(parent)
        self.db = db_manager
        self.mandatory = mandatory
        self.theme = theme
        self.license_activated = False

        self.setWindowTitle("FastPST - License & Activation")
        self.resize(520, 440)
        self.setModal(True)
        self._init_ui()
        self._check_current_license()

    def _init_ui(self):
        is_dark = self.theme == "dark"
        card_bg = "#27272a" if is_dark else "#ffffff"
        card_border = "#3f3f46" if is_dark else "#cbd5e1"
        input_bg = "#1f1f23" if is_dark else "#ffffff"
        input_text = "#f8fafc" if is_dark else "#0f172a"
        sub_text = "#94a3b8" if is_dark else "#475569"

        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(20, 20, 20, 18)

        # 1. App Info Header Card
        about_card = QFrame()
        about_card.setStyleSheet(f"""
            QFrame {{
                background-color: {card_bg};
                border: 1px solid {card_border};
                border-radius: 8px;
                padding: 10px;
            }}
        """)
        about_layout = QVBoxLayout(about_card)
        about_layout.setSpacing(4)

        app_title = QLabel("FastPST — Mail Data File Viewer")
        app_title.setFont(QFont("sans-serif", 12, QFont.Bold))
        title_color = "#38bdf8" if is_dark else "#1e3a8a"
        app_title.setStyleSheet(f"color: {title_color}; font-weight: bold;")
        about_layout.addWidget(app_title)

        version_lbl = QLabel("Version 1.0.0 (Standalone Edition)")
        version_lbl.setFont(QFont("sans-serif", 9))
        version_lbl.setStyleSheet(f"color: {sub_text};")
        about_layout.addWidget(version_lbl)

        formats_lbl = QLabel("Supported: .pst • .ost • .mbox • .mbx • .eml")
        formats_lbl.setStyleSheet("color: #0284c7; font-weight: bold; font-size: 11px;")
        about_layout.addWidget(formats_lbl)

        github_lbl = QLabel("GitHub: <a href='https://github.com/IAmHeroForFun/FastPST' style='color: #38bdf8;'>github.com/IAmHeroForFun/FastPST</a>")
        github_lbl.setOpenExternalLinks(True)
        github_lbl.setStyleSheet("font-size: 11px;")
        about_layout.addWidget(github_lbl)

        layout.addWidget(about_card)

        # 2. License Status Card
        self.lic_card = QFrame()
        self.lic_card.setStyleSheet(f"""
            QFrame {{
                background-color: {card_bg};
                border: 1px solid {card_border};
                border-radius: 8px;
                padding: 10px;
            }}
        """)
        lic_layout = QVBoxLayout(self.lic_card)
        lic_layout.setSpacing(4)

        lic_header = QLabel("License Information")
        lic_header.setFont(QFont("sans-serif", 10, QFont.Bold))
        lic_header.setStyleSheet(f"color: {input_text}; font-weight: bold;")
        lic_layout.addWidget(lic_header)

        self.status_lbl = QLabel("Status: Checking...")
        self.status_lbl.setFont(QFont("sans-serif", 10, QFont.Bold))
        lic_layout.addWidget(self.status_lbl)

        self.client_lbl = QLabel("Licensed To: -")
        self.client_lbl.setStyleSheet(f"color: {sub_text};")
        lic_layout.addWidget(self.client_lbl)

        self.expiry_lbl = QLabel("Expiration: -")
        self.expiry_lbl.setStyleSheet(f"color: {sub_text};")
        lic_layout.addWidget(self.expiry_lbl)

        layout.addWidget(self.lic_card)

        # 3. Key Input section
        key_lbl = QLabel("Enter / Update License Key:")
        key_lbl.setFont(QFont("sans-serif", 9, QFont.Bold))
        key_lbl.setStyleSheet(f"color: {input_text};")
        layout.addWidget(key_lbl)

        self.key_input = QTextEdit()
        self.key_input.setPlaceholderText("Paste your FPST-... license key here")
        self.key_input.setFixedHeight(55)
        self.key_input.setFont(QFont("Monospace", 9))
        self.key_input.setStyleSheet(f"""
            QTextEdit {{
                background-color: {input_bg};
                color: {input_text};
                border: 1px solid {card_border};
                border-radius: 6px;
                padding: 6px;
            }}
            QTextEdit:focus {{
                border: 1px solid #38bdf8;
            }}
        """)
        layout.addWidget(self.key_input)

        # 4. Action Buttons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(8)

        self.activate_btn = QPushButton("💾 Activate / Update Key")
        self.activate_btn.setStyleSheet("""
            QPushButton {
                background-color: #2563eb;
                color: #ffffff;
                font-weight: bold;
                padding: 7px 16px;
                border-radius: 5px;
                border: none;
            }
            QPushButton:hover {
                background-color: #1d4ed8;
            }
        """)
        self.activate_btn.clicked.connect(self._on_activate_clicked)
        btn_layout.addWidget(self.activate_btn)

        if not self.mandatory:
            close_btn = QPushButton("Close")
            close_btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {'#3f3f46' if is_dark else '#e2e8f0'};
                    color: {input_text};
                    font-weight: bold;
                    padding: 7px 14px;
                    border-radius: 5px;
                    border: 1px solid {card_border};
                }}
                QPushButton:hover {{
                    background-color: {'#52525b' if is_dark else '#cbd5e1'};
                }}
            """)
            close_btn.clicked.connect(self.accept)
            btn_layout.addWidget(close_btn)

        layout.addLayout(btn_layout)

    def _check_current_license(self):
        saved_key = load_saved_license()
        if saved_key:
            is_valid, msg, details = verify_license_token(saved_key, db_manager=self.db)
            if is_valid:
                days = details.get("days_remaining", 0)
                client = details.get("client", "Valued Customer")
                expiry = details.get("expiry", "-")
                self.status_lbl.setText(f"Status: ✓ Active ({days} day{'s' if days != 1 else ''} remaining)")
                self.status_lbl.setStyleSheet("color: #16a34a; font-weight: bold;")
                self.client_lbl.setText(f"Licensed To: {client}")
                self.expiry_lbl.setText(f"Expiration: {expiry}")
                return
            else:
                self.status_lbl.setText(f"Status: ✕ {msg}")
                self.status_lbl.setStyleSheet("color: #dc2626; font-weight: bold;")
                self.client_lbl.setText(f"Licensed To: {details.get('client', '-')}")
                self.expiry_lbl.setText(f"Expiration: {details.get('expiry', '-')}")
                return

        self.status_lbl.setText("Status: ✕ No active license found")
        self.status_lbl.setStyleSheet("color: #dc2626; font-weight: bold;")

    def _on_activate_clicked(self):
        raw_key = self.key_input.toPlainText().strip()
        if not raw_key:
            QMessageBox.warning(self, "Invalid Key", "Please paste a license key.")
            return

        is_valid, msg, details = verify_license_token(raw_key, db_manager=self.db)
        if is_valid:
            save_license(raw_key)
            self.license_activated = True
            days = details.get("days_remaining", 0)
            client = details.get("client", "Customer")
            QMessageBox.information(
                self, "License Activated",
                f"License successfully activated for {client}!\n\nValid for {days} days (Expires: {details.get('expiry')})."
            )
            self.accept()
        else:
            QMessageBox.critical(self, "Activation Failed", f"License verification failed:\n\n{msg}")


class FastPSTQtApp(QMainWindow):
    """PySide6 Desktop Application for FastPST with Outlook 3-Pane navigation and Dark/Light theme."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("FastPST - Universal Mail Data File Viewer & Search")
        self.resize(1200, 800)
        self.setMinimumSize(950, 600)

        # Base directories
        self.current_folder = get_app_directory()
        self.db_path = get_database_path()
        self.db = DatabaseManager(self.db_path)

        # Theme
        self.current_theme = load_theme_preference(self.db)

        # State & Filters
        self.selected_file_filter: Optional[str] = None
        self.selected_folder_filter: Optional[str] = None
        self.current_email_data: Optional[Dict[str, Any]] = None
        self.is_indexing = False
        self.signals = WorkerSignals()

        # Signals connection
        self.signals.status_updated.connect(self._on_status_updated)
        self.signals.progress_updated.connect(self._on_progress_updated)
        self.signals.no_files_found.connect(self._on_no_files_found)
        self.signals.error_dialog.connect(self._on_error_dialog)
        self.signals.indexing_complete.connect(self._on_indexing_complete)

        # Search debounce timer
        self.search_timer = QTimer(self)
        self.search_timer.setSingleShot(True)
        self.search_timer.timeout.connect(self.execute_search)

        self._init_ui()
        self._apply_theme()
        self._refresh_license_status()

        # Check license on startup
        QTimer.singleShot(100, self._check_startup_license)

    def _apply_theme(self):
        """Applies the current theme (Light or Dark) via QPalette and QSS."""
        app_inst = QApplication.instance()
        if app_inst:
            apply_theme(app_inst, self.current_theme)

        if self.current_theme == "dark":
            self.theme_btn.setText("☀️ Light")
            self.theme_btn.setToolTip("Switch to Outlook Light Mode")
            self.body_view.setStyleSheet("QTextBrowser { background-color: #18181b; color: #f8fafc; border: 1px solid #3f3f46; }")
            self.body_view.document().setDefaultStyleSheet("body { background-color: #18181b; color: #f8fafc; } * { color: #f8fafc; } a { color: #38bdf8; }")
        else:
            self.theme_btn.setText("🌙 Dark")
            self.theme_btn.setToolTip("Switch to Outlook Dark Mode")
            self.body_view.setStyleSheet("QTextBrowser { background-color: #ffffff; color: #0f172a; border: 1px solid #cbd5e1; }")
            self.body_view.document().setDefaultStyleSheet("body { background-color: #ffffff; color: #0f172a; } * { color: #0f172a; } a { color: #2563eb; }")

        # Repaint message list cards with active theme colors
        self.list_widget.viewport().update()

        # Refresh reading pane if an email is currently loaded
        if self.current_email_data:
            self._render_reading_pane(self.current_email_data)

    def toggle_theme(self):
        """Toggles between Light and Dark mode."""
        self.current_theme = "light" if self.current_theme == "dark" else "dark"
        save_theme_preference(self.db, self.current_theme)
        self._apply_theme()
        self._refresh_license_status()

    def _init_ui(self):
        """Builds Qt user interface with Outlook 3-Pane layout, message cards, and theme/license buttons."""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(10, 10, 10, 6)
        main_layout.setSpacing(8)

        # 1. Top Toolbar (Folder & Actions)
        top_frame = QFrame()
        top_frame.setObjectName("TopFrame")
        top_layout = QHBoxLayout(top_frame)
        top_layout.setContentsMargins(4, 4, 4, 4)
        top_layout.setSpacing(6)

        folder_lbl = QLabel("Folder:")
        folder_lbl.setFont(QFont("sans-serif", 10, QFont.Bold))
        top_layout.addWidget(folder_lbl)

        self.folder_input = QLineEdit(self.current_folder)
        self.folder_input.setReadOnly(True)
        top_layout.addWidget(self.folder_input, stretch=1)

        browse_btn = QPushButton("📁 Browse...")
        browse_btn.clicked.connect(self.browse_folder)
        top_layout.addWidget(browse_btn)

        self.scan_btn = QPushButton("⟳ Scan & Index")
        self.scan_btn.clicked.connect(self.start_manual_scan)
        top_layout.addWidget(self.scan_btn)

        self.count_badge = QLabel("0 Emails Shown")
        self.count_badge.setStyleSheet(
            "background-color: #2b579a; color: #ffffff; padding: 4px 10px; border-radius: 4px; font-weight: bold;"
        )
        top_layout.addWidget(self.count_badge)

        main_layout.addWidget(top_frame)

        # 2. Search Bar & Filters
        search_frame = QFrame()
        search_frame.setObjectName("SearchFrame")
        search_layout = QHBoxLayout(search_frame)
        search_layout.setContentsMargins(4, 4, 4, 4)
        search_layout.setSpacing(6)

        search_lbl = QLabel("🔍 Search:")
        search_lbl.setFont(QFont("sans-serif", 10))
        search_layout.addWidget(search_lbl)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search by subject, sender, body keywords...")
        self.search_input.textChanged.connect(lambda: self.search_timer.start(250))
        self.search_input.returnPressed.connect(self.execute_search)
        search_layout.addWidget(self.search_input, stretch=1)

        scope_lbl = QLabel("In:")
        search_layout.addWidget(scope_lbl)

        self.scope_combo = QComboBox()
        self.scope_combo.addItems(["all", "subject", "sender", "recipients", "body"])
        self.scope_combo.currentTextChanged.connect(self.execute_search)
        search_layout.addWidget(self.scope_combo)

        self.att_checkbox = QCheckBox("📎 Has Attachments")
        self.att_checkbox.toggled.connect(self.execute_search)
        search_layout.addWidget(self.att_checkbox)

        clear_btn = QPushButton("Clear")
        clear_btn.clicked.connect(self.clear_search)
        search_layout.addWidget(clear_btn)

        main_layout.addWidget(search_frame)

        # 3. Enhanced Progress Panel
        self.progress_panel = QFrame()
        self.progress_panel.setObjectName("ProgressPanel")
        prog_layout = QVBoxLayout(self.progress_panel)
        prog_layout.setContentsMargins(10, 8, 10, 8)
        prog_layout.setSpacing(4)

        prog_header_layout = QHBoxLayout()
        self.progress_title_lbl = QLabel("⏳ Indexing Mail Data Files...")
        self.progress_title_lbl.setStyleSheet("font-weight: bold;")
        prog_header_layout.addWidget(self.progress_title_lbl)

        self.progress_stats_lbl = QLabel("0% Complete")
        self.progress_stats_lbl.setStyleSheet("font-weight: bold;")
        self.progress_stats_lbl.setAlignment(Qt.AlignRight)
        prog_header_layout.addWidget(self.progress_stats_lbl)
        prog_layout.addLayout(prog_header_layout)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setFixedHeight(12)
        prog_layout.addWidget(self.progress_bar)

        self.progress_detail_lbl = QLabel("Scanning folder for .pst, .ost, .mbox, .eml files...")
        self.progress_detail_lbl.setObjectName("MetaSubLabel")
        self.progress_detail_lbl.setStyleSheet("font-size: 11px;")
        prog_layout.addWidget(self.progress_detail_lbl)

        self.progress_panel.setVisible(False)
        main_layout.addWidget(self.progress_panel)

        # 4. Outlook 3-Pane Horizontal Splitter
        splitter = QSplitter(Qt.Horizontal)
        main_layout.addWidget(splitter, stretch=1)

        # Pane 1 (Left): Mailboxes & Folders Navigation Tree
        self.tree_widget = QTreeWidget()
        self.tree_widget.setHeaderLabel("📂 Mailboxes & Folders")
        self.tree_widget.setMinimumWidth(180)
        self.tree_widget.itemSelectionChanged.connect(self.on_tree_selection_changed)
        splitter.addWidget(self.tree_widget)

        # Pane 2 (Middle): Outlook 2-Line Message Cards List
        self.list_widget = QListWidget()
        self.list_widget.setMinimumWidth(280)
        self.card_delegate = EmailCardDelegate(self.list_widget, theme_getter=lambda: self.current_theme)
        self.list_widget.setItemDelegate(self.card_delegate)
        self.list_widget.itemSelectionChanged.connect(self.on_list_item_selected)
        self.list_widget.itemDoubleClicked.connect(self.on_list_item_double_clicked)
        splitter.addWidget(self.list_widget)

        # Pane 3 (Right): Reading Pane
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(6, 0, 0, 0)
        right_layout.setSpacing(6)

        # Header Info Card
        self.header_card = QFrame()
        self.header_card.setObjectName("HeaderCard")
        hc_layout = QVBoxLayout(self.header_card)
        hc_layout.setContentsMargins(8, 8, 8, 8)
        hc_layout.setSpacing(4)

        self.pane_subject = QLabel("Select an email from the list to view")
        self.pane_subject.setFont(QFont("sans-serif", 12, QFont.Bold))
        self.pane_subject.setWordWrap(True)
        hc_layout.addWidget(self.pane_subject)

        # Meta grid
        self.pane_from = QLabel("From: -")
        self.pane_from.setObjectName("MetaSubLabel")
        hc_layout.addWidget(self.pane_from)

        self.pane_to = QLabel("To: -")
        self.pane_to.setObjectName("MetaSubLabel")
        hc_layout.addWidget(self.pane_to)

        date_file_layout = QHBoxLayout()
        self.pane_date = QLabel("Date: -")
        self.pane_date.setObjectName("MetaSubLabel")
        date_file_layout.addWidget(self.pane_date)

        self.pane_file = QLabel("Source: -")
        self.pane_file.setObjectName("MetaSubLabel")
        date_file_layout.addWidget(self.pane_file, alignment=Qt.AlignRight)
        hc_layout.addLayout(date_file_layout)

        self.pane_attachments = QLabel("")
        self.pane_attachments.setVisible(False)
        hc_layout.addWidget(self.pane_attachments)

        right_layout.addWidget(self.header_card)

        # Body text browser
        self.body_view = QTextBrowser()
        self.body_view.setOpenExternalLinks(True)
        self.body_view.setFont(QFont("sans-serif", 10))
        right_layout.addWidget(self.body_view, stretch=1)

        # Action Buttons
        action_layout = QHBoxLayout()
        action_layout.setSpacing(8)

        self.open_app_btn = QPushButton("✉ Open in Outlook / Mail App")
        self.open_app_btn.setStyleSheet("font-weight: bold; padding: 6px 12px;")
        self.open_app_btn.clicked.connect(self.open_in_external_app)
        self.open_app_btn.setEnabled(False)
        action_layout.addWidget(self.open_app_btn)

        self.save_eml_btn = QPushButton("💾 Save Email As...")
        self.save_eml_btn.clicked.connect(self.save_email_as)
        self.save_eml_btn.setEnabled(False)
        action_layout.addWidget(self.save_eml_btn)

        right_layout.addLayout(action_layout)

        splitter.addWidget(right_widget)
        splitter.setSizes([230, 450, 520])

        # 5. Bottom Status Bar with Theme Switcher and License Button
        status_bar = self.statusBar()
        self.status_lbl = QLabel("Ready")
        status_bar.addWidget(self.status_lbl, stretch=1)

        # Theme Switcher Button
        self.theme_btn = QPushButton("🌙 Dark")
        self.theme_btn.setCursor(Qt.PointingHandCursor)
        self.theme_btn.clicked.connect(self.toggle_theme)
        status_bar.addPermanentWidget(self.theme_btn)

        # Bottom Right Clickable License Badge
        self.license_badge_btn = QPushButton("🔑 License: Checking...")
        self.license_badge_btn.setCursor(Qt.PointingHandCursor)
        self.license_badge_btn.setToolTip("Click to view license status or enter a new license key")
        self.license_badge_btn.clicked.connect(self.open_license_dialog)
        status_bar.addPermanentWidget(self.license_badge_btn)

    # --- Licensing Management ---

    def _refresh_license_status(self) -> bool:
        """Updates the bottom right license badge styling and text."""
        saved_key = load_saved_license()
        is_dark = self.current_theme == "dark"

        if not saved_key:
            self.license_badge_btn.setText("✕ License: No Key (Click to Activate)")
            self.license_badge_btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {'#450a0a' if is_dark else '#fee2e2'};
                    color: {'#fca5a5' if is_dark else '#991b1b'};
                    border: 1px solid {'#991b1b' if is_dark else '#f87171'};
                    border-radius: 4px;
                    padding: 2px 10px;
                    font-weight: bold;
                }}
            """)
            return False

        is_valid, msg, details = verify_license_token(saved_key, db_manager=self.db)
        days = details.get("days_remaining", 0)
        client = details.get("client", "Customer")

        if is_valid:
            if days <= 7:
                # Expiring soon (Amber)
                self.license_badge_btn.setText(f"⚠️ License: {client} ({days}d left)")
                self.license_badge_btn.setStyleSheet(f"""
                    QPushButton {{
                        background-color: {'#451a03' if is_dark else '#fef3c7'};
                        color: {'#fcd34d' if is_dark else '#92400e'};
                        border: 1px solid {'#b45309' if is_dark else '#fcd34d'};
                        border-radius: 4px;
                        padding: 2px 10px;
                        font-weight: bold;
                    }}
                """)
            else:
                # Active (Green)
                self.license_badge_btn.setText(f"🔑 License: {client} ({days} days left)")
                self.license_badge_btn.setStyleSheet(f"""
                    QPushButton {{
                        background-color: {'#052e16' if is_dark else '#dcfce7'};
                        color: {'#86efac' if is_dark else '#166534'};
                        border: 1px solid {'#16a34a' if is_dark else '#86efac'};
                        border-radius: 4px;
                        padding: 2px 10px;
                        font-weight: bold;
                    }}
                """)
            return True
        else:
            # Expired / Tampered (Red)
            self.license_badge_btn.setText("✕ License: Expired (Click to Renew)")
            self.license_badge_btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {'#450a0a' if is_dark else '#fee2e2'};
                    color: {'#fca5a5' if is_dark else '#991b1b'};
                    border: 1px solid {'#991b1b' if is_dark else '#f87171'};
                    border-radius: 4px;
                    padding: 2px 10px;
                    font-weight: bold;
                }}
            """)
            return False

    def open_license_dialog(self):
        """Opens the License & Activation window."""
        dialog = LicenseDialog(self, db_manager=self.db, mandatory=False, theme=self.current_theme)
        dialog.exec()
        self._refresh_license_status()

    def _check_startup_license(self):
        """Validates license on application startup; prompts for activation if required."""
        is_licensed = self._refresh_license_status()
        if not is_licensed:
            dialog = LicenseDialog(self, db_manager=self.db, mandatory=True, theme=self.current_theme)
            if dialog.exec() != QDialog.Accepted or not self._refresh_license_status():
                QMessageBox.critical(
                    self, "Activation Required",
                    "A valid license key is required to use FastPST.\nClosing application."
                )
                sys.exit(0)

        # If licensed, proceed to auto-scan
        self.auto_start_scan()

    # --- Folder Tree Management ---

    def _populate_folder_tree(self):
        """Populates the left navigation tree with mailboxes and subfolders."""
        self.tree_widget.clear()
        total_in_db = self.db.get_total_email_count()

        # Root: All Mailboxes
        root_item = QTreeWidgetItem(self.tree_widget)
        root_item.setText(0, f"📂 All Mailboxes ({total_in_db:,})")
        root_item.setData(0, Qt.UserRole, (None, None))
        root_item.setFont(0, QFont("sans-serif", 9, QFont.Bold))

        files_data = self.db.get_folder_tree()
        for f_info in files_data:
            f_path = f_info["file_path"]
            f_name = f_info["file_name"]
            f_total = f_info["total_emails"]

            file_node = QTreeWidgetItem(root_item)
            file_node.setText(0, f"📦 {f_name} ({f_total:,})")
            file_node.setData(0, Qt.UserRole, (f_path, None))
            file_node.setFont(0, QFont("sans-serif", 9, QFont.Bold))

            for folder_item in f_info.get("folders", []):
                folder_path = folder_item["folder_path"]
                display_name = folder_item["display_name"]
                count = folder_item["count"]

                folder_node = QTreeWidgetItem(file_node)
                
                # Contextual folder icon
                icon_prefix = "📁"
                dl = display_name.lower()
                if "inbox" in dl:
                    icon_prefix = "📥"
                elif "sent" in dl:
                    icon_prefix = "📤"
                elif "deleted" in dl or "trash" in dl:
                    icon_prefix = "🗑️"
                elif "draft" in dl:
                    icon_prefix = "📝"
                elif "junk" in dl or "spam" in dl:
                    icon_prefix = "🚫"

                folder_node.setText(0, f"{icon_prefix} {display_name} ({count:,})")
                folder_node.setData(0, Qt.UserRole, (f_path, folder_path))

        # Expand all for clear visibility like Outlook
        self.tree_widget.expandAll()
        root_item.setSelected(True)

    def on_tree_selection_changed(self):
        """Filters email list when user clicks a file or folder in the tree."""
        selected_items = self.tree_widget.selectedItems()
        if not selected_items:
            self.selected_file_filter = None
            self.selected_folder_filter = None
        else:
            item = selected_items[0]
            filter_data = item.data(0, Qt.UserRole)
            if filter_data:
                self.selected_file_filter, self.selected_folder_filter = filter_data
            else:
                self.selected_file_filter = None
                self.selected_folder_filter = None

        self.execute_search()

    # --- Search & Message List Population ---

    def clear_search(self):
        self.search_input.clear()
        self.att_checkbox.setChecked(False)
        self.scope_combo.setCurrentText("all")
        self.execute_search()

    def execute_search(self):
        query = self.search_input.text().strip()
        scope = self.scope_combo.currentText()
        has_att = self.att_checkbox.isChecked()

        results = self.db.search_emails(
            query=query,
            field_filter=scope,
            has_attachments_only=has_att,
            file_path_filter=self.selected_file_filter,
            folder_path_filter=self.selected_folder_filter,
            limit=1000
        )
        self._populate_list(results)

    def _populate_list(self, email_rows: List[Dict[str, Any]]):
        self.list_widget.clear()

        for email_item in email_rows:
            item = QListWidgetItem(self.list_widget)
            item.setData(Qt.UserRole, email_item["id"])
            item.setData(Qt.UserRole + 1, email_item)
            self.list_widget.addItem(item)

        self.count_badge.setText(f"{len(email_rows)} Emails Shown")

    # --- Selection & Reading Pane ---

    def on_list_item_selected(self):
        selected_items = self.list_widget.selectedItems()
        if not selected_items:
            return

        item = selected_items[0]
        email_id = item.data(Qt.UserRole)
        if not email_id:
            return

        email_data = self.db.get_email_by_id(email_id)
        if email_data:
            self.current_email_data = email_data
            self._render_reading_pane(email_data)

    def on_list_item_double_clicked(self, item: QListWidgetItem):
        self.on_list_item_selected()
        self.open_in_external_app()

    def _render_reading_pane(self, email_data: Dict[str, Any]):
        subject = email_data.get("subject") or "(No Subject)"
        sender = email_data.get("sender") or "Unknown"
        recipients = email_data.get("recipients") or "-"
        date_sent = email_data.get("date_sent") or "-"
        file_name = email_data.get("file_name") or "-"
        folder_path = email_data.get("folder_path") or "-"
        attachments = email_data.get("attachments") or []
        is_dark = self.current_theme == "dark"

        self.pane_subject.setText(subject)
        self.pane_from.setText(f"From: {sender}")
        self.pane_to.setText(f"To: {recipients}")
        self.pane_date.setText(f"Date: {date_sent}")
        self.pane_file.setText(f"Source: {file_name} • {folder_path}")

        if attachments:
            att_names = ", ".join([a.get("name", "attachment") for a in attachments])
            self.pane_attachments.setText(f"📎 Attachments ({len(attachments)}): {att_names}")
            att_bg = "rgba(56, 189, 248, 0.15)" if is_dark else "rgba(2, 132, 199, 0.15)"
            att_color = "#38bdf8" if is_dark else "#0284c7"
            self.pane_attachments.setStyleSheet(
                f"color: {att_color}; font-weight: bold; background-color: {att_bg}; padding: 3px 8px; border-radius: 4px;"
            )
            self.pane_attachments.setVisible(True)
        else:
            self.pane_attachments.setVisible(False)

        html_body = email_data.get("html_body")
        plain_body = email_data.get("plain_body")

        rendered_html = format_email_body_html(html_body, plain_body, is_dark)
        self.body_view.setHtml(rendered_html)

        self.open_app_btn.setEnabled(True)
        self.save_eml_btn.setEnabled(True)

    # --- Actions ---

    def open_in_external_app(self):
        if not self.current_email_data:
            return
        try:
            eml_path = EmailExporter.export_to_temp_eml(self.current_email_data)
            success, msg = MailLauncher.open_email_file(eml_path)
            if not success:
                QMessageBox.warning(self, "Launch Warning", msg)
            else:
                self.status_lbl.setText("Email opened in default mail client.")
        except Exception as e:
            QMessageBox.critical(self, "Error Opening Email", str(e))

    def save_email_as(self):
        if not self.current_email_data:
            return
        subj = "".join([c for c in (self.current_email_data.get("subject") or "email") if c.isalnum() or c in " -_"]).strip()
        default_name = f"{subj[:40]}.eml"

        save_path, _ = QFileDialog.getSaveFileName(
            self, "Save Email As", default_name, "Email Files (*.eml);;All Files (*)"
        )
        if save_path:
            try:
                eml_bytes = EmailExporter.create_eml_bytes(self.current_email_data)
                with open(save_path, "wb") as f:
                    f.write(eml_bytes)
                self.status_lbl.setText(f"Email saved to {os.path.basename(save_path)}")
            except Exception as e:
                QMessageBox.critical(self, "Save Error", str(e))

    # --- Scanning & Background Worker ---

    def browse_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Folder Containing Mail Files", self.current_folder)
        if folder:
            self.current_folder = folder
            self.folder_input.setText(folder)
            self.start_manual_scan()

    def start_manual_scan(self):
        self._start_scan_thread(force_reindex=True)

    def auto_start_scan(self):
        self._start_scan_thread(force_reindex=False)

    def _start_scan_thread(self, force_reindex: bool):
        if self.is_indexing:
            return

        self.is_indexing = True
        self.scan_btn.setEnabled(False)
        self.progress_panel.setVisible(True)
        self.progress_bar.setValue(0)
        self.progress_stats_lbl.setText("0% Complete")
        self.progress_detail_lbl.setText("Scanning folder for mail data files...")
        self.status_lbl.setText("Scanning folder...")

        thread = threading.Thread(
            target=self._scan_worker,
            args=(self.current_folder, force_reindex),
            daemon=True
        )
        thread.start()

    def _scan_worker(self, folder: str, force_reindex: bool):
        start_time = time.time()
        try:
            discovered = scan_directory_for_psts(folder, recursive=True)
            total_files = len(discovered)

            if not discovered:
                self.signals.no_files_found.emit(folder)
                self.signals.indexing_complete.emit(0, 0.0)
                return

            total_new_indexed = 0

            for f_idx, f_info in enumerate(discovered, start=1):
                file_path = f_info["path"]
                file_size = f_info["size"]
                mtime = f_info["mtime"]
                filename = f_info["filename"]
                size_mb = file_size / (1024 * 1024)

                base_pct = int(((f_idx - 1) / total_files) * 100)
                file_weight = 100.0 / total_files

                if not force_reindex and self.db.is_file_indexed_and_current(file_path, file_size, mtime):
                    pct = int((f_idx / total_files) * 100)
                    self.signals.progress_updated.emit(f_idx, total_files, filename, size_mb, 0, pct)
                    continue

                _, ext = os.path.splitext(filename)
                if ext.lower() in {".pst", ".ost"} and not PYPFF_AVAILABLE:
                    self.signals.error_dialog.emit(
                        f"pypff / libpff is required to parse {filename}.\nRun 'pip install libpff-python'."
                    )
                    continue

                self.signals.status_updated.emit(f"Indexing ({f_idx}/{total_files}): {filename}...")
                self.signals.progress_updated.emit(f_idx, total_files, filename, size_mb, 0, base_pct)
                self.db.remove_file_records(file_path)

                batch = []
                count = 0

                try:
                    parser = get_mail_parser(file_path)
                    with parser:
                        for msg in parser.parse_all_messages():
                            batch.append(msg)
                            count += 1
                            if len(batch) >= 50:
                                self.db.insert_emails_batch(batch)
                                batch.clear()
                                curr_pct = min(99, int(base_pct + (file_weight * 0.8)))
                                self.signals.progress_updated.emit(f_idx, total_files, filename, size_mb, count, curr_pct)

                        if batch:
                            self.db.insert_emails_batch(batch)
                            batch.clear()

                    self.db.record_file_indexed(file_path, file_size, mtime, count)
                    total_new_indexed += count

                    file_done_pct = int((f_idx / total_files) * 100)
                    self.signals.progress_updated.emit(f_idx, total_files, filename, size_mb, count, file_done_pct)

                except Exception as e:
                    logger.error(f"Error parsing {filename}: {e}")
                    self.signals.status_updated.emit(f"Error parsing {filename}: {e}")

            elapsed = time.time() - start_time
            self.signals.indexing_complete.emit(total_new_indexed, elapsed)

        except Exception as e:
            logger.error(f"Scan error: {e}")
            self.signals.status_updated.emit(f"Scan error: {e}")
            self.signals.indexing_complete.emit(0, 0.0)

    # --- UI Signal Handlers ---

    def _on_status_updated(self, message: str):
        self.status_lbl.setText(message)

    def _on_progress_updated(self, file_idx: int, total_files: int, filename: str, size_mb: float, count: int, percent: int):
        self.progress_bar.setValue(percent)
        self.progress_stats_lbl.setText(f"{percent}% Complete")
        size_str = f"{size_mb:.1f} MB" if size_mb < 1024 else f"{(size_mb/1024):.2f} GB"
        count_str = f" • {count:,} emails extracted" if count > 0 else ""
        self.progress_detail_lbl.setText(
            f"File ({file_idx}/{total_files}): {filename} ({size_str}){count_str}"
        )

    def _on_no_files_found(self, folder: str):
        self.progress_panel.setVisible(False)
        self.status_lbl.setText("No .pst, .ost, .mbox, or .eml files found in this directory.")
        self._populate_folder_tree()

    def _on_error_dialog(self, error_message: str):
        QMessageBox.warning(self, "FastPST Notice", error_message)

    def _on_indexing_complete(self, new_count: int, elapsed_sec: float):
        self.is_indexing = False
        self.scan_btn.setEnabled(True)
        self.progress_bar.setValue(100)
        self.progress_stats_lbl.setText("100% Complete")

        total_in_db = self.db.get_total_email_count()
        if elapsed_sec > 0:
            summary = f"✓ Indexing complete! {new_count:,} new emails indexed in {elapsed_sec:.1f}s ({total_in_db:,} total)."
        else:
            summary = f"✓ Index current: {total_in_db:,} total emails loaded."

        self.progress_detail_lbl.setText(summary)
        self.status_lbl.setText(summary)
        self.count_badge.setText(f"{total_in_db:,} Emails Shown")

        QTimer.singleShot(4000, lambda: self.progress_panel.setVisible(False) if not self.is_indexing else None)
        
        # Populate the Outlook navigation tree and email list
        self._populate_folder_tree()
        self.execute_search()

    def closeEvent(self, event):
        cleanup_temp_files()
        event.accept()


def launch_app_qt():
    """Entry point for PySide6 application with Fusion style enforcement."""
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    
    # Enforce standard cross-platform Fusion engine to eliminate OS theme glitches
    app.setStyle("Fusion")
    
    window = FastPSTQtApp()
    window.show()
    sys.exit(app.exec())
