# FastPST 🚀

**FastPST** is a lightning-fast, lightweight, zero-configuration desktop tool for scanning, searching, viewing, and opening emails directly from Outlook `.pst` and `.ost` data files on **Windows** and **Linux**.

---

## 🖥️ UI Layout (Side-by-Side Outlook Style)

```
+----------------------------------------------------------------------------------------------------+
|  FastPST - Outlook Data File Viewer & Search                                                       |
+----------------------------------------------------------------------------------------------------+
|  Folder: C:\MyEmails\   | [ 📁 Browse... ] [ ⟳ Scan & Index ] | 1,420 Emails Loaded                 |
|  🔍 Search: [ project report                       ] In: [ All Fields ▾ ] [📎 Has Attachments]     |
+----------------------------------------------------------------------------------------------------+
|  EMAILS LIST (Left Side)               |  EMAIL READING PANE (Right Side)                          |
|  Date       | From       | Subject     |                                                           |
|-------------+------------+-------------|  Subject: Project FastPST Status                          |
|  2026-08-20 | John Doe   | Status 📎   |  From: John Doe <john.doe@example.com>                    |
|  2026-08-19 | Jane Smith | Financials  |  To: Team <team@example.com>                              |
|  2026-08-18 | IT Support | Alert 📎    |  Date: Aug 20, 2026 14:30   | Source: backup.pst          |
|  2026-08-17 | Marketing  | Newsletter  |  📎 Attachments (1): report.pdf                            |
|             |            |             |  -------------------------------------------------------  |
|             |            |             |  Hi Team,                                                 |
|             |            |             |                                                           |
|             |            |             |  Here is the full email body displayed directly on the   |
|             |            |             |  right side when you click on any email in the left list! |
|             |            |             |                                                           |
|             |            |             |  [ ✉ Open in Outlook / Mail App ]   [ 💾 Save Email As ]  |
+----------------------------------------------------------------------------------------------------+
```

---

## ✨ Features

- 📁 **Zero-Configuration Auto-Discovery**: Automatically finds and loads all `.pst` and `.ost` files in the folder the tool is placed in.
- ⚡ **Instant Search**: Powered by SQLite3 with **FTS5 (Full-Text Search)** for sub-millisecond keyword, sender, and phrase queries across thousands of emails.
- 📖 **Left/Right Reading Split**: Single-click any email on the left list to immediately read the full body, headers, and attachments on the right side.
- ✉️ **One-Click Outlook / Mail Client Launch**: Double-click any email to generate a temporary message behind the scenes and open it directly in **Microsoft Outlook** (Windows) or **Thunderbird** (Linux).
- 📎 **Attachment Management**: View and save attachments directly from within the app.
- 💾 **Export On Demand**: Save any message permanently as a standard `.eml` file with a single click.

---

## 🖥️ Platform Support & Quick Start

### 🪟 Windows Quick Start

#### Option A: Running from Python
1. Double-click **`run_windows.bat`** (or run `python main.py`).

#### Option B: Building Single Standalone `FastPST.exe`
1. Double-click **`build_exe.bat`** (or run `python build_exe.py`).
2. Your standalone executable will be created at:
   ```text
   dist\FastPST.exe
   ```
3. Copy **`FastPST.exe`** into any folder with `.pst` or `.ost` files.
4. **Double-click `FastPST.exe`** — it runs with a clean GUI window (no command prompt), auto-indexes emails in that folder, and lets you search and open emails in Outlook immediately.

---

### 🐧 Linux Quick Start

#### Option A: Running from Python
1. Run the launcher script:
   ```bash
   ./run_linux.sh
   ```

#### Option B: Building Standalone Linux Binary
1. Build the standalone binary:
   ```bash
   ./build_linux.sh
   ```
2. Your standalone binary will be created at:
   ```text
   dist/FastPST
   ```
3. Copy **`dist/FastPST`** into any folder containing `.pst` or `.ost` files and run:
   ```bash
   ./FastPST
   ```

---

## 🧪 Running Automated Tests

Run the full automated unit test suite:

```bash
python -m unittest discover -s tests -p "test_*.py" -v
```

---

## 📄 License
MIT License
