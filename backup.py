"""Local backup, export and restore helpers for Phillap.

A backup is a single .zip bundle holding a consistent snapshot of the SQLite
database, settings.json and the uploaded documents. Every function takes
explicit paths so it can be exercised against temporary folders. Bundles stay
on this PC; they are not encrypted and not synced anywhere.
"""
from __future__ import annotations

import csv
from contextlib import contextmanager
import io
import hashlib
import json
import math
import os
import re
import shutil
import sqlite3
import tempfile
import zipfile
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

KEEP_DAILY = 7
KEEP_WEEKLY = 4
KEEP_PRE_RESTORE = 5
MAX_BUNDLE_BYTES = 4 * 1024 * 1024 * 1024
DAILY_RE = re.compile(r"phillap-backup-(\d{8})\.zip")
WEEKLY_RE = re.compile(r"phillap-weekly-backup-(\d{6})\.zip")
PRE_RE = re.compile(r"pre-restore-(\d{8}-\d{6})(?:-\d+)?\.zip")
ENCRYPTED_RE = re.compile(r"phillap-encrypted-backup-(\d{8}-\d{6})(?:-\d+)?\.enc")
ENCRYPTED_MAGIC = b"PHILLAPENC1"
ENCRYPTED_KDF_ITERATIONS = 600_000
DB_ENTRY = "phillap.sqlite3"
SETTINGS_ENTRY = "settings.json"
FILE_PREFIX = "files/"
FILE_NAME_RE = re.compile(r"[a-f0-9]{32}__[^/\\:\x00]+")
REQUIRED_TABLES = {"entries"}


def _connect_ro(path: Path) -> sqlite3.Connection:
    return sqlite3.connect(f"{Path(path).resolve().as_uri()}?mode=ro", uri=True)


def _snapshot_db(src: Path, dest: Path) -> None:
    source = sqlite3.connect(src)
    target = sqlite3.connect(dest)
    try:
        source.backup(target)
    finally:
        target.close()
        source.close()


def _write_bundle(dest: Path, db_path: Path, settings_path: Path | None, files_dir: Path | None) -> None:
    """Write a bundle atomically (temp file then replace)."""
    tmp = dest.with_name(dest.name + ".tmp")
    tmp.unlink(missing_ok=True)
    with tempfile.TemporaryDirectory(dir=dest.parent) as work:
        snap = Path(work) / DB_ENTRY
        _snapshot_db(db_path, snap)
        with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.write(snap, DB_ENTRY)
            if settings_path and Path(settings_path).is_file():
                zf.write(settings_path, SETTINGS_ENTRY)
            if files_dir and Path(files_dir).is_dir():
                for f in sorted(Path(files_dir).iterdir()):
                    if f.is_file() and not f.is_symlink() and FILE_NAME_RE.fullmatch(f.name):
                        zf.write(f, FILE_PREFIX + f.name)
    os.replace(tmp, dest)


def _prune(backup_dir: Path, regex: re.Pattern, keep: int) -> None:
    files = sorted((p for p in backup_dir.iterdir() if regex.fullmatch(p.name)), key=lambda p: p.name, reverse=True)
    for old in files[keep:]:
        old.unlink()


def create_daily_backup(db_path: Path, backup_dir: Path, now: datetime | None = None,
                        settings_path: Path | None = None, files_dir: Path | None = None) -> dict:
    """Create today's bundle if missing. An existing same-day bundle is never overwritten."""
    db_path, backup_dir = Path(db_path), Path(backup_dir)
    now = now or datetime.now()
    if not db_path.exists():
        return {"created": False, "reason": "no database yet"}
    backup_dir.mkdir(parents=True, exist_ok=True)
    name = f"phillap-backup-{now:%Y%m%d}.zip"
    dest = backup_dir / name
    if dest.exists():
        return {"created": False, "name": name, "reason": "already backed up today"}
    _write_bundle(dest, db_path, settings_path, files_dir)
    _prune(backup_dir, DAILY_RE, KEEP_DAILY)
    return {"created": True, "name": name}


def _derive_encryption_key(passphrase: str, salt: bytes) -> bytes:
    if not isinstance(passphrase, str) or len(passphrase) < 12:
        raise ValueError("Use a backup passphrase that is at least 12 characters long.")
    try:
        password = passphrase.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise ValueError("The backup passphrase contains invalid text.") from exc
    if len(password) > 1024:
        raise ValueError("Backup passphrases are limited to 1024 UTF-8 bytes.")
    return hashlib.pbkdf2_hmac("sha256", password, salt, ENCRYPTED_KDF_ITERATIONS, dklen=32)


def create_encrypted_backup(db_path: Path, backup_dir: Path, passphrase: str,
                            now: datetime | None = None, settings_path: Path | None = None,
                            files_dir: Path | None = None) -> dict:
    """Create an optional manual AES-GCM backup without storing its passphrase."""
    db_path, backup_dir = Path(db_path), Path(backup_dir)
    if not db_path.is_file():
        raise ValueError("There is no database to back up yet.")
    backup_dir.mkdir(parents=True, exist_ok=True)
    now = now or datetime.now()
    stem = f"phillap-encrypted-backup-{now:%Y%m%d-%H%M%S}"
    name, suffix = f"{stem}.enc", 0
    while (backup_dir / name).exists():
        suffix += 1
        name = f"{stem}-{suffix}.enc"
    dest = backup_dir / name
    tmp = dest.with_name(dest.name + ".tmp")
    salt, nonce = os.urandom(16), os.urandom(12)
    header = ENCRYPTED_MAGIC + salt + nonce
    key = _derive_encryption_key(passphrase, salt)
    encryptor = Cipher(algorithms.AES(key), modes.GCM(nonce)).encryptor()
    encryptor.authenticate_additional_data(header)
    try:
        with tempfile.TemporaryDirectory(dir=backup_dir) as work:
            archive = Path(work) / "backup.zip"
            _write_bundle(archive, db_path, settings_path, files_dir)
            if archive.stat().st_size > MAX_BUNDLE_BYTES:
                raise ValueError("The backup is too large to encrypt.")
            with archive.open("rb") as source, tmp.open("wb") as output:
                output.write(header)
                while chunk := source.read(1024 * 1024):
                    output.write(encryptor.update(chunk))
                output.write(encryptor.finalize())
                output.write(encryptor.tag)
        os.replace(tmp, dest)
    except Exception:
        tmp.unlink(missing_ok=True)
        raise
    return {"created": True, "name": name, "encrypted": True}


@contextmanager
def _plain_backup(path: Path, passphrase: str | None):
    path = Path(path)
    if not ENCRYPTED_RE.fullmatch(path.name):
        yield path
        return
    if not isinstance(passphrase, str) or len(passphrase) < 12:
        raise ValueError("Enter the passphrase for this encrypted backup.")
    size = path.stat().st_size
    header_size = len(ENCRYPTED_MAGIC) + 16 + 12
    if size < header_size + 16 or size > MAX_BUNDLE_BYTES + header_size + 16:
        raise _bad()
    temp = tempfile.TemporaryDirectory()
    plain = Path(temp.name) / "backup.zip"
    try:
        with path.open("rb") as source:
            header = source.read(header_size)
            if len(header) != header_size or not header.startswith(ENCRYPTED_MAGIC):
                raise _bad()
            salt_start = len(ENCRYPTED_MAGIC)
            salt = header[salt_start:salt_start + 16]
            nonce = header[salt_start + 16:]
            source.seek(-16, os.SEEK_END)
            tag = source.read(16)
            ciphertext_size = size - header_size - 16
            source.seek(header_size)
            key = _derive_encryption_key(passphrase, salt)
            decryptor = Cipher(algorithms.AES(key), modes.GCM(nonce, tag)).decryptor()
            decryptor.authenticate_additional_data(header)
            with plain.open("wb") as output:
                remaining = ciphertext_size
                while remaining:
                    chunk = source.read(min(1024 * 1024, remaining))
                    if not chunk:
                        raise _bad()
                    remaining -= len(chunk)
                    output.write(decryptor.update(chunk))
                output.write(decryptor.finalize())
        yield plain
    except InvalidTag as exc:
        raise ValueError("The passphrase is incorrect or the encrypted backup is damaged.") from exc
    finally:
        temp.cleanup()


def create_weekly_backup(db_path: Path, backup_dir: Path, now: datetime | None = None,
                         settings_path: Path | None = None, files_dir: Path | None = None) -> dict:
    """Create one weekly snapshot if this ISO week has not been backed up."""
    db_path, backup_dir = Path(db_path), Path(backup_dir)
    if not db_path.exists():
        return {"created": False, "reason": "no database yet"}
    backup_dir.mkdir(parents=True, exist_ok=True)
    iso = (now or datetime.now()).isocalendar()
    name = f"phillap-weekly-backup-{iso.year}{iso.week:02d}.zip"
    dest = backup_dir / name
    if dest.exists():
        return {"created": False, "name": name, "reason": "already backed up this week"}
    _write_bundle(dest, db_path, settings_path, files_dir)
    _prune(backup_dir, WEEKLY_RE, KEEP_WEEKLY)
    return {"created": True, "name": name}


def create_pre_restore_backup(db_path: Path, backup_dir: Path, now: datetime | None = None,
                              settings_path: Path | None = None, files_dir: Path | None = None) -> str | None:
    db_path, backup_dir = Path(db_path), Path(backup_dir)
    if not db_path.exists():
        return None
    backup_dir.mkdir(parents=True, exist_ok=True)
    now = now or datetime.now()
    stem, n = f"pre-restore-{now:%Y%m%d-%H%M%S}", 0
    while True:
        name = f"{stem}.zip" if n == 0 else f"{stem}-{n}.zip"
        dest = backup_dir / name
        if not dest.exists():
            break
        n += 1
    _write_bundle(dest, db_path, settings_path, files_dir)
    _prune(backup_dir, PRE_RE, KEEP_PRE_RESTORE)
    return name


def list_backups(backup_dir: Path) -> list[dict]:
    backup_dir = Path(backup_dir)
    if not backup_dir.is_dir():
        return []
    items = []
    for p in backup_dir.iterdir():
        kind = "daily" if DAILY_RE.fullmatch(p.name) else "weekly" if WEEKLY_RE.fullmatch(p.name) else "pre-restore" if PRE_RE.fullmatch(p.name) else "encrypted" if ENCRYPTED_RE.fullmatch(p.name) else None
        if kind and p.is_file():
            st = p.stat()
            items.append({"name": p.name, "kind": kind, "size": st.st_size,
                          "modified": datetime.fromtimestamp(st.st_mtime).isoformat(timespec="seconds")})
    return sorted(items, key=lambda i: i["name"], reverse=True)


def resolve_backup(backup_dir: Path, name: str) -> Path:
    """Map a bare backup file name to a path, rejecting anything else."""
    if not isinstance(name, str) or not (DAILY_RE.fullmatch(name) or WEEKLY_RE.fullmatch(name) or PRE_RE.fullmatch(name) or ENCRYPTED_RE.fullmatch(name)):
        raise ValueError("Choose a backup from the list.")
    root = Path(backup_dir).resolve()
    path = (root / name).resolve()
    if path.parent != root or not path.is_file():
        raise ValueError("That backup was not found.")
    return path


def _bad() -> ValueError:
    return ValueError("That backup is not a valid Phillap backup.")


def _check_members(zf: zipfile.ZipFile) -> list[zipfile.ZipInfo]:
    infos = zf.infolist()
    names = [i.filename for i in infos]
    if len(set(names)) != len(names) or DB_ENTRY not in names:
        raise _bad()
    total = 0
    for i in infos:
        n = i.filename
        ok = n in (DB_ENTRY, SETTINGS_ENTRY) or (n.startswith(FILE_PREFIX) and FILE_NAME_RE.fullmatch(n[len(FILE_PREFIX):]))
        if not ok or i.is_dir():
            raise _bad()
        total += i.file_size
    if total > MAX_BUNDLE_BYTES:
        raise _bad()
    return infos


def _extract(zf: zipfile.ZipFile, name: str, dest: Path) -> None:
    with zf.open(name) as src, open(dest, "wb") as out:
        shutil.copyfileobj(src, out)


def validate_db(path: Path) -> None:
    try:
        conn = _connect_ro(path)
        try:
            if conn.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise ValueError("That backup failed its integrity check.")
            tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        finally:
            conn.close()
    except sqlite3.DatabaseError as exc:
        raise _bad() from exc
    if not REQUIRED_TABLES <= tables:
        raise _bad()


def validate_backup(path: Path, passphrase: str | None = None) -> None:
    try:
        with _plain_backup(path, passphrase) as plain:
            with zipfile.ZipFile(plain) as zf:
                _check_members(zf)
                if zf.testzip() is not None:
                    raise _bad()
                with tempfile.TemporaryDirectory() as work:
                    _extract(zf, DB_ENTRY, Path(work) / DB_ENTRY)
                    validate_db(Path(work) / DB_ENTRY)
    except zipfile.BadZipFile as exc:
        raise _bad() from exc


def inspect_backup(path: Path, passphrase: str | None = None) -> dict:
    """Validate a bundle and summarize its files and database row counts."""
    path = Path(path)
    validate_backup(path, passphrase)
    with _plain_backup(path, passphrase) as plain:
        with zipfile.ZipFile(plain) as zf:
            contents = [
                {"name": info.filename, "size_bytes": info.file_size}
                for info in zf.infolist()
            ]
            with tempfile.TemporaryDirectory() as work:
                db_copy = Path(work) / DB_ENTRY
                _extract(zf, DB_ENTRY, db_copy)
                conn = _connect_ro(db_copy)
                try:
                    row_counts = []
                    for table in _tables(conn):
                        quoted_table = table.replace('"', '""')
                        count = conn.execute(f'SELECT COUNT(*) FROM "{quoted_table}"').fetchone()[0]
                        row_counts.append({"name": table, "rows": count})
                finally:
                    conn.close()
    return {"name": path.name, "size_bytes": path.stat().st_size, "contents": contents, "tables": row_counts, "encrypted": bool(ENCRYPTED_RE.fullmatch(path.name))}


def restore_backup(db_path: Path, backup_dir: Path, name: str, confirm: bool, now: datetime | None = None,
                   settings_path: Path | None = None, files_dir: Path | None = None,
                   passphrase: str | None = None) -> dict:
    """Restore a named bundle over the live data after saving a pre-restore bundle.

    Requires confirm=True. The pre-restore bundle holds the current database,
    settings and documents so the restore can be undone.
    """
    if confirm is not True:
        raise ValueError("Restoring replaces your current data. Please confirm to continue.")
    db_path, backup_dir = Path(db_path), Path(backup_dir)
    source = resolve_backup(backup_dir, name)
    validate_backup(source, passphrase)
    pre = create_pre_restore_backup(db_path, backup_dir, now, settings_path, files_dir)
    with _plain_backup(source, passphrase) as plain, zipfile.ZipFile(plain) as zf, tempfile.TemporaryDirectory() as work:
        work = Path(work)
        _extract(zf, DB_ENTRY, work / DB_ENTRY)
        members = {i.filename for i in zf.infolist()}
        if files_dir is not None:
            files_dir = Path(files_dir)
            files_dir.mkdir(parents=True, exist_ok=True)
            wanted = set()
            for m in sorted(members):
                if m.startswith(FILE_PREFIX):
                    fname = m[len(FILE_PREFIX):]
                    wanted.add(fname)
                    tmp = files_dir / (fname + ".restoring")
                    _extract(zf, m, tmp)
                    os.replace(tmp, files_dir / fname)
            for f in files_dir.iterdir():
                if f.is_file() and FILE_NAME_RE.fullmatch(f.name) and f.name not in wanted:
                    f.unlink()
        if settings_path is not None and SETTINGS_ENTRY in members:
            _extract(zf, SETTINGS_ENTRY, work / SETTINGS_ENTRY)
            shutil.copyfile(work / SETTINGS_ENTRY, settings_path)
        src = _connect_ro(work / DB_ENTRY)
        dest = sqlite3.connect(db_path)
        try:
            src.backup(dest)
        finally:
            dest.close()
            src.close()
    return {"restored": name, "pre_restore_backup": pre}


def _tables(conn: sqlite3.Connection) -> list[str]:
    return [r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' "
        "AND name != 'schema_version' AND name != 'file_search' "
        "AND name NOT LIKE 'file_search_%' AND name != 'document_search_state' ORDER BY name"
    )]


def export_json(db_path: Path) -> dict:
    conn = _connect_ro(Path(db_path))
    conn.row_factory = sqlite3.Row
    try:
        data = {t: [dict(r) for r in conn.execute(f'SELECT * FROM "{t}"')] for t in _tables(conn)}
    finally:
        conn.close()
    return {"app": "Phillap", "exported_at": datetime.now().isoformat(timespec="seconds"), "tables": data}


def import_json(db_path: Path, text: str, confirm: bool = False,
                backup_dir: Path | None = None, settings_path: Path | None = None,
                files_dir: Path | None = None) -> dict:
    """Replace database records from a matching JSON export after saving a safety bundle."""
    if confirm is not True:
        raise ValueError("Confirm that the JSON import should replace current database records.")
    if not isinstance(text, str):
        raise ValueError("Choose a valid JSON export file.")
    try:
        if len(text.encode("utf-8")) > 15_000_000:
            raise ValueError("JSON imports are limited to 15 MB.")
    except UnicodeError as exc:
        raise ValueError("The JSON file contains invalid text encoding.") from exc

    def unique_object(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("The JSON file contains duplicate object keys.")
            result[key] = value
        return result

    def reject_constant(value):
        raise ValueError(f"The JSON file contains an invalid number: {value}.")

    try:
        document = json.loads(text, object_pairs_hook=unique_object, parse_constant=reject_constant)
    except (UnicodeError, RecursionError) as exc:
        raise ValueError("The JSON file is invalid or too deeply nested.") from exc
    if not isinstance(document, dict) or document.get("app") not in {"Phillap", "AVA"}:
        raise ValueError("Choose a JSON export created by this app.")
    tables = document.get("tables")
    if not isinstance(tables, dict):
        raise ValueError("The JSON export does not contain database tables.")

    db_path = Path(db_path)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        current_tables = _tables(conn)
        if set(tables) != set(current_tables):
            raise ValueError("The JSON export has a different database schema. Update the app or use a matching export.")
        prepared = {}
        total_rows = 0
        for table in current_tables:
            rows = tables[table]
            if not isinstance(rows, list):
                raise ValueError(f"The JSON export has invalid rows for {table}.")
            columns = [row["name"] for row in conn.execute(f'PRAGMA table_info("{table}")')]
            prepared_rows = []
            for row in rows:
                total_rows += 1
                if total_rows > 100_000:
                    raise ValueError("JSON imports are limited to 100,000 records.")
                if not isinstance(row, dict) or set(row) != set(columns):
                    raise ValueError(f"The JSON export has invalid columns for {table}.")
                values = []
                for column in columns:
                    value = row[column]
                    if isinstance(value, bool) or not (
                        value is None or isinstance(value, (str, int, float))
                    ) or isinstance(value, float) and not math.isfinite(value):
                        raise ValueError(f"The JSON export contains an invalid value in {table}.{column}.")
                    values.append(value)
                prepared_rows.append(values)
            prepared[table] = (columns, prepared_rows)

        safety_copy = create_pre_restore_backup(
            db_path, Path(backup_dir) if backup_dir else db_path.parent / "backups",
            settings_path=settings_path, files_dir=files_dir,
        )
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("BEGIN IMMEDIATE")
        conn.execute("PRAGMA defer_foreign_keys=ON")
        for table in current_tables:
            conn.execute(f'DELETE FROM "{table}"')
        for table, (columns, rows) in prepared.items():
            if rows:
                names = ",".join(f'"{column}"' for column in columns)
                placeholders = ",".join("?" for _ in columns)
                conn.executemany(
                    f'INSERT INTO "{table}" ({names}) VALUES ({placeholders})', rows
                )
        if conn.execute("PRAGMA foreign_key_check").fetchone():
            raise ValueError("The JSON export contains records with invalid relationships.")
        conn.commit()
        return {
            "imported": total_rows,
            "tables": len(current_tables),
            "pre_import_backup": safety_copy,
        }
    except sqlite3.IntegrityError as exc:
        conn.rollback()
        raise ValueError("The JSON export violates database constraints.") from exc
    except (ValueError, sqlite3.Error):
        conn.rollback()
        raise
    finally:
        conn.close()


def _csv_cell(value):
    if isinstance(value, str) and value[:1] in ("=", "+", "-", "@", "\t", "\r"):
        return "'" + value
    return value


def export_csv(db_path: Path, table: str) -> str:
    conn = _connect_ro(Path(db_path))
    try:
        if table not in _tables(conn):
            raise ValueError("Unknown table.")
        cur = conn.execute(f'SELECT * FROM "{table}"')
        out = io.StringIO()
        writer = csv.writer(out, lineterminator="\r\n")
        writer.writerow([c[0] for c in cur.description])
        for row in cur:
            writer.writerow([_csv_cell(v) for v in row])
        return out.getvalue()
    finally:
        conn.close()


def _read_csv(text: str) -> tuple[list[str], list[dict[str, str]]]:
    if not isinstance(text, str) or len(text.encode("utf-8")) > 15_000_000:
        raise ValueError("CSV imports are limited to 15 MB.")
    reader = csv.DictReader(io.StringIO(text, newline=""))
    if not reader.fieldnames:
        raise ValueError("The CSV file must include a header row.")
    headers = [str(header or "").strip().casefold() for header in reader.fieldnames]
    if any(not header for header in headers) or len(set(headers)) != len(headers):
        raise ValueError("CSV headers must be non-empty and unique.")
    rows = []
    for row in reader:
        if len(rows) >= 10_000:
            raise ValueError("CSV imports are limited to 10,000 rows.")
        if None in row:
            raise ValueError("A CSV row has more values than the header.")
        rows.append({header: str(row[original] or "").strip() for header, original in zip(headers, reader.fieldnames)})
    return headers, rows


def import_csv(db_path: Path, kind: str, text: str) -> dict:
    """Append validated to-do, recurring-money, or transaction rows atomically."""
    headers, rows = _read_csv(text)
    conn = sqlite3.connect(db_path)
    try:
        if kind == "todos":
            if "title" not in headers:
                raise ValueError("To-do CSV needs a title column.")
            inserts = []
            for row in rows:
                if row.get("area", "todos").casefold() not in ("", "todos"):
                    continue
                title, content = row.get("title", ""), row.get("content", "")
                due_date = row.get("due_date", "") or row.get("due", "") or None
                due_time = row.get("due_time", "") or None
                if due_time and (not due_date or not re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", due_time)):
                    raise ValueError("To-do due times must use HH:MM and include a due date.")
                try:
                    priority = int(row.get("priority", "2") or "2")
                except ValueError as exc:
                    raise ValueError("To-do priority must be 1 (high), 2 (normal), or 3 (later).") from exc
                if priority not in {1, 2, 3}:
                    raise ValueError("To-do priority must be 1 (high), 2 (normal), or 3 (later).")
                tags = row.get("tags", "")
                tag_list = list(dict.fromkeys(tag.strip() for tag in tags.split(",") if tag.strip()))
                if len(tag_list) > 12 or any(len(tag) > 24 or not re.fullmatch(r"[\w -]+", tag) for tag in tag_list):
                    raise ValueError("Use up to 12 tags, each 24 characters or fewer, with letters, numbers, spaces, hyphens, or underscores.")
                if not title or len(title) > 160 or len(content) > 12_000:
                    raise ValueError("To-do titles and details must be within the app's limits.")
                if due_date:
                    try:
                        due_date = date.fromisoformat(due_date).isoformat()
                    except ValueError as exc:
                        raise ValueError("To-do due dates must use YYYY-MM-DD.") from exc
                inserts.append((title, content, due_date, due_time, priority, ",".join(tag_list)))
            if not inserts:
                raise ValueError("No to-do rows were found in the CSV.")
            conn.execute("BEGIN IMMEDIATE")
            conn.executemany(
                "INSERT INTO entries(area,title,content,due_date,due_time,priority,tags) VALUES('todos',?,?,?,?,?,?)",
                inserts,
            )
        elif kind == "money":
            if not {"direction", "title", "frequency"} <= set(headers) or not ({"amount_cents", "amount"} & set(headers)):
                raise ValueError("Money CSV needs direction, title, frequency, and amount or amount_cents columns.")
            inserts = []
            supported_frequencies = {"weekly", "biweekly", "monthly", "quarterly", "yearly", "once"}
            for row in rows:
                direction = row.get("direction", "").casefold()
                frequency = row.get("frequency", "").casefold()
                title = row.get("title", "")
                if direction not in {"income", "expense"} or frequency not in supported_frequencies:
                    raise ValueError("Money rows need income/expense and a supported frequency.")
                if not title or len(title) > 120:
                    raise ValueError("Money titles must be 1–120 characters.")
                try:
                    if row.get("amount_cents", ""):
                        cents = int(row["amount_cents"])
                    else:
                        raw_amount = row.get("amount", "").replace("$", "").replace(",", "")
                        decimal_amount = Decimal(raw_amount)
                        if not decimal_amount.is_finite():
                            raise InvalidOperation
                        cents = int((decimal_amount * 100).quantize(Decimal("1")))
                except (ValueError, InvalidOperation) as exc:
                    raise ValueError("Enter a valid money amount.") from exc
                if cents <= 0 or cents > 10_000_000_000:
                    raise ValueError("Money amounts must be greater than zero and below $100,000,000.")
                due_day = row.get("due_day", "") or None
                if due_day:
                    try:
                        due_day = int(due_day)
                    except ValueError as exc:
                        raise ValueError("Due day must be a day of the month from 1 to 31.") from exc
                    if not 1 <= due_day <= 31:
                        raise ValueError("Due day must be a day of the month from 1 to 31.")
                inserts.append((direction, title, row.get("category", ""), cents, frequency,
                                due_day, row.get("household_member", "Me") or "Me", row.get("note", "")))
            if not inserts:
                raise ValueError("No money rows were found in the CSV.")
            conn.execute("BEGIN IMMEDIATE")
            conn.executemany(
                "INSERT INTO finance_items(direction,title,category,amount_cents,frequency,due_day,household_member,note) VALUES(?,?,?,?,?,?,?,?)",
                inserts,
            )
        elif kind == "transactions":
            title_column = "description" if "description" in headers else "title"
            date_column = "date" if "date" in headers else "transaction_date"
            if title_column not in headers or date_column not in headers or not ({"amount", "amount_cents"} & set(headers)):
                raise ValueError("Transaction CSV needs date, description or title, and amount or amount_cents columns.")
            inserts = []
            for row in rows:
                title = row.get(title_column, "")
                if not title or len(title) > 120:
                    raise ValueError("Transaction descriptions must be 1–120 characters.")
                if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", row[date_column]):
                    raise ValueError("Transaction dates must use YYYY-MM-DD.")
                try:
                    transaction_date = date.fromisoformat(row[date_column]).isoformat()
                except ValueError as exc:
                    raise ValueError("Transaction dates must use YYYY-MM-DD.") from exc
                amount_key = "amount_cents" if row.get("amount_cents", "") else "amount"
                try:
                    if amount_key == "amount_cents":
                        raw_cents = int(row[amount_key])
                        direction_from_sign = "expense" if raw_cents < 0 else "income"
                        cents = abs(raw_cents)
                    else:
                        raw_amount = row[amount_key].replace("$", "").replace(",", "")
                        decimal_amount = Decimal(raw_amount)
                        if not decimal_amount.is_finite():
                            raise InvalidOperation
                        direction_from_sign = "expense" if decimal_amount < 0 else "income"
                        cents = int((abs(decimal_amount) * 100).quantize(Decimal("1")))
                except (ValueError, InvalidOperation) as exc:
                    raise ValueError("Enter a valid transaction amount.") from exc
                direction = row.get("direction", "").casefold() or direction_from_sign
                if direction not in {"income", "expense"} or cents <= 0 or cents > 10_000_000_000:
                    raise ValueError("Transactions need income/expense and a nonzero amount below $100,000,000.")
                category = row.get("category", "")
                if len(category) > 60:
                    raise ValueError("Transaction categories must be 60 characters or fewer.")
                inserts.append((direction, title, category, cents, transaction_date))
            if not inserts:
                raise ValueError("No transaction rows were found in the CSV.")
            conn.execute("BEGIN IMMEDIATE")
            conn.executemany(
                "INSERT INTO finance_transactions(direction,title,category,amount_cents,transaction_date) VALUES(?,?,?,?,?)",
                inserts,
            )
        else:
            raise ValueError("Choose To-dos, Money, or Transactions as the CSV import type.")
        conn.commit()
        return {"imported": len(inserts), "kind": kind}
    except (ValueError, sqlite3.Error):
        conn.rollback()
        raise
    finally:
        conn.close()


def export_tables(db_path: Path) -> list[str]:
    conn = _connect_ro(Path(db_path))
    try:
        return _tables(conn)
    finally:
        conn.close()