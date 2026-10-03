"""Local backup, export and restore helpers for Phillap.

A backup is a single .zip bundle holding a consistent snapshot of the SQLite
database, settings.json and the uploaded documents. Every function takes
explicit paths so it can be exercised against temporary folders. Bundles stay
on this PC; they are not encrypted and not synced anywhere.
"""
from __future__ import annotations

import csv
import io
import os
import re
import shutil
import sqlite3
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path

KEEP_DAILY = 7
KEEP_PRE_RESTORE = 5
MAX_BUNDLE_BYTES = 4 * 1024 * 1024 * 1024
DAILY_RE = re.compile(r"phillap-backup-(\d{8})\.zip")
PRE_RE = re.compile(r"pre-restore-(\d{8}-\d{6})(?:-\d+)?\.zip")
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
        kind = "daily" if DAILY_RE.fullmatch(p.name) else "pre-restore" if PRE_RE.fullmatch(p.name) else None
        if kind and p.is_file():
            st = p.stat()
            items.append({"name": p.name, "kind": kind, "size": st.st_size,
                          "modified": datetime.fromtimestamp(st.st_mtime).isoformat(timespec="seconds")})
    return sorted(items, key=lambda i: i["name"], reverse=True)


def resolve_backup(backup_dir: Path, name: str) -> Path:
    """Map a bare backup file name to a path, rejecting anything else."""
    if not isinstance(name, str) or not (DAILY_RE.fullmatch(name) or PRE_RE.fullmatch(name)):
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


def validate_backup(path: Path) -> None:
    try:
        with zipfile.ZipFile(path) as zf:
            _check_members(zf)
            if zf.testzip() is not None:
                raise _bad()
            with tempfile.TemporaryDirectory() as work:
                _extract(zf, DB_ENTRY, Path(work) / DB_ENTRY)
                validate_db(Path(work) / DB_ENTRY)
    except zipfile.BadZipFile as exc:
        raise _bad() from exc


def restore_backup(db_path: Path, backup_dir: Path, name: str, confirm: bool, now: datetime | None = None,
                   settings_path: Path | None = None, files_dir: Path | None = None) -> dict:
    """Restore a named bundle over the live data after saving a pre-restore bundle.

    Requires confirm=True. The pre-restore bundle holds the current database,
    settings and documents so the restore can be undone.
    """
    if confirm is not True:
        raise ValueError("Restoring replaces your current data. Please confirm to continue.")
    db_path, backup_dir = Path(db_path), Path(backup_dir)
    source = resolve_backup(backup_dir, name)
    validate_backup(source)
    pre = create_pre_restore_backup(db_path, backup_dir, now, settings_path, files_dir)
    with zipfile.ZipFile(source) as zf, tempfile.TemporaryDirectory() as work:
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
    return [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]


def export_json(db_path: Path) -> dict:
    conn = _connect_ro(Path(db_path))
    conn.row_factory = sqlite3.Row
    try:
        data = {t: [dict(r) for r in conn.execute(f'SELECT * FROM "{t}"')] for t in _tables(conn)}
    finally:
        conn.close()
    return {"app": "Phillap", "exported_at": datetime.now().isoformat(timespec="seconds"), "tables": data}


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


def export_tables(db_path: Path) -> list[str]:
    conn = _connect_ro(Path(db_path))
    try:
        return _tables(conn)
    finally:
        conn.close()