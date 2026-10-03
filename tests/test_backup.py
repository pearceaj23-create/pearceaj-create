import sqlite3
import sys
import tempfile
import unittest
import zipfile
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import backup  # noqa: E402

FID = "a" * 32
DAY1 = "phillap-backup-20260101.zip"


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
        self.files = self.root / "files"
        self.files.mkdir()
        self.settings = self.root / "settings.json"
        self.settings.write_text('{"a": 1}')
        (self.files / f"{FID}__doc.txt").write_text("hello doc")
        make_db(self.db)

    def tearDown(self):
        self.tmp.cleanup()

    def daily(self, now):
        return backup.create_daily_backup(self.db, self.dir, now, self.settings, self.files)

    def restore(self, name, confirm=True):
        return backup.restore_backup(self.db, self.dir, name, confirm, None, self.settings, self.files)

    def test_bundle_contents_and_no_overwrite(self):
        now = datetime(2026, 1, 1, 9)
        self.assertTrue(self.daily(now)["created"])
        with zipfile.ZipFile(self.dir / DAY1) as zf:
            self.assertEqual(set(zf.namelist()), {"phillap.sqlite3", "settings.json", f"files/{FID}__doc.txt"})
        make_db(self.db, ("changed",))
        self.assertFalse(self.daily(now)["created"])

    def test_rotation_keeps_seven(self):
        for i in range(10):
            self.daily(datetime(2026, 1, 1) + timedelta(days=i))
        names = [b["name"] for b in backup.list_backups(self.dir)]
        self.assertEqual(len(names), 7)
        self.assertEqual(names[0], "phillap-backup-20260110.zip")

    def test_restore_brings_back_data_settings_and_documents(self):
        self.daily(datetime(2026, 1, 1))
        make_db(self.db, ("two",))
        self.settings.write_text('{"a": 2}')
        (self.files / f"{FID}__doc.txt").write_text("changed")
        (self.files / ("b" * 32 + "__new.txt")).write_text("new")
        result = self.restore(DAY1)
        self.assertEqual(titles(self.db), ["one"])
        self.assertEqual(self.settings.read_text(), '{"a": 1}')
        self.assertEqual((self.files / f"{FID}__doc.txt").read_text(), "hello doc")
        self.assertFalse((self.files / ("b" * 32 + "__new.txt")).exists())
        with zipfile.ZipFile(self.dir / result["pre_restore_backup"]) as zf:
            self.assertIn("files/" + "b" * 32 + "__new.txt", zf.namelist())

    def test_restore_requires_confirm(self):
        self.daily(datetime(2026, 1, 1))
        for flag in (False, None, "true", 1):
            with self.assertRaises(ValueError):
                self.restore(DAY1, flag)

    def test_path_traversal_names_rejected(self):
        self.daily(datetime(2026, 1, 1))
        outside = self.root / DAY1
        outside.write_bytes(b"x")
        for name in ["../" + DAY1, str(outside), "..\\x.zip", "live.sqlite3", DAY1 + "/../../live.sqlite3", "", None]:
            with self.assertRaises(ValueError):
                self.restore(name)

    def test_malicious_archive_members_rejected(self):
        self.dir.mkdir()
        for member in ("../evil.txt", "files/../evil", "/abs.txt", "files/notanid.txt"):
            path = self.dir / DAY1
            path.unlink(missing_ok=True)
            with zipfile.ZipFile(path, "w") as zf:
                zf.writestr("phillap.sqlite3", b"")
                zf.writestr(member, "x")
            with self.assertRaises(ValueError):
                self.restore(DAY1)
        self.assertEqual(titles(self.db), ["one"])

    def test_corrupt_and_foreign_backups_rejected(self):
        self.dir.mkdir()
        (self.dir / DAY1).write_bytes(b"not a zip" * 50)
        with self.assertRaises(ValueError):
            self.restore(DAY1)
        foreign = self.root / "f.sqlite3"
        conn = sqlite3.connect(foreign)
        conn.execute("CREATE TABLE other(x)")
        conn.commit()
        conn.close()
        with zipfile.ZipFile(self.dir / "phillap-backup-20260102.zip", "w") as zf:
            zf.write(foreign, "phillap.sqlite3")
        with self.assertRaises(ValueError):
            self.restore("phillap-backup-20260102.zip")
        self.assertEqual(titles(self.db), ["one"])

    def test_exports(self):
        make_db(self.db, ("=cmd()", "plain"))
        self.assertEqual(len(backup.export_json(self.db)["tables"]["entries"]), 3)
        self.assertIn("'=cmd()", backup.export_csv(self.db, "entries"))
        with self.assertRaises(ValueError):
            backup.export_csv(self.db, "entries; DROP TABLE entries")


if __name__ == "__main__":
    unittest.main()