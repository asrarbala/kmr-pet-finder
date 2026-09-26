import asyncio
import json
import os
import sqlite3
import tempfile
import unittest
from contextlib import closing


SAMPLE_POST = {
    "status": "LOST",
    "species": "dog",
    "breed": "Kashmiri Sheepdog",
    "pet_name": "Buddy",
    "description": "Brown dog with a red collar",
    "area": "Lal Chowk",
    "district": "Srinagar",
    "event_date": "2026-09-26",
    "contact_name": "Amina",
    "contact_phone": "9876543210",
}


class OwnershipTests(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):
        cls.project_dir = os.getcwd()
        cls.temp_dir = tempfile.TemporaryDirectory()
        os.chdir(cls.temp_dir.name)

        # Start with an old database so the startup upgrade and legacy ownership are exercised.
        with closing(sqlite3.connect("pets.db")) as connection:
            connection.execute("""
                CREATE TABLE pet_posts (
                    id INTEGER PRIMARY KEY, status VARCHAR(5) NOT NULL,
                    species VARCHAR NOT NULL, breed VARCHAR, pet_name VARCHAR,
                    description TEXT NOT NULL, area VARCHAR NOT NULL,
                    district VARCHAR NOT NULL, event_date DATE NOT NULL,
                    contact_name VARCHAR NOT NULL, contact_phone VARCHAR NOT NULL,
                    contact_email VARCHAR, photo_url VARCHAR, created_at DATETIME NOT NULL
                )
            """)
            connection.execute("""
                INSERT INTO pet_posts (
                    status, species, breed, description, area, district,
                    event_date, contact_name, contact_phone, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                "LOST", "dog", None, "Legacy post", "Lal Chowk", "Srinagar",
                "2026-09-26", "Amina", "9876543210", "2026-09-26 12:00:00",
            ))
            connection.commit()

        import main
        from database import engine

        cls.app = main.app
        cls.engine = engine

    @classmethod
    def tearDownClass(cls):
        cls.engine.dispose()
        os.chdir(cls.project_dir)
        cls.temp_dir.cleanup()

    async def request(self, method, path, payload=None, token=None):
        body = json.dumps(payload).encode() if payload is not None else b""
        headers = [(b"content-type", b"application/json")]
        if token is not None:
            headers.append((b"x-edit-token", token.encode()))
        scope = {
            "type": "http",
            "asgi": {"version": "3.0"},
            "http_version": "1.1",
            "method": method,
            "scheme": "http",
            "path": path,
            "raw_path": path.encode(),
            "query_string": b"",
            "root_path": "",
            "headers": headers,
            "client": ("test", 12345),
            "server": ("test", 80),
        }
        sent = []
        received = False

        async def receive():
            nonlocal received
            if not received:
                received = True
                return {"type": "http.request", "body": body, "more_body": False}
            await asyncio.Event().wait()

        async def send(message):
            sent.append(message)

        await self.app(scope, receive, send)
        status = next(message["status"] for message in sent if message["type"] == "http.response.start")
        content = b"".join(message.get("body", b"") for message in sent if message["type"] == "http.response.body")
        return status, json.loads(content) if content else None

    async def test_create_read_update_delete(self):
        status, created = await self.request("POST", "/pets", SAMPLE_POST)
        self.assertEqual(status, 201)
        token = created["edit_token"]
        self.assertTrue(token)
        post_id = created["id"]

        with closing(sqlite3.connect("pets.db")) as connection:
            stored_hash = connection.execute(
                "SELECT edit_token_hash FROM pet_posts WHERE id = ?", (post_id,)
            ).fetchone()[0]
        self.assertIsNotNone(stored_hash)
        self.assertNotEqual(stored_hash, token)

        for path in ("/pets", f"/pets/{post_id}"):
            status, public = await self.request("GET", path)
            self.assertEqual(status, 200)
            post = public[0] if isinstance(public, list) else public
            self.assertNotIn("edit_token", post)
            self.assertNotIn("edit_token_hash", post)
            self.assertEqual(post["breed"], "Kashmiri Sheepdog")

        changed = {**SAMPLE_POST, "pet_name": "Buddy II"}
        for missing_or_wrong in (None, "wrong-token"):
            status, _ = await self.request("PUT", f"/pets/{post_id}", changed, missing_or_wrong)
            self.assertEqual(status, 403)
            status, _ = await self.request("DELETE", f"/pets/{post_id}", token=missing_or_wrong)
            self.assertEqual(status, 403)

        status, updated = await self.request("PUT", f"/pets/{post_id}", changed, token)
        self.assertEqual(status, 200)
        self.assertEqual(updated["pet_name"], "Buddy II")
        self.assertNotIn("edit_token", updated)
        self.assertNotIn("edit_token_hash", updated)

        status, body = await self.request("DELETE", f"/pets/{post_id}", token=token)
        self.assertEqual(status, 204)
        self.assertIsNone(body)
        status, _ = await self.request("GET", f"/pets/{post_id}")
        self.assertEqual(status, 404)

    async def test_legacy_post_cannot_be_changed(self):
        status, legacy = await self.request("GET", "/pets/1")
        self.assertEqual(status, 200)
        self.assertIsNone(legacy["breed"])
        for token in (None, "any-token"):
            status, _ = await self.request("PUT", "/pets/1", SAMPLE_POST, token)
            self.assertEqual(status, 403)
            status, _ = await self.request("DELETE", "/pets/1", token=token)
            self.assertEqual(status, 403)
        status, _ = await self.request("PUT", "/pets/999", SAMPLE_POST, "any-token")
        self.assertEqual(status, 404)
        status, _ = await self.request("DELETE", "/pets/999", token="any-token")
        self.assertEqual(status, 404)


if __name__ == "__main__":
    unittest.main()
