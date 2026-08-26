"""
FastPST - PySide6 (Qt) Desktop Application
Provides high-performance email browsing, reading pane, search, and mail client redirection.
Used automatically when Tkinter shared libraries are not present on the Linux host.
"""

import os
import sys
import threading
import logging
from typing import List, Dict, Any, Optional

from PySide6.QtCore import Qt, Signal, QObject, QTimer
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLineEdit, QPushButton, QLabel, QTableWidget, QTableWidgetItem,
    QHeaderView, QSplitter, QTextBrowser, QComboBox, QCheckBox,
    QProgressBar, QFileDialog, QMessageBox, QFrame
)
from PySide6.QtGui import QFont, QIcon

from fastpst.utils import get_app_directory, get_database_path
from fastpst.scanner import scan_directory_for_psts
from fastpst.parser import PSTParser, PYPFF_AVAILABLE, get_mail_parser
from fastpst.db import DatabaseManager
from fastpst.exporter import EmailExporter, cleanup_temp_files
from fastpst.launcher import MailLauncher

logger = logging.getLogger("fastpst.app_qt")


class WorkerSignals(QObject):
    status_updated = Signal(str)
    no_files_found = Signal(str)
    error_dialog = Signal(str)
    indexing_complete = Signal(int)


class FastPSTQtApp(QMainWindow):
    """PySide6 Desktop Application for FastPST."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("FastPST - Outlook Data File Viewer & Search")
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
        self.signals.no_files_found.connect(self._on_no_files_found)
        self.signals.error_dialog.connect(self._on_error_dialog)
        self.signals.indexing_complete.connect(self._on_indexing_complete)

        # Search debounce timer
        self.search_timer = QTimer(self)
        self.search_timer.setSingleShot(True)
        self.search_timer.timeout.connect(self.execute_search)

        self._init_ui()

        # Auto-scan folder on startup
        QTimer.singleShot(300, self.auto_start_scan)

    def _init_ui(self):
        """Builds Qt user interface."""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(8, 8, 8, 4)
        main_layout.setSpacing(6)

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
        self.count_badge.setStyleSheet("background-color: #e0e0e0; color: #222; padding: 4px 8px; border-radius: 4px; font-weight: bold;")
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

        # 3. Main Splitter (Left: Email List, Right: Reading Pane)
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

        # Single click -> Show full email in reading pane on the right
        self.table.itemSelectionChanged.connect(self._on_table_select)
        # Double click -> Open directly in Outlook / Thunderbird!
        self.table.itemDoubleClicked.connect(self._on_table_double_click)

        splitter.addWidget(self.table)

        # Right Reading Pane
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(4, 0, 0, 0)
        right_layout.setSpacing(6)

        # Header card
        header_card = QFrame()
        header_card.setFrameShape(QFrame.StyledPanel)
        header_layout = QVBoxLayout(header_card)
        header_layout.setContentsMargins(10, 10, 10, 10)
        header_layout.setSpacing(4)

        self.subject_lbl = QLabel("(Select an email from the left list to read)")
        self.subject_lbl.setFont(QFont("sans-serif", 12, QFont.Bold))
        self.subject_lbl.setWordWrap(True)
        header_layout.addWidget(self.subject_lbl)

        self.from_lbl = QLabel("From: -")
        header_layout.addWidget(self.from_lbl)

        self.to_lbl = QLabel("To: -")
        header_layout.addWidget(self.to_lbl)

        self.date_lbl = QLabel("Date: -")
        header_layout.addWidget(self.date_lbl)

        self.attachments_lbl = QLabel("")
        self.attachments_lbl.setStyleSheet("color: #0066cc; font-style: italic;")
        header_layout.addWidget(self.attachments_lbl)

        right_layout.addWidget(header_card)

        # Email Body Text Browser
        self.body_browser = QTextBrowser()
        self.body_browser.setFont(QFont("sans-serif", 10))
        right_layout.addWidget(self.body_browser, stretch=1)

        # Action Buttons
        action_layout = QHBoxLayout()
        self.open_mail_btn = QPushButton("✉ Open in Outlook / Default Mail App")
        self.open_mail_btn.setEnabled(False)
        self.open_mail_btn.clicked.connect(self.open_selected_in_mail_client)
        action_layout.addWidget(self.open_mail_btn)

        self.save_as_btn = QPushButton("💾 Save Email As...")
        self.save_as_btn.setEnabled(False)
        self.save_as_btn.clicked.connect(self.save_selected_email_as)
        action_layout.addWidget(self.save_as_btn)

        action_layout.addStretch()
        right_layout.addLayout(action_layout)

        splitter.addWidget(right_widget)
        splitter.setSizes([480, 670])

        # 4. Status Bar
        status_bar = self.statusBar()
        self.status_lbl = QLabel("Ready")
        status_bar.addWidget(self.status_lbl, stretch=1)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setMaximumWidth(180)
        self.progress_bar.setVisible(False)
        status_bar.addPermanentWidget(self.progress_bar)

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

        for row_idx, email in enumerate(email_rows):
            att_sym = "📎" if email.get("has_attachments") else ""
            
            items = [
                QTableWidgetItem(email.get("date_sent", "")),
                QTableWidgetItem(email.get("sender", "")),
                QTableWidgetItem(email.get("subject") or "(No Subject)"),
                QTableWidgetItem(att_sym),
                QTableWidgetItem(email.get("file_name", ""))
            ]
            items[3].setTextAlignment(Qt.AlignCenter)

            for col_idx, item in enumerate(items):
                # Store email ID in UserRole of the first item
                if col_idx == 0:
                    item.setData(Qt.UserRole, email["id"])
                self.table.setItem(row_idx, col_idx, item)

        self.table.setSortingEnabled(True)
        self.count_badge.setText(f"{len(email_rows)} Emails")
        self.status_lbl.setText(f"Displaying {len(email_rows)} email(s)")

    # --- Selection & Redirection ---

    def _on_table_select(self):
        selected_rows = self.table.selectedItems()
        if not selected_rows:
            return

        row = self.table.currentRow()
        first_item = self.table.item(row, 0)
        if not first_item:
            return

        email_id = first_item.data(Qt.UserRole)
        email_data = self.db.get_email_by_id(email_id)
        if not email_data:
            return

        self.current_email_data = email_data

        # Update Header
        self.subject_lbl.setText(email_data.get("subject") or "(No Subject)")
        self.from_lbl.setText(f"From: {email_data.get('sender', '')}")
        self.to_lbl.setText(f"To: {email_data.get('recipients', '')}")
        self.date_lbl.setText(f"Date: {email_data.get('date_sent', '')}   |   Source: {email_data.get('file_name', '')} ({email_data.get('folder_path', '')})")

        attachments = email_data.get("attachments", [])
        if attachments:
            att_names = ", ".join([a.get("name", "attachment") for a in attachments])
            self.attachments_lbl.setText(f"📎 Attachments ({len(attachments)}): {att_names}")
        else:
            self.attachments_lbl.setText("")

        # Update Body
        html = email_data.get("html_body")
        plain = email_data.get("plain_body")
        if html and len(html.strip()) > 0:
            self.body_browser.setHtml(html)
        elif plain and len(plain.strip()) > 0:
            self.body_browser.setPlainText(plain)
        else:
            self.body_browser.setPlainText("(No message body)")

        self.open_mail_btn.setEnabled(True)
        self.save_as_btn.setEnabled(True)

    def _on_table_double_click(self, item):
        self._on_table_select()
        self.open_selected_in_mail_client()

    def open_selected_in_mail_client(self):
        if not self.current_email_data:
            return

        self.status_lbl.setText("Exporting email to temporary file...")
        try:
            temp_file = EmailExporter.export_to_temp_msg(self.current_email_data)
            success, msg = MailLauncher.open_email_file(temp_file)
            if success:
                self.status_lbl.setText("Opened in default mail client.")
            else:
                QMessageBox.warning(self, "Mail Client", msg)
                self.status_lbl.setText(f"Notice: {msg}")
        except Exception as e:
            logger.error(f"Error opening email: {e}")
            QMessageBox.critical(self, "Error", f"Could not launch email: {e}")

    def save_selected_email_as(self):
        if not self.current_email_data:
            return

        subject_clean = "".join([c if c.isalnum() or c in " ._-" else "_" for c in (self.current_email_data.get("subject") or "email")])[:40]
        default_name = f"{subject_clean}.eml"

        target_path, _ = QFileDialog.getSaveFileName(
            self, "Save Email As", os.path.join(self.current_folder, default_name), "Email Message (*.eml);;All Files (*.*)"
        )
        if target_path:
            try:
                EmailExporter.save_email_as(self.current_email_data, target_path)
                QMessageBox.information(self, "Saved", f"Email saved to:\n{target_path}")
            except Exception as e:
                QMessageBox.critical(self, "Save Error", f"Failed to save email: {e}")

    def browse_folder(self):
        selected_dir = QFileDialog.getExistingDirectory(self, "Select Folder with .PST/.OST files", self.current_folder)
        if selected_dir and os.path.exists(selected_dir):
            self.current_folder = selected_dir
            self.folder_input.setText(self.current_folder)
            self.start_manual_scan()

    # --- Background Scanning ---

    def auto_start_scan(self):
        self._start_scan_thread(force_reindex=False)

    def start_manual_scan(self):
        self._start_scan_thread(force_reindex=True)

    def _start_scan_thread(self, force_reindex: bool):
        if self.is_indexing:
            return

        self.is_indexing = True
        self.progress_bar.setVisible(True)
        self.status_lbl.setText("Scanning directory for PST and OST files...")

        thread = threading.Thread(
            target=self._scan_worker,
            args=(self.current_folder, force_reindex),
            daemon=True
        )
        thread.start()

    def _scan_worker(self, folder: str, force_reindex: bool):
        try:
            discovered = scan_directory_for_psts(folder, recursive=True)
            self.signals.status_updated.emit(f"Found {len(discovered)} PST/OST file(s). Checking index...")

            if not discovered:
                self.signals.no_files_found.emit(folder)
                self.signals.indexing_complete.emit(0)
                return

            total_new_indexed = 0

            for f_info in discovered:
                file_path = f_info["path"]
                file_size = f_info["size"]
                mtime = f_info["mtime"]
                filename = f_info["filename"]

                if not force_reindex and self.db.is_file_indexed_and_current(file_path, file_size, mtime):
                    continue

                _, ext = os.path.splitext(filename)
                if ext.lower() in {".pst", ".ost"} and not PYPFF_AVAILABLE:
                    self.signals.error_dialog.emit(
                        f"pypff / libpff is required to parse {filename}.\nRun 'pip install libpff-python'."
                    )
                    continue

                self.signals.status_updated.emit(f"Indexing {filename}...")
                self.db.remove_file_records(file_path)

                batch = []
                count = 0

                try:
                    parser = get_mail_parser(file_path)
                    with parser:
                        for msg in parser.parse_all_messages():
                            batch.append(msg)
                            count += 1
                            if len(batch) >= 100:
                                self.db.insert_emails_batch(batch)
                                batch.clear()
                                self.signals.status_updated.emit(f"Indexing {filename}: {count} emails...")

                        if batch:
                            self.db.insert_emails_batch(batch)
                            batch.clear()

                    self.db.record_file_indexed(file_path, file_size, mtime, count)
                    total_new_indexed += count

                except Exception as e:
                    logger.error(f"Error parsing {filename}: {e}")
                    self.signals.status_updated.emit(f"Error parsing {filename}: {e}")

            self.signals.indexing_complete.emit(total_new_indexed)

        except Exception as e:
            logger.error(f"Scan error: {e}")
            self.signals.status_updated.emit(f"Scan error: {e}")
            self.signals.indexing_complete.emit(0)

    def _on_status_updated(self, text: str):
        self.status_lbl.setText(text)

    def _on_no_files_found(self, folder: str):
        self.status_lbl.setText(f"No .pst or .ost files found in {os.path.basename(folder)}")

    def _on_error_dialog(self, text: str):
        QMessageBox.warning(self, "Notice", text)

    def _on_indexing_complete(self, total: int):
        self.is_indexing = False
        self.progress_bar.setVisible(False)
        self.execute_search()

    def closeEvent(self, event):
        cleanup_temp_files()
        event.accept()


def launch_app_qt():
    """Entry point for PySide6 Qt GUI."""
    app = QApplication.instance()
    if not app:
        app = QApplication(sys.argv)
    window = FastPSTQtApp()
    window.show()
    app.exec()


if __name__ == "__main__":
    launch_app_qt()
