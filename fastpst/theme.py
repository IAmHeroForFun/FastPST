"""
FastPST - Universal Theme Engine (Outlook Light & Dark Mode)
Provides complete Fusion palette synchronization, full QSS stylesheets,
and intelligent HTML email dark-mode adaptation.
Eliminates OS theme clashes, black-on-black text, white-on-white text, and unstyled boxes.
"""

import os
import re
import html
import logging
from typing import Optional

from PySide6.QtGui import QPalette, QColor
from PySide6.QtWidgets import QApplication

logger = logging.getLogger("fastpst.theme")


def get_light_palette() -> QPalette:
    """Returns a full, explicit light palette."""
    p = QPalette()
    p.setColor(QPalette.Window, QColor("#f1f5f9"))
    p.setColor(QPalette.WindowText, QColor("#0f172a"))
    p.setColor(QPalette.Base, QColor("#ffffff"))
    p.setColor(QPalette.AlternateBase, QColor("#f8fafc"))
    p.setColor(QPalette.ToolTipBase, QColor("#ffffff"))
    p.setColor(QPalette.ToolTipText, QColor("#0f172a"))
    p.setColor(QPalette.Text, QColor("#0f172a"))
    p.setColor(QPalette.Button, QColor("#ffffff"))
    p.setColor(QPalette.ButtonText, QColor("#0f172a"))
    p.setColor(QPalette.BrightText, QColor("#dc2626"))
    p.setColor(QPalette.Link, QColor("#2563eb"))
    p.setColor(QPalette.Highlight, QColor("#2563eb"))
    p.setColor(QPalette.HighlightedText, QColor("#ffffff"))
    p.setColor(QPalette.PlaceholderText, QColor("#94a3b8"))
    return p


def get_dark_palette() -> QPalette:
    """Returns a full, explicit dark palette."""
    p = QPalette()
    p.setColor(QPalette.Window, QColor("#18181b"))
    p.setColor(QPalette.WindowText, QColor("#f8fafc"))
    p.setColor(QPalette.Base, QColor("#18181b"))
    p.setColor(QPalette.AlternateBase, QColor("#222226"))
    p.setColor(QPalette.ToolTipBase, QColor("#27272a"))
    p.setColor(QPalette.ToolTipText, QColor("#f8fafc"))
    p.setColor(QPalette.Text, QColor("#f8fafc"))
    p.setColor(QPalette.Button, QColor("#27272a"))
    p.setColor(QPalette.ButtonText, QColor("#f8fafc"))
    p.setColor(QPalette.BrightText, QColor("#ef4444"))
    p.setColor(QPalette.Link, QColor("#38bdf8"))
    p.setColor(QPalette.Highlight, QColor("#2563eb"))
    p.setColor(QPalette.HighlightedText, QColor("#ffffff"))
    p.setColor(QPalette.PlaceholderText, QColor("#71717a"))
    return p


def get_light_stylesheet() -> str:
    """Returns the comprehensive Outlook Light stylesheet."""
    return """
    QMainWindow, QDialog, QWidget {
        background-color: #f1f5f9;
        color: #0f172a;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    }
    QFrame#TopFrame, QFrame#SearchFrame, QFrame#HeaderCard, QFrame#ProgressPanel {
        background-color: #ffffff;
        border: 1px solid #cbd5e1;
        border-radius: 6px;
    }
    QLabel {
        color: #0f172a;
        background-color: transparent;
    }
    QLabel#MetaSubLabel {
        color: #64748b;
        background-color: transparent;
    }
    QLineEdit, QComboBox, QTextEdit {
        background-color: #ffffff;
        color: #0f172a;
        border: 1px solid #cbd5e1;
        border-radius: 4px;
        padding: 5px 8px;
        selection-background-color: #2563eb;
        selection-color: #ffffff;
    }
    QLineEdit:focus, QComboBox:focus, QTextEdit:focus {
        border: 1px solid #2563eb;
    }
    QComboBox QAbstractItemView {
        background-color: #ffffff;
        color: #0f172a;
        selection-background-color: #2563eb;
        selection-color: #ffffff;
        border: 1px solid #cbd5e1;
    }
    QPushButton {
        background-color: #ffffff;
        color: #0f172a;
        border: 1px solid #cbd5e1;
        border-radius: 4px;
        padding: 5px 12px;
        font-weight: 500;
    }
    QPushButton:hover {
        background-color: #e2e8f0;
        border-color: #94a3b8;
    }
    QPushButton:pressed {
        background-color: #cbd5e1;
    }
    QPushButton:disabled {
        background-color: #f1f5f9;
        color: #94a3b8;
        border-color: #e2e8f0;
    }
    QTreeWidget {
        background-color: #ffffff;
        color: #0f172a;
        border: 1px solid #cbd5e1;
        border-radius: 6px;
        padding: 4px;
    }
    QTreeWidget::item {
        padding: 4px 6px;
        border-radius: 4px;
    }
    QTreeWidget::item:hover {
        background-color: #f1f5f9;
    }
    QTreeWidget::item:selected {
        background-color: #2563eb;
        color: #ffffff;
    }
    QListWidget {
        background-color: #ffffff;
        color: #0f172a;
        border: 1px solid #cbd5e1;
        border-radius: 6px;
        padding: 2px;
    }
    QListWidget::item {
        border-bottom: 1px solid #e2e8f0;
    }
    QListWidget::item:hover {
        background-color: #f1f5f9;
    }
    QListWidget::item:selected {
        background-color: #2563eb;
        color: #ffffff;
    }
    QTableWidget {
        background-color: #ffffff;
        alternate-background-color: #f8fafc;
        color: #0f172a;
        gridline-color: #e2e8f0;
        border: 1px solid #cbd5e1;
        border-radius: 6px;
        selection-background-color: #2563eb;
        selection-color: #ffffff;
    }
    QTableWidget::item:selected {
        background-color: #2563eb;
        color: #ffffff;
    }
    QHeaderView::section {
        background-color: #f1f5f9;
        color: #334155;
        padding: 6px;
        border: none;
        border-bottom: 2px solid #cbd5e1;
        font-weight: bold;
    }
    QTextBrowser {
        background-color: #ffffff;
        color: #0f172a;
        border: 1px solid #cbd5e1;
        border-radius: 6px;
        padding: 10px;
    }
    QStatusBar {
        background-color: #e2e8f0;
        color: #334155;
        border-top: 1px solid #cbd5e1;
    }
    QProgressBar {
        border: 1px solid #cbd5e1;
        border-radius: 4px;
        background-color: #e2e8f0;
        text-align: center;
    }
    QProgressBar::chunk {
        background-color: #2563eb;
        border-radius: 3px;
    }
    QCheckBox {
        color: #0f172a;
        background-color: transparent;
        spacing: 6px;
    }
    QSplitter::handle {
        background-color: #cbd5e1;
    }
    QScrollBar:vertical, QScrollBar:horizontal {
        background-color: #f1f5f9;
        border: none;
    }
    QScrollBar::handle:vertical, QScrollBar::handle:horizontal {
        background-color: #cbd5e1;
        border-radius: 4px;
    }
    """


def get_dark_stylesheet() -> str:
    """Returns the comprehensive Outlook Dark stylesheet."""
    return """
    QMainWindow, QDialog, QWidget {
        background-color: #18181b;
        color: #f8fafc;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    }
    QFrame#TopFrame, QFrame#SearchFrame, QFrame#HeaderCard, QFrame#ProgressPanel {
        background-color: #27272a;
        border: 1px solid #3f3f46;
        border-radius: 6px;
    }
    QLabel {
        color: #f8fafc;
        background-color: transparent;
    }
    QLabel#MetaSubLabel {
        color: #94a3b8;
        background-color: transparent;
    }
    QLineEdit, QComboBox, QTextEdit {
        background-color: #1f1f23;
        color: #f8fafc;
        border: 1px solid #3f3f46;
        border-radius: 4px;
        padding: 5px 8px;
        selection-background-color: #3b82f6;
        selection-color: #ffffff;
    }
    QLineEdit:focus, QComboBox:focus, QTextEdit:focus {
        border: 1px solid #38bdf8;
    }
    QComboBox QAbstractItemView {
        background-color: #27272a;
        color: #f8fafc;
        selection-background-color: #2563eb;
        selection-color: #ffffff;
        border: 1px solid #3f3f46;
    }
    QPushButton {
        background-color: #27272a;
        color: #f8fafc;
        border: 1px solid #3f3f46;
        border-radius: 4px;
        padding: 5px 12px;
        font-weight: 500;
    }
    QPushButton:hover {
        background-color: #3f3f46;
        border-color: #71717a;
    }
    QPushButton:pressed {
        background-color: #52525b;
    }
    QPushButton:disabled {
        background-color: #1f1f23;
        color: #52525b;
        border-color: #27272a;
    }
    QTreeWidget {
        background-color: #18181b;
        color: #f8fafc;
        border: 1px solid #3f3f46;
        border-radius: 6px;
        padding: 4px;
    }
    QTreeWidget::item {
        padding: 4px 6px;
        border-radius: 4px;
    }
    QTreeWidget::item:hover {
        background-color: #27272a;
    }
    QTreeWidget::item:selected {
        background-color: #2563eb;
        color: #ffffff;
    }
    QListWidget {
        background-color: #18181b;
        color: #f8fafc;
        border: 1px solid #3f3f46;
        border-radius: 6px;
        padding: 2px;
    }
    QListWidget::item {
        border-bottom: 1px solid #27272a;
    }
    QListWidget::item:hover {
        background-color: #27272a;
    }
    QListWidget::item:selected {
        background-color: #2563eb;
        color: #ffffff;
    }
    QTableWidget {
        background-color: #18181b;
        alternate-background-color: #222226;
        color: #f8fafc;
        gridline-color: #2e2e33;
        border: 1px solid #3f3f46;
        border-radius: 6px;
        selection-background-color: #2563eb;
        selection-color: #ffffff;
    }
    QTableWidget::item:selected {
        background-color: #2563eb;
        color: #ffffff;
    }
    QHeaderView::section {
        background-color: #27272a;
        color: #e2e8f0;
        padding: 6px;
        border: none;
        border-bottom: 2px solid #3f3f46;
        font-weight: bold;
    }
    QTextBrowser {
        background-color: #18181b;
        color: #f8fafc;
        border: 1px solid #3f3f46;
        border-radius: 6px;
        padding: 10px;
    }
    QStatusBar {
        background-color: #18181b;
        color: #94a3b8;
        border-top: 1px solid #27272a;
    }
    QProgressBar {
        border: 1px solid #3f3f46;
        border-radius: 4px;
        background-color: #27272a;
        text-align: center;
    }
    QProgressBar::chunk {
        background-color: #38bdf8;
        border-radius: 3px;
    }
    QCheckBox {
        color: #f8fafc;
        background-color: transparent;
        spacing: 6px;
    }
    QSplitter::handle {
        background-color: #3f3f46;
    }
    QScrollBar:vertical, QScrollBar:horizontal {
        background-color: #18181b;
        border: none;
    }
    QScrollBar::handle:vertical, QScrollBar::handle:horizontal {
        background-color: #3f3f46;
        border-radius: 4px;
    }
    """


def adapt_html_for_dark_mode(raw_html: str) -> str:
    """
    Strips inline white/light backgrounds, removes hardcoded dark text colors,
    and formats HTML for crisp dark-mode rendering in QTextBrowser.
    """
    if not raw_html:
        return ""

    s = raw_html

    # 1. Remove background attributes: bgcolor="...", background="..."
    s = re.sub(r'(?i)\b(bgcolor|background)\s*=\s*["\']?[^"\'>\s]+["\']?', '', s)

    # 2. Clean inline style attributes
    def clean_style(match):
        style_val = match.group(1)
        # Remove background-color / background declarations
        style_val = re.sub(r'(?i)background(?:-color)?\s*:\s*[^;"]+;?', '', style_val)
        # Convert dark text colors (#000000, black, #111, #222, #333, rgb(0,0,0), etc) to #f8fafc
        style_val = re.sub(
            r'(?i)color\s*:\s*(?:#(?:000000|000|111111|111|222222|222|333333|333|444444|444|1e1e1e|0f172a)|black|rgb\(\s*0\s*,\s*0\s*,\s*0\s*\))\s*;?',
            'color: #f8fafc;',
            style_val
        )
        return f'style="{style_val.strip()}"'

    s = re.sub(r'(?i)style\s*=\s*["\']([^"\']*)["\']', clean_style, s)

    # 3. Replace <font color="black"> / <font color="#000000">
    s = re.sub(
        r'(?i)<font\s+([^>]*?)color\s*=\s*["\']?(?:#(?:000000|000|111111|111|222222|222|333333|333|444444|444|1e1e1e|0f172a)|black)["\']?',
        r'<font \1color="#f8fafc"',
        s
    )

    # 4. Global CSS styling wrapper
    css = """
    <style>
        body {
            background-color: #18181b;
            color: #f8fafc;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            font-size: 13px;
            line-height: 1.5;
            margin: 0;
            padding: 8px;
        }
        p, div, span, td, th, li, font, h1, h2, h3, h4, h5, h6 {
            color: #f8fafc;
        }
        a, a * {
            color: #38bdf8;
            text-decoration: underline;
        }
        table {
            border-color: #3f3f46;
            color: #f8fafc;
        }
        td, th {
            border-color: #3f3f46;
            color: #f8fafc;
        }
        code, pre {
            background-color: #27272a;
            color: #38bdf8;
            border: 1px solid #3f3f46;
            padding: 4px;
            border-radius: 4px;
        }
        blockquote {
            border-left: 3px solid #38bdf8;
            color: #94a3b8;
            margin: 8px 0;
            padding-left: 10px;
        }
    </style>
    """

    if "<head>" in s.lower():
        s = re.sub(r'(?i)(<head[^>]*>)', r'\1' + css, s, count=1)
    elif "<html>" in s.lower():
        s = re.sub(r'(?i)(<html[^>]*>)', r'\1<head>' + css + '</head>', s, count=1)
    else:
        s = f"<html><head>{css}</head><body>{s}</body></html>"

    return s


def format_email_body_html(html_body: Optional[str], plain_body: Optional[str], is_dark: bool) -> str:
    """Formats either HTML or plain text body with appropriate high-contrast theme styling."""
    if html_body and html_body.strip():
        if is_dark:
            return adapt_html_for_dark_mode(html_body)
        else:
            return html_body

    if plain_body and plain_body.strip():
        escaped = html.escape(plain_body)
        bg = "#18181b" if is_dark else "#ffffff"
        fg = "#f8fafc" if is_dark else "#0f172a"
        return f"""
        <html>
        <head>
        <style>
            body {{
                background-color: {bg};
                color: {fg};
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
                white-space: pre-wrap;
                line-height: 1.5;
                font-size: 13px;
                padding: 8px;
            }}
        </style>
        </head>
        <body>{escaped}</body>
        </html>
        """

    return '<div style="color: #94a3b8; font-style: italic; padding: 8px;">(This message has no body content)</div>'


def apply_theme(app_instance: QApplication, theme_name: str):
    """Applies the palette and stylesheet universally to the entire application."""
    if not app_instance:
        return

    if theme_name == "dark":
        app_instance.setPalette(get_dark_palette())
        app_instance.setStyleSheet(get_dark_stylesheet())
    else:
        app_instance.setPalette(get_light_palette())
        app_instance.setStyleSheet(get_light_stylesheet())


def save_theme_preference(db_manager, theme_name: str):
    """Saves the user's theme preference in the database."""
    if not db_manager:
        return
    try:
        conn = db_manager.get_connection()
        with conn:
            conn.execute(
                "INSERT OR REPLACE INTO system_state (key, value) VALUES ('theme', ?)",
                (theme_name,),
            )
    except Exception as e:
        logger.debug(f"Could not save theme preference: {e}")


def load_theme_preference(db_manager) -> str:
    """Loads the saved theme preference ('light' or 'dark'). Defaults to 'light'."""
    if not db_manager:
        return "light"
    try:
        conn = db_manager.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM system_state WHERE key = 'theme'")
        row = cursor.fetchone()
        if row and row["value"]:
            return row["value"].lower()
    except Exception as e:
        logger.debug(f"Could not load theme preference: {e}")
    return "light"
