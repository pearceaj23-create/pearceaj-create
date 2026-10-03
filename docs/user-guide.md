# Phillap user guide and troubleshooting

Phillap is a local-first personal organizer for Windows. It serves a web interface from your own PC and stores records in a local SQLite database.

## Getting started

Requirements: Windows. The standalone release bundles Python; Ollama is optional for the local assistant. Python 3.10 or later is needed only when running from source.

1. For the assistant, install Ollama and download a model, for example `ollama pull qwen2.5:3b`. Phillap checks the configured Ollama endpoint at startup and shows whether the selected model is available.
2. Optionally sign in to GitHub CLI with `gh auth login` for GitHub features.
3. For a standalone release, double-click `Phillap.exe`; it starts the local server and opens the browser. From source, double-click `Start-Phillap.bat` or run `python -m pip install -r requirements.txt` followed by `python app.py`.
4. If the browser does not open automatically, visit `http://127.0.0.1:8765`. To upgrade a standalone installation, close Phillap and replace `Phillap.exe` with the copy from the latest release ZIP. The database and settings remain in `%LOCALAPPDATA%\Phillap`.

Keep the app process running while you use Phillap. The web server listens on this PC only; closing the process stops it.

## Data and privacy

**Check for updates** in Reading & appearance contacts GitHub only when you click it and retrieves public release metadata. It sends no Phillap records or files and never downloads or installs an update automatically. To update a standalone installation, close Phillap, download and extract the release ZIP, then replace `Phillap.exe`; your local database, settings, and documents remain under `%LOCALAPPDATA%\Phillap`.

Data is stored under `%LOCALAPPDATA%\Phillap`: `phillap.sqlite3` (database), `settings.json`, `files` (uploads and edited copies), and `backups` (backup bundles). The database and automatic backups are unencrypted by default; optional manual encrypted backups are available. Phillap does not sync them to the cloud. An optional PIN lock on Data protection gates the local API after you lock the app or restart it; it stores a salted PBKDF2 hash, not the PIN. The lock is a casual-access deterrent, not encryption or protection from someone who can inspect the running app or access your Windows account. People using the same Windows profile can see entries, uploaded files, and assistant conversations while the app is unlocked. Protect your Windows sign-in and avoid storing passwords, account numbers, or card details.

## Main areas

- **Today and Home:** Today shows overdue and due-today to-dos, tasks completed today, a month calendar for dated tasks, priority goals, and quick add. You can turn a pasted note into a reviewed list of task titles; nothing saves until you choose which titles to keep, and the note is processed locally without an AI model. You can request a daily summary using open tasks, completed tasks, and goals; this data is sent to the configured Ollama model only after you click **Generate today's summary**. **What’s next?** offers a single-task focus using priority and due-date order; snoozed tasks are excluded. Home has shortcuts, open to-dos, recent thoughts, a monthly money estimate, and file upload. Each area shows at most 200 entries.
- **To-dos and goals:** Add a task with optional due date, time, priority, comma-separated tags, and a daily, weekly, or monthly repeat schedule; recurring tasks require a due date and add their next occurrence when completed. Monthly dates that do not exist in the next month are clamped to that month’s last day. Today orders tasks by priority, then schedule until you set a custom order. **Plan my day** opens the task list, where your manual order also guides Today’s focus. Use tags to keep related tasks recognizable. Use **Snooze 1 hour** or **Snooze 1 day** on an overdue or due-today task to hide it temporarily from Today; unsnooze it from the Snoozed section. Snoozed tasks return to their due-date group when the timer expires. Expand a task’s **Subtasks** section to track its smaller steps; those steps remain with the task if it is moved to the recycle bin and restored. On Today, press **/** to focus search, **N** to open quick add, or **Esc** to close overlays (shortcuts pause while typing in a field). Optional browser notifications can be enabled from Today; the app must stay open, and permission is requested only when you choose Enable browser reminders. Goals support high, normal, or later priority. From the Goals page, **Suggest next steps** sends that goal and Today/goals context to the configured local Ollama model only when clicked; suggestions are text and do not create tasks automatically. In the To-dos list, drag the grip beside a task to set a custom order (or focus the grip and press the up/down arrow keys); before you reorder, tasks use the default completion, priority, and due-date order. On touch screens, swipe a task to the right to complete it.
  The **Weekly review** summarizes completed tasks this Monday-to-Sunday week, remaining overdue tasks, and tasks due before next Monday; it also offers a brief reflection prompt. Deleted notes and tasks move to **More > Recycle bin**, where you can restore them or explicitly delete them permanently.
- **Money:** Add income and bills as weekly, every two weeks, monthly, quarterly, yearly, or one-time items. Monthly bills with a due day appear on Today during the seven days before they are due; this is a reminder, not a payment tracker. Phillap estimates monthly listed income minus recurring listed expenses; one-time items are excluded. Monthly category budgets compare planned limits with recurring expenses you entered; one-time expenses do not count toward monthly totals. **Savings goals** track a target, optional date, and contributions that you record; progress is based only on those entries. **Net-worth snapshot** subtracts manually entered liabilities from manually entered assets; it is not a live valuation or connected account balance. **Debt payoff estimates** project a balance using a fixed entered annual rate and monthly payment, with an optional extra amount; if payment does not cover estimated interest, the app says no payoff estimate is available. These are calculations only, not a recommended plan or lender quote. You can also record manual transactions, review a calendar-year summary with category and month charts, and export the report as CSV. In the Data protection area, import a bank CSV with date, description/title, signed amount, and optional category columns; negative amounts are treated as expenses and positive amounts as income unless a direction column is supplied. This is manual tracking, not bank integration, live balances, or financial advice. The summary can omit taxes, irregular expenses, savings, debt, or unentered items.
- **Plans & projects:** Create projects with materials, quantities, unit prices, quote sources, and checklists. Add optional due dates to checklist steps to see a simple project timeline, or append reviewed starter steps for moving, event planning, or a home project. The fence starter uses rough assumptions and is not a structural design, code review, or purchase-ready quote. Verify measurements, specifications, boundaries, utility markings, and local rules before buying or building.
- **Health log:** Add dated personal notes for your own reference. These are not diagnoses or medical advice and are not sent to the assistant automatically.
- **Contacts & birthdays:** Save a contact name, birthday, and optional note locally. Dates are reminders only; Phillap does not send notifications to contacts.
- **Packing lists:** Group items into named lists and mark each item packed or unpacked.
- **Home maintenance:** Keep dated local reminders, notes, and optional yearly repeat labels. These are not service instructions; check product guidance or a qualified provider when appropriate.
- **Shopping wishlist:** Save items and notes, then mark them purchased if you choose. Phillap does not place orders.
- **Reading list:** Save book/article titles, notes, and a simple unread/reading/finished status.
- **Habits:** Add a small routine and check it off for today. The count reflects completed check-ins in the last seven days. This is a private self-organization log, not a health assessment or medical recommendation.
- **Food & Pantry:** Plan breakfasts, lunches, dinners, and snacks for two across a selected 14-day window. Each meal can record ingredients, preparation notes, and whether it uses leftovers. Keep a grocery checklist, save recipe notes, and track pantry quantities and optional use-by dates. This does not create purchases, verify product ingredients, or establish food safety; review package labels and dates yourself. Meal notes are not nutrition or medical advice.
- **Files and Library:** Upload individual files or import a folder of PDF, images (PNG, JPEG, GIF, WebP), Word (`.docx`), Excel (`.xlsx`), Markdown, text, CSV, and supported code/config files, up to 10 MB each. Identical file contents are flagged to avoid accidental duplicates. Mark files Critical or Non-critical, assign a category, and add comma-separated tags for Library search. Select multiple files to change their category together. Set optional document expiry dates to see an alert for items due within 30 days. Preview PDFs and images in the app, rename uploaded files, and see total library storage. Non-critical files receive a 10-day review date; Phillap never deletes them automatically. Library searches and organizes documents and saved assistant conversations. **Edit copy** saves extracted text as a separate local copy; it does not change the original. PDF and Word copies use Markdown; text and code retain their extension.
- **Assistant:** Searches selected folders (up to 300 files per folder) and uses up to five matching excerpts. When asked, Phillap sends those excerpts and your question to the configured Ollama endpoint. Open Today tasks and goals are excluded unless you check **Include my open Today tasks and goals as context for this question**; that opt-in applies only to the current message and sends a bounded list to the local Ollama endpoint. You can paste web text and a source URL; Phillap cannot read browser pages directly. Conversations are local to this Windows profile.
- **Web & AI:** Opens websites in your normal browser and stores up to 50 local bookmarks. Phillap does not read browser credentials or page contents. External AI sites have their own terms and may charge.
- **Computer:** Can open a specific path after confirmation, download a supplied public HTTPS link, or preview and copy files to categorized folders. It does not move or delete originals, run arbitrary shell commands, or let the model operate Windows on its own.
- **Appearance:** Reading settings include dark background themes or a light paper theme, serif/sans-serif fonts, larger type, and high contrast with reduced motion. These preferences are saved in this browser on this PC. The first-run welcome tour explains local storage, the assistant, and navigation; replay it from **Reading & appearance**. Open **Reading & appearance > Customize bottom navigation** to reorder visible destinations or hide them; hidden destinations remain available from **More**. On Today, **Customize Today widgets** lets you hide sections and move them up or down; those preferences stay in this browser.

## Search and supported documents

Search is local and can cover records, file names, and document text; uploaded-document text is indexed incrementally in the local database for larger libraries, and changed or removed files update the index. Matching text is highlighted in results. Filter results by area, record type, or creation/upload date. Opening an entry result takes you to that specific record. Recent searches are retained in this browser, and you can save up to 20 frequently used queries locally. PDF extraction requires `pypdf`; scanned-image PDFs need OCR. Excel workbooks are read-only and searched by visible cell values and formula expressions. Hidden sheets and rows are skipped, and formula cells without a saved result may not show current values.

## Backups, export, and restore

Phillap saves an unencrypted daily backup at launch and keeps the seven most recent daily bundles. A same-day backup is not overwritten. Optional weekly backups are also unencrypted. You can create a separate manual encrypted backup using AES-GCM with a passphrase of at least 12 characters; the passphrase is never saved, and you must enter it to verify or restore the bundle. If the passphrase is lost, that encrypted backup cannot be recovered. Keep the passphrase separately from the file. In **More > Data protection**, you can back up now, export everything as JSON or a table as CSV, and restore a bundle. Restore replaces current data, settings, and documents after confirmation; a safety copy is saved first. This page also offers a 6–12 digit local app PIN and **Lock Phillap**. The PIN is stored as a salted PBKDF2 hash, not as the original digits; Phillap starts locked after restart. The lock is only a casual-access deterrent, does not encrypt your data, and is not recoverable if forgotten.

The local API limits write requests to 300 per minute per client address and returns HTTP 429 with a retry delay when exceeded. Responses include a Content Security Policy and standard framing, MIME-sniffing, referrer, and permissions headers; the policy permits the inline script and styles used by the single-page interface. The Data protection page shows backup sizes, previews archive files and database row counts before restore, verifies bundles, opens the backup folder, and lets you choose a local backup folder. It warns when no daily backup is newer than two days. Weekly backups are optional; when enabled, Phillap creates one per ISO week and keeps the four most recent. Use **Check database integrity** to run SQLite integrity validation. Schema updates are versioned and applied transactionally. Unexpected server failures are logged to `%LOCALAPPDATA%\Phillap\ava-errors.log`; the log records the route and exception type, not query strings or submitted content.

CSV imports append supported To-do or Money records and validate the entire file before writing. JSON import accepts an export from the same app/database schema and replaces database records only after confirmation; it first saves a safety backup. JSON import does not replace settings or uploaded files. Both imports are local, capped at 15 MB, and reject invalid input without partially applying records.

## Troubleshooting

### Phillap does not start

Confirm Python 3.10 or later is installed. From the Phillap folder, run `python -m pip install -r requirements.txt`, then `python app.py`. Keep the terminal open and check its error output.

### The page does not load

Check that the server is still running and visit `http://127.0.0.1:8765` on the same PC. If another program occupies port 8765, resolve that conflict locally; do not expose Phillap to a network as a workaround.

### A PDF has no searchable text

Only text-based PDFs can be extracted. Scanned pages are images and require OCR. Confirm `pypdf` is installed from the requirements.

### Excel search misses a value

Only visible cell values are indexed. Hidden sheets/rows are skipped, and formulas without saved results may be blank. Recalculate and save the workbook in a spreadsheet app, then upload the updated copy if appropriate.

### The assistant is unavailable

Ollama must be installed, running, and have a model downloaded. For example, run `ollama pull qwen2.5:3b`, ensure Ollama is running, and retry. Do not paste information into an external AI service unless you intend to send it there.

### A file is missing from Library or search

Check Files and `%LOCALAPPDATA%\Phillap\files`. Confirm the format is supported and the upload is within 10 MB. Folder search scans up to 300 files and only extracts supported content.

### I forgot my app PIN

The PIN only deters casual access and cannot be recovered. Close Phillap, open `%LOCALAPPDATA%\Phillap\settings.json` in a text editor, delete the `"app_lock"` entry (keep the JSON valid), save, and start Phillap again. The lock will be off and you can set a new PIN under Data protection. Your data is not changed.

### Restore replaced data unexpectedly

Restore replaces current data. Phillap creates a safety copy first; stop making further changes and restore the appropriate safety copy from **More > Data protection** if necessary.

## Important limitations

Phillap is a personal local app, not a multi-user service. It does not provide partner accounts, private profiles, sharing permissions, encrypted app storage or backups, shared sync, or automatic Google Calendar integration. The optional PIN lock only deters casual local access; it is not a substitute for Windows account security or encryption. Do not publish it online or use it for multiple people until real invited-user authentication, access controls, and protected storage are implemented and reviewed. Money estimates are not financial advice, project estimates are not construction guidance, and health organization is not medical advice.
