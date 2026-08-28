"""
FastPST - PySide6 (Qt) Desktop Application
Provides high-performance email browsing, reading pane, search, and mail client redirection.
Includes unified About & Offline Cryptographic License verification with high-contrast UI.
"""

import os
import sys
import time
import threading
import logging
from typing import List, Dict, Any, Optional

from PySide6.QtCore import Qt, Signal, QObject, QTimer
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLineEdit, QPushButton, QLabel, QTableWidget, QTableWidgetItem,
    QHeaderView, QSplitter, QTextBrowser, QTextEdit, QComboBox, QCheckBox,
    QProgressBar, QFileDialog, QMessageBox, QFrame, QDialog
)
from PySide6.QtGui import QFont, QIcon

from fastpst.utils import get_app_directory, get_database_path
from fastpst.scanner import scan_directory_for_psts
from fastpst.parser import PSTParser, PYPFF_AVAILABLE, get_mail_parser
from fastpst.db import DatabaseManager
from fastpst.exporter import EmailExporter, cleanup_temp_files
from fastpst.launcher import MailLauncher
from fastpst.license import verify_license_token, save_license, load_saved_license

logger = logging.getLogger("fastpst.app_qt")


class WorkerSignals(QObject):
    status_updated = Signal(str)
    progress_updated = Signal(int, int, str, float, int, int)
    no_files_found = Signal(str)
    error_dialog = Signal(str)
    indexing_complete = Signal(int, float)


class LicenseDialog(QDialog):
    """Modal dialog for viewing license status and activating/renewing offline keys."""

    def __init__(self, parent=None, db_manager=None, mandatory: bool = False):
        super().__init__(parent)
        self.db = db_manager
        self.mandatory = mandatory
        self.license_activated = False

        self.setWindowTitle("FastPST - License & Activation")
        self.resize(520, 440)
        self.setModal(True)
        self.setStyleSheet("""
            QDialog {
                background-color: #f8fafc;
            }
            QLabel {
                color: #0f172a;
            }
        """)
        self._init_ui()
        self._check_current_license()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(20, 20, 20, 18)

        # 1. App Info Header Card
        about_card = QFrame()
        about_card.setStyleSheet("""
            QFrame {
                background-color: #ffffff;
                border: 1px solid #cbd5e1;
                border-radius: 8px;
                padding: 10px;
            }
            QLabel {
                background: transparent;
            }
        """)
        about_layout = QVBoxLayout(about_card)
        about_layout.setSpacing(4)

        app_title = QLabel("FastPST — Mail Data File Viewer")
        app_title.setFont(QFont("sans-serif", 12, QFont.Bold))
        app_title.setStyleSheet("color: #1e3a8a; font-weight: bold;")
        about_layout.addWidget(app_title)

        version_lbl = QLabel("Version 1.0.0 (Standalone Edition)")
        version_lbl.setFont(QFont("sans-serif", 9))
        version_lbl.setStyleSheet("color: #475569;")
        about_layout.addWidget(version_lbl)

        formats_lbl = QLabel("Supported: .pst • .ost • .mbox • .mbx • .eml")
        formats_lbl.setStyleSheet("color: #0284c7; font-weight: bold; font-size: 11px;")
        about_layout.addWidget(formats_lbl)

        github_lbl = QLabel("GitHub: <a href='https://github.com/IAmHeroForFun/FastPST' style='color: #2563eb;'>github.com/IAmHeroForFun/FastPST</a>")
        github_lbl.setOpenExternalLinks(True)
        github_lbl.setStyleSheet("font-size: 11px;")
        about_layout.addWidget(github_lbl)

        layout.addWidget(about_card)

        # 2. License Status Card
        self.lic_card = QFrame()
        self.lic_card.setStyleSheet("""
            QFrame {
                background-color: #ffffff;
                border: 1px solid #cbd5e1;
                border-radius: 8px;
                padding: 10px;
            }
            QLabel {
                background: transparent;
            }
        """)
        lic_layout = QVBoxLayout(self.lic_card)
        lic_layout.setSpacing(4)

        lic_header = QLabel("License Information")
        lic_header.setFont(QFont("sans-serif", 10, QFont.Bold))
        lic_header.setStyleSheet("color: #0f172a; font-weight: bold;")
        lic_layout.addWidget(lic_header)

        self.status_lbl = QLabel("Status: Checking...")
        self.status_lbl.setFont(QFont("sans-serif", 10, QFont.Bold))
        lic_layout.addWidget(self.status_lbl)

        self.client_lbl = QLabel("Licensed To: -")
        self.client_lbl.setStyleSheet("color: #334155;")
        lic_layout.addWidget(self.client_lbl)

        self.expiry_lbl = QLabel("Expiration: -")
        self.expiry_lbl.setStyleSheet("color: #334155;")
        lic_layout.addWidget(self.expiry_lbl)

        layout.addWidget(self.lic_card)

        # 3. Key Input section
        key_lbl = QLabel("Enter / Update License Key:")
        key_lbl.setFont(QFont("sans-serif", 9, QFont.Bold))
        key_lbl.setStyleSheet("color: #0f172a;")
        layout.addWidget(key_lbl)

        self.key_input = QTextEdit()
        self.key_input.setPlaceholderText("Paste your FPST-... license key here")
        self.key_input.setFixedHeight(55)
        self.key_input.setFont(QFont("Monospace", 9))
        self.key_input.setStyleSheet("""
            QTextEdit {
                background-color: #ffffff;
                color: #0f172a;
                border: 1px solid #94a3b8;
                border-radius: 6px;
                padding: 6px;
            }
            QTextEdit:focus {
                border: 1px solid #2563eb;
            }
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
            close_btn.setStyleSheet("""
                QPushButton {
                    background-color: #e2e8f0;
                    color: #1e293b;
                    font-weight: bold;
                    padding: 7px 14px;
                    border-radius: 5px;
                    border: 1px solid #cbd5e1;
                }
                QPushButton:hover {
                    background-color: #cbd5e1;
                }
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
    """PySide6 Desktop Application for FastPST."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("FastPST - Universal Mail Data File Viewer & Search")
        self.resize(1150, 780)
        self.setMinimumSize(900, 600)

        # Base directories
        self.current_folder = get_app_directory()
        self.db_path = get_database_path()
        self.db = DatabaseManager(self.db_path)

        # State
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
        self._refresh_license_status()

        # Check license on startup
        QTimer.singleShot(100, self._check_startup_license)

    def _init_ui(self):
        """Builds Qt user interface with side-by-side layout, progress tracking, and license button."""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(10, 10, 10, 6)
        main_layout.setSpacing(8)

        # 1. Top Toolbar (Folder & Actions)
        top_frame = QFrame()
        top_layout = QHBoxLayout(top_frame)
        top_layout.setContentsMargins(0, 0, 0, 0)
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

        self.count_badge = QLabel("0 Emails Loaded")
        self.count_badge.setStyleSheet(
            "background-color: #2b579a; color: #ffffff; padding: 4px 10px; border-radius: 4px; font-weight: bold;"
        )
        top_layout.addWidget(self.count_badge)

        main_layout.addWidget(top_frame)

        # 2. Search Bar & Filters
        search_frame = QFrame()
        search_layout = QHBoxLayout(search_frame)
        search_layout.setContentsMargins(0, 0, 0, 0)
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
        self.progress_panel.setStyleSheet("""
            QFrame#ProgressPanel {
                background-color: #f1f5f9;
                border: 1px solid #cbd5e1;
                border-radius: 6px;
            }
        """)
        self.progress_panel.setObjectName("ProgressPanel")
        prog_layout = QVBoxLayout(self.progress_panel)
        prog_layout.setContentsMargins(10, 8, 10, 8)
        prog_layout.setSpacing(4)

        prog_header_layout = QHBoxLayout()
        self.progress_title_lbl = QLabel("⏳ Indexing Mail Data Files...")
        self.progress_title_lbl.setStyleSheet("font-weight: bold; color: #1e3a8a;")
        prog_header_layout.addWidget(self.progress_title_lbl)

        self.progress_stats_lbl = QLabel("0% Complete")
        self.progress_stats_lbl.setStyleSheet("font-weight: bold; color: #334155;")
        self.progress_stats_lbl.setAlignment(Qt.AlignRight)
        prog_header_layout.addWidget(self.progress_stats_lbl)
        prog_layout.addLayout(prog_header_layout)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setFixedHeight(12)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: 1px solid #cbd5e1;
                border-radius: 4px;
                background-color: #e2e8f0;
            }
            QProgressBar::chunk {
                background-color: #2563eb;
                border-radius: 3px;
            }
        """)
        prog_layout.addWidget(self.progress_bar)

        self.progress_detail_lbl = QLabel("Scanning folder for .pst, .ost, .mbox, .eml files...")
        self.progress_detail_lbl.setStyleSheet("color: #64748b; font-size: 11px;")
        prog_layout.addWidget(self.progress_detail_lbl)

        self.progress_panel.setVisible(False)
        main_layout.addWidget(self.progress_panel)

        # 4. Main Horizontal Splitter (Left: Email List, Right: Reading Pane)
        splitter = QSplitter(Qt.Horizontal)
        main_layout.addWidget(splitter, stretch=1)

        # Left Table: Emails List
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["Date", "From", "Subject", "📎", "File"])
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.SingleSelection)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSortingEnabled(True)
        self.table.setAlternatingRowColors(True)
        self.table.itemSelectionChanged.connect(self.on_table_row_selected)
        self.table.cellDoubleClicked.connect(self.on_table_double_clicked)
        splitter.addWidget(self.table)

        # Right Reading Pane
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(6, 0, 0, 0)
        right_layout.setSpacing(6)

        # Header Info Card
        header_card = QFrame()
        header_card.setStyleSheet("""
            QFrame {
                background-color: #f8f9fa;
                border: 1px solid #dee2e6;
                border-radius: 6px;
                padding: 6px;
            }
        """)
        hc_layout = QVBoxLayout(header_card)
        hc_layout.setContentsMargins(6, 6, 6, 6)
        hc_layout.setSpacing(4)

        self.pane_subject = QLabel("Select an email from the left list to view")
        self.pane_subject.setFont(QFont("sans-serif", 12, QFont.Bold))
        self.pane_subject.setWordWrap(True)
        hc_layout.addWidget(self.pane_subject)

        # Meta grid
        self.pane_from = QLabel("From: -")
        self.pane_from.setStyleSheet("color: #333;")
        hc_layout.addWidget(self.pane_from)

        self.pane_to = QLabel("To: -")
        self.pane_to.setStyleSheet("color: #555;")
        hc_layout.addWidget(self.pane_to)

        date_file_layout = QHBoxLayout()
        self.pane_date = QLabel("Date: -")
        self.pane_date.setStyleSheet("color: #666;")
        date_file_layout.addWidget(self.pane_date)

        self.pane_file = QLabel("File: -")
        self.pane_file.setStyleSheet("color: #666;")
        date_file_layout.addWidget(self.pane_file, alignment=Qt.AlignRight)
        hc_layout.addLayout(date_file_layout)

        self.pane_attachments = QLabel("")
        self.pane_attachments.setStyleSheet(
            "color: #0b5ed7; font-weight: bold; background-color: #e7f1ff; padding: 2px 6px; border-radius: 4px;"
        )
        self.pane_attachments.setVisible(False)
        hc_layout.addWidget(self.pane_attachments)

        right_layout.addWidget(header_card)

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
        splitter.setSizes([480, 670])

        # 5. Bottom Status Bar with Clickable License Button
        status_bar = self.statusBar()
        self.status_lbl = QLabel("Ready")
        status_bar.addWidget(self.status_lbl, stretch=1)

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
        if not saved_key:
            self.license_badge_btn.setText("✕ License: No Key (Click to Activate)")
            self.license_badge_btn.setStyleSheet("""
                QPushButton {
                    background-color: #fee2e2;
                    color: #991b1b;
                    border: 1px solid #f87171;
                    border-radius: 4px;
                    padding: 2px 10px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #fecaca;
                }
            """)
            return False

        is_valid, msg, details = verify_license_token(saved_key, db_manager=self.db)
        days = details.get("days_remaining", 0)
        client = details.get("client", "Customer")

        if is_valid:
            if days <= 7:
                # Expiring soon (Amber)
                self.license_badge_btn.setText(f"⚠️ License: {client} ({days}d left)")
                self.license_badge_btn.setStyleSheet("""
                    QPushButton {
                        background-color: #fef3c7;
                        color: #92400e;
                        border: 1px solid #fcd34d;
                        border-radius: 4px;
                        padding: 2px 10px;
                        font-weight: bold;
                    }
                    QPushButton:hover {
                        background-color: #fde68a;
                    }
                """)
            else:
                # Active (Green)
                self.license_badge_btn.setText(f"🔑 License: {client} ({days} days left)")
                self.license_badge_btn.setStyleSheet("""
                    QPushButton {
                        background-color: #dcfce7;
                        color: #166534;
                        border: 1px solid #86efac;
                        border-radius: 4px;
                        padding: 2px 10px;
                        font-weight: bold;
                    }
                    QPushButton:hover {
                        background-color: #bbf7d0;
                    }
                """)
            return True
        else:
            # Expired / Tampered (Red)
            self.license_badge_btn.setText("✕ License: Expired (Click to Renew)")
            self.license_badge_btn.setStyleSheet("""
                QPushButton {
                    background-color: #fee2e2;
                    color: #991b1b;
                    border: 1px solid #f87171;
                    border-radius: 4px;
                    padding: 2px 10px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #fecaca;
                }
            """)
            return False

    def open_license_dialog(self):
        """Opens the License & Activation window."""
        dialog = LicenseDialog(self, db_manager=self.db, mandatory=False)
        dialog.exec()
        self._refresh_license_status()

    def _check_startup_license(self):
        """Validates license on application startup; prompts for activation if required."""
        is_licensed = self._refresh_license_status()
        if not is_licensed:
            dialog = LicenseDialog(self, db_manager=self.db, mandatory=True)
            if dialog.exec() != QDialog.Accepted or not self._refresh_license_status():
                QMessageBox.critical(
                    self, "Activation Required",
                    "A valid license key is required to use FastPST.\nClosing application."
                )
                sys.exit(0)

        # If licensed, proceed to auto-scan
        self.auto_start_scan()

    # --- Search & Table Population ---

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
            limit=1000
        )
        self._populate_table(results)

    def _populate_table(self, email_rows: List[Dict[str, Any]]):
        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(email_rows))

        for row_idx, email_item in enumerate(email_rows):
            att_sym = "📎" if email_item.get("has_attachments") else ""
            
            items = [
                QTableWidgetItem(email_item.get("date_sent", "")),
                QTableWidgetItem(email_item.get("sender", "")),
                QTableWidgetItem(email_item.get("subject") or "(No Subject)"),
                QTableWidgetItem(att_sym),
                QTableWidgetItem(email_item.get("file_name", ""))
            ]
            items[3].setTextAlignment(Qt.AlignCenter)

            for col_idx, item in enumerate(items):
                if col_idx == 0:
                    item.setData(Qt.UserRole, email_item["id"])
                self.table.setItem(row_idx, col_idx, item)

        self.table.setSortingEnabled(True)
        self.count_badge.setText(f"{len(email_rows)} Emails Loaded")

    # --- Selection & Reading Pane ---

    def on_table_row_selected(self):
        selected_items = self.table.selectedItems()
        if not selected_items:
            return

        row = selected_items[0].row()
        item = self.table.item(row, 0)
        if not item:
            return

        email_id = item.data(Qt.UserRole)
        if not email_id:
            return

        email_data = self.db.get_email_by_id(email_id)
        if email_data:
            self.current_email_data = email_data
            self._render_reading_pane(email_data)

    def _render_reading_pane(self, email_data: Dict[str, Any]):
        subject = email_data.get("subject") or "(No Subject)"
        sender = email_data.get("sender") or "Unknown"
        recipients = email_data.get("recipients") or "-"
        date_sent = email_data.get("date_sent") or "-"
        file_name = email_data.get("file_name") or "-"
        attachments = email_data.get("attachments") or []

        self.pane_subject.setText(subject)
        self.pane_from.setText(f"From: {sender}")
        self.pane_to.setText(f"To: {recipients}")
        self.pane_date.setText(f"Date: {date_sent}")
        self.pane_file.setText(f"Source: {file_name}")

        if attachments:
            att_names = ", ".join([a.get("name", "attachment") for a in attachments])
            self.pane_attachments.setText(f"📎 Attachments ({len(attachments)}): {att_names}")
            self.pane_attachments.setVisible(True)
        else:
            self.pane_attachments.setVisible(False)

        html_body = email_data.get("html_body")
        plain_body = email_data.get("plain_body")

        if html_body and html_body.strip():
            self.body_view.setHtml(html_body)
        elif plain_body and plain_body.strip():
            self.body_view.setPlainText(plain_body)
        else:
            self.body_view.setPlainText("(This message has no body content)")

        self.open_app_btn.setEnabled(True)
        self.save_eml_btn.setEnabled(True)

    # --- Actions ---

    def on_table_double_clicked(self, row: int, col: int):
        self.on_table_row_selected()
        self.open_in_external_app()

    def open_in_external_app(self):
        if not self.current_email_data:
            return
        try:
            eml_path = EmailExporter.export_to_temp_eml(self.current_email_data)
            success, msg = MailLauncher.open_email(eml_path)
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
        self.count_badge.setText(f"{total_in_db:,} Emails Loaded")

        QTimer.singleShot(4000, lambda: self.progress_panel.setVisible(False) if not self.is_indexing else None)
        self.execute_search()

    def closeEvent(self, event):
        cleanup_temp_files()
        event.accept()


def launch_app_qt():
    """Entry point for PySide6 application."""
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    window = FastPSTQtApp()
    window.show()
    sys.exit(app.exec())
