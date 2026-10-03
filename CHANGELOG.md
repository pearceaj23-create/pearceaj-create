# Phillap changelog

Notable product milestones are recorded here. Patch-sized fixes may remain in Git history; a new version entry is added for meaningful feature releases.

## Unreleased

- Quiet hours for browser reminders can now be changed on Today (default 22:00-07:00).
- Assistant page has a model picker and a Check again button.
- CI builds Phillap.zip and keeps it as a 14-day artifact.

## 0.1.2

- Browser reminders stay quiet between 22:00 and 07:00.
- Calendar now shows monthly bills on their due dates.
- Added a Print money summary button on the Money page.
- Documented forgotten-PIN recovery (with a test) and refreshed launch troubleshooting and the download page note.

## 0.1.1

- Added a Today backup reminder when the newest backup is over 7 days old or missing.
- Added a print button and print stylesheet for the weekly review.
- Added a ? keyboard shortcut help dialog.
- Added Dependabot for GitHub Actions and pip.

## 0.1.0

- Added an optional local app PIN lock using a salted PBKDF2 hash; it gates the local API but is not encryption or multi-user access control.
- Added separate manual AES-GCM encrypted backups; encryption passphrases are never stored, and automatic backups remain unencrypted.
- Added the first-run welcome tour, Today-widget ordering/visibility, a light paper theme, and reduced-motion-aware pressed-button feedback.
- Added upcoming monthly bill due dates to Today and a manual GitHub release check with a documented executable replacement path.
- Added a PyInstaller single-file Windows build that packages Python, dependencies, and local UI assets; source and release ZIP workflows remain documented.
- Expanded the local Food & Pantry, project, life-area, document-library, Assistant, task, search, and finance tools; see the user guide for scope and limitations.

## 0.0.4

- Today screen opens first (overdue, due today, priority goals, quick add) with a fixed bottom navigation bar and a More menu.
- Automatic daily local backup (7 kept), JSON/CSV export, and confirmed restore with a pre-restore backup (Data protection).
- Backups are .zip bundles including settings and uploaded documents; restore saves a safety copy first. Local search covers records, file names and document contents.
- A floating "+ Add" button on every screen opens a quick task/reminder sheet (a date makes it a reminder).
- Automatic backups are unencrypted; optional manual encrypted backups are now documented in Unreleased. Cloud sync and time-of-day reminders are not included.

## 0.0.2 — 2026-10-02

First recorded feature milestone after the initial local Phillap build.

- Added manual recurring income and bill tracking with normalized monthly totals; one-time entries stay out of recurring totals.
- Added editable project plans with rough fence material quantities, source-backed prices, estimates, and checklists.
- Added custom life spaces and priority-sorted big goals for organizing personal plans.
- Improved the home screen with shortcuts, monthly summary, and clearer local-privacy explanations.
- Added a web launchpad with editable local bookmarks for common AI/Google sites, explicit paste-in web excerpts for local Q&A, saved local Q&A history, adjustable fonts/text size/high contrast, and read-aloud answers.
- Added Critical/Non-critical upload labels; non-critical files receive a 10-day review date but are never deleted automatically.
- Kept records local; no bank linking, shared user accounts, embedded browser, direct Google sign-in, live store prices, or cloud AI are claimed by this release.

## 0.0.3 — 2026-10-02

- Added a searchable Library for uploaded documents/PDFs and saved assistant conversations, with editable categories and saved-chat open/remove actions.
- Added basic read-only Excel (.xlsx) ingestion with sheet/cell references; hidden sheets and rows are excluded by default.
- Added suggested categories at upload and a visible review window for non-critical file retention (files are never deleted automatically).


