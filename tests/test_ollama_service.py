import unittest
from unittest.mock import patch

from backend.config import Config
from backend.services import llm_service, ollama_service

_EXACT_MODEL = "qwen2.5:3b-instruct"


class OllamaServiceTests(unittest.TestCase):
    def setUp(self):
        self._saved_mode = Config.APP_MODE
        self._saved_enabled = Config.OLLAMA_ENABLED
        Config.APP_MODE = "real"
        Config.OLLAMA_ENABLED = True

    def tearDown(self):
        Config.APP_MODE = self._saved_mode
        Config.OLLAMA_ENABLED = self._saved_enabled

    def test_exact_qwen_model_from_config(self):
        self.assertEqual(Config.OLLAMA_MODEL, _EXACT_MODEL)

    def test_is_available_reports_known_model(self):
        tags = {"models": [
            {"name": "qwen2.5:1.5b"}, {"name": _EXACT_MODEL}, {"name": "bge-m3:latest"},
        ]}
        with patch("backend.services.ollama_service.requests.get") as get:
            get.return_value.raise_for_status.return_value = None
            get.return_value.json.return_value = tags
            status = ollama_service.is_available()
        self.assertTrue(status["available"])
        self.assertTrue(status["model_present"])
        self.assertEqual(status["model"], _EXACT_MODEL)

    def test_chat_returns_text_on_success(self):
        with patch("backend.services.ollama_service.requests.post") as post:
            post.return_value.raise_for_status.return_value = None
            post.return_value.json.return_value = {"response": "  hello "}
            out = ollama_service.chat("hi")
        self.assertEqual(out, "hello")

    def test_chat_returns_none_when_unreachable(self):
        with patch("backend.services.ollama_service.requests.post", side_effect=OSError("down")):
            self.assertIsNone(ollama_service.chat("hi"))

    def test_chat_json_extracts_embedded_json(self):
        raw = 'Sure! Here is the JSON:\n```json\n{"classification": "concept_gap", "reason": "x", "confidence": 0.9}\n```'
        with patch("backend.services.ollama_service.chat", return_value=raw):
            data = ollama_service.chat_json("p")
        self.assertEqual(data["classification"], "concept_gap")
        self.assertEqual(data["confidence"], 0.9)

    def test_demo_mode_still_calls_ollama_when_enabled(self):
        Config.APP_MODE = "demo"
        Config.OLLAMA_ENABLED = True
        with patch("backend.services.ollama_service.requests.post") as post:
            post.return_value.raise_for_status.return_value = None
            post.return_value.json.return_value = {"response": "hi"}
            out = ollama_service.chat("hi")
        self.assertEqual(out, "hi")
        post.assert_called_once()

    def test_disabled_never_calls_ollama(self):
        Config.OLLAMA_ENABLED = False
        with patch("backend.services.ollama_service.requests.post") as post:
            self.assertIsNone(ollama_service.chat("hi"))
        post.assert_not_called()

    def test_misconception_detector_real(self):
        payload = {"classification": "concept_gap",
                   "reason": "Student understands the vocabulary but misunderstood sunlight.",
                   "confidence": 0.88,
                   "suggested_action": "Explain using a plant-growth example."}
        with patch("backend.services.ollama_service.chat_json", return_value=payload):
            result = llm_service.analyze_misconception("Why do plants need sunlight?", "To make their own food.",
                                                       "Because plants like the sun.")
        self.assertEqual(result["mode"], "real")
        self.assertEqual(result["engine"], f"ollama:{_EXACT_MODEL}")
        self.assertEqual(result["classification"], "concept_gap")
        self.assertEqual(result["confidence"], 0.88)

    def test_misconception_detector_correct(self):
        payload = {"classification": "correct", "reason": "Match", "confidence": 0.97,
                   "suggested_action": "None"}
        with patch("backend.services.ollama_service.chat_json", return_value=payload):
            result = llm_service.analyze_misconception("Why do plants need sunlight?",
                                                       "To make food", "To make food")
        self.assertEqual(result["classification"], "correct")

    def test_misconception_detector_language_gap(self):
        payload = {"classification": "language_gap", "reason": "Idea correct but in wrong language.",
                   "confidence": 0.9, "suggested_action": "Use bilingual prompt."}
        with patch("backend.services.ollama_service.chat_json", return_value=payload):
            result = llm_service.analyze_misconception("Why do plants need sunlight?",
                                                       "To make food", "ᱪᱟᱸᱫᱚ ᱛᱮ..")
        self.assertEqual(result["classification"], "language_gap")

    def test_misconception_detector_fallback_on_bad_json(self):
        with patch("backend.services.ollama_service.chat_json", return_value=None):
            result = llm_service.analyze_misconception("Q", "A", "wrong", concept="root")
        self.assertEqual(result["mode"], "fallback")
        self.assertEqual(result["engine"], "heuristic-classifier")
        self.assertIn("warning", result)
        self.assertIn(result["classification"], {"concept_gap", "context_gap", "correct"})

    def test_misconception_detector_rejects_invalid_classification(self):
        with patch("backend.services.ollama_service.chat_json",
                   return_value={"classification": "not-a-class", "confidence": 1.0}):
            result = llm_service.analyze_misconception("Q", "A", "wrong")
        self.assertEqual(result["mode"], "fallback")

    def test_alternate_explanation_real(self):
        with patch("backend.services.ollama_service.chat", return_value="Think of sunlight as the plant's kitchen light."):
            result = llm_service.format_alternate_explanation("sunlight", "many think leaves eat soil")
        self.assertEqual(result["mode"], "real")
        self.assertEqual(result["engine"], f"ollama:{_EXACT_MODEL}")
        self.assertIn("kitchen", result["explanation"])

    def test_alternate_explanation_fallback_when_down(self):
        with patch("backend.services.ollama_service.chat", return_value=None):
            result = llm_service.format_alternate_explanation("root", "confused root with stem")
        self.assertEqual(result["mode"], "fallback")
        self.assertEqual(result["engine"], "canned-explanation")

    def test_doubt_explanation_real(self):
        with patch("backend.services.ollama_service.chat", return_value="The stem carries water upwards like a straw."):
            result = llm_service.explain_doubt("तना क्या करता है?", ["The stem carries water."])
        self.assertEqual(result["mode"], "real")
        self.assertIn("straw", result["answer"])

    def test_doubt_explanation_calls_ollama_when_enabled_in_demo_mode(self):
        Config.APP_MODE = "demo"
        Config.OLLAMA_ENABLED = True
        with patch("backend.services.ollama_service.chat", return_value="The stem carries water upwards."):
            result = llm_service.explain_doubt("तना क्या करता है?", [])
        self.assertEqual(result["mode"], "real")
        self.assertEqual(result["engine"], f"ollama:{_EXACT_MODEL}")

    def test_weak_concept_insight_real(self):
        with patch("backend.services.ollama_service.chat",
                   return_value="Roots are invisible in everyday life, so children mix them up with stems."):
            result = llm_service.explain_weak_concept("root", 45)
        self.assertEqual(result["mode"], "real")
        self.assertIn("root", result["explanation"].lower())

    def test_worksheet_scoring_is_deterministic_regardless_of_llm(self):
        from backend.services import worksheet_service

        worksheet = {"questions": [
            {"id": "q1", "concept": "root", "correct_option": "Root"},
            {"id": "q2", "concept": "leaf", "correct_option": "Leaf"},
        ]}
        captured = {}

        def _capture(doc):
            captured.update(doc)
            return {"_id": "sub-1"}

        with patch("backend.services.worksheet_service.get_worksheet", return_value=worksheet), \
             patch("backend.services.worksheet_service.json_store.worksheet_submissions.insert_one") as ins, \
             patch.object(llm_service, "analyze_misconception") as analyze:
            ins.side_effect = _capture
            analyze.return_value = {
                "mode": "real", "engine": f"ollama:{_EXACT_MODEL}",
                "classification": "concept_gap", "reason": "r", "confidence": 0.8,
                "suggested_action": "a", "warning": None,
            }
            worksheet_service.submit_worksheet(
                "w", "s1", {"q1": "Root", "q2": "Wrong"}, explanations={"q1": "Roots soak up water"},
            )

        # Deterministic score is computed from the answer key, LLM cannot alter it.
        self.assertEqual(captured["score_percent"], 50)
        self.assertEqual(captured["correct_count"], 1)
        self.assertEqual(captured["concept_results"], {"root": "correct", "leaf": "incorrect"})
        # Additive diagnostic only.
        self.assertIn("q1", captured["llm_analysis"])
        self.assertEqual(captured["llm_analysis"]["q1"]["classification"], "concept_gap")

    def test_worksheet_no_explanations_means_no_llm_call(self):
        from backend.services import worksheet_service

        worksheet = {"questions": [
            {"id": "q1", "concept": "root", "correct_option": "Root"},
            {"id": "q2", "concept": "leaf", "correct_option": "Leaf"},
        ]}
        with patch("backend.services.worksheet_service.get_worksheet", return_value=worksheet), \
             patch("backend.services.worksheet_service.json_store.worksheet_submissions.insert_one") as ins, \
             patch.object(llm_service, "analyze_misconception") as analyze:
            ins.return_value = {"_id": "sub-2"}
            worksheet_service.submit_worksheet("w", "s2", {"q1": "Root", "q2": "Leaf"})
        analyze.assert_not_called()

    def test_recommendations_keep_deterministic_numbers_and_add_explanation(self):
        from backend.services import personalization_service

        weak = [{"concept": "root", "mastery_percent": 40}]
        with patch("backend.services.assessment_service.weak_concepts", return_value=weak), \
             patch("backend.services.flashcard_service.get_by_concept", return_value={"_id": "fc1"}), \
             patch.object(llm_service, "explain_weak_concept",
                          return_value={"mode": "real", "engine": f"ollama:{_EXACT_MODEL}",
                                        "explanation": "Roots are hidden underground, so children guess the stem."}):
            recs = personalization_service.recommendations_for(None)

        self.assertEqual(recs[0]["concept"], "root")
        self.assertEqual(recs[0]["mastery_percent"], 40)
        self.assertEqual(recs[0]["flashcard_id"], "fc1")
        self.assertIn("Re-teach", recs[0]["recommendation"])
        self.assertEqual(recs[0]["explanation_mode"], "real")
        self.assertIn("alternate_explanation", recs[0])


if __name__ == "__main__":
    unittest.main()