# Phillap

Phillap 0.0.4 is a local-first personal life assistant for Windows. Its start dashboard links to separate Thoughts, Dreams, To-dos, Money, Plans & projects, Journal, Files, Assistant, and Computer areas. You can also create custom spaces such as Baby, Health, Home, or Relationships. Entries are stored on this PC in SQLite; the local model does not automatically receive those personal entries.

## Start Phillap

Requirements: Windows, Python 3.10+, Git for Windows, GitHub CLI (optional), and Ollama.

1. Download a small local model once with `ollama pull qwen2.5:3b`.
2. Sign in with `gh auth login` if you want GitHub features.
3. Double-click `Start-Phillap.bat`. It installs the PDF reader when needed, starts Phillap, and opens the browser. Or run `python -m pip install -r requirements.txt` and `python app.py`, then open `http://127.0.0.1:8765`.

The web server listens on this PC only. Personal entries are stored in `%LOCALAPPDATA%\Phillap\phillap.sqlite3`; settings live in `%LOCALAPPDATA%\Phillap\settings.json`; uploaded files live in `%LOCALAPPDATA%\Phillap\files`. The database is not encrypted by Phillap and is not synced to any cloud. Phillap opens on a Today screen (overdue and due-today to-dos first, then top-priority goals) with a bottom navigation bar and quick add. Each launch saves one daily backup bundle (.zip with the database, settings and uploaded documents) in `%LOCALAPPDATA%\Phillap\backups` (the 7 most recent are kept; same-day backups are never overwritten). The Today screen has a local search over records, file names and document text (text-based files, DOCX, XLSX and PDF when pypdf is installed; nothing leaves this PC). Under More > Data protection you can back up now, export everything as JSON or any table as CSV, and restore a backup after explicit confirmation; a safety copy of your current data, settings and documents is saved first, and restore replaces them. Backups are local and unencrypted copies, so also copy them somewhere safe yourself. Protect your Windows login and do not store passwords, account numbers, or card details.

## Home dashboard and life areas

Home shows open to-dos, recent thoughts, the monthly money estimate, file upload, and shortcuts to each area. Open **Library** to search, categorize, download, and manage uploaded documents and saved assistant conversations together. Categories can be changed at any time; file-name and conversation-text search stays on this PC. Each built-in life area has its own accent color. Choose among Forest Temple, Moonlit Grove, Golden Canopy, Moss Sanctuary, and Quiet Stone background themes; the selection is saved in this browser on this PC. The illustrated forest-and-stone artwork is bundled locally and does not require an image service. Reading settings include selectable serif/sans fonts, larger type, and high contrast with reduced motion. Thoughts, Dreams, Journal, To-dos, and custom spaces have separate forms and saved lists. To-dos can have a due date and completion state.

### Money

Add income and bills as weekly, every two weeks, monthly, quarterly, yearly, or one-time items. Phillap converts recurring amounts to monthly estimates and displays listed income minus listed expenses. One-time items are excluded from that recurring total. You may label an item with a household member and category. This is manual tracking only: it does not connect to banks, account providers, or live balances, and it is not financial advice. The estimate may omit taxes, irregular expenses, savings, debt, or any item you have not entered.

### Big goals

Save high-, normal-, and later-priority goals. The Home screen keeps the highest-priority goals visible.

### Plans and projects

Create a project, then add or edit material quantities, unit prices, and quote sources, and track checklist steps. The fence starter uses adjustable dimensions and rough quantity assumptions to help begin planning; it is not a structural design, code review, or purchase-ready quote. Prices start at $0 until you enter a current quote. Estimates exclude tax, delivery, tools, waste, labor, and permit fees. Confirm measurements, product specifications, property boundaries, utility markings, and local rules before buying or building.

Custom spaces and household labels are local organization features, not separate user accounts or sharing permissions. Partner accounts, separate private profiles, encrypted app storage, shared sync, direct Google sign-in, and automatic Google Calendar integration are not implemented; do not treat this prototype as ready for multi-user or public use. The current shared PC app has no per-person access controls.

Each area displays at most 200 entries at once. SQLite has no configured total-entry quota; practical capacity depends on free disk space.

## Files and assistant

Choose or drag in PDF, Word (.docx), Excel (.xlsx), Markdown, text, CSV, and supported code/config files from Home or Files. Label each upload Critical or Non-critical. Non-critical files get a 10-day review date; Phillap never automatically deletes files. You can keep them indefinitely or remove them yourself. Select **Edit copy** to revise extracted text; Phillap saves a separate copy in its local file library and leaves the downloaded or synced original unchanged. Use **Download** on the edited copy to place it in a synced folder; this does not update Google Drive automatically. Editing PDF and Word documents creates a Markdown text copy; text and code files keep their original extension. Uploads are limited to 10 MB each, with no separate total-file quota beyond disk space. The assistant scans up to 300 files in each source folder and uses up to five matching excerpts per answer. PDF text extraction uses `pypdf`; scanned-image PDFs need OCR. Excel workbooks are read-only and searched by visible cell values, with worksheet/cell references in the extracted text; hidden sheets and rows are skipped. Formula cells with no saved result may not provide a current calculated value. The assistant sends matching excerpts and your question to the configured Ollama endpoint when you ask. It can also use web-page text that you explicitly paste, with the source URL included for citation; Phillap cannot read browser pages directly. It does not automatically send your personal life-area entries. Assistant conversations are saved locally and visible to anyone using this same Windows profile. Only select files and folders you are comfortable sharing with your local model.

## Web & AI browser shortcuts

The Web & AI area opens ChatGPT, Gemini, Claude, Google Docs, Google Voice, Google Search, or a website you enter in your normal browser. You can keep up to 50 local bookmarks. This preserves your browser sign-in; Phillap does not see credentials or page contents. Google Voice calls are made by you on its site. Search opens Google in your browser. To ask the local assistant about web research, paste selected text and its source URL into the Assistant. This is a browser launchpad, not an embedded browser or automatic web crawler. External AI sites have their own terms and may charge; Phillap does not send your files to them.

## Computer tools

The Computer area can open an exact file/application path after confirmation. It can download an explicitly provided public HTTPS link (maximum 50 MB, redirects blocked) into `Downloads\Phillap`. It can preview then copy up to 500 top-level files into categorized subfolders under `Phillap Organized`; it never moves or deletes originals. It does not run arbitrary shell commands or let the model operate Windows on its own.

## GitHub

The writable fork is `pearceaj23-create/pearceaj-create`, and `upstream` points to `jacobbaltins/pearceaj-create`. Issue and pull-request listing uses GitHub CLI. Creating issues requires write access; creating a pull request also requires a branch with commits pushed to the fork.

See [CHANGELOG.md](CHANGELOG.md) for recorded feature milestones.

## Download page

docs/index.html is a static download page (host it with GitHub Pages from the docs folder). Run package.ps1 to build dist\Phillap.zip, then attach it to a GitHub release named Phillap.zip; the page's button points at the latest release. No site is published and no release exists yet. Python 3.10+ is still required on the user's PC.
