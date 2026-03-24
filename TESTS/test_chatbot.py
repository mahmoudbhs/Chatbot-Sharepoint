import os
import sys
import tempfile
import unittest


BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASE_DIR)

from API.engine import ChatbotEngine  # noqa: E402
from API.knowledge_base import build_training_samples, load_knowledge_base  # noqa: E402
from API.llm_client import LLMClient  # noqa: E402
from API.memory_store import MemoryStore  # noqa: E402
from API.sharepoint_connector import SharePointConnector  # noqa: E402


class FakeConnector:
    def __init__(self):
        self.documents = [
            {
                "title": "Creer un site SharePoint",
                "category": "sharepoint",
                "content": "Pour creer un site SharePoint, connectez-vous puis lancez la creation.",
                "url": "https://example.test/sharepoint/create",
            },
            {
                "title": "Gerer les droits d'un site SharePoint",
                "category": "sharepoint",
                "content": "Pour gerer les droits SharePoint, ouvrez les autorisations du site.",
                "url": "https://example.test/sharepoint/permissions",
            },
            {
                "title": "Diagnostic d'une synchronisation OneDrive",
                "category": "onedrive",
                "content": "Verifiez l'icone OneDrive puis relancez la synchronisation.",
                "url": "https://example.test/onedrive/sync",
            },
        ]

    def get_user_guides(self):
        return [
            {"title": "Guide Teams", "url": "https://example.test/teams"},
            {"title": "Guide SharePoint", "url": "https://example.test/sharepoint"},
        ]

    def get_faq_items(self):
        return [
            {
                "category": "sharepoint",
                "answer": "SharePoint est une plateforme collaborative de gestion documentaire.",
                "url": "https://example.test/sharepoint-faq",
                "title": "FAQ SharePoint",
            }
        ]

    def search_knowledge(self, query, limit=3):
        if "gouvernance" in query.lower() or "sharepoint" in query.lower():
            return [
                {
                    "score": 0.8,
                    "title": "Bonnes pratiques SharePoint",
                    "category": "sharepoint",
                    "content": "Utilisez une structure simple, des proprietaires identifies et des permissions revues regulierement.",
                    "url": "https://example.test/knowledge/sharepoint",
                }
            ][:limit]
        if "onedrive" in query.lower():
            return [
                {
                    "score": 0.7,
                    "title": "Diagnostic d'une synchronisation OneDrive",
                    "category": "onedrive",
                    "content": "Verifiez l'icone OneDrive puis relancez la synchronisation.",
                    "url": "https://example.test/onedrive/sync",
                }
            ][:limit]
        return []

    def get_documents_by_category(self, category, limit=4):
        return [doc for doc in self.documents if doc["category"] == category][:limit]


class FakeLLMClient:
    def __init__(self, prefix="LLM: "):
        self.prefix = prefix
        self.calls = 0

    def generate_reply(self, user_message, deterministic_reply, history, knowledge_titles=None):
        self.calls += 1
        return self.prefix + deterministic_reply


def build_engine(llm_client=None, memory_store=None):
    knowledge_base = load_knowledge_base()
    return ChatbotEngine(
        knowledge_base=knowledge_base,
        connector=FakeConnector(),
        llm_client=llm_client,
        memory_store=memory_store,
    )


class EmptyKnowledgeConnector(FakeConnector):
    def search_knowledge(self, query, limit=3):
        return []

    def get_documents_by_category(self, category, limit=4):
        return []


class ChatbotTests(unittest.TestCase):
    def test_knowledge_base_alignment(self):
        knowledge_base = load_knowledge_base()
        samples = build_training_samples(knowledge_base)

        self.assertTrue(knowledge_base["intents"])
        self.assertTrue(knowledge_base["defaults"])
        self.assertGreaterEqual(len(samples), len(knowledge_base["intents"]))

        tags = {intent["tag"] for intent in knowledge_base["intents"]}
        sample_tags = {sample["tag"] for sample in samples}
        self.assertEqual(tags, sample_tags)

    def test_engine_returns_guides_for_get_guide(self):
        engine = build_engine()

        reply = engine.safe_response("Montre-moi un guide", session_id="guide-test")

        self.assertEqual(reply["intent"], "get_guide")
        self.assertIn("Guide Teams", reply["response"])

    def test_engine_keeps_deterministic_mode_without_llm(self):
        engine = build_engine(llm_client=LLMClient())
        reply = engine.safe_response("salut", session_id="deterministic-no-llm")

        self.assertNotIn("LLM:", reply["response"])

    def test_engine_persists_topic_preferences(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            memory_path = os.path.join(temp_dir, "memory.json")
            memory_store = MemoryStore(path=memory_path)

            engine = build_engine(memory_store=memory_store)
            engine.safe_response("un projet onedrive", session_id="persist-1")

            reloaded_engine = build_engine(memory_store=MemoryStore(path=memory_path))
            reply = reloaded_engine.safe_response("salut", session_id="persist-1")

            self.assertIn("onedrive", reply["response"].lower())

    def test_engine_handles_small_talk(self):
        engine = build_engine()

        reply = engine.safe_response("ca va ?", session_id="smalltalk-1")

        self.assertEqual(reply["intent"], "small_talk")
        self.assertIn("ca va", reply["response"].lower())

    def test_engine_handles_embedded_small_talk(self):
        engine = build_engine()

        reply = engine.safe_response("sinon toi cava ?", session_id="smalltalk-2")

        self.assertEqual(reply["intent"], "small_talk")
        self.assertIn("ca va", reply["response"].lower())

    def test_engine_can_overlay_llm_without_replacing_core_logic(self):
        fake_llm = FakeLLMClient()
        engine = build_engine(llm_client=fake_llm)

        reply = engine.safe_response("salut", session_id="llm-overlay-1")

        self.assertEqual(reply["intent"], "small_talk")
        self.assertTrue(reply["response"].startswith("LLM: "))
        self.assertEqual(fake_llm.calls, 1)

    def test_engine_asks_for_clarification_on_vague_message(self):
        engine = build_engine()

        reply = engine.safe_response("j'ai un probleme", session_id="clarify-1")

        self.assertEqual(reply["intent"], "clarification")
        self.assertIn("sharepoint", reply["response"].lower())

    def test_engine_asks_for_clarification_on_incomplete_request(self):
        engine = build_engine()

        reply = engine.safe_response("je veux", session_id="clarify-2")

        self.assertEqual(reply["intent"], "clarification")
        self.assertTrue(
            "termine ta phrase" in reply["response"].lower()
            or "pas encore la fin" in reply["response"].lower()
            or "pas complete" in reply["response"].lower()
        )

    def test_engine_asks_for_clarification_on_je_souhaite(self):
        engine = build_engine()

        reply = engine.safe_response("je souhaite", session_id="clarify-3")

        self.assertEqual(reply["intent"], "clarification")
        self.assertTrue(
            "termine ta phrase" in reply["response"].lower()
            or "pas encore la fin" in reply["response"].lower()
            or "pas complete" in reply["response"].lower()
        )

    def test_engine_uses_knowledge_base_for_business_answer(self):
        engine = build_engine()

        reply = engine.safe_response(
            "Quelles sont les bonnes pratiques de gouvernance SharePoint ?",
            session_id="knowledge-1",
        )

        self.assertIn("permissions", reply["response"])
        self.assertNotIn("detail", reply["response"])
        self.assertIn("Tu peux aussi regarder", reply["response"])

    def test_engine_refuses_unreliable_business_answer_without_source(self):
        knowledge_base = load_knowledge_base()
        engine = ChatbotEngine(
            knowledge_base=knowledge_base,
            connector=EmptyKnowledgeConnector(),
            llm_client=LLMClient(),
        )

        reply = engine.safe_response("Comment creer un site SharePoint ?", session_id="reliable-1")

        self.assertEqual(reply["intent"], "clarification")
        self.assertIn("fiable", reply["response"].lower())

    def test_engine_uses_context_for_follow_up_message(self):
        engine = build_engine()

        first_reply = engine.safe_response(
            "Comment creer un site SharePoint ?",
            session_id="ctx-1",
        )
        second_reply = engine.safe_response("et pour les droits ?", session_id="ctx-1")

        self.assertEqual(first_reply["intent"], "sharepoint_creation")
        self.assertIn(
            second_reply["intent"],
            {"sharepoint_partage", "sharepoint_creation", "follow_up"},
        )

    def test_engine_keeps_conversational_context_after_small_talk(self):
        engine = build_engine()

        engine.safe_response("Comment creer un site SharePoint ?", session_id="ctx-2")
        reply = engine.safe_response("merci", session_id="ctx-2")

        self.assertEqual(reply["intent"], "small_talk")
        self.assertTrue("etape suivante" in reply["response"].lower() or "suite" in reply["response"].lower())

    def test_engine_fallback_for_unknown_message(self):
        engine = build_engine()

        reply = engine.safe_response("abracadabra quantum licorne", session_id="unknown-1")

        self.assertTrue(reply["response"])
        self.assertTrue(reply["quick_replies"])

    def test_connector_searches_local_knowledge_base(self):
        connector = SharePointConnector()
        results = connector.search_knowledge("synchronisation OneDrive bloquee", limit=2)

        self.assertTrue(results)
        self.assertEqual(results[0]["category"], "onedrive")

    def test_topic_only_message_proposes_redirects(self):
        engine = build_engine()
        reply = engine.safe_response("one drive", session_id="topic-1")

        self.assertEqual(reply["intent"], "clarification")
        self.assertIn("OneDrive", reply["response"])
        self.assertIn("Diagnostic", reply["response"])

    def test_explicit_topic_switch_breaks_previous_context(self):
        engine = build_engine()

        engine.safe_response("un projet onedrive", session_id="topic-switch-1")
        reply = engine.safe_response("et un site sharepoint ?", session_id="topic-switch-1")

        self.assertIn("SharePoint", reply["response"])
        self.assertNotIn("OneDrive", reply["response"])

    def test_api_chat_endpoint(self):
        from API.app import app

        client = app.test_client()
        response = client.post(
            "/api/chat",
            json={"message": "Comment creer un site SharePoint ?", "session_id": "api-1"},
        )

        payload = response.get_json()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload["status"], "success")
        self.assertTrue(payload["response"])
        self.assertIn("confidence", payload)
        self.assertIn("Creer un site", payload["response"])


if __name__ == "__main__":
    unittest.main()
