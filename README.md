# Phillap

Phillap is a local-first personal life assistant for Windows. Its start dashboard links to separate Thoughts, Dreams, To-dos, Finances, Journal, Files, Assistant, and Computer areas. Entries are stored on this PC in SQLite; the local model does not automatically receive those personal entries. Section accents change with the selected life area.

## Start Phillap

Requirements: Windows, Python 3.10+, Git for Windows, GitHub CLI (optional), and Ollama.

1. Download a small local model once with `ollama pull qwen2.5:3b`.
2. Sign in with `gh auth login` if you want GitHub features.
3. Double-click `Start-Phillap.bat`. It installs the PDF reader when needed, starts Phillap, and opens the browser. Or run `python -m pip install -r requirements.txt` and `python app.py`, then open `http://127.0.0.1:8765`.

The web server listens on this PC only. Personal entries are stored in `%LOCALAPPDATA%\Phillap\phillap.sqlite3`; settings live in `%LOCALAPPDATA%\Phillap\settings.json`; uploaded files live in `%LOCALAPPDATA%\Phillap\files`. Data is not encrypted by Phillap and has no automatic cloud backup. Protect your Windows login, back up important data yourself, and do not store passwords, account numbers, or card details.

## Home dashboard and life areas

Home shows open to-dos, recent thoughts, file upload, and shortcuts to each area. Each life area has its own accent color. Choose among Forest Temple, Moonlit Grove, Golden Canopy, Moss Sanctuary, and Quiet Stone background themes; the selection is saved in this browser on this PC. The illustrated forest-and-stone artwork is bundled locally and does not require an image service. Thoughts, Dreams, Journal, To-dos, and Finances have separate forms and saved lists. To-dos can have a due date and completion state. Finance entries can contain an optional dollar amount; this is a basic private note tracker, not a bank connection or financial advice.

Each area displays at most 200 entries at once. SQLite has no configured total-entry quota; practical capacity depends on free disk space.

## Files and assistant

Choose or drag in PDF, Word (.docx), Markdown, text, CSV, and supported code/config files from Home or Files. Select **Edit copy** to revise extracted text; Phillap saves a separate copy in its local file library and leaves the downloaded or synced original unchanged. Use **Download** on the edited copy to place it in a synced folder; this does not update Google Drive automatically. Editing PDF and Word documents creates a Markdown text copy; text and code files keep their original extension. Uploads are limited to 10 MB each, with no separate total-file quota beyond disk space. The assistant scans up to 300 files in each source folder and uses up to five matching excerpts per answer. PDF text extraction uses `pypdf`; scanned-image PDFs need OCR. The assistant sends matching excerpts and your question to the configured Ollama endpoint when you ask. It does not automatically send your personal life-area entries. Only select files and folders you are comfortable sharing with your local model.

## Computer tools

The Computer area can open an exact file/application path after confirmation. It can download an explicitly provided public HTTPS link (maximum 50 MB, redirects blocked) into `Downloads\Phillap`. It can preview then copy up to 500 top-level files into categorized subfolders under `Phillap Organized`; it never moves or deletes originals. It does not run arbitrary shell commands or let the model operate Windows on its own.

## GitHub

The writable fork is `pearceaj23-create/pearceaj-create`, and `upstream` points to `jacobbaltins/pearceaj-create`. Issue and pull-request listing uses GitHub CLI. Creating issues requires write access; creating a pull request also requires a branch with commits pushed to the fork.
