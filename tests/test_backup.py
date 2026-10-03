import sqlite3
import sys
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import backup  # noqa: E402


def make_db(path, titles=("one",)):
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE IF NOT EXISTS entries(id INTEGER PRIMARY KEY, title TEXT)")
    conn.executemany("INSERT INTO entries(title) VALUES(?)", [(t,) for t in titles])
    conn.commit()
    conn.close()


def titles(path):
    conn = sqlite3.connect(path)
    try:
        return [r[0] for r in conn.execute("SELECT title FROM entries ORDER BY id")]
    finally:
        conn.close()


class BackupTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.db = self.root / "live.sqlite3"
        self.dir = self.root / "backups"
        make_db(self.db)

    def tearDown(self):
        self.tmp.cleanup()

    def test_daily_backup_not_overwritten(self):
        now = datetime(2026, 1, 10, 9)
        self.assertTrue(backup.create_daily_backup(self.db, self.dir, now)["created"])
        make_db(self.db, ("changed",))
        self.assertFalse(backup.create_daily_backup(self.db, self.dir, now)["created"])
        self.assertEqual(titles(self.dir / "phillap-backup-20260110.sqlite3"), ["one"])

    def test_rotation_keeps_seven(self):
        start = datetime(2026, 1, 1)
        for i in range(10):
            backup.create_daily_backup(self.db, self.dir, start + timedelta(days=i))
        names = [b["name"] for b in backup.list_backups(self.dir)]
        self.assertEqual(len(names), 7)
        self.assertEqual(names[0], "phillap-backup-20260110.sqlite3")

    def test_restore_with_pre_restore_backup(self):
        backup.create_daily_backup(self.db, self.dir, datetime(2026, 1, 1))
        make_db(self.db, ("two",))
        result = backup.restore_backup(self.db, self.dir, "phillap-backup-20260101.sqlite3", True)
        self.assertEqual(titles(self.db), ["one"])
        self.assertIn("two", titles(self.dir / result["pre_restore_backup"]))

    def test_restore_requires_confirm(self):
        backup.create_daily_backup(self.db, self.dir, datetime(2026, 1, 1))
        for flag in (False, None, "true", 1):
            with self.assertRaises(ValueError):
                backup.restore_backup(self.db, self.dir, "phillap-backup-20260101.sqlite3", flag)

    def test_path_traversal_rejected(self):
        backup.create_daily_backup(self.db, self.dir, datetime(2026, 1, 1))
        outside = self.root / "phillap-backup-20260101.sqlite3"
        make_db(outside)
        bad = ["../phillap-backup-20260101.sqlite3", str(outside), "..\\x.sqlite3", "live.sqlite3",
               "phillap-backup-20260101.sqlite3/../../live.sqlite3", "", None]
        for name in bad:
            with self.assertRaises(ValueError):
                backup.restore_backup(self.db, self.dir, name, True)

    def test_corrupt_and_foreign_backups_rejected(self):
        self.dir.mkdir()
        (self.dir / "phillap-backup-20260101.sqlite3").write_bytes(b"not a database" * 50)
        with self.assertRaises(ValueError):
            backup.restore_backup(self.db, self.dir, "phillap-backup-20260101.sqlite3", True)
        foreign = self.dir / "phillap-backup-20260102.sqlite3"
        conn = sqlite3.connect(foreign)
        conn.execute("CREATE TABLE other(x)")
        conn.commit()
        conn.close()
        with self.assertRaises(ValueError):
            backup.restore_backup(self.db, self.dir, foreign.name, True)
        self.assertEqual(titles(self.db), ["one"])

    def test_exports(self):
        make_db(self.db, ("=cmd()", "plain"))
        data = backup.export_json(self.db)
        self.assertEqual(len(data["tables"]["entries"]), 3)
        csv_text = backup.export_csv(self.db, "entries")
        self.assertIn("'=cmd()", csv_text)
        with self.assertRaises(ValueError):
            backup.export_csv(self.db, "entries; DROP TABLE entries")


if __name__ == "__main__":
    unittest.main()