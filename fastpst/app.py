"""
FastPST - Tkinter Desktop GUI Application
Provides full-featured email viewing, search, reading pane, and one-click
redirection to Microsoft Outlook or system default email clients.
"""

import os
import sys
import time
import threading
import queue
import logging
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, scrolledtext
from typing import Optional, List, Dict, Any

from fastpst.utils import get_app_directory, get_database_path, cleanup_temp_files
from fastpst.scanner import scan_directory_for_psts
from fastpst.parser import PSTParser, PYPFF_AVAILABLE, get_mail_parser
from fastpst.db import DatabaseManager
from fastpst.exporter import EmailExporter
from fastpst.launcher import MailLauncher

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("fastpst.app")


class FastPSTApp:
    """Main FastPST GUI Application."""

    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("FastPST - Outlook Data File Viewer & Search")
        self.root.geometry("1150x780")
        self.root.minsize(900, 600)

        # Base directories
        self.current_folder = get_app_directory()
        self.db_path = get_database_path()
        self.db = DatabaseManager(self.db_path)

        # State
        self.current_selected_email_id: Optional[int] = None
        self.current_email_data: Optional[Dict[str, Any]] = None
        self.sort_column = "date_sent"
        self.sort_reverse = True
        self.is_indexing = False
        self.task_queue = queue.Queue()

        # Build UI
        self._setup_styles()
        self._build_top_toolbar()
        self._build_search_bar()
        self._build_main_panes()
        self._build_status_bar()

        # Handle window close
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        # Process periodic queue events
        self.root.after(100, self._process_queue)

        # Auto-scan directory on startup
        self.root.after(300, self.auto_start_scan)

    def _setup_styles(self):
        """Sets up ttk themes and visual styles."""
        self.style = ttk.Style()
        try:
            self.style.theme_use("clam")
        except Exception:
            pass

        # Treeview styling
        self.style.configure(
            "Treeview",
            rowheight=26,
            font=("Segoe UI" if sys.platform == "win32" else "Helvetica", 10),
        )
        self.style.configure(
            "Treeview.Heading",
            font=("Segoe UI" if sys.platform == "win32" else "Helvetica", 10, "bold"),
        )
        self.style.map("Treeview", background=[("selected", "#0078D7")], foreground=[("selected", "#ffffff")])

    def _build_top_toolbar(self):
        """Top toolbar showing current directory and action buttons."""
        top_frame = ttk.Frame(self.root, padding="8 8 8 4")
        top_frame.pack(fill=tk.X)

        folder_lbl = ttk.Label(top_frame, text="Folder:", font=("Segoe UI" if sys.platform == "win32" else "Helvetica", 10, "bold"))
        folder_lbl.pack(side=tk.LEFT, padx=(0, 4))

        self.folder_var = tk.StringVar(value=self.current_folder)
        self.folder_entry = ttk.Entry(top_frame, textvariable=self.folder_var, state="readonly", width=55)
        self.folder_entry.pack(side=tk.LEFT, padx=(0, 8), fill=tk.X, expand=True)

        browse_btn = ttk.Button(top_frame, text="📁 Browse...", command=self.browse_folder)
        browse_btn.pack(side=tk.LEFT, padx=(0, 6))

        self.scan_btn = ttk.Button(top_frame, text="⟳ Scan & Index", command=self.start_manual_scan)
        self.scan_btn.pack(side=tk.LEFT, padx=(0, 8))

        self.email_count_badge = ttk.Label(
            top_frame,
            text="0 Emails Loaded",
            background="#e1dfdd",
            foreground="#323130",
            padding="4 2 4 2",
            font=("Segoe UI" if sys.platform == "win32" else "Helvetica", 9, "bold")
        )
        self.email_count_badge.pack(side=tk.RIGHT, padx=4)

    def _build_search_bar(self):
        """Search inputs, scope filter, and options."""
        search_frame = ttk.Frame(self.root, padding="8 4 8 8")
        search_frame.pack(fill=tk.X)

        search_lbl = ttk.Label(search_frame, text="🔍 Search:", font=("Segoe UI" if sys.platform == "win32" else "Helvetica", 10))
        search_lbl.pack(side=tk.LEFT, padx=(0, 6))

        self.search_var = tk.StringVar()
        self.search_entry = ttk.Entry(search_frame, textvariable=self.search_var, font=("Segoe UI" if sys.platform == "win32" else "Helvetica", 10))
        self.search_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 6))
        self.search_entry.bind("<KeyRelease>", self._on_search_keyrelease)
        self.search_entry.bind("<Return>", lambda e: self.execute_search())

        # Search Scope
        scope_lbl = ttk.Label(search_frame, text="In:")
        scope_lbl.pack(side=tk.LEFT, padx=(4, 4))

        self.scope_var = tk.StringVar(value="all")
        scope_combo = ttk.Combobox(
            search_frame,
            textvariable=self.scope_var,
            values=["all", "subject", "sender", "recipients", "body"],
            state="readonly",
            width=12
        )
        scope_combo.pack(side=tk.LEFT, padx=(0, 8))
        scope_combo.bind("<<ComboboxSelected>>", lambda e: self.execute_search())

        # Has Attachments Filter
        self.att_filter_var = tk.BooleanVar(value=False)
        att_chk = ttk.Checkbutton(
            search_frame, text="📎 Has Attachments", variable=self.att_filter_var, command=self.execute_search
        )
        att_chk.pack(side=tk.LEFT, padx=(0, 8))

        clear_btn = ttk.Button(search_frame, text="Clear", command=self.clear_search)
        clear_btn.pack(side=tk.LEFT)

    def _build_main_panes(self):
        """Splits the window into left (email list table) and right (reading pane)."""
        self.paned = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        self.paned.pack(fill=tk.BOTH, expand=True, padx=8, pady=(0, 4))

        # --- Left Pane: Emails Table ---
        left_pane = ttk.Frame(self.paned)
        self.paned.add(left_pane, weight=4)

        # Treeview columns
        columns = ("date_sent", "sender", "subject", "has_attachments", "file_name")
        self.tree = ttk.Treeview(left_pane, columns=columns, show="headings", selectmode="browse")

        self.tree.heading("date_sent", text="Date", command=lambda: self._sort_by("date_sent"))
        self.tree.heading("sender", text="From", command=lambda: self._sort_by("sender"))
        self.tree.heading("subject", text="Subject", command=lambda: self._sort_by("subject"))
        self.tree.heading("has_attachments", text="📎", command=lambda: self._sort_by("has_attachments"))
        self.tree.heading("file_name", text="File", command=lambda: self._sort_by("file_name"))

        self.tree.column("date_sent", width=120, minwidth=90)
        self.tree.column("sender", width=140, minwidth=100)
        self.tree.column("subject", width=220, minwidth=140)
        self.tree.column("has_attachments", width=30, minwidth=30, anchor="center")
        self.tree.column("file_name", width=90, minwidth=70)

        vsb = ttk.Scrollbar(left_pane, orient=tk.VERTICAL, command=self.tree.yview)
        hsb = ttk.Scrollbar(left_pane, orient=tk.HORIZONTAL, command=self.tree.xview)
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        self.tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")

        left_pane.grid_rowconfigure(0, weight=1)
        left_pane.grid_columnconfigure(0, weight=1)

        # Bind Single Click (Select) -> Load body in reading pane on right
        self.tree.bind("<<TreeviewSelect>>", self._on_tree_select)
        # Bind Double Click -> Open directly in Outlook / Default Mail Client!
        self.tree.bind("<Double-1>", self._on_tree_double_click)

        # --- Right Pane: Reading Pane ---
        right_pane = ttk.Frame(self.paned)
        self.paned.add(right_pane, weight=5)

        # Email Header block
        header_card = ttk.Frame(right_pane, padding="10", relief="groove")
        header_card.pack(fill=tk.X, padx=4, pady=4)

        self.subject_lbl = ttk.Label(
            header_card,
            text="(Select an email from the left list to read)",
            font=("Segoe UI" if sys.platform == "win32" else "Helvetica", 12, "bold"),
            wraplength=550
        )
        self.subject_lbl.pack(anchor="w", pady=(0, 6))

        meta_frame = ttk.Frame(header_card)
        meta_frame.pack(fill=tk.X)

        self.from_lbl = ttk.Label(meta_frame, text="From: -", font=("Segoe UI" if sys.platform == "win32" else "Helvetica", 9))
        self.from_lbl.pack(anchor="w", pady=1)

        self.to_lbl = ttk.Label(meta_frame, text="To: -", font=("Segoe UI" if sys.platform == "win32" else "Helvetica", 9))
        self.to_lbl.pack(anchor="w", pady=1)

        self.date_lbl = ttk.Label(meta_frame, text="Date: -", font=("Segoe UI" if sys.platform == "win32" else "Helvetica", 9))
        self.date_lbl.pack(anchor="w", pady=1)

        self.attachments_lbl = ttk.Label(meta_frame, text="", font=("Segoe UI" if sys.platform == "win32" else "Helvetica", 9, "italic"))
        self.attachments_lbl.pack(anchor="w", pady=(4, 0))

        # Email Body Text (ScrolledText)
        self.body_text = scrolledtext.ScrolledText(
            right_pane,
            wrap=tk.WORD,
            font=("Segoe UI" if sys.platform == "win32" else "Helvetica", 10),
            padx=10,
            pady=10
        )
        self.body_text.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)
        self.body_text.config(state="disabled")

        # Right Action Bar
        action_bar = ttk.Frame(right_pane, padding="6")
        action_bar.pack(fill=tk.X)

        self.open_mail_btn = ttk.Button(
            action_bar,
            text="✉ Open in Outlook / Default Mail App",
            command=self.open_selected_in_mail_client,
            state="disabled"
        )
        self.open_mail_btn.pack(side=tk.LEFT, padx=(0, 8))

        self.save_as_btn = ttk.Button(
            action_bar,
            text="💾 Save Email As...",
            command=self.save_selected_email_as,
            state="disabled"
        )
        self.save_as_btn.pack(side=tk.LEFT)

    def _build_status_bar(self):
        """Bottom status bar with determinate progress bar and details."""
        status_frame = ttk.Frame(self.root, padding="4 4 4 4", relief="sunken")
        status_frame.pack(fill=tk.X, side=tk.BOTTOM)

        self.status_label = ttk.Label(status_frame, text="Ready", font=("Segoe UI" if sys.platform == "win32" else "Helvetica", 9))
        self.status_label.pack(side=tk.LEFT, padx=4, fill=tk.X, expand=True)

        self.progress_percent_label = ttk.Label(status_frame, text="", font=("Segoe UI" if sys.platform == "win32" else "Helvetica", 9, "bold"))
        self.progress_percent_label.pack(side=tk.RIGHT, padx=(4, 8))

        self.progress_bar = ttk.Progressbar(status_frame, mode="determinate", maximum=100, length=220)
        self.progress_bar.pack(side=tk.RIGHT, padx=4)

    # --- Data & Event Handling ---

    def _on_search_keyrelease(self, event):
        """Debounced live search trigger."""
        if hasattr(self, "_search_timer") and self._search_timer:
            self.root.after_cancel(self._search_timer)
        self._search_timer = self.root.after(250, self.execute_search)

    def clear_search(self):
        """Clears search input and reloads all emails."""
        self.search_var.set("")
        self.att_filter_var.set(False)
        self.scope_var.set("all")
        self.execute_search()

    def execute_search(self):
        """Fetches search results from database and refreshes Treeview."""
        query = self.search_var.get().strip()
        scope = self.scope_var.get()
        has_att = self.att_filter_var.get()

        results = self.db.search_emails(
            query=query,
            field_filter=scope,
            has_attachments_only=has_att,
            limit=1000
        )
        self._populate_tree(results)

    def _populate_tree(self, email_rows: List[Dict[str, Any]]):
        """Populates the Treeview table with email records."""
        # Clear existing items
        for item in self.tree.get_children():
            self.tree.delete(item)

        for row in email_rows:
            att_symbol = "📎" if row.get("has_attachments") else ""
            self.tree.insert(
                "",
                tk.END,
                iid=str(row["id"]),
                values=(
                    row.get("date_sent", ""),
                    row.get("sender", ""),
                    row.get("subject", "(No Subject)"),
                    att_symbol,
                    row.get("file_name", "")
                )
            )

        self.email_count_badge.config(text=f"{len(email_rows)} Emails")
        self.status_label.config(text=f"Displaying {len(email_rows)} email(s)")

    def _sort_by(self, col: str):
        """Sorts Treeview items when column header is clicked."""
        items = [(self.tree.set(k, col), k) for k in self.tree.get_children("")]
        
        # Toggle reverse
        if self.sort_column == col:
            self.sort_reverse = not self.sort_reverse
        else:
            self.sort_column = col
            self.sort_reverse = False

        items.sort(reverse=self.sort_reverse)
        for index, (_, k) in enumerate(items):
            self.tree.move(k, "", index)

    def _on_tree_select(self, event):
        """Single click: displays email details and body in reading pane."""
        selected = self.tree.selection()
        if not selected:
            return

        email_id = int(selected[0])
        self.current_selected_email_id = email_id
        
        # Fetch full email from database
        email_data = self.db.get_email_by_id(email_id)
        if not email_data:
            return

        self.current_email_data = email_data

        # Update headers
        self.subject_lbl.config(text=email_data.get("subject") or "(No Subject)")
        self.from_lbl.config(text=f"From: {email_data.get('sender', '')}")
        self.to_lbl.config(text=f"To: {email_data.get('recipients', '')}")
        self.date_lbl.config(text=f"Date: {email_data.get('date_sent', '')}   |   Source: {email_data.get('file_name', '')} ({email_data.get('folder_path', '')})")

        attachments = email_data.get("attachments", [])
        if attachments:
            att_names = ", ".join([a.get("name", "attachment") for a in attachments])
            self.attachments_lbl.config(text=f"📎 Attachments ({len(attachments)}): {att_names}")
        else:
            self.attachments_lbl.config(text="")

        # Update Body Text
        body = email_data.get("plain_body") or email_data.get("html_body") or "(No message body content)"
        self.body_text.config(state="normal")
        self.body_text.delete("1.0", tk.END)
        self.body_text.insert(tk.END, body)
        self.body_text.config(state="disabled")

        # Enable action buttons
        self.open_mail_btn.config(state="normal")
        self.save_as_btn.config(state="normal")

    def _on_tree_double_click(self, event):
        """Double click: immediately opens the email in Outlook / default mail client."""
        self._on_tree_select(event)
        self.open_selected_in_mail_client()

    def open_selected_in_mail_client(self):
        """Exports the selected email to a temp file and opens default mail client."""
        if not self.current_email_data:
            return

        self.status_label.config(text="Preparing email to open...")
        try:
            temp_file = EmailExporter.export_to_temp_msg(self.current_email_data)
            success, msg = MailLauncher.open_email_file(temp_file)
            if success:
                self.status_label.config(text="Email opened in default mail client.")
            else:
                messagebox.showerror("Error Opening Email", msg)
                self.status_label.config(text=f"Error: {msg}")
        except Exception as e:
            logger.error(f"Error opening email: {e}")
            messagebox.showerror("Error", f"Could not launch email: {e}")
            self.status_label.config(text=f"Failed: {e}")

    def save_selected_email_as(self):
        """Allows user to permanently save the email as .eml or .msg."""
        if not self.current_email_data:
            return

        subject_clean = "".join([c if c.isalnum() or c in " ._-" else "_" for c in (self.current_email_data.get("subject") or "email")])[:40]
        default_name = f"{subject_clean}.eml"

        target_path = filedialog.asksaveasfilename(
            initialfile=default_name,
            defaultextension=".eml",
            filetypes=[("Email Message (.eml)", "*.eml"), ("All Files", "*.*")]
        )
        if target_path:
            try:
                EmailExporter.save_email_as(self.current_email_data, target_path)
                messagebox.showinfo("Saved", f"Email successfully saved to:\n{target_path}")
            except Exception as e:
                messagebox.showerror("Save Error", f"Failed to save email: {e}")

    def browse_folder(self):
        """Allows the user to select another folder to scan."""
        selected_dir = filedialog.askdirectory(initialdir=self.current_folder, title="Select Folder Containing .PST or .OST Files")
        if selected_dir and os.path.exists(selected_dir):
            self.current_folder = selected_dir
            self.folder_var.set(self.current_folder)
            self.start_manual_scan()

    # --- Scanning & Background Indexing ---

    def auto_start_scan(self):
        """Scans current folder automatically on startup."""
        self._start_scan_thread(force_reindex=False)

    def start_manual_scan(self):
        """Triggered by 'Scan & Index' button."""
        self._start_scan_thread(force_reindex=True)

    def _start_scan_thread(self, force_reindex: bool = False):
        """Launches directory scanning and indexing in a background thread."""
        if self.is_indexing:
            return

        self.is_indexing = True
        self.progress_bar["value"] = 0
        self.progress_percent_label.config(text="0%")
        self.status_label.config(text="Scanning folder for mail data files...")

        thread = threading.Thread(
            target=self._scan_and_index_worker,
            args=(self.current_folder, force_reindex),
            daemon=True
        )
        thread.start()

    def _scan_and_index_worker(self, folder: str, force_reindex: bool):
        """Worker thread executing discovery and parsing."""
        start_time = time.time()
        try:
            discovered = scan_directory_for_psts(folder, recursive=True)
            total_files = len(discovered)

            if not discovered:
                self.task_queue.put(("no_files_found", folder))
                self.task_queue.put(("indexing_complete", (0, 0.0)))
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
                    self.task_queue.put(("progress", (pct, f"File ({f_idx}/{total_files}): {filename} (Already indexed)")))
                    continue

                _, ext = os.path.splitext(filename)
                if ext.lower() in {".pst", ".ost"} and not PYPFF_AVAILABLE:
                    self.task_queue.put((
                        "error_dialog",
                        f"pypff / libpff is required to parse {filename}.\nRun 'pip install libpff-python'."
                    ))
                    continue

                size_str = f"{size_mb:.1f} MB" if size_mb < 1024 else f"{(size_mb/1024):.2f} GB"
                self.task_queue.put(("progress", (base_pct, f"Indexing ({f_idx}/{total_files}): {filename} ({size_str})...")))
                
                # Remove stale records if reindexing
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
                                self.task_queue.put(("progress", (curr_pct, f"Indexing ({f_idx}/{total_files}): {filename} • {count:,} emails...")))

                        if batch:
                            self.db.insert_emails_batch(batch)
                            batch.clear()

                    self.db.record_file_indexed(file_path, file_size, mtime, count)
                    total_new_indexed += count
                    file_done_pct = int((f_idx / total_files) * 100)
                    self.task_queue.put(("progress", (file_done_pct, f"Indexed ({f_idx}/{total_files}): {filename} ({count:,} emails)")))

                except Exception as e:
                    logger.error(f"Failed to parse {filename}: {e}")
                    self.task_queue.put(("status", f"Error parsing {filename}: {e}"))

            elapsed = time.time() - start_time
            self.task_queue.put(("indexing_complete", (total_new_indexed, elapsed)))

        except Exception as e:
            logger.error(f"Error in scan worker: {e}")
            self.task_queue.put(("status", f"Scan error: {e}"))
            self.task_queue.put(("indexing_complete", (0, 0.0)))

    def _process_queue(self):
        """Polls task queue to update UI from background threads safely."""
        try:
            while True:
                msg_type, data = self.task_queue.get_nowait()
                if msg_type == "status":
                    self.status_label.config(text=data)
                elif msg_type == "progress":
                    pct, text = data
                    self.progress_bar["value"] = pct
                    self.progress_percent_label.config(text=f"{pct}%")
                    self.status_label.config(text=text)
                elif msg_type == "no_files_found":
                    self.status_label.config(text=f"No mail files found in {os.path.basename(data)}")
                elif msg_type == "error_dialog":
                    messagebox.showwarning("Prerequisite Notice", data)
                elif msg_type == "indexing_complete":
                    count, elapsed = data
                    self.is_indexing = False
                    self.progress_bar["value"] = 100
                    self.progress_percent_label.config(text="100%")
                    total_in_db = self.db.get_total_email_count()
                    if elapsed > 0:
                        msg = f"✓ Indexing complete! {count:,} new emails indexed in {elapsed:.1f}s ({total_in_db:,} total)."
                    else:
                        msg = f"✓ Index current: {total_in_db:,} total emails loaded."
                    self.status_label.config(text=msg)
                    self.execute_search()
        except queue.Empty:
            pass

        # Reschedule check
        self.root.after(100, self._process_queue)

    def _on_close(self):
        """Cleanup temporary files and close application."""
        cleanup_temp_files()
        self.root.destroy()


def launch_app():
    """Entrypoint function to run the FastPST GUI."""
    root = tk.Tk()
    app = FastPSTApp(root)
    root.mainloop()


if __name__ == "__main__":
    launch_app()
