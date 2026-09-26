import asyncio
import base64
import json
import os
import sqlite3
import tempfile
import unittest
from contextlib import closing
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch
from urllib.parse import urlsplit


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
PNG_IMAGE = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jRZkAAAAASUVORK5CYII="
)


class OwnershipTests(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):
        cls.project_dir = os.getcwd()
        cls.temp_dir = tempfile.TemporaryDirectory()
        os.chdir(cls.temp_dir.name)
        cls.env_patch = patch.dict(os.environ, {
            "KMR_DATABASE_PATH": str(Path(cls.temp_dir.name) / "pets.db"),
            "KMR_DATABASE_URL": "",
        })
        cls.env_patch.start()

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
                "2026-09-26", "Amina", "123", "2026-09-26 12:00:00",
            ))
            connection.commit()

        import main
        from database import engine

        cls.app = main.app
        cls.engine = engine
        cls.upload_dir = main.UPLOAD_DIR

    @classmethod
    def tearDownClass(cls):
        cls.engine.dispose()
        cls.env_patch.stop()
        os.chdir(cls.project_dir)
        cls.temp_dir.cleanup()

    async def request(self, method, path, payload=None, token=None, upload=None,
                      extra_headers=None, return_headers=False):
        url = urlsplit(path)
        if upload is None:
            body = json.dumps(payload).encode() if payload is not None else b""
            headers = [(b"content-type", b"application/json")]
        else:
            filename, content_type, image = upload
            boundary = "kmr-test-boundary"
            body = (
                f'--{boundary}\r\nContent-Disposition: form-data; name="photo"; filename="{filename}"\r\n'
                f'Content-Type: {content_type}\r\n\r\n'
            ).encode() + image + f"\r\n--{boundary}--\r\n".encode()
            headers = [(b"content-type", f"multipart/form-data; boundary={boundary}".encode())]
        if token is not None:
            headers.append((b"x-edit-token", token.encode()))
        if extra_headers:
            headers.extend((name.lower().encode(), value.encode()) for name, value in extra_headers.items())
        scope = {
            "type": "http",
            "asgi": {"version": "3.0"},
            "http_version": "1.1",
            "method": method,
            "scheme": "http",
            "path": url.path,
            "raw_path": url.path.encode(),
            "query_string": url.query.encode(),
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
        response_start = next(message for message in sent if message["type"] == "http.response.start")
        status = response_start["status"]
        content = b"".join(message.get("body", b"") for message in sent if message["type"] == "http.response.body")
        content_type = dict(response_start["headers"]).get(b"content-type", b"")
        parsed_content = json.loads(content) if content and content_type.startswith(b"application/json") else content or None
        if return_headers:
            return status, parsed_content, dict(response_start["headers"])
        return status, parsed_content

    async def test_configuration(self):
        from sqlalchemy.engine import URL, make_url

        from config import PROJECT_DIR, allowed_frontend_origins, database_url

        with patch.dict(os.environ, {"KMR_DATABASE_URL": "", "KMR_DATABASE_PATH": ""}):
            self.assertEqual(Path(make_url(database_url()).database), PROJECT_DIR / "pets.db")
        with patch.dict(os.environ, {"KMR_DATABASE_URL": "", "KMR_DATABASE_PATH": "data/other.db"}):
            self.assertEqual(Path(make_url(database_url()).database), PROJECT_DIR / "data/other.db")
        with patch.dict(os.environ, {"KMR_DATABASE_URL": "sqlite:///relative.db"}):
            self.assertEqual(Path(make_url(database_url()).database), PROJECT_DIR / "relative.db")
        absolute_url = str(URL.create("sqlite", database=str(Path(self.temp_dir.name) / "custom.db")))
        with patch.dict(os.environ, {"KMR_DATABASE_URL": absolute_url}):
            self.assertEqual(Path(make_url(database_url()).database), Path(self.temp_dir.name) / "custom.db")

        with patch.dict(os.environ, {"KMR_FRONTEND_ORIGINS": ""}):
            self.assertEqual(allowed_frontend_origins(), [])
        with patch.dict(os.environ, {"KMR_FRONTEND_ORIGINS": "http://example.test:3000, http://localhost:5173/"}):
            self.assertEqual(allowed_frontend_origins(), ["http://example.test:3000", "http://localhost:5173"])
        with patch.dict(os.environ, {"KMR_FRONTEND_ORIGINS": "*"}):
            with self.assertRaises(ValueError):
                allowed_frontend_origins()

    async def test_cors(self):
        for origin in ("http://localhost:5173", "http://127.0.0.1:5173"):
            status, _, headers = await self.request(
                "OPTIONS", "/pets/2/photo",
                extra_headers={
                    "Origin": origin,
                    "Access-Control-Request-Method": "POST",
                    "Access-Control-Request-Headers": "X-Edit-Token, Content-Type",
                },
                return_headers=True,
            )
            self.assertEqual(status, 200)
            self.assertEqual(headers[b"access-control-allow-origin"], origin.encode())
            self.assertIn(b"POST", headers[b"access-control-allow-methods"])
            self.assertIn(b"x-edit-token", headers[b"access-control-allow-headers"].lower())
            self.assertNotIn(b"access-control-allow-credentials", headers)

        status, _, headers = await self.request(
            "GET", "/", extra_headers={"Origin": "http://localhost:5173"}, return_headers=True
        )
        self.assertEqual(status, 200)
        self.assertEqual(headers[b"access-control-allow-origin"], b"http://localhost:5173")
        status, _, headers = await self.request(
            "OPTIONS", "/pets", extra_headers={
                "Origin": "http://unlisted.test",
                "Access-Control-Request-Method": "POST",
            }, return_headers=True
        )
        self.assertEqual(status, 400)
        self.assertNotIn(b"access-control-allow-origin", headers)

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
        self.assertEqual(legacy["contact_phone"], "123")
        for token in (None, "any-token"):
            status, _ = await self.request("PUT", "/pets/1", SAMPLE_POST, token)
            self.assertEqual(status, 403)
            status, _ = await self.request("DELETE", "/pets/1", token=token)
            self.assertEqual(status, 403)
        status, _ = await self.request("PUT", "/pets/999", SAMPLE_POST, "any-token")
        self.assertEqual(status, 404)
        status, _ = await self.request("DELETE", "/pets/999", token="any-token")
        self.assertEqual(status, 404)

    async def test_post_validation(self):
        invalid_posts = [
            {"status": "MISSING"},
            {"species": "   "},
            {"description": "   "},
            {"area": "   "},
            {"district": "   "},
            {"contact_name": "   "},
            {"contact_phone": "   "},
            {"contact_phone": "1234"},
            {"contact_phone": "call-me-1234567"},
            {"contact_email": "not-an-email"},
            {"event_date": "not-a-date"},
            {"species": "x" * 51},
            {"breed": "x" * 81},
            {"description": "x" * 2001},
        ]
        for change in invalid_posts:
            with self.subTest(change=change):
                status, _ = await self.request("POST", "/pets", {**SAMPLE_POST, **change})
                self.assertEqual(status, 422)

        trimmed = {**SAMPLE_POST, "species": " dog ", "breed": " ",
                   "contact_email": " amina@example.com ", "contact_phone": " +91 98765 43210 "}
        status, created = await self.request("POST", "/pets", trimmed)
        self.assertEqual(status, 201)
        self.assertEqual(created["species"], "dog")
        self.assertEqual(created["breed"], "")
        self.assertEqual(created["contact_email"], "amina@example.com")
        self.assertEqual(created["contact_phone"], "+91 98765 43210")

        status, _ = await self.request(
            "PUT", f"/pets/{created['id']}", {**SAMPLE_POST, "description": "  "}, created["edit_token"]
        )
        self.assertEqual(status, 422)
        status, unchanged = await self.request("GET", f"/pets/{created['id']}")
        self.assertEqual(status, 200)
        self.assertEqual(unchanged["description"], SAMPLE_POST["description"])

    async def test_future_event_date_is_rejected(self):
        india_time = timezone(timedelta(hours=5, minutes=30))
        today = datetime.now(india_time).date()
        future = today + timedelta(days=1)

        status, _ = await self.request("POST", "/pets", {**SAMPLE_POST, "event_date": future.isoformat()})
        self.assertEqual(status, 422)

        status, created = await self.request("POST", "/pets", {**SAMPLE_POST, "event_date": today.isoformat()})
        self.assertEqual(status, 201)
        status, _ = await self.request(
            "PUT", f"/pets/{created['id']}",
            {**SAMPLE_POST, "event_date": future.isoformat()}, created["edit_token"],
        )
        self.assertEqual(status, 422)
        status, unchanged = await self.request("GET", f"/pets/{created['id']}")
        self.assertEqual(status, 200)
        self.assertEqual(unchanged["event_date"], today.isoformat())

    async def test_pagination_and_filters(self):
        from database import SessionLocal
        from models import PetPost, PostStatus

        with SessionLocal() as db:
            for number in range(22):
                db.add(PetPost(
                    status=PostStatus.FOUND, species="cat", description=f"Cat {number}",
                    area="Sopore", district="Baramulla", event_date=date(2026, 10, 1),
                    contact_name="Amina", contact_phone="9876543210",
                    created_at=datetime(2026, 10, 1, tzinfo=timezone.utc) + timedelta(minutes=number),
                ))
            db.commit()

        filters = ("status=FOUND&species=cat&district=Baramulla&area=Sopore"
                   "&event_date_from=2026-10-01&event_date_to=2026-10-01")
        status, default_page = await self.request("GET", "/pets")
        self.assertEqual(status, 200)
        self.assertEqual(len(default_page), 20)
        status, first_page = await self.request("GET", f"/pets?{filters}")
        self.assertEqual(status, 200)
        self.assertEqual(len(first_page), 20)
        self.assertEqual(first_page[0]["description"], "Cat 21")
        self.assertEqual(first_page[-1]["description"], "Cat 2")

        status, second_page = await self.request("GET", f"/pets?{filters}&limit=5&offset=20")
        self.assertEqual(status, 200)
        self.assertEqual([post["description"] for post in second_page], ["Cat 1", "Cat 0"])

        status, all_posts = await self.request("GET", f"/pets?{filters}&limit=100")
        self.assertEqual(status, 200)
        self.assertEqual(len(all_posts), 22)
        for query in ("limit=101", "limit=0", "offset=-1"):
            status, _ = await self.request("GET", f"/pets?{query}")
            self.assertEqual(status, 422)
        status, no_matches = await self.request("GET", "/pets?species=bird&district=Baramulla")
        self.assertEqual(status, 200)
        self.assertEqual(no_matches, [])

    async def test_photo_upload_and_replacement(self):
        status, created = await self.request("POST", "/pets", SAMPLE_POST)
        self.assertEqual(status, 201)
        post_id = created["id"]
        token = created["edit_token"]
        photo_route = f"/pets/{post_id}/photo"
        image_upload = ("my-photo.png", "image/png", PNG_IMAGE)

        for missing_or_wrong in (None, "wrong-token"):
            status, _ = await self.request("POST", photo_route, token=missing_or_wrong, upload=image_upload)
            self.assertEqual(status, 403)
        status, _ = await self.request("POST", "/pets/999/photo", token=token, upload=image_upload)
        self.assertEqual(status, 404)
        status, _ = await self.request("POST", "/pets/1/photo", token=token, upload=image_upload)
        self.assertEqual(status, 403)
        status, unchanged = await self.request("GET", f"/pets/{post_id}")
        self.assertEqual(status, 200)
        self.assertIsNone(unchanged["photo_url"])

        for invalid_upload in (
            ("notes.txt", "text/plain", b"not an image"),
            ("fake.png", "image/png", b"not an image"),
        ):
            status, _ = await self.request("POST", photo_route, token=token, upload=invalid_upload)
            self.assertEqual(status, 415)
        too_large = ("large.png", "image/png", PNG_IMAGE + b"x" * (5 * 1024 * 1024))
        status, _ = await self.request("POST", photo_route, token=token, upload=too_large)
        self.assertEqual(status, 413)

        status, uploaded = await self.request("POST", photo_route, token=token, upload=image_upload)
        self.assertEqual(status, 200)
        first_url = uploaded["photo_url"]
        self.assertTrue(first_url.startswith(f"/uploads/{post_id}-"))
        self.assertNotIn("my-photo", first_url)
        self.assertNotIn("edit_token", uploaded)
        first_path = self.upload_dir / Path(first_url).name
        self.addCleanup(first_path.unlink, missing_ok=True)
        self.assertEqual(first_path.read_bytes(), PNG_IMAGE)
        status, served_image = await self.request("GET", first_url)
        self.assertEqual(status, 200)
        self.assertEqual(served_image, PNG_IMAGE)

        status, detail = await self.request("GET", f"/pets/{post_id}")
        self.assertEqual(status, 200)
        self.assertEqual(detail["photo_url"], first_url)
        status, posts = await self.request("GET", "/pets?limit=100")
        self.assertEqual(status, 200)
        self.assertEqual(next(post for post in posts if post["id"] == post_id)["photo_url"], first_url)

        status, replaced = await self.request("POST", photo_route, token=token, upload=image_upload)
        self.assertEqual(status, 200)
        second_url = replaced["photo_url"]
        second_path = self.upload_dir / Path(second_url).name
        self.addCleanup(second_path.unlink, missing_ok=True)
        self.assertNotEqual(first_url, second_url)
        self.assertFalse(first_path.exists())
        self.assertEqual(second_path.read_bytes(), PNG_IMAGE)

        status, _ = await self.request("DELETE", f"/pets/{post_id}", token=token)
        self.assertEqual(status, 204)
        self.assertFalse(second_path.exists())


if __name__ == "__main__":
    unittest.main()
