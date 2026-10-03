import json
from io import BytesIO
import sqlite3
import tempfile
import threading
import unittest
from unittest import mock
import urllib.error
import urllib.request
import zipfile
from datetime import date, datetime, timedelta
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

import app


class SchemaMigrationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.db_path = self.root / "legacy.sqlite3"
        conn = sqlite3.connect(self.db_path)
        conn.execute("CREATE TABLE uploaded_file_meta (file_id TEXT PRIMARY KEY, importance TEXT NOT NULL)")
        conn.execute("INSERT INTO uploaded_file_meta(file_id, importance) VALUES('f1', 'critical')")
        conn.execute("CREATE TABLE conversations (id INTEGER PRIMARY KEY, title TEXT NOT NULL)")
        conn.execute("INSERT INTO conversations(id, title) VALUES(1, 'old conversation')")
        conn.commit()
        conn.close()

    def tearDown(self):
        self.tmp.cleanup()

    def test_legacy_database_migrates_once_and_preserves_data(self):
        with patch.object(app, "CONFIG_DIR", self.root), patch.object(app, "DATA_FILE", self.db_path):
            with app.db_connect() as conn:
                version = conn.execute("SELECT version FROM schema_version").fetchone()[0]
                self.assertEqual(version, app.SCHEMA_VERSION)
                self.assertEqual(conn.execute("SELECT importance FROM uploaded_file_meta WHERE file_id='f1'").fetchone()[0], "critical")
                self.assertEqual(conn.execute("SELECT category FROM uploaded_file_meta WHERE file_id='f1'").fetchone()[0], "Other")
                self.assertEqual(tuple(conn.execute("SELECT title, category FROM conversations WHERE id=1").fetchone()), ("old conversation", "Other"))
            with app.db_connect() as conn:
                self.assertEqual([tuple(row) for row in conn.execute("SELECT version FROM schema_version")], [(app.SCHEMA_VERSION,)])
                self.assertEqual(len(conn.execute("PRAGMA table_info(conversations)").fetchall()), 3)

    def test_version_one_database_migrates_recycle_bin(self):
        with patch.object(app, "CONFIG_DIR", self.root), patch.object(app, "DATA_FILE", self.db_path):
            with app.db_connect() as conn:
                conn.execute("UPDATE schema_version SET version=1")
                conn.execute("DROP TABLE deleted_entries")
            with app.db_connect() as conn:
                self.assertEqual(conn.execute("SELECT version FROM schema_version").fetchone()[0], app.SCHEMA_VERSION)
                self.assertIn("deleted_entries", {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")})
                self.assertIn("due_time", {row[1] for row in conn.execute("PRAGMA table_info(entries)")})
                self.assertIn("due_time", {row[1] for row in conn.execute("PRAGMA table_info(deleted_entries)")})
                self.assertIn("tags", {row[1] for row in conn.execute("PRAGMA table_info(entries)")})
                self.assertIn("priority", {row[1] for row in conn.execute("PRAGMA table_info(deleted_entries)")})
                self.assertIn("snoozed_until", {row[1] for row in conn.execute("PRAGMA table_info(entries)")})
                self.assertIn("snoozed_until", {row[1] for row in conn.execute("PRAGMA table_info(deleted_entries)")})
                self.assertIn("completed_at", {row[1] for row in conn.execute("PRAGMA table_info(entries)")})
                self.assertIn("completed_at", {row[1] for row in conn.execute("PRAGMA table_info(deleted_entries)")})
                self.assertIn("tags", {row[1] for row in conn.execute("PRAGMA table_info(uploaded_file_meta)")})
                self.assertIn("recurrence", {row[1] for row in conn.execute("PRAGMA table_info(entries)")})
                self.assertIn("recurrence_series_id", {row[1] for row in conn.execute("PRAGMA table_info(deleted_entries)")})
                self.assertIn("sort_order", {row[1] for row in conn.execute("PRAGMA table_info(entries)")})
                self.assertIn("task_order_state", {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")})
                self.assertIn("file_search", {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")})
                self.assertNotIn("file_search", app.backup.export_tables(self.db_path))
                self.assertIn("finance_budgets", {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")})
                self.assertIn("finance_transactions", {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")})
                self.assertIn("finance_savings_goals", {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")})
                self.assertIn("finance_savings_contributions", {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")})

    def test_version_seventeen_database_migrates_food_lists(self):
        with patch.object(app, "CONFIG_DIR", self.root), patch.object(app, "DATA_FILE", self.db_path):
            with app.db_connect() as conn:
                conn.execute("UPDATE schema_version SET version=16")
                conn.execute("DROP TABLE food_meal_plan")
            with app.db_connect() as conn:
                self.assertEqual(conn.execute("SELECT version FROM schema_version").fetchone()[0], app.SCHEMA_VERSION)
                tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
                self.assertTrue({"food_meal_plan", "food_grocery_items", "food_recipes", "food_pantry_items"} <= tables)

    def test_database_from_newer_version_is_not_opened_for_writes(self):
        conn = sqlite3.connect(self.db_path)
        conn.execute("CREATE TABLE schema_version (version INTEGER NOT NULL)")
        conn.execute("INSERT INTO schema_version(version) VALUES(?)", (app.SCHEMA_VERSION + 1,))
        conn.commit()
        conn.close()
        with patch.object(app, "CONFIG_DIR", self.root), patch.object(app, "DATA_FILE", self.db_path):
            with self.assertRaisesRegex(RuntimeError, "newer version"):
                with app.db_connect():
                    pass
        conn = sqlite3.connect(self.db_path)
        try:
            self.assertEqual(conn.execute("SELECT version FROM schema_version").fetchone()[0], app.SCHEMA_VERSION + 1)
        finally:
            conn.close()


class ApiRateLimitTests(unittest.TestCase):
    def setUp(self):
        with app._RATE_LIMIT_LOCK:
            self.original_requests = app._RATE_LIMIT_REQUESTS
            app._RATE_LIMIT_REQUESTS = {}

    def tearDown(self):
        with app._RATE_LIMIT_LOCK:
            app._RATE_LIMIT_REQUESTS = self.original_requests

    def test_post_limiter_allows_burst_then_recovers_after_window(self):
        with patch.object(app, "_RATE_LIMIT_MAX_POSTS", 2):
            self.assertFalse(app.post_rate_limited("127.0.0.1", now=10))
            self.assertFalse(app.post_rate_limited("127.0.0.1", now=11))
            self.assertTrue(app.post_rate_limited("127.0.0.1", now=12))
            self.assertFalse(app.post_rate_limited("127.0.0.1", now=70))
            self.assertFalse(app.post_rate_limited("::1", now=12))


class HealthAndLoggingTests(unittest.TestCase):
    def setUp(self):
        with app._APP_LOCK_STATE:
            app._APP_UNLOCKED = False
            app._APP_LOCK_FAILURES = {}
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.patchers = [
            patch.object(app, "CONFIG_DIR", self.root),
            patch.object(app, "DATA_FILE", self.root / "test.sqlite3"),
            patch.object(app, "CONFIG_FILE", self.root / "settings.json"),
            patch.object(app, "BACKUP_DIR", self.root / "backups"),
            patch.object(app, "PORT", 0),
        ]
        for patcher in self.patchers:
            patcher.start()
        self.server = ThreadingHTTPServer((app.HOST, 0), app.Handler)
        app.PORT = self.server.server_address[1]
        self.base = f"http://{app.HOST}:{app.PORT}"
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)
        with app._APP_LOCK_STATE:
            app._APP_UNLOCKED = False
            app._APP_LOCK_FAILURES = {}
        for patcher in reversed(self.patchers):
            patcher.stop()
        self.tmp.cleanup()

    def get_json(self, path):
        with urllib.request.urlopen(self.base + path, timeout=10) as response:
            return response.status, json.loads(response.read())

    def get_json_error(self, path):
        try:
            return self.get_json(path)
        except urllib.error.HTTPError as error:
            with error:
                return error.code, json.loads(error.read())

    def post_json(self, path, body):
        request = urllib.request.Request(
            self.base + path,
            data=json.dumps(body).encode("utf-8"),
            headers={"Content-Type": "application/json", "Origin": self.base},
        )
        try:
            with urllib.request.urlopen(request, timeout=10) as response:
                return response.status, json.loads(response.read())
        except urllib.error.HTTPError as error:
            with error:
                return error.code, json.loads(error.read())

    def test_encrypted_backup_routes_require_passphrase_and_roundtrip(self):
        app.save_entry({"area": "todos", "title": "Backup secret"})
        status, result = self.post_json("/api/backups/create-encrypted", {"passphrase": "stored nowhere 123"})
        self.assertEqual(status, 201)
        self.assertTrue(result["encrypted"])
        self.assertEqual(self.get_json("/api/backups")[1]["backups"][0]["kind"], "encrypted")
        status, error = self.post_json("/api/backups/verify", {"name": result["name"]})
        self.assertEqual(status, 400)
        self.assertIn("passphrase", error["error"])
        status, verified = self.post_json("/api/backups/verify", {
            "name": result["name"], "passphrase": "stored nowhere 123"
        })
        self.assertEqual((status, verified), (200, {"valid": True}))
        status, error = self.post_json("/api/backups/restore", {
            "name": result["name"], "confirm": True, "passphrase": "bad passphrase 123"
        })
        self.assertEqual(status, 400)
        self.assertIn("incorrect", error["error"])
        app.save_entry({"area": "todos", "title": "Current data"})
        status, restored = self.post_json("/api/backups/restore", {
            "name": result["name"], "confirm": True, "passphrase": "stored nowhere 123"
        })
        self.assertEqual(status, 200)
        self.assertTrue(restored["restored"].endswith(".enc"))
        with app.db_connect() as conn:
            titles = [row[0] for row in conn.execute("SELECT title FROM entries ORDER BY id")]
        self.assertIn("Backup secret", titles)
        self.assertNotIn("Current data", titles)

    def test_removing_app_lock_from_settings_recovers_forgotten_pin(self):
        self.post_json("/api/lock/setup", {"pin": "042681"})
        self.post_json("/api/lock", {})
        self.assertEqual(self.get_json_error("/api/areas")[0], 423)
        path = self.root / "settings.json"
        config = json.loads(path.read_text(encoding="utf-8"))
        config.pop("app_lock")
        path.write_text(json.dumps(config), encoding="utf-8")
        self.assertEqual(self.get_json("/api/lock/status")[1], {"enabled": False, "unlocked": True})
        self.assertEqual(self.get_json("/api/areas")[0], 200)

    def test_app_lock_hashes_pin_and_gates_local_api_until_unlocked(self):
        status, initial = self.get_json("/api/lock/status")
        self.assertEqual((status, initial), (200, {"enabled": False, "unlocked": True}))
        status, error = self.post_json("/api/lock/setup", {"pin": "123"})
        self.assertEqual(status, 400)
        self.assertIn("6 to 12 digits", error["error"])
        status, enabled = self.post_json("/api/lock/setup", {"pin": "042681"})
        self.assertEqual(status, 201)
        self.assertEqual(enabled, {"enabled": True, "unlocked": True})
        config = json.loads((self.root / "settings.json").read_text(encoding="utf-8"))
        self.assertNotIn("042681", json.dumps(config))
        self.assertEqual(len(config["app_lock"]["salt"]), 32)
        self.assertEqual(len(config["app_lock"]["hash"]), 64)
        with patch.object(app, "ollama_status", return_value={"models": []}):
            public_config = self.get_json("/api/config")[1]
        self.assertNotIn("app_lock", public_config)
        status, saved_config = self.post_json("/api/config", {
            "repo": "owner/repo", "docs_path": str(self.root), "model": "test-model",
            "ollama_url": "http://127.0.0.1:11434",
        })
        self.assertEqual(status, 200)
        self.assertNotIn("app_lock", saved_config)
        self.assertEqual(json.loads((self.root / "settings.json").read_text(encoding="utf-8"))["app_lock"], config["app_lock"])
        status, result = self.post_json("/api/lock", {})
        self.assertEqual((status, result), (200, {"enabled": True, "unlocked": False}))
        status, error = self.get_json_error("/api/areas")
        self.assertEqual(status, 423)
        self.assertIn("locked", error["error"])
        self.assertEqual(self.get_json("/api/lock/status")[1]["unlocked"], False)
        status, error = self.post_json("/api/lock/unlock", {"pin": "111111"})
        self.assertEqual(status, 400)
        self.assertIn("incorrect", error["error"])
        status, result = self.post_json("/api/lock/unlock", {"pin": "042681"})
        self.assertEqual((status, result), (200, {"enabled": True, "unlocked": True}))
        self.assertEqual(self.get_json("/api/areas")[0], 200)
        status, error = self.post_json("/api/lock/disable", {"pin": "000000"})
        self.assertEqual(status, 400)
        status, disabled = self.post_json("/api/lock/disable", {"pin": "042681"})
        self.assertEqual((status, disabled), (200, {"enabled": False, "unlocked": True}))
        self.assertIsNone(json.loads((self.root / "settings.json").read_text(encoding="utf-8"))["app_lock"])

    def test_project_checklist_templates_append_reviewable_steps(self):
        status, project = self.post_json("/api/projects", {"title": "Moving plan"})
        self.assertEqual(status, 201)
        status, result = self.post_json("/api/projects/template", {
            "project_id": project["id"], "template": "moving"
        })
        self.assertEqual(status, 201)
        self.assertGreaterEqual(len(result["steps"]), 5)
        self.assertTrue(all(not step["completed"] and step["due_date"] is None for step in result["steps"]))
        status, error = self.post_json("/api/projects/template", {
            "project_id": project["id"], "template": "missing"
        })
        self.assertEqual(status, 400)
        self.assertIn("template", error["error"])
        status, error = self.post_json("/api/projects/template", {
            "project_id": 999999, "template": "moving"
        })
        self.assertEqual(status, 400)
        self.assertIn("Project not found", error["error"])

    def test_local_life_lists_validate_and_update_typed_records(self):
        status, health = self.post_json("/api/life/health", {"title": "Daily note", "details": "A short private note."})
        self.assertEqual(status, 201)
        self.assertEqual(health["event_date"], app.date.today().isoformat())
        status, contact = self.post_json("/api/life/contacts", {
            "title": "Alex", "event_date": "2000-02-29", "details": "Birthday reminder"
        })
        self.assertEqual(status, 201)
        status, packing = self.post_json("/api/life/packing", {
            "title": "Charger", "group_name": "Weekend trip", "details": "Phone charger"
        })
        self.assertEqual(status, 201)
        status, packed = self.post_json("/api/life/update", {"id": packing["id"], "status": "packed"})
        self.assertEqual((status, packed["status"]), (200, "packed"))
        status, maintenance = self.post_json("/api/life/maintenance", {
            "title": "Replace filter", "event_date": "2032-03-01", "recurrence": "yearly"
        })
        self.assertEqual(status, 201)
        status, done = self.post_json("/api/life/update", {"id": maintenance["id"], "status": "done"})
        self.assertEqual((status, done["status"]), (200, "done"))
        status, wishlist = self.post_json("/api/life/wishlist", {"title": "Garden gloves"})
        self.assertEqual(status, 201)
        status, purchased = self.post_json("/api/life/update", {"id": wishlist["id"], "status": "purchased"})
        self.assertEqual((status, purchased["status"]), (200, "purchased"))
        status, reading = self.post_json("/api/life/reading", {"title": "A book", "details": "Author name"})
        self.assertEqual(status, 201)
        status, reading_now = self.post_json("/api/life/update", {"id": reading["id"], "status": "reading"})
        self.assertEqual((status, reading_now["status"]), (200, "reading"))
        self.assertEqual(self.get_json("/api/life/contacts")[1][0]["event_date"], "2000-02-29")
        for route, payload in (
            ("/api/life/contacts", {"title": "Invalid birthday", "event_date": "2001-02-29"}),
            ("/api/life/packing", {"title": "Unassigned item"}),
            ("/api/life/maintenance", {"title": "Invalid date", "event_date": "2032-02-30"}),
            ("/api/life/reading", {"title": "Invalid details", "details": "x" * 4001}),
        ):
            status, error = self.post_json(route, payload)
            self.assertEqual(status, 400)
            self.assertTrue(error["error"])
        status, error = self.post_json("/api/life/update", {"id": reading["id"], "status": "purchased"})
        self.assertEqual(status, 400)
        for record in (health, contact, packing, maintenance, wishlist, reading):
            status, result = self.post_json("/api/life/delete", {"id": record["id"]})
            self.assertEqual((status, result), (200, {"deleted": True}))

    def test_habits_track_idempotent_date_scoped_checkins(self):
        status, habit = self.post_json("/api/habits", {"name": "Read for a few minutes"})
        self.assertEqual(status, 201)
        self.assertFalse(habit["done_today"])
        today = app.date.today().isoformat()
        status, checked = self.post_json("/api/habits/check", {
            "id": habit["id"], "date": today, "completed": True
        })
        self.assertEqual((status, checked["completed"]), (200, True))
        self.post_json("/api/habits/check", {"id": habit["id"], "date": today, "completed": True})
        listed = self.get_json("/api/habits")[1]
        self.assertTrue(listed[0]["done_today"])
        self.assertEqual(listed[0]["completed_days"], 1)
        for values in (
            {"id": habit["id"], "date": "2032-02-30", "completed": True},
            {"id": habit["id"], "date": today, "completed": "yes"},
            {"id": 999999, "date": today, "completed": True},
        ):
            status, error = self.post_json("/api/habits/check", values)
            self.assertEqual(status, 400)
            self.assertTrue(error["error"])
        status, _ = self.post_json("/api/habits/check", {"id": habit["id"], "date": today, "completed": False})
        self.assertEqual(status, 200)
        self.assertEqual(self.get_json("/api/habits")[1][0]["completed_days"], 0)
        status, deleted = self.post_json("/api/habits/delete", {"id": habit["id"]})
        self.assertEqual((status, deleted), (200, {"deleted": True}))
        self.assertEqual(self.get_json("/api/habits")[1], [])
        with app.db_connect() as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM habit_completions WHERE habit_id=?", (habit["id"],)).fetchone()[0], 0)

    def test_project_checklist_steps_accept_optional_validated_dates(self):
        status, project = self.post_json("/api/projects", {
            "title": "Backyard project", "description": "Plan a manageable sequence."
        })
        self.assertEqual(status, 201)
        status, step = self.post_json("/api/projects/step", {
            "project_id": project["id"], "title": "Get a quote", "due_date": "2032-06-15"
        })
        self.assertEqual(status, 201)
        self.assertEqual(step["due_date"], "2032-06-15")
        self.assertEqual(app.list_projects()[0]["steps"][0]["due_date"], "2032-06-15")
        for value in ("2032-02-30", "2032/06/15", 123):
            status, error = self.post_json("/api/projects/step", {
                "project_id": project["id"], "title": "Invalid date", "due_date": value
            })
            self.assertEqual(status, 400)
            self.assertTrue(error["error"])
        status, no_date = self.post_json("/api/projects/step", {
            "project_id": project["id"], "title": "Flexible step"
        })
        self.assertEqual(status, 201)
        self.assertIsNone(no_date["due_date"])

    def test_food_meal_plan_validates_saves_lists_and_deletes(self):
        start = "2032-02-28"
        status, empty = self.get_json(f"/api/food/meals?start={start}")
        self.assertEqual(status, 200)
        self.assertEqual((empty["start"], empty["end"]), ("2032-02-28", "2032-03-12"))
        self.assertEqual(empty["meals"], [])

        status, meal = self.post_json("/api/food/meals", {
            "meal_date": "2032-03-01",
            "meal_type": "dinner",
            "title": "Leftover roast",
            "ingredients": "Roast, potatoes, vegetables",
            "instructions": "Reheat thoroughly; check labels.",
            "uses_leftovers": True,
        })
        self.assertEqual(status, 201)
        self.assertTrue(meal["uses_leftovers"])
        self.assertEqual(meal["title"], "Leftover roast")
        status, result = self.get_json(f"/api/food/meals?start={start}")
        self.assertEqual(status, 200)
        self.assertEqual(result["meals"], [meal])

        status, outside = self.get_json("/api/food/meals?start=2032-03-13")
        self.assertEqual(status, 200)
        self.assertEqual(outside["meals"], [])
        for payload in (
            {"meal_date": "2032-02-30", "meal_type": "dinner", "title": "Invalid date"},
            {"meal_date": "2032-03-01", "meal_type": "brunch", "title": "Invalid type"},
            {"meal_date": "2032-03-01", "meal_type": "dinner", "title": " "},
            {"meal_date": "2032-03-01", "meal_type": [], "title": "Invalid type"},
            {"meal_date": "2032-03-01", "meal_type": "lunch", "title": "Invalid leftovers", "uses_leftovers": "yes"},
        ):
            status, error = self.post_json("/api/food/meals", payload)
            self.assertEqual(status, 400)
            self.assertTrue(error["error"])
        status, error = self.get_json_error("/api/food/meals?start=2032-02-30")
        self.assertEqual(status, 400)
        status, deleted = self.post_json("/api/food/meals/delete", {"id": meal["id"]})
        self.assertEqual((status, deleted), (200, {"deleted": True}))
        status, result = self.get_json(f"/api/food/meals?start={start}")
        self.assertEqual(result["meals"], [])

    def test_update_check_reports_newer_release_without_installing_it(self):
        release = {
            "tag_name": "v0.9.0",
            "html_url": f"https://github.com/{app.UPDATE_REPOSITORY}/releases/tag/v0.9.0",
        }
        real_urlopen = urllib.request.urlopen
        def mocked_urlopen(request, timeout=0):
            url = request.full_url if hasattr(request, "full_url") else request
            if str(url).startswith("https://api.github.com/"):
                return BytesIO(json.dumps(release).encode())
            return real_urlopen(request, timeout=timeout)
        with patch.object(app.urllib.request, "urlopen", side_effect=mocked_urlopen) as open_url:
            status, result = self.get_json("/api/update")
        self.assertEqual(status, 200)
        self.assertTrue(result["update_available"])
        self.assertEqual(result["latest_version"], "0.9.0")
        self.assertEqual(result["current_version"], app.APP_VERSION)
        github_call = next(call for call in open_url.call_args_list if str(getattr(call.args[0], "full_url", call.args[0])).startswith("https://api.github.com/"))
        self.assertEqual(github_call.kwargs["timeout"], 5)

    def test_today_shows_monthly_bills_due_within_seven_days(self):
        app.save_finance({"direction": "expense", "title": "Power", "amount": "85.25", "frequency": "monthly", "due_day": 20})
        app.save_finance({"direction": "expense", "title": "Past this month", "amount": "12", "frequency": "monthly", "due_day": 10})
        app.save_finance({"direction": "income", "title": "Payday", "amount": "500", "frequency": "monthly", "due_day": 20})
        today = datetime(2031, 5, 15, 12, 0)
        result = app.get_today(today)
        self.assertEqual(result["bills_due"], [{"title": "Power", "amount": 85.25, "due_date": "2031-05-20"}])

    def test_today_reports_backup_age(self):
        now = datetime(2031, 5, 15, 12, 0)
        self.assertIsNone(app.get_today(now)["backup_age_days"])
        with mock.patch.object(app.backup, "list_backups", return_value=[{"name": "x.zip", "modified": "2031-05-10T12:00:00"}]):
            self.assertEqual(app.get_today(now)["backup_age_days"], 5)

    def test_habit_streak_counts_consecutive_days(self):
        habit = app.save_habit({"name": "Walk"})
        today = date.today()
        for back in (0, 1, 2, 4):
            app.set_habit_completion({"id": habit["id"], "completed": True, "date": (today - timedelta(days=back)).isoformat()})
        listed = app.list_habits()[0]
        self.assertGreaterEqual(listed["streak"], 1)
        self.assertLessEqual(listed["streak"], 3)

    def test_year_review_summarises_the_year(self):
        review = app.year_review(2031)
        self.assertEqual((review["year"], review["tasks_completed"], review["habit_checkins"]), (2031, 0, 0))
        self.assertEqual(len(review["tasks_by_month"]), 12)
        with self.assertRaises(ValueError):
            app.year_review("abc")
    def test_update_check_reports_when_no_public_release_exists(self):
        real_urlopen = urllib.request.urlopen
        def mocked_urlopen(request, timeout=0):
            url = request.full_url if hasattr(request, "full_url") else request
            if str(url).startswith("https://api.github.com/"):
                raise urllib.error.HTTPError(str(url), 404, "Not Found", {}, BytesIO())
            return real_urlopen(request, timeout=timeout)
        with patch.object(app.urllib.request, "urlopen", side_effect=mocked_urlopen):
            status, result = self.get_json_error("/api/update")
        self.assertEqual(status, 500)
        self.assertIn("No public Phillap release is available yet", result["error"])

    def test_update_check_rejects_untrusted_release_link(self):
        release = {"tag_name": "v99.0", "html_url": "https://example.com/evil"}
        real_urlopen = urllib.request.urlopen
        def mocked_urlopen(request, timeout=0):
            url = request.full_url if hasattr(request, "full_url") else request
            if str(url).startswith("https://api.github.com/"):
                return BytesIO(json.dumps(release).encode())
            return real_urlopen(request, timeout=timeout)
        with patch.object(app.urllib.request, "urlopen", side_effect=mocked_urlopen):
            status, result = self.get_json_error("/api/update")
        self.assertEqual(status, 500)
        self.assertIn("release link was invalid", result["error"])

    def test_post_api_rate_limit_returns_retry_after(self):
        with patch.object(app, "_RATE_LIMIT_MAX_POSTS", 0):
            request = urllib.request.Request(
                self.base + "/api/entries",
                data=json.dumps({"area": "todos", "title": "Blocked request"}).encode("utf-8"),
                headers={"Content-Type": "application/json", "Origin": self.base},
            )
            with self.assertRaises(urllib.error.HTTPError) as caught:
                urllib.request.urlopen(request, timeout=10)
        error = caught.exception
        try:
            self.assertEqual(error.code, 429)
            self.assertEqual(error.headers["Retry-After"], str(app._RATE_LIMIT_WINDOW_SECONDS))
            self.assertIn("Too many requests", json.loads(error.read())["error"])
        finally:
            error.close()

    def test_security_headers_are_applied_to_html_and_json_responses(self):
        for route in ("/", "/api/health"):
            with urllib.request.urlopen(self.base + route, timeout=10) as response:
                self.assertIn("default-src 'self'", response.headers["Content-Security-Policy"])
                self.assertEqual(response.headers["X-Content-Type-Options"], "nosniff")
                self.assertEqual(response.headers["X-Frame-Options"], "DENY")
                self.assertEqual(response.headers["Referrer-Policy"], "no-referrer")
                self.assertIn("camera=()", response.headers["Permissions-Policy"])
        self.assertIn("script-src 'self' 'unsafe-inline'", response.headers["Content-Security-Policy"])

    def test_food_groceries_recipes_and_pantry_validate_and_persist(self):
        status, grocery = self.post_json("/api/food/groceries", {"item": "Eggs", "quantity": "1 dozen"})
        self.assertEqual(status, 201)
        self.assertFalse(grocery["checked"])
        status, checked = self.post_json("/api/food/groceries/toggle", {"id": grocery["id"], "checked": True})
        self.assertEqual(status, 200)
        self.assertTrue(checked["checked"])
        self.assertEqual(self.get_json("/api/food/groceries")[1], [checked])
        status, _ = self.post_json("/api/food/groceries/toggle", {"id": grocery["id"], "checked": "yes"})
        self.assertEqual(status, 400)

        status, recipe = self.post_json("/api/food/recipes", {
            "title": "Roast dinner", "ingredients": "Roast; olive oil", "instructions": "Check labels first."
        })
        self.assertEqual(status, 201)
        self.assertEqual(self.get_json("/api/food/recipes")[1], [recipe])
        status, pantry = self.post_json("/api/food/pantry", {
            "item": "Rice", "quantity": "One bag", "expiry_date": "2032-12-31", "notes": "Top shelf"
        })
        self.assertEqual(status, 201)
        self.assertEqual(self.get_json("/api/food/pantry")[1], [pantry])
        for route, payload in (
            ("/api/food/groceries", {"item": ""}),
            ("/api/food/recipes", {"title": "Recipe", "ingredients": "x" * 5001}),
            ("/api/food/pantry", {"item": "Rice", "expiry_date": "2032-02-30"}),
        ):
            status, error = self.post_json(route, payload)
            self.assertEqual(status, 400)
            self.assertTrue(error["error"])
        for route, record in (("/api/food/groceries/delete", grocery),
                              ("/api/food/recipes/delete", recipe),
                              ("/api/food/pantry/delete", pantry)):
            status, result = self.post_json(route, {"id": record["id"]})
            self.assertEqual((status, result), (200, {"deleted": True}))
        self.assertEqual(self.get_json("/api/food/groceries")[1], [])
        self.assertEqual(self.get_json("/api/food/recipes")[1], [])
        self.assertEqual(self.get_json("/api/food/pantry")[1], [])

    def test_food_meal_plan_is_included_in_json_export(self):
        app.save_food_meal({
            "meal_date": "2032-03-01",
            "meal_type": "lunch",
            "title": "Planned leftovers",
        })
        exported = app.backup.export_json(app.DATA_FILE)
        self.assertEqual(exported["tables"]["food_meal_plan"][0]["title"], "Planned leftovers")

    def test_json_import_route_requires_confirmation_and_saves_safety_backup(self):
        with app.db_connect() as conn:
            conn.execute("INSERT INTO entries(area,title) VALUES('todos','from export')")
            project_id = conn.execute("INSERT INTO projects(title) VALUES('Project in export')").lastrowid
            conn.execute("INSERT INTO project_materials(project_id,name) VALUES(?, 'Material in export')", (project_id,))
            conversation_id = conn.execute("INSERT INTO conversations(title) VALUES('Conversation in export')").lastrowid
            conn.execute("INSERT INTO conversation_messages(conversation_id,role,content) VALUES(?, 'user', 'Message in export')", (conversation_id,))
        export = json.dumps(app.backup.export_json(app.DATA_FILE))
        with app.db_connect() as conn:
            conn.execute("INSERT INTO entries(area,title) VALUES('todos','must be replaced')")
        status, rejected = self.post_json("/api/import/json", {"json_text": export})
        self.assertEqual(status, 400)
        self.assertIn("Confirm", rejected["error"])
        status, result = self.post_json("/api/import/json", {"json_text": export, "confirm": True})
        self.assertEqual(status, 200)
        self.assertTrue((self.root / "backups" / result["pre_import_backup"]).is_file())
        with app.db_connect() as conn:
            titles = [row[0] for row in conn.execute("SELECT title FROM entries ORDER BY id")]
        self.assertIn("from export", titles)
        self.assertNotIn("must be replaced", titles)
        with app.db_connect() as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM project_materials").fetchone()[0], 1)
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM conversation_messages").fetchone()[0], 1)
        invalid_export = json.loads(export)
        message = dict(invalid_export["tables"]["conversation_messages"][0])
        message["id"] = 10000
        message["conversation_id"] = 999999
        invalid_export["tables"]["conversation_messages"].append(message)
        status, rejected = self.post_json("/api/import/json", {
            "json_text": json.dumps(invalid_export), "confirm": True,
        })
        self.assertEqual(status, 400)
        self.assertIn("invalid relationships", rejected["error"])
        with app.db_connect() as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM entries WHERE title='from export'").fetchone()[0], 1)
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM conversation_messages").fetchone()[0], 1)

    def test_entries_can_be_restored_or_permanently_removed_from_recycle_bin(self):
        with app.db_connect() as conn:
            conn.execute("INSERT INTO entries(area,title,content) VALUES('todos','Recover me','saved detail')")
            entry_id = conn.execute("SELECT id FROM entries WHERE title='Recover me'").fetchone()[0]
        status, deleted = self.post_json("/api/entries/delete", {"id": entry_id})
        self.assertEqual((status, deleted), (200, {"deleted": True}))
        _, active = self.get_json("/api/entries/todos")
        _, trash = self.get_json("/api/entries/deleted")
        self.assertFalse(any(row["id"] == entry_id for row in active))
        trashed = next(row for row in trash if row["title"] == "Recover me")
        self.assertEqual(trashed["content"], "saved detail")
        status, restored = self.post_json("/api/entries/restore", {"id": trashed["id"]})
        self.assertEqual((status, restored["id"], restored["area"]), (200, entry_id, "todos"))
        _, active = self.get_json("/api/entries/todos")
        self.assertTrue(any(row["id"] == entry_id for row in active))
        self.post_json("/api/entries/delete", {"id": entry_id})
        _, trash = self.get_json("/api/entries/deleted")
        trashed = next(row for row in trash if row["title"] == "Recover me")
        status, rejected = self.post_json("/api/entries/purge", {"id": trashed["id"]})
        self.assertEqual(status, 400)
        self.assertIn("Confirm", rejected["error"])
        status, result = self.post_json("/api/entries/purge", {"id": trashed["id"], "confirm": True})
        self.assertEqual((status, result), (200, {"deleted": True, "permanent": True}))
        _, trash = self.get_json("/api/entries/deleted")
        self.assertFalse(any(row["title"] == "Recover me" for row in trash))

    def test_subtasks_survive_recycle_restore_and_are_removed_on_permanent_delete(self):
        _, parent = self.post_json("/api/entries", {"area": "todos", "title": "Parent task"})
        status, subtask = self.post_json("/api/subtasks", {"entry_id": parent["id"], "title": "First step"})
        self.assertEqual((status, subtask["completed"]), (201, False))
        status, updated = self.post_json("/api/subtasks/toggle", {"id": subtask["id"], "completed": True})
        self.assertEqual((status, updated["completed"]), (200, True))
        _, active = self.get_json("/api/entries/todos")
        self.assertEqual(active[0]["subtasks"][0]["title"], "First step")
        self.post_json("/api/entries/delete", {"id": parent["id"]})
        _, trash = self.get_json("/api/entries/deleted")
        deleted = next(row for row in trash if row["title"] == "Parent task")
        self.post_json("/api/entries/restore", {"id": deleted["id"]})
        _, active = self.get_json("/api/entries/todos")
        restored = next(row for row in active if row["title"] == "Parent task")
        self.assertEqual(restored["subtasks"][0]["title"], "First step")
        self.post_json("/api/entries/delete", {"id": parent["id"]})
        _, trash = self.get_json("/api/entries/deleted")
        deleted = next(row for row in trash if row["title"] == "Parent task")
        status, _ = self.post_json("/api/entries/purge", {"id": deleted["id"], "confirm": True})
        self.assertEqual(status, 200)
        _, children = self.get_json(f"/api/subtasks?entry_id={parent['id']}")
        self.assertEqual(children, [])

    def test_todo_due_time_is_saved_and_validated(self):
        status, created = self.post_json("/api/entries", {
            "area": "todos", "title": "Timed task", "due_date": "2031-04-05", "due_time": "14:30", "priority": 1, "tags": "bills",
        })
        self.assertEqual((status, created["due_date"], created["due_time"], created["priority"], created["tags"]), (201, "2031-04-05", "14:30", 1, "bills"))
        status, rejected = self.post_json("/api/entries", {
            "area": "todos", "title": "Bad time", "due_date": "2031-04-05", "due_time": "25:00",
        })
        self.assertEqual(status, 400)
        self.assertIn("HH:MM", rejected["error"])
        status, rejected = self.post_json("/api/entries", {
            "area": "todos", "title": "Time without date", "due_time": "14:30",
        })
        self.assertEqual(status, 400)
        self.assertIn("requires a to-do due date", rejected["error"])

    def test_recurring_todos_generate_next_month_once_and_restore(self):
        status, task = self.post_json("/api/entries", {
            "area": "todos", "title": "Monthly review", "due_date": "2031-01-31", "due_time": "09:15", "priority": 1, "tags": "home", "recurrence": "monthly",
        })
        self.assertEqual((status, task["recurrence"], task["recurrence_series_id"]), (201, "monthly", task["id"]))
        status, completed = self.post_json("/api/entries/toggle", {"id": task["id"], "completed": True})
        self.assertEqual(status, 200)
        _, entries = self.get_json("/api/entries/todos")
        next_task = next(item for item in entries if item["id"] != task["id"] and item["recurrence_series_id"] == task["id"])
        self.assertEqual((next_task["due_date"], next_task["due_time"], next_task["recurrence"]), ("2031-02-28", "09:15", "monthly"))
        self.post_json("/api/entries/toggle", {"id": task["id"], "completed": False})
        self.post_json("/api/entries/toggle", {"id": task["id"], "completed": True})
        _, entries = self.get_json("/api/entries/todos")
        self.assertEqual(sum(item["recurrence_series_id"] == task["id"] for item in entries), 2)
        self.post_json("/api/entries/delete", {"id": next_task["id"]})
        _, trash = self.get_json("/api/entries/deleted")
        self.assertEqual(next(item for item in trash if item["original_id"] == next_task["id"])["recurrence"], "monthly")
        restored = self.post_json("/api/entries/restore", {"id": next(item for item in trash if item["original_id"] == next_task["id"])["id"]})
        self.assertEqual(restored[0], 200)

    def test_todo_order_can_be_rearranged_and_is_persisted(self):
        _, first = self.post_json("/api/entries", {"area": "todos", "title": "First task", "priority": 1})
        _, second = self.post_json("/api/entries", {"area": "todos", "title": "Second task", "priority": 3})
        _, items = self.get_json("/api/entries/todos")
        self.assertEqual([item["id"] for item in items[:2]], [first["id"], second["id"]])
        status, result = self.post_json("/api/entries/reorder", {"ids": [second["id"], first["id"]]})
        self.assertEqual((status, result["ids"]), (200, [second["id"], first["id"]]))
        _, items = self.get_json("/api/entries/todos")
        self.assertEqual([item["id"] for item in items[:2]], [second["id"], first["id"]])
        _, today = self.get_json("/api/today")
        self.assertEqual([item["id"] for item in today["focus_tasks"][:2]], [second["id"], first["id"]])
        for invalid in ([second["id"]], [first["id"], first["id"]], [True, second["id"]], [second["id"], first["id"], 999999]):
            status, error = self.post_json("/api/entries/reorder", {"ids": invalid})
            self.assertEqual(status, 400)
            self.assertTrue(error["error"])

    def test_recurring_todos_validate_schedule_and_date(self):
        for values in (
            {"recurrence": "weekly"},
            {"recurrence": "daily", "due_date": "2031-02-30"},
            {"recurrence": ["daily"], "due_date": "2031-02-01"},
        ):
            status, error = self.post_json("/api/entries", {"area": "todos", "title": "Invalid repeat", **values})
            self.assertEqual(status, 400)
            self.assertTrue(error["error"])
        self.assertEqual(app.next_recurrence_date("2031-12-31", "daily"), "2032-01-01")
        self.assertEqual(app.next_recurrence_date("2031-12-31", "weekly"), "2032-01-07")
        self.assertIsNone(app.next_recurrence_date("9999-12-31", "monthly"))

    def test_task_priority_and_tags_are_validated_stored_and_ordered(self):
        for title, priority, tags in [("Later task", 3, "home"), ("High task", 1, "home, errands")]:
            status, created = self.post_json("/api/entries", {
                "area": "todos", "title": title, "priority": priority, "tags": tags,
            })
            self.assertEqual((status, created["priority"], created["tags"]), (201, priority, tags.replace(", ", ",")))
        _, entries = self.get_json("/api/entries/todos")
        self.assertEqual(entries[0]["title"], "High task")
        for invalid in [
            {"priority": 0, "tags": "ok"},
            {"priority": 2, "tags": "bad/tag"},
            {"priority": 2, "tags": ",".join(f"tag{i}" for i in range(13))},
        ]:
            status, body = self.post_json("/api/entries", {
                "area": "todos", "title": "Invalid task", **invalid,
            })
            self.assertEqual(status, 400)
            self.assertTrue(body["error"])

    def test_weekly_review_summarizes_this_weeks_tasks(self):
        now = datetime.now()
        week_start = (now.date() - timedelta(days=now.weekday())).isoformat()
        _, completed = self.post_json("/api/entries", {"area": "todos", "title": "Weekly completed"})
        self.post_json("/api/entries/toggle", {"id": completed["id"], "completed": True})
        overdue_date = (now.date() - timedelta(days=1)).isoformat()
        due_date = (now.date() + timedelta(days=6 - now.weekday())).isoformat()
        _, overdue = self.post_json("/api/entries", {"area": "todos", "title": "Weekly overdue", "due_date": overdue_date})
        _, due = self.post_json("/api/entries", {"area": "todos", "title": "Weekly upcoming", "due_date": due_date})
        status, review = self.get_json("/api/weekly-review")
        self.assertEqual(status, 200)
        self.assertEqual(review["week_start"], week_start)
        self.assertIn(completed["id"], [item["id"] for item in review["completed"]])
        self.assertIn(overdue["id"], [item["id"] for item in review["overdue"]])
        self.assertIn(due["id"], [item["id"] for item in review["due_this_week"]])
        self.assertEqual(review["open_count"], 2)

    def test_done_today_tracks_completion_and_reopen(self):
        status, task = self.post_json("/api/entries", {"area": "todos", "title": "Finish today"})
        self.assertEqual(status, 201)
        status, completed = self.post_json("/api/entries/toggle", {"id": task["id"], "completed": True})
        self.assertEqual(status, 200)
        self.assertTrue(completed["completed_at"])
        _, today = self.get_json("/api/today")
        self.assertIn(task["id"], [item["id"] for item in today["done_today"]])
        status, reopened = self.post_json("/api/entries/toggle", {"id": task["id"], "completed": False})
        self.assertEqual((status, reopened["completed_at"]), (200, None))
        _, today = self.get_json("/api/today")
        self.assertNotIn(task["id"], [item["id"] for item in today["done_today"]])

    def test_focus_tasks_follow_priority_order_and_exclude_snoozed_entries(self):
        _, later = self.post_json("/api/entries", {"area": "todos", "title": "Later focus", "priority": 3})
        _, high = self.post_json("/api/entries", {"area": "todos", "title": "High focus", "priority": 1})
        self.post_json("/api/entries/snooze", {"id": high["id"], "minutes": 60})
        _, today = self.get_json("/api/today")
        self.assertEqual([item["id"] for item in today["focus_tasks"]], [later["id"]])

    def test_snooze_hides_tasks_from_today_and_can_be_cleared(self):
        due_today = app.datetime.now().strftime("%Y-%m-%d")
        status, task = self.post_json("/api/entries", {
            "area": "todos", "title": "Snoozable", "due_date": due_today,
        })
        self.assertEqual(status, 201)
        _, today = self.get_json("/api/today")
        self.assertTrue(any(item["id"] == task["id"] for item in today["due_today"]))
        status, snoozed = self.post_json("/api/entries/snooze", {"id": task["id"], "minutes": 60})
        self.assertEqual(status, 200)
        self.assertTrue(snoozed["snoozed_until"])
        _, today = self.get_json("/api/today")
        self.assertFalse(any(item["id"] == task["id"] for item in today["due_today"]))
        self.assertTrue(any(item["id"] == task["id"] for item in today["snoozed"]))
        status, unsnoozed = self.post_json("/api/entries/snooze", {"id": task["id"], "minutes": 0})
        self.assertEqual((status, unsnoozed["snoozed_until"]), (200, None))
        _, today = self.get_json("/api/today")
        self.assertTrue(any(item["id"] == task["id"] for item in today["due_today"]))
        for payload in ({"id": task["id"], "minutes": 10}, {"id": task["id"], "minutes": []}, {"id": task["id"], "minutes": True}):
            status, body = self.post_json("/api/entries/snooze", payload)
            self.assertEqual(status, 400)
            self.assertIn("snooze duration", body["error"])
        status, body = self.post_json("/api/entries/snooze", {"id": 999999, "minutes": 60})
        self.assertEqual(status, 400)
        self.assertIn("not found", body["error"])

    def test_monthly_category_budgets_compare_to_entered_recurring_costs(self):
        for title, category, amount, frequency in (
            ("Rent", "Housing", 1200, "monthly"),
            ("Insurance", "housing", 600, "yearly"),
            ("Groceries", "Food", 400, "monthly"),
            ("One-time repair", "Housing", 100, "once"),
        ):
            status, _ = self.post_json("/api/finance", {
                "direction": "expense", "title": title, "category": category,
                "amount": amount, "frequency": frequency,
            })
            self.assertEqual(status, 201)

        status, budget = self.post_json("/api/finance/budget", {"category": " Housing ", "amount": 1500})
        self.assertEqual((status, budget), (201, {"category": "Housing", "amount": 1500.0}))
        status, updated = self.post_json("/api/finance/budget", {"category": "housing", "amount": 1800})
        self.assertEqual((status, updated["amount"]), (201, 1800.0))

        status, finances = self.get_json("/api/finances")
        self.assertEqual(status, 200)
        self.assertEqual(len(finances["budgets"]), 1)
        self.assertEqual(finances["budgets"][0], {
            "category": "Housing", "amount": 1800.0,
            "monthly_expenses": 1250.0, "remaining": 550.0,
        })
        exported = app.backup.export_json(app.DATA_FILE)
        self.assertIn("finance_budgets", exported["tables"])
        self.assertEqual(exported["tables"]["finance_budgets"][0]["amount_cents"], 180000)

        for invalid in (
            {"category": " ", "amount": 20},
            {"category": "Food", "amount": 0},
            {"category": "Food", "amount": "NaN"},
            {"category": "F" * 61, "amount": 20},
        ):
            status, body = self.post_json("/api/finance/budget", invalid)
            self.assertEqual(status, 400)
            self.assertIn("budget", body["error"].lower())

        status, result = self.post_json("/api/finance/budget/delete", {"category": "HOUSING"})
        self.assertEqual((status, result), (200, {"deleted": True}))
        self.assertEqual(self.get_json("/api/finances")[1]["budgets"], [])

    def test_net_worth_snapshot_aggregates_manual_assets_and_liabilities(self):
        for item_type, title, category, amount in (
            ("asset", "Savings", "Cash", 1500.25),
            ("asset", "Car", "Vehicle", 3000),
            ("liability", "Loan", "Vehicle", 750),
        ):
            status, body = self.post_json("/api/finance/net-worth", {
                "item_type": item_type, "title": title, "category": category, "amount": amount,
            })
            self.assertEqual(status, 201, body)
        snapshot = self.get_json("/api/finance/net-worth")[1]
        self.assertEqual((snapshot["assets"], snapshot["liabilities"], snapshot["net_worth"]),
                         (4500.25, 750.0, 3750.25))
        self.assertEqual(len(snapshot["items"]), 3)

        for payload in (
            {"item_type": "other", "title": "Invalid", "amount": 1},
            {"item_type": "asset", "title": "", "amount": 1},
            {"item_type": "liability", "title": "Invalid amount", "amount": "inf"},
            {"item_type": "liability", "title": "Invalid category", "category": "x" * 61, "amount": 1},
        ):
            status, body = self.post_json("/api/finance/net-worth", payload)
            self.assertEqual(status, 400)
            self.assertTrue(body["error"])
        self.assertEqual(len(app.backup.export_json(app.DATA_FILE)["tables"]["finance_net_worth_items"]), 3)
        status, result = self.post_json("/api/finance/net-worth/delete", {"id": snapshot["items"][0]["id"]})
        self.assertEqual((status, result), (200, {"deleted": True}))

    def test_debt_payoff_projection_handles_interest_extra_payments_and_validation(self):
        status, zero_interest = self.post_json("/api/finance/debts", {
            "title": "No-interest balance", "balance": 1200, "apr_percent": 0, "monthly_payment": 100,
        })
        self.assertEqual(status, 201)
        self.assertEqual((zero_interest["payoff_months"], zero_interest["total_interest"], zero_interest["total_paid"]),
                         (12, 0, 1200.0))

        status, base = self.post_json("/api/finance/debts", {
            "title": "Card", "balance": 1200, "apr_percent": 12, "monthly_payment": 110,
        })
        self.assertEqual(status, 201)
        status, faster = self.post_json("/api/finance/debts", {
            "title": "Card with extra", "balance": 1200, "apr_percent": 12,
            "monthly_payment": 110, "extra_payment": 30,
        })
        self.assertEqual(status, 201)
        self.assertLess(faster["payoff_months"], base["payoff_months"])
        self.assertLess(faster["total_interest"], base["total_interest"])

        status, not_amortizing = self.post_json("/api/finance/debts", {
            "title": "Payment below interest", "balance": 1000, "apr_percent": 100,
            "monthly_payment": 1,
        })
        self.assertEqual(status, 201)
        self.assertIsNone(not_amortizing["payoff_months"])
        self.assertEqual(not_amortizing["monthly_interest"], 83.33)

        for payload in (
            {"title": "", "balance": 20, "apr_percent": 2, "monthly_payment": 2},
            {"title": "Bad balance", "balance": "NaN", "apr_percent": 2, "monthly_payment": 2},
            {"title": "Bad rate", "balance": 20, "apr_percent": 101, "monthly_payment": 2},
            {"title": "Bad payment", "balance": 20, "apr_percent": 2, "monthly_payment": 0},
            {"title": "Bad extra", "balance": 20, "apr_percent": 2, "monthly_payment": 2, "extra_payment": "NaN"},
        ):
            status, body = self.post_json("/api/finance/debts", payload)
            self.assertEqual(status, 400)
            self.assertTrue(body["error"])
        self.assertEqual(len(app.backup.export_json(app.DATA_FILE)["tables"]["finance_debts"]), 4)
        status, result = self.post_json("/api/finance/debts/delete", {"id": faster["id"]})
        self.assertEqual((status, result), (200, {"deleted": True}))
        self.assertNotIn(faster["id"], [item["id"] for item in app.list_debts()])

    def test_savings_goals_track_validated_dated_contributions_and_export(self):
        status, goal = self.post_json("/api/finance/savings", {
            "title": " Emergency fund ", "target_amount": 1000,
            "target_date": "2027-06-01", "note": "Local target",
        })
        self.assertEqual(status, 201)
        goal_id = goal["id"]
        self.assertEqual((goal["title"], goal["target_amount"], goal["saved_amount"], goal["progress_percent"]),
                         ("Emergency fund", 1000.0, 0.0, 0))

        status, updated = self.post_json("/api/finance/savings/contribution", {
            "goal_id": goal_id, "amount": 125.50, "date": "2026-10-03", "note": "First deposit",
        })
        self.assertEqual(status, 201)
        self.assertEqual((updated["saved_amount"], updated["remaining_amount"], updated["progress_percent"]),
                         (125.5, 874.5, 12.6))
        status, over_target = self.post_json("/api/finance/savings/contribution", {
            "goal_id": goal_id, "amount": 1000, "date": "2026-10-04",
        })
        self.assertEqual(status, 201)
        self.assertEqual((over_target["saved_amount"], over_target["remaining_amount"], over_target["progress_percent"]),
                         (1125.5, 0, 100))
        self.assertEqual(over_target["contribution_count"], 2)

        invalid_requests = (
            ("/api/finance/savings", {"title": "", "target_amount": 10}),
            ("/api/finance/savings", {"title": "Invalid amount", "target_amount": "NaN"}),
            ("/api/finance/savings", {"title": "Invalid date", "target_amount": 10, "target_date": "20270230"}),
            ("/api/finance/savings/contribution", {"goal_id": 99999, "amount": 2}),
            ("/api/finance/savings/contribution", {"goal_id": goal_id, "amount": 0}),
            ("/api/finance/savings/contribution", {"goal_id": goal_id, "amount": 2, "date": "20261003"}),
        )
        for route, payload in invalid_requests:
            status, body = self.post_json(route, payload)
            self.assertEqual(status, 400)
            self.assertTrue(body["error"])

        exported = app.backup.export_json(app.DATA_FILE)
        self.assertEqual(len(exported["tables"]["finance_savings_goals"]), 1)
        self.assertEqual(len(exported["tables"]["finance_savings_contributions"]), 2)
        status, result = self.post_json("/api/finance/savings/contribution/delete", {"id": over_target["contributions"][0]["id"]})
        self.assertEqual((status, result), (200, {"deleted": True}))
        status, result = self.post_json("/api/finance/savings/delete", {"id": goal_id})
        self.assertEqual((status, result), (200, {"deleted": True}))
        with app.db_connect() as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM finance_savings_contributions").fetchone()[0], 0)

    def test_yearly_finance_report_summarizes_manual_transactions_and_exports_csv(self):
        for direction, title, category, amount, transaction_date in (
            ("income", "Pay", "Work", 2500, "2025-01-03"),
            ("expense", "Groceries", "Food", 50, "2025-02-10"),
            ("expense", "Market", "food", 15, "2025-12-31"),
            ("expense", "Old bill", "Home", 100, "2024-12-31"),
        ):
            status, body = self.post_json("/api/finance/transaction", {
                "direction": direction, "title": title, "category": category,
                "amount": amount, "date": transaction_date,
            })
            self.assertEqual(status, 201, body)

        status, invalid_date = self.post_json("/api/finance/transaction", {
            "direction": "expense", "title": "Bad date", "amount": 1, "date": "20250104",
        })
        self.assertEqual(status, 400)
        self.assertIn("YYYY-MM-DD", invalid_date["error"])

        status, report = self.get_json("/api/finance/report?year=2025")
        self.assertEqual(status, 200)
        self.assertEqual((report["income"], report["expenses"], report["net"]), (2500.0, 65.0, 2435.0))
        self.assertEqual(report["months"][0], {"month": "2025-01", "income": 2500.0, "expenses": 0.0})
        self.assertEqual(report["months"][11], {"month": "2025-12", "income": 0.0, "expenses": 15.0})
        self.assertEqual(report["categories"], [{"category": "food", "amount": 65.0}])
        self.assertEqual(len(report["transactions"]), 3)

        for invalid in ("0", "10000", "not-a-year"):
            status, body = self.get_json_error("/api/finance/report?year=" + invalid)
            self.assertEqual(status, 400)
            self.assertIn("report year", body["error"].lower())
        with urllib.request.urlopen(self.base + "/api/finance/report.csv?year=2025", timeout=10) as response:
            csv_text = response.read().decode("utf-8-sig")
            self.assertIn("Year-end summary", csv_text)
            self.assertIn("Groceries", csv_text)
            self.assertIn("2435.0", csv_text)
        status, bad_export = self.get_json_error("/api/finance/report.csv?year=%0d%0aInjected%3A%20value")
        self.assertEqual(status, 400)
        self.assertIn("report year", bad_export["error"].lower())
        exported = app.backup.export_json(app.DATA_FILE)
        self.assertEqual(len(exported["tables"]["finance_transactions"]), 4)

    def test_finance_report_csv_escapes_spreadsheet_formula_cells(self):
        status, _ = self.post_json("/api/finance/transaction", {
            "direction": "expense", "title": "=1+1", "category": "@budget", "amount": 5, "date": "2025-01-01",
        })
        self.assertEqual(status, 201)
        with urllib.request.urlopen(self.base + "/api/finance/report.csv?year=2025", timeout=10) as response:
            csv_text = response.read().decode("utf-8-sig")
        self.assertIn("'=1+1", csv_text)
        self.assertIn("'@budget", csv_text)

    def test_csv_import_route_appends_valid_rows(self):
        with app.db_connect() as conn:
            conn.execute("SELECT 1")
        status, result = self.post_json("/api/import/csv", {
            "kind": "todos", "csv_text": "title,content,due_date\nImported through API,temporary,2031-01-02\n",
        })
        self.assertEqual((status, result["imported"], result["kind"]), (200, 1, "todos"))
        with app.db_connect() as conn:
            row = conn.execute("SELECT title,due_date FROM entries WHERE title='Imported through API'").fetchone()
            self.assertEqual(tuple(row), ("Imported through API", "2031-01-02"))

    def test_document_search_uses_incremental_full_text_index(self):
        with patch.object(app, "CONFIG_DIR", self.root):
            uploaded = app.store_uploaded_file({
                "name": "large-library.txt", "content": "WmVicmFmaXNoIGFyY2hpdmUgc2VhcmNoIGNvbnRlbnQu", "importance": "critical", "category": "General",
            })
            result = app.universal_search("zebrafish archive")
            self.assertIn(uploaded["id"], [item["id"] for item in result["results"] if item["kind"] == "file"])
            with app.db_connect() as conn:
                self.assertEqual(conn.execute("SELECT COUNT(*) FROM file_search WHERE file_id=?", (uploaded["id"],)).fetchone()[0], 1)
            app.uploaded_file(uploaded["id"]).write_text("Quokka notes and local document search.", encoding="utf-8")
            changed = app.universal_search("quokka notes")
            self.assertIn(uploaded["id"], [item["id"] for item in changed["results"] if item["kind"] == "file"])
            stale = app.universal_search("zebrafish archive")
            self.assertNotIn(uploaded["id"], [item["id"] for item in stale["results"] if item["kind"] == "file"])
            app.delete_uploaded_file(uploaded["id"])
            with app.db_connect() as conn:
                self.assertEqual(conn.execute("SELECT COUNT(*) FROM file_search WHERE file_id=?", (uploaded["id"],)).fetchone()[0], 0)

    def test_pdf_and_image_uploads_have_safe_preview_responses(self):
        with patch.object(app, "CONFIG_DIR", self.root):
            image = app.store_uploaded_file({
                "name": "pixel.png", "content": "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/lXcAAAAASUVORK5CYII=",
                "importance": "critical", "category": "General",
            })
            pdf = app.store_uploaded_file({
                "name": "sample.pdf", "content": "JVBERi0xLjQKJUVPRg==", "importance": "critical", "category": "General",
            })
            for item, mime in ((image, "image/png"), (pdf, "application/pdf")):
                with urllib.request.urlopen(self.base + "/api/files/" + item["id"] + "/preview", timeout=10) as response:
                    self.assertEqual(response.headers["Content-Type"], mime)
                    self.assertEqual(response.read(), app.uploaded_file(item["id"]).read_bytes())
            self.assertTrue(next(item for item in app.list_uploaded_files() if item["id"] == image["id"])["previewable"])
            self.assertFalse(next(item for item in app.list_uploaded_files() if item["id"] == image["id"])["supported"])

    def test_library_expiry_bulk_category_rename_and_duplicate_detection(self):
        first = app.store_uploaded_file({
            "name": "first.txt", "content": "c2VjdXJlIGZpbGUgY29udGVudA==", "importance": "critical", "category": "General",
        })
        second = app.store_uploaded_file({
            "name": "second.txt", "content": "c2Vjb25kIGZpbGUgY29udGVudA==", "importance": "critical", "category": "Other",
        })
        status, response = self.post_json("/api/library/expiry", {"id": first["id"], "expiry_date": "2032-11-30"})
        self.assertEqual((status, response["expiry_date"]), (200, "2032-11-30"))
        self.assertEqual(next(item for item in app.list_uploaded_files() if item["id"] == first["id"])["expiry_date"], "2032-11-30")
        for invalid in ("2032-02-30", "2032/11/30", 12):
            status, error = self.post_json("/api/library/expiry", {"id": first["id"], "expiry_date": invalid})
            self.assertEqual(status, 400)
            self.assertTrue(error["error"])
        status, updated = self.post_json("/api/library/category/bulk", {
            "ids": [first["id"], second["id"]], "category": "Legal"
        })
        self.assertEqual((status, updated["updated"]), (200, 2))
        self.assertEqual({item["category"] for item in app.list_uploaded_files()}, {"Legal"})
        status, error = self.post_json("/api/library/category/bulk", {
            "ids": [first["id"], "0" * 32], "category": "Home"
        })
        self.assertEqual(status, 400)
        self.assertEqual({item["category"] for item in app.list_uploaded_files()}, {"Legal"})
        status, renamed = self.post_json("/api/files/rename", {"id": first["id"], "name": "renamed.txt"})
        self.assertEqual((status, renamed["name"]), (200, "renamed.txt"))
        self.assertEqual(app.uploaded_file(first["id"]).read_bytes(), b"secure file content")
        self.assertEqual(self.get_json("/api/library?q=renamed&category=All")[1]["files"][0]["id"], first["id"])
        for invalid in ("../outside.txt", "bad.exe", "name?.txt", "x" * 201 + ".txt"):
            status, error = self.post_json("/api/files/rename", {"id": first["id"], "name": invalid})
            self.assertEqual(status, 400)
            self.assertTrue(error["error"])
        status, error = self.post_json("/api/files", {
            "name": "duplicate.txt", "content": "c2VjdXJlIGZpbGUgY29udGVudA==", "importance": "critical", "category": "General",
        })
        self.assertEqual(status, 400)
        self.assertIn("same contents", error["error"])
        filtered = self.get_json("/api/library?q=renamed&category=All")[1]
        self.assertEqual(filtered["storage"]["file_count"], 2)
        self.assertEqual(filtered["storage"]["total_bytes"], len(b"secure file content") + len(b"second file content"))

    def test_file_tags_are_normalized_validated_and_searchable(self):
        with patch.object(app, "CONFIG_DIR", self.root):
            uploaded = app.store_uploaded_file({
                "name": "tagged.txt", "content": "dGFnZ2VkIGNvbnRlbnQ=", "importance": "critical", "category": "General",
            })
        status, saved = self.post_json("/api/library/tags", {"id": uploaded["id"], "tags": " tax, yearly, tax "})
        self.assertEqual((status, saved["tags"]), (200, "tax,yearly"))
        status, result = self.get_json("/api/library?q=yearly&category=All")
        self.assertEqual(status, 200)
        self.assertEqual([item["id"] for item in result["files"]], [uploaded["id"]])
        for invalid in ("bad/tag", ",".join(f"tag{i}" for i in range(13)), "x" * 25):
            status, response = self.post_json("/api/library/tags", {"id": uploaded["id"], "tags": invalid})
            self.assertEqual(status, 400)
            self.assertTrue(response["error"])

    def test_excel_extraction_indexes_formulas_with_cached_values(self):
        workbook = self.root / "formulas.xlsx"
        with zipfile.ZipFile(workbook, "w") as archive:
            archive.writestr("xl/workbook.xml", '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="Budget" sheetId="1" r:id="rId1"/></sheets></workbook>')
            archive.writestr("xl/_rels/workbook.xml.rels", '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Target="worksheets/sheet1.xml" Type="worksheet"/></Relationships>')
            archive.writestr("xl/worksheets/sheet1.xml", '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData><row r="1"><c r="A1"><f>SUM(B1:B2)</f><v>42</v></c></row></sheetData></worksheet>')
        extracted = app.read_document_text(workbook)
        self.assertIn("A1=42 [formula: SUM(B1:B2)]", extracted)
        self.assertIn("SUM(B1:B2)", extracted)

    def test_search_results_include_filterable_dates(self):
        self.post_json("/api/entries", {"area": "todos", "title": "Filterable entry"})
        status, response = self.get_json("/api/search?q=Filterable")
        self.assertEqual(status, 200)
        result = next(item for item in response["results"] if item["title"] == "Filterable entry")
        self.assertEqual(result["kind"], "entry")
        self.assertTrue(result["date"])

    def test_calendar_returns_only_scheduled_tasks_for_requested_month(self):
        self.post_json("/api/entries", {"area": "todos", "title": "March task", "due_date": "2032-03-05"})
        self.post_json("/api/entries", {"area": "todos", "title": "April task", "due_date": "2032-04-01"})
        self.post_json("/api/entries", {"area": "todos", "title": "No date"})
        status, calendar = self.get_json("/api/calendar?month=2032-03")
        self.assertEqual(status, 200)
        self.assertEqual(calendar["month"], "2032-03")
        self.assertEqual([item["title"] for item in calendar["entries"]], ["March task"])
        self.assertEqual(calendar["bills"], [])
        app.save_finance({"direction": "expense", "title": "Rent", "amount": "900", "frequency": "monthly", "due_day": 31})
        self.assertEqual(self.get_json("/api/calendar?month=2032-02")[1]["bills"], [{"title": "Rent", "amount": 900.0, "due_date": "2032-02-29"}])
        for invalid in ("2032-13", "2032-3", "2032-03-01", "0000-01"):
            status, response = self.get_json_error("/api/calendar?month=" + invalid)
            self.assertEqual(status, 400)
            self.assertIn("Calendar month", response["error"])

    def test_health_route_checks_database(self):
        status, body = self.get_json("/api/health")
        self.assertEqual(status, 200)
        self.assertEqual(body, {"status": "ok"})

    def test_integrity_route_checks_database(self):
        with app.db_connect() as conn:
            conn.execute("SELECT 1")
        status, body = self.get_json("/api/integrity")
        self.assertEqual(status, 200)
        self.assertEqual(body, {"ok": True})

    def test_backup_inspect_verify_and_open_routes_use_temporary_paths(self):
        with app.db_connect() as conn:
            conn.execute("SELECT 1")
        created = app.backup.create_daily_backup(app.DATA_FILE, app.BACKUP_DIR, settings_path=app.CONFIG_FILE)
        self.assertTrue(created["created"])
        status, weekly = self.post_json("/api/backups/weekly", {"enabled": True})
        self.assertEqual(status, 200)
        self.assertTrue(weekly["enabled"])
        self.assertTrue(weekly["created"])
        self.assertTrue(json.loads((self.root / "settings.json").read_text())["weekly_backups"])
        status, disabled = self.post_json("/api/backups/weekly", {"enabled": False})
        self.assertEqual((status, disabled["enabled"]), (200, False))
        status, info = self.post_json("/api/backups/inspect", {"name": created["name"]})
        self.assertEqual(status, 200)
        self.assertIn("entries", [table["name"] for table in info["tables"]])
        status, result = self.post_json("/api/backups/verify", {"name": created["name"]})
        self.assertEqual((status, result), (200, {"valid": True}))
        status, result = self.post_json("/api/backups/inspect", {"name": "../outside.zip"})
        self.assertEqual(status, 400)
        with patch.object(app.os, "startfile", create=True) as open_folder:
            status, result = self.post_json("/api/backups/open", {})
        self.assertEqual((status, result), (200, {"opened": True}))
        open_folder.assert_called_once_with(str(self.root / "backups"))
        custom_dir = self.root / "custom backups"
        status, result = self.post_json("/api/backups/directory", {"backup_dir": str(custom_dir)})
        self.assertEqual(status, 200)
        self.assertEqual(result["backup_dir"], str(custom_dir.resolve()))
        self.assertEqual(app.BACKUP_DIR, custom_dir.resolve())
        self.assertEqual(json.loads((self.root / "settings.json").read_text())["backup_dir"], str(custom_dir.resolve()))
        status, _ = self.post_json("/api/backups/directory", {"backup_dir": "relative-folder"})
        self.assertEqual(status, 400)
        status, _ = self.post_json("/api/backups/directory", {"backup_dir": "\\\\server\\share"})
        self.assertEqual(status, 400)
        picked_dir = self.root / "picked backups"
        with patch("tkinter.Tk") as root_window, patch("tkinter.filedialog.askdirectory", return_value=str(picked_dir)) as picker:
            status, result = self.post_json("/api/backups/pick-directory", {})
        self.assertEqual(status, 200)
        self.assertEqual(result["backup_dir"], str(picked_dir.resolve()))
        picker.assert_called_once()
        root_window.return_value.destroy.assert_called_once()

    def test_unexpected_route_failure_is_logged_without_query_or_error_text(self):
        with patch.object(app, "list_areas", side_effect=OSError("private path detail")):
            with self.assertRaises(urllib.error.HTTPError) as caught:
                self.get_json("/api/areas?secret=not-for-log")
        self.assertEqual(caught.exception.code, 500)
        caught.exception.close()
        log = (self.root / "ava-errors.log").read_text(encoding="utf-8")
        self.assertIn("GET /api/areas failed (OSError)", log)
        self.assertNotIn("secret=not-for-log", log)
        self.assertNotIn("private path detail", log)


    def test_ollama_status_reports_selected_model_and_unavailable_service(self):
        config = {"model": "qwen2.5:3b", "ollama_url": "http://127.0.0.1:11434"}
        with patch.object(
            app.urllib.request, "urlopen", side_effect=lambda *_args, **_kwargs: BytesIO(
                json.dumps({"models": [{"name": "qwen2.5:3b"}, {"name": "other:latest"}]}).encode()
            )
        ):
            result = app.ollama_status(config)
            self.assertTrue(result["available"])
            self.assertTrue(result["model_available"])
            self.assertEqual(result["models"], ["qwen2.5:3b", "other:latest"])

        with patch.object(app.urllib.request, "urlopen", side_effect=urllib.error.URLError("offline")):
            result = app.ollama_status(config)
            self.assertFalse(result["available"])
            self.assertIn("Could not reach", result["message"])

    def test_note_to_tasks_validates_and_inserts_selected_titles_atomically(self):
        before = len(app.list_entries("todos"))
        status, result = self.post_json("/api/tasks/from-note", {
            "tasks": ["Call the dentist", "Compare project options"],
        })
        self.assertEqual(status, 201)
        self.assertEqual([task["title"] for task in result["tasks"]], ["Call the dentist", "Compare project options"])
        self.assertEqual(len(app.list_entries("todos")), before + 2)
        for tasks in ([], [""], ["x" * 161], [f"task {i}" for i in range(21)], ["valid", None]):
            status, error = self.post_json("/api/tasks/from-note", {"tasks": tasks})
            self.assertEqual(status, 400)
            self.assertTrue(error["error"])
        self.assertEqual(len(app.list_entries("todos")), before + 2)

    def test_assistant_today_and_goals_context_is_explicitly_opt_in(self):
        app.save_entry({"area": "todos", "title": "Prepare appointment notes", "due_date": "2030-05-10"})
        completed = app.save_entry({"area": "todos", "title": "Send the project update"})
        app.update_entry({"id": completed["id"], "completed": True})
        goal = app.save_goal({"title": "Finish certification", "description": "Study the practice materials", "priority": 1})
        config = {"docs_path": str(self.root / "documents"), "model": "test-model", "ollama_url": "http://127.0.0.1:11434"}
        response_bytes = json.dumps({"message": {"content": "A local answer."}}).encode()

        with patch.object(app, "documents", return_value=[]), patch.object(
            app.urllib.request, "urlopen", side_effect=lambda *_args, **_kwargs: BytesIO(response_bytes)
        ) as urlopen:
            app.ollama_chat(config, "What should I focus on?", [], include_today_goals=False)
            without_context = json.loads(urlopen.call_args.args[0].data)["messages"][0]["content"]
            self.assertNotIn("Prepare appointment notes", without_context)
            self.assertNotIn("Finish certification", without_context)

            app.ollama_chat(config, "What should I focus on?", [], include_today_goals=True)
            with_context = json.loads(urlopen.call_args.args[0].data)["messages"][0]["content"]
            self.assertIn("Prepare appointment notes", with_context)
            self.assertIn("Send the project update", with_context)
            self.assertIn("Finish certification", with_context)
            self.assertIn("USER-APPROVED TODAY AND GOALS CONTEXT", with_context)

        with patch.object(app, "ollama_chat", return_value={"answer": "Local answer.", "sources": []}) as chat:
            status, result = self.post_json("/api/chat", {"question": "What next?", "include_today_goals": True})
            self.assertEqual(status, 200)
            self.assertEqual(result["answer"], "Local answer.")
            self.assertTrue(chat.call_args.args[-1])
        status, error = self.post_json("/api/chat", {"question": "What next?", "include_today_goals": "yes"})
        self.assertEqual(status, 400)
        self.assertIn("Choose whether", error["error"])

        with patch.object(app, "ollama_chat", return_value={"answer": "Today's summary.", "sources": []}) as summary:
            status, result = self.post_json("/api/assistant/daily-summary", {})
            self.assertEqual((status, result["summary"]), (200, "Today's summary."))
            self.assertTrue(summary.call_args.kwargs["include_today_goals"])

        with patch.object(app, "ollama_chat", return_value={"answer": "Review one practice topic.", "sources": []}) as suggestion:
            status, result = self.post_json("/api/goals/next-steps", {"id": goal["id"]})
            self.assertEqual((status, result["suggestions"]), (200, "Review one practice topic."))
            self.assertIn("Finish certification", suggestion.call_args.args[1])
            self.assertTrue(suggestion.call_args.kwargs["include_today_goals"])
        status, error = self.post_json("/api/goals/next-steps", {"id": "missing"})
        self.assertEqual(status, 400)
        self.assertIn("valid goal", error["error"])


if __name__ == "__main__":
    unittest.main()
