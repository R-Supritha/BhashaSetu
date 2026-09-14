import unittest
from unittest.mock import patch

from backend.app import create_app
from backend.config import Config
from backend.services import translation_service
from backend.services.translation_engines import BhashiniDhruvaEngine
from backend.utils.security import issue_token

_SAT_DEMO = "ᱫᱟᱨᱮ ᱵᱟᱲᱟᱭ ᱞᱟᱹᱜᱤᱫ ᱥᱮᱛᱟᱜ ᱵᱟᱹᱱᱩᱜᱼᱟ ᱾"


class TranslationConfigTests(unittest.TestCase):
    def setUp(self):
        # Isolate the service from whatever APP_MODE other tests set.
        self._saved_mode = Config.APP_MODE

    def tearDown(self):
        Config.APP_MODE = self._saved_mode

    def test_bhashini_env_vars_are_optional(self):
        self.assertIsInstance(Config.BHASHINI_USER_ID, str)
        self.assertIsInstance(Config.BHASHINI_API_KEY, str)
        self.assertIsInstance(Config.BHASHINI_PIPELINE_ID, str)

    def test_hi_to_sat_and_sat_to_hi_keep_fallback_metadata_labelled(self):
        Config.APP_MODE = "demo"
        # Normal sentence
        hi_to_sat = translation_service.translate(
            "पौधों को बढ़ने के लिए धूप और पानी चाहिए。",
            "hi",
            "sat",
        )
        self.assertEqual(hi_to_sat["mode"], "fallback")
        self.assertIn(hi_to_sat["engine"], {"demo-phrase-table", "lesson-glossary", "none"})
        self.assertIn("warning", hi_to_sat)

        # Classroom-related sentence in reverse direction
        sat_to_hi = translation_service.translate(
            "ᱫᱟᱨᱮ ᱚᱠᱚ ᱞᱟᱹᱜᱤᱫ ᱪᱟᱸᱰᱚ ᱠᱟᱱᱟ ᱥᱮᱛᱟᱜ ᱫᱚ ᱡᱟᱹᱨᱩᱲᱤᱭᱟᱹ ᱟᱠᱟᱱᱟ?",
            "sat",
            "hi",
        )
        self.assertEqual(sat_to_hi["mode"], "fallback")
        self.assertIn(sat_to_hi["engine"], {"demo-phrase-table", "lesson-glossary", "none"})
        self.assertIn("warning", sat_to_hi)

    def test_bhashini_engine_parses_pipeline_and_returns_target(self):
        # DHRUVA two-step contract: pipeline-config response, then compute response.
        config_response = {
            "pipelineInferenceAPIEnfPoint": {
                "callbackURL": "https://dhruva-api.bhashini.gov.in/services/inference/pipeline",
                "inferenceApiKey": {"name": "Authorization", "value": "inference-token-123"},
            },
            "pipelineResponseConfig": [
                {
                    "taskType": "translation",
                    "config": [
                        {
                            "language": {"sourceLanguage": "hi", "targetLanguage": "sat"},
                            "serviceId": "ai4bharat/indictrans-v2-all-gpu--t4",
                        }
                    ],
                }
            ],
        }
        compute_response = {"pipelineResponse": [{"output": [{"source": "...", "target": _SAT_DEMO}]}]}

        with patch("backend.services.translation_engines.requests.post") as post:
            post.side_effect = [_FakeResponse(config_response), _FakeResponse(compute_response)]
            engine = BhashiniDhruvaEngine(user_id="user-1", api_key="key-1", pipeline_id="pipe-1")

            result = engine.translate("पौधों को बढ़ने के लिए धूप चाहिए।", "hi", "sat")

        self.assertEqual(result, _SAT_DEMO)
        # Second call must reuse the cached pipeline config (no extra config POST).
        self.assertEqual(post.call_count, 2)

    def test_bhashini_real_response_mode_is_real_for_hi_to_sat(self):
        """When NLLB is unavailable and Bhashini is configured, engine='bhashini'."""
        class _StubEngine:
            def available(self):
                return True

            def translate(self, text, source, target):
                return _SAT_DEMO

        Config.APP_MODE = "real"
        with patch("backend.services.translation_service._get_nllb_engine", return_value=None), \
             patch("backend.services.translation_service._get_bhashini_engine", return_value=_StubEngine()):
            hi_to_sat = translation_service.translate("पौधों को बढ़ने के लिए धूप चाहिए।", "hi", "sat")

        self.assertEqual(hi_to_sat["mode"], "real")
        self.assertEqual(hi_to_sat["engine"], "bhashini")
        self.assertIn("ᱫᱟᱨᱮ", hi_to_sat["translated_text"])

    def test_bhashini_api_failure_returns_fallback(self):
        """When both NLLB and Bhashini are unavailable, mode falls back."""
        class _BrokenEngine:
            def available(self):
                return True

            def translate(self, text, source, target):
                raise RuntimeError("Bhashini down")

        Config.APP_MODE = "real"
        with patch("backend.services.translation_service._get_nllb_engine", return_value=None), \
             patch("backend.services.translation_service._get_bhashini_engine", return_value=_BrokenEngine()):
            result = translation_service.translate("पौधों को बढ़ने के लिए धूप चाहिए।", "hi", "sat")

        self.assertEqual(result["mode"], "fallback")
        self.assertEqual(result["engine"], "demo-phrase-table")
        self.assertIn("fallback", result["mode"])

    def test_missing_bhashini_credentials_returns_fallback(self):
        """When NLLB is unavailable and Bhashini has no credentials, mode falls back."""
        Config.APP_MODE = "real"
        with patch("backend.services.translation_service._get_nllb_engine", return_value=None), \
             patch.object(Config, "BHASHINI_USER_ID", ""), patch.object(
            Config, "BHASHINI_API_KEY", ""
        ), patch.object(Config, "BHASHINI_PIPELINE_ID", ""):
            result = translation_service.translate("पौधों को बढ़ने के लिए धूप चाहिए।", "hi", "sat")

        self.assertEqual(result["mode"], "fallback")
        self.assertEqual(result["engine"], "demo-phrase-table")

    def test_frontend_and_stitch_pages_are_served_by_flask_static_routes(self):
        app = create_app()
        client = app.test_client()

        filesystem_asset = client.get("/assets/js/api.js")
        self.assertEqual(filesystem_asset.status_code, 200)

        # Stitch pages are served via named Flask routes, not raw paths
        for route in ["/", "/dashboard", "/lesson-setup", "/live-classroom",
                       "/worksheet", "/analytics", "/dictionary"]:
            resp = client.get(route)
            self.assertEqual(resp.status_code, 200, f"Route {route} should return 200")

    @patch("backend.services.rag_service.retrieve")
    @patch("backend.services.llm_service.generate_explanation")
    def test_rag_ask_route_returns_grounded_ollama_response_shape(self, generate_explanation, retrieve):
        from backend.app import create_app

        app = create_app()
        client = app.test_client()
        token = issue_token("teacher-1")

        retrieve.return_value = {
            "mode": "real",
            "engine": "chromadb",
            "chunks": ["Plants have roots, stems, leaves, flowers, and fruits."],
            "hits": [{
                "text": "Plants have roots, stems, leaves, flowers, and fruits.",
                "score": 0.77,
                "lesson": "plant-parts",
                "topic": "plant science",
                "grade": "3",
                "subject": "science",
                "document_id": "book-123",
                "source_name": "parts-of-a-plant.pdf",
            }],
            "grounded": True,
            "warning": None,
        }
        generate_explanation.return_value = {
            "mode": "real",
            "engine": "ollama:qwen2.5:3b-instruct",
            "answer": "A plant has roots, stem, leaves, flower, and fruit.",
            "warning": None,
        }

        response = client.post(
            "/api/rag/ask",
            headers={"Authorization": f"Bearer {token}"},
            json={"textbook_id": "book-123", "question": "What are the parts of a plant?"},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["mode"], "real")
        self.assertEqual(payload["engine"], "ollama:qwen2.5:3b-instruct")
        self.assertIn("parts of a plant", payload["answer"].lower())
        self.assertEqual(len(payload["sources"]), 1)

    def test_real_translation_is_only_possible_with_configured_credentials(self):
        """When NLLB is unavailable, real translation needs Bhashini credentials."""
        Config.APP_MODE = "real"
        with patch("backend.services.translation_service._get_nllb_engine", return_value=None), \
             patch.object(Config, "BHASHINI_USER_ID", ""), patch.object(
            Config, "BHASHINI_API_KEY", ""
        ), patch.object(Config, "BHASHINI_PIPELINE_ID", ""):
            result = translation_service.translate("पौधों को बढ़ने के लिए धूप चाहिए।", "hi", "sat")
        self.assertEqual(result["mode"], "fallback")

    def test_nllb_provides_real_translation_without_credentials(self):
        """NLLB-200 enables real translation without any cloud credentials."""
        Config.APP_MODE = "real"
        result = translation_service.translate("पौधों को बढ़ने के लिए धूप और पानी चाहिए।", "hi", "sat")
        self.assertEqual(result["mode"], "real")
        self.assertEqual(result["engine"], "nllb-200")
        self.assertTrue(len(result["translated_text"]) > 0)


class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


if __name__ == "__main__":
    unittest.main()