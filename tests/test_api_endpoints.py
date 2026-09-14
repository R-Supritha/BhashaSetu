"""Tests for core API endpoints: health, auth, lessons, translate, flashcards, dictionary."""

import unittest

from backend.app import create_app
from backend.config import Config
from backend.utils.security import issue_token


class HealthEndpointTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app()
        self.client = self.app.test_client()

    def test_health_returns_ok(self):
        resp = self.client.get("/api/health")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertEqual(data["status"], "ok")
        self.assertIn("app_mode", data)


class AuthEndpointTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app()
        self.client = self.app.test_client()

    def test_login_with_valid_credentials(self):
        resp = self.client.post("/api/auth/login", json={
            "teacher_id": "T-1001",
            "password": "demo1234",
        })
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertIn("token", data)
        self.assertIn("teacher", data)
        self.assertEqual(data["teacher"]["id"], "T-1001")

    def test_login_with_wrong_password(self):
        resp = self.client.post("/api/auth/login", json={
            "teacher_id": "T-1001",
            "password": "wrongpassword",
        })
        self.assertEqual(resp.status_code, 401)

    def test_login_with_missing_fields(self):
        resp = self.client.post("/api/auth/login", json={"teacher_id": "T-1001"})
        self.assertEqual(resp.status_code, 400)

    def test_me_with_valid_token(self):
        token = issue_token("T-1001")
        resp = self.client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertEqual(data["id"], "T-1001")

    def test_me_without_token(self):
        resp = self.client.get("/api/auth/me")
        self.assertEqual(resp.status_code, 401)

    def test_logout(self):
        token = issue_token("T-1001")
        resp = self.client.post("/api/auth/logout", headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(resp.status_code, 200)


class LessonsEndpointTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app()
        self.client = self.app.test_client()
        self.token = issue_token("T-1001")

    def _auth(self):
        return {"Authorization": f"Bearer {self.token}"}

    def test_list_lessons(self):
        resp = self.client.get("/api/lessons", headers=self._auth())
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertIsInstance(data, list)
        self.assertGreater(len(data), 0)

    def test_get_lesson_by_id(self):
        resp = self.client.get("/api/lessons/lesson-parts-of-a-plant", headers=self._auth())
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertEqual(data["_id"], "lesson-parts-of-a-plant")
        self.assertIn("concepts", data)

    def test_lessons_requires_auth(self):
        resp = self.client.get("/api/lessons")
        self.assertEqual(resp.status_code, 401)


class TranslateEndpointTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app()
        self.client = self.app.test_client()
        self.token = issue_token("T-1001")
        self._saved_mode = Config.APP_MODE
        Config.APP_MODE = "demo"

    def tearDown(self):
        Config.APP_MODE = self._saved_mode

    def _auth(self):
        return {"Authorization": f"Bearer {self.token}"}

    def test_translate_hi_to_sat(self):
        resp = self.client.post("/api/translate", headers=self._auth(), json={
            "text": "पौधों को बढ़ने के लिए धूप चाहिए।",
            "source_language": "hi",
            "target_language": "sat",
        })
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertIn("translated_text", data)
        self.assertIn("mode", data)

    def test_translate_same_language_passthrough(self):
        resp = self.client.post("/api/translate", headers=self._auth(), json={
            "text": "hello",
            "source_language": "en",
            "target_language": "en",
        })
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertEqual(data["mode"], "passthrough")

    def test_translate_requires_auth(self):
        resp = self.client.post("/api/translate", json={
            "text": "test",
            "source_language": "hi",
            "target_language": "sat",
        })
        self.assertEqual(resp.status_code, 401)


class FlashcardsEndpointTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app()
        self.client = self.app.test_client()
        self.token = issue_token("T-1001")

    def _auth(self):
        return {"Authorization": f"Bearer {self.token}"}

    def test_list_flashcards(self):
        resp = self.client.get("/api/flashcards", headers=self._auth())
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertIsInstance(data, list)
        self.assertGreater(len(data), 0)

    def test_retrieve_flashcard_by_concept(self):
        resp = self.client.post("/api/flashcards/retrieve", headers=self._auth(), json={
            "text": "What is a root?",
        })
        self.assertEqual(resp.status_code, 200)


class DictionaryEndpointTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app()
        self.client = self.app.test_client()

    def test_list_dictionary(self):
        resp = self.client.get("/api/dictionary")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertIsInstance(data, list)
        self.assertGreater(len(data), 0)

    def test_dictionary_search(self):
        resp = self.client.get("/api/dictionary?q=plant")
        self.assertEqual(resp.status_code, 200)

    def test_dictionary_does_not_require_auth(self):
        resp = self.client.get("/api/dictionary")
        self.assertEqual(resp.status_code, 200)


class FrontendPageTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app()
        self.client = self.app.test_client()

    def test_index_page(self):
        resp = self.client.get("/")
        self.assertEqual(resp.status_code, 200)

    def test_dashboard_page(self):
        resp = self.client.get("/dashboard")
        self.assertEqual(resp.status_code, 200)

    def test_lesson_setup_page(self):
        resp = self.client.get("/lesson-setup")
        self.assertEqual(resp.status_code, 200)

    def test_live_classroom_page(self):
        resp = self.client.get("/live-classroom")
        self.assertEqual(resp.status_code, 200)

    def test_worksheet_page(self):
        resp = self.client.get("/worksheet")
        self.assertEqual(resp.status_code, 200)

    def test_analytics_page(self):
        resp = self.client.get("/analytics")
        self.assertEqual(resp.status_code, 200)

    def test_dictionary_page(self):
        resp = self.client.get("/dictionary")
        self.assertEqual(resp.status_code, 200)

    def test_api_js_served(self):
        resp = self.client.get("/assets/js/api.js")
        self.assertEqual(resp.status_code, 200)


if __name__ == "__main__":
    unittest.main()
