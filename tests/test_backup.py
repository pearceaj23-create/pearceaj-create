import json
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
    conn.execute("""CREATE TABLE IF NOT EXISTS entries(
        id INTEGER PRIMARY KEY AUTOINCREMENT, area TEXT NOT NULL DEFAULT 'todos',
        title TEXT NOT NULL, content TEXT NOT NULL DEFAULT '', amount_cents INTEGER,
        due_date TEXT, due_time TEXT, priority INTEGER NOT NULL DEFAULT 2, tags TEXT NOT NULL DEFAULT '', completed INTEGER NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)""")
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

    def test_weekly_rotation_uses_iso_weeks_across_year_boundary(self):
        dates = [datetime(2025, 12, 15) + timedelta(days=7 * offset) for offset in range(6)]
        for day in dates:
            result = backup.create_weekly_backup(self.db, self.dir, day, self.settings, self.files)
            self.assertTrue(result["created"])
        names = [item["name"] for item in backup.list_backups(self.dir) if item["kind"] == "weekly"]
        self.assertEqual(len(names), backup.KEEP_WEEKLY)
        self.assertEqual(names[0], "phillap-weekly-backup-202604.zip")
        self.assertEqual(names[-1], "phillap-weekly-backup-202601.zip")
        self.assertFalse(backup.create_weekly_backup(self.db, self.dir, dates[-1], self.settings, self.files)["created"])

    def test_rotation_keeps_seven(self):
        for i in range(10):
            self.daily(datetime(2026, 1, 1) + timedelta(days=i))
        names = [b["name"] for b in backup.list_backups(self.dir)]
        self.assertEqual(len(names), 7)
        self.assertEqual(names[0], "phillap-backup-20260110.zip")

    def test_inspect_backup_validates_and_lists_contents(self):
        self.daily(datetime(2026, 1, 1))
        info = backup.inspect_backup(self.dir / DAY1)
        self.assertEqual(info["name"], DAY1)
        self.assertGreater(info["size_bytes"], 0)
        self.assertEqual({entry["name"] for entry in info["contents"]}, {
            "phillap.sqlite3", "settings.json", f"files/{FID}__doc.txt",
        })
        entries = next(table for table in info["tables"] if table["name"] == "entries")
        self.assertEqual(entries["rows"], 1)

    def test_encrypted_backup_roundtrips_and_rejects_wrong_passphrase_or_tampering(self):
        passphrase = "correct horse battery staple"
        result = backup.create_encrypted_backup(
            self.db, self.dir, passphrase, datetime(2026, 1, 1, 9), self.settings, self.files
        )
        encrypted = self.dir / result["name"]
        self.assertTrue(result["encrypted"])
        self.assertIn({"name": result["name"], "kind": "encrypted", "size": encrypted.stat().st_size,
                       "modified": backup.list_backups(self.dir)[0]["modified"]}, backup.list_backups(self.dir))
        ciphertext = encrypted.read_bytes()
        self.assertTrue(ciphertext.startswith(backup.ENCRYPTED_MAGIC))
        self.assertNotIn(b"hello doc", ciphertext)
        self.assertNotIn(b"one", ciphertext)
        with self.assertRaisesRegex(ValueError, "passphrase"):
            backup.inspect_backup(encrypted)
        with self.assertRaisesRegex(ValueError, "incorrect"):
            backup.inspect_backup(encrypted, "wrong passphrase value")
        info = backup.inspect_backup(encrypted, passphrase)
        self.assertTrue(info["encrypted"])
        self.assertIn("phillap.sqlite3", {item["name"] for item in info["contents"]})
        make_db(self.db, ("current",))
        with self.assertRaisesRegex(ValueError, "incorrect"):
            backup.restore_backup(self.db, self.dir, result["name"], True, settings_path=self.settings,
                                 files_dir=self.files, passphrase="wrong passphrase value")
        self.assertEqual(titles(self.db), ["one", "current"])
        damaged = bytearray(ciphertext)
        damaged[-20] ^= 1
        encrypted.write_bytes(damaged)
        with self.assertRaisesRegex(ValueError, "incorrect|damaged"):
            backup.validate_backup(encrypted, passphrase)
        encrypted.write_bytes(ciphertext)
        restored = backup.restore_backup(self.db, self.dir, result["name"], True, settings_path=self.settings,
                                         files_dir=self.files, passphrase=passphrase)
        self.assertEqual(restored["restored"], result["name"])
        self.assertEqual(titles(self.db), ["one"])
        self.assertEqual((self.files / f"{FID}__doc.txt").read_text(), "hello doc")

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

    def test_rotation_across_month_boundary(self):
        start = datetime(2026, 1, 28)
        for day in range(10):
            self.daily(start + timedelta(days=day))
        names = [item["name"] for item in backup.list_backups(self.dir)]
        self.assertEqual(len(names), backup.KEEP_DAILY)
        self.assertEqual(names[0], "phillap-backup-20260206.zip")
        self.assertEqual(names[-1], "phillap-backup-20260131.zip")

    def test_restore_while_database_connection_is_open(self):
        self.daily(datetime(2026, 1, 1))
        make_db(self.db, ("current",))
        active_connection = sqlite3.connect(self.db)
        try:
            self.assertEqual([row[0] for row in active_connection.execute("SELECT title FROM entries ORDER BY id")], ["one", "current"])
            self.restore(DAY1)
        finally:
            active_connection.close()
        self.assertEqual(titles(self.db), ["one"])

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

    def test_json_import_replaces_records_only_after_confirmation_and_saves_backup(self):
        make_db(self.db, ("from export",))
        export = backup.export_json(self.db)
        make_db(self.db, ("must be replaced",))
        with self.assertRaises(ValueError):
            backup.import_json(self.db, json.dumps(export), backup_dir=self.dir)
        self.assertEqual(titles(self.db), ["one", "from export", "must be replaced"])
        result = backup.import_json(
            self.db, json.dumps(export), True, self.dir, self.settings, self.files
        )
        self.assertEqual(titles(self.db), ["one", "from export"])
        self.assertEqual(result["tables"], 1)
        self.assertGreaterEqual(result["imported"], 2)
        self.assertTrue((self.dir / result["pre_import_backup"]).is_file())

    def test_invalid_json_export_does_not_mutate_database(self):
        make_db(self.db, ("kept",))
        export = backup.export_json(self.db)
        export["tables"]["entries"][0]["unexpected"] = "invalid"
        with self.assertRaisesRegex(ValueError, "invalid columns"):
            backup.import_json(self.db, json.dumps(export), True, self.dir)
        self.assertEqual(titles(self.db), ["one", "kept"])
        self.assertEqual(list(self.dir.glob("pre-restore-*.zip")), [])

    def test_csv_import_appends_todos_and_money_atomically(self):
        todo_csv = 'area,title,content,due_date,due_time,priority,tags\ntodos,"Buy, then install","quoted detail",2030-02-03,14:30,1,home\nthoughts,skip me,,,,,\n'
        result = backup.import_csv(self.db, "todos", todo_csv)
        self.assertEqual(result, {"imported": 1, "kind": "todos"})
        self.assertEqual(titles(self.db), ["one", "Buy, then install"])
        conn = sqlite3.connect(self.db)
        try:
            self.assertEqual(conn.execute("SELECT due_time,priority,tags FROM entries WHERE title='Buy, then install'").fetchone(), ("14:30", 1, "home"))
        finally:
            conn.close()
        conn = sqlite3.connect(self.db)
        conn.execute("""CREATE TABLE finance_items (
            id INTEGER PRIMARY KEY, direction TEXT NOT NULL, title TEXT NOT NULL,
            category TEXT NOT NULL DEFAULT '', amount_cents INTEGER NOT NULL,
            frequency TEXT NOT NULL, due_day INTEGER, household_member TEXT NOT NULL DEFAULT 'Me',
            note TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)""")
        conn.commit()
        conn.close()
        result = backup.import_csv(self.db, "money", "direction,title,amount,frequency\nexpense,Groceries,$12.34,monthly\n")
        self.assertEqual(result, {"imported": 1, "kind": "money"})
        conn = sqlite3.connect(self.db)
        try:
            self.assertEqual(conn.execute("SELECT title, amount_cents FROM finance_items").fetchone(), ("Groceries", 1234))
            before = conn.execute("SELECT COUNT(*) FROM finance_items").fetchone()[0]
        finally:
            conn.close()
        invalid = "direction,title,amount,frequency\nexpense,Valid,4.00,monthly\nexpense,Invalid,nan,monthly\n"
        with self.assertRaises(ValueError):
            backup.import_csv(self.db, "money", invalid)
        conn = sqlite3.connect(self.db)
        try:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM finance_items").fetchone()[0], before)
        finally:
            conn.close()

    def test_bank_transaction_csv_import_infers_signed_amount_direction_atomically(self):
        conn = sqlite3.connect(self.db)
        conn.execute("""CREATE TABLE finance_transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT, direction TEXT NOT NULL, title TEXT NOT NULL,
            category TEXT NOT NULL DEFAULT '', amount_cents INTEGER NOT NULL, transaction_date TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)""")
        conn.commit()
        conn.close()
        result = backup.import_csv(
            self.db, "transactions",
            "date,description,amount,category\n2025-01-02,Groceries,-42.15,Food\n2025-01-03,Paycheck,1250.00,Income\n",
        )
        self.assertEqual(result, {"imported": 2, "kind": "transactions"})
        conn = sqlite3.connect(self.db)
        try:
            self.assertEqual(
                conn.execute("SELECT direction,title,category,amount_cents,transaction_date FROM finance_transactions ORDER BY id").fetchall(),
                [("expense", "Groceries", "Food", 4215, "2025-01-02"),
                 ("income", "Paycheck", "Income", 125000, "2025-01-03")],
            )
        finally:
            conn.close()
        with self.assertRaisesRegex(ValueError, "Transaction dates"):
            backup.import_csv(self.db, "transactions", "date,title,amount\nnot-a-date,Invalid,-5\n")
        conn = sqlite3.connect(self.db)
        try:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM finance_transactions").fetchone()[0], 2)
        finally:
            conn.close()

    def test_exports(self):
        make_db(self.db, ("=cmd()", "plain"))
        self.assertEqual(len(backup.export_json(self.db)["tables"]["entries"]), 3)
        self.assertIn("'=cmd()", backup.export_csv(self.db, "entries"))
        with self.assertRaises(ValueError):
            backup.export_csv(self.db, "entries; DROP TABLE entries")


if __name__ == "__main__":
    unittest.main()
