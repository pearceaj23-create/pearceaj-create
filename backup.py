"""Local backup, export and restore helpers for Phillap.

All functions take explicit paths so they can be tested against temporary
databases. Backups are plain SQLite copies stored on this PC (not encrypted
and not synced anywhere).
"""
from __future__ import annotations

import csv
import io
import os
import re
import sqlite3
from datetime import datetime
from pathlib import Path

KEEP_DAILY = 7
KEEP_PRE_RESTORE = 5
DAILY_RE = re.compile(r"phillap-backup-(\d{8})\.sqlite3")
PRE_RE = re.compile(r"pre-restore-(\d{8}-\d{6})(?:-\d+)?\.sqlite3")
REQUIRED_TABLES = {"entries"}


def _connect_ro(path: Path) -> sqlite3.Connection:
    return sqlite3.connect(f"{Path(path).resolve().as_uri()}?mode=ro", uri=True)


def _copy_db(src: Path, dest: Path) -> None:
    """Consistent copy via SQLite's online backup API, written atomically."""
    tmp = dest.with_name(dest.name + ".tmp")
    if tmp.exists():
        tmp.unlink()
    source = sqlite3.connect(src)
    target = sqlite3.connect(tmp)
    try:
        source.backup(target)
    finally:
        target.close()
        source.close()
    os.replace(tmp, dest)


def _prune(backup_dir: Path, regex: re.Pattern, keep: int) -> None:
    files = sorted((p for p in backup_dir.iterdir() if regex.fullmatch(p.name)), key=lambda p: p.name, reverse=True)
    for old in files[keep:]:
        old.unlink()


def create_daily_backup(db_path: Path, backup_dir: Path, now: datetime | None = None) -> dict:
    """Create today's backup if missing. An existing same-day backup is never overwritten."""
    db_path, backup_dir = Path(db_path), Path(backup_dir)
    now = now or datetime.now()
    if not db_path.exists():
        return {"created": False, "reason": "no database yet"}
    backup_dir.mkdir(parents=True, exist_ok=True)
    name = f"phillap-backup-{now:%Y%m%d}.sqlite3"
    dest = backup_dir / name
    if dest.exists():
        return {"created": False, "name": name, "reason": "already backed up today"}
    _copy_db(db_path, dest)
    _prune(backup_dir, DAILY_RE, KEEP_DAILY)
    return {"created": True, "name": name}


def create_pre_restore_backup(db_path: Path, backup_dir: Path, now: datetime | None = None) -> str | None:
    db_path, backup_dir = Path(db_path), Path(backup_dir)
    if not db_path.exists():
        return None
    backup_dir.mkdir(parents=True, exist_ok=True)
    now = now or datetime.now()
    stem, n = f"pre-restore-{now:%Y%m%d-%H%M%S}", 0
    while True:
        name = f"{stem}.sqlite3" if n == 0 else f"{stem}-{n}.sqlite3"
        dest = backup_dir / name
        if not dest.exists():
            break
        n += 1
    _copy_db(db_path, dest)
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


def validate_backup(path: Path) -> None:
    try:
        conn = _connect_ro(path)
        try:
            if conn.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise ValueError("That backup failed its integrity check.")
            tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        finally:
            conn.close()
    except sqlite3.DatabaseError as exc:
        raise ValueError("That backup is not a valid Phillap database.") from exc
    if not REQUIRED_TABLES <= tables:
        raise ValueError("That backup is not a valid Phillap database.")


def restore_backup(db_path: Path, backup_dir: Path, name: str, confirm: bool, now: datetime | None = None) -> dict:
    """Restore a named backup over the live database after making a pre-restore backup."""
    if confirm is not True:
        raise ValueError("Restoring replaces your current data. Please confirm to continue.")
    db_path, backup_dir = Path(db_path), Path(backup_dir)
    source = resolve_backup(backup_dir, name)
    validate_backup(source)
    pre = create_pre_restore_backup(db_path, backup_dir, now)
    src = _connect_ro(source)
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