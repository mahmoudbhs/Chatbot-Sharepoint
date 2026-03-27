import os
import sys
import tempfile
import unittest


BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASE_DIR)

from API.engine import ChatbotEngine  # noqa: E402
from API.graph_connector import GraphConnector  # noqa: E402
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

    def test_engine_answers_teams_navigation_question(self):
        engine = ChatbotEngine(
            knowledge_base=load_knowledge_base(),
            connector=SharePointConnector(),
            llm_client=LLMClient(),
        )

        reply = engine.safe_response("Comment naviguer dans Teams ?", session_id="teams-nav-1")

        self.assertIn("Activite", reply["response"])
        self.assertIn("Conversations", reply["response"])

    def test_engine_answers_teams_file_sharing_question(self):
        engine = ChatbotEngine(
            knowledge_base=load_knowledge_base(),
            connector=SharePointConnector(),
            llm_client=LLMClient(),
        )

        reply = engine.safe_response("Comment partager un fichier dans Teams ?", session_id="teams-file-1")

        self.assertIn("Joindre", reply["response"])
        self.assertIn("fichier", reply["response"].lower())

    def test_engine_answers_onedrive_access_question(self):
        engine = ChatbotEngine(
            knowledge_base=load_knowledge_base(),
            connector=SharePointConnector(),
            llm_client=LLMClient(),
        )

        reply = engine.safe_response("Qui a acces a mon fichier OneDrive ?", session_id="onedrive-access-1")

        self.assertIn("Gerer l'acces", reply["response"])

    def test_engine_answers_sharepoint_navigation_question(self):
        engine = ChatbotEngine(
            knowledge_base=load_knowledge_base(),
            connector=SharePointConnector(),
            llm_client=LLMClient(),
        )

        reply = engine.safe_response("Comment naviguer dans SharePoint ?", session_id="sharepoint-nav-1")

        self.assertIn("sites suivis", reply["response"].lower())
        self.assertIn("sites frequents", reply["response"].lower())

    def test_engine_answers_sharepoint_search_site_question(self):
        engine = ChatbotEngine(
            knowledge_base=load_knowledge_base(),
            connector=SharePointConnector(),
            llm_client=LLMClient(),
        )

        reply = engine.safe_response("Comment retrouver un site SharePoint ?", session_id="sharepoint-search-1")

        self.assertIn("barre de recherche", reply["response"].lower())
        self.assertIn("recents", reply["response"].lower())

    def test_engine_answers_sharepoint_version_history_question(self):
        engine = ChatbotEngine(
            knowledge_base=load_knowledge_base(),
            connector=SharePointConnector(),
            llm_client=LLMClient(),
        )

        reply = engine.safe_response("Comment voir l'historique des versions dans SharePoint ?", session_id="sharepoint-version-1")

        self.assertIn("Historique des versions", reply["response"])
        self.assertIn("restaurer", reply["response"].lower())

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

    def test_sharepoint_resources_use_official_microsoft_domains(self):
        connector = SharePointConnector()
        sharepoint_docs = [
            doc for doc in connector.documents if doc.get("category") == "sharepoint"
        ]

        self.assertTrue(sharepoint_docs)
        for document in sharepoint_docs:
            self.assertTrue(
                document["url"].startswith("https://support.microsoft.com/")
                or document["url"].startswith("https://learn.microsoft.com/")
            )

    def test_graph_connector_status_without_env_is_not_configured(self):
        connector = GraphConnector()
        status = connector.get_status()

        self.assertIn("enabled", status)
        self.assertIn("configured", status)
        if not status["enabled"]:
            self.assertFalse(status["configured"])

    def test_engine_answers_sharepoint_permission_roles_question(self):
        engine = ChatbotEngine(
            knowledge_base=load_knowledge_base(),
            connector=SharePointConnector(),
            llm_client=LLMClient(),
        )

        reply = engine.safe_response(
            "Quelle difference entre proprietaire membre et visiteur sur SharePoint ?",
            session_id="sharepoint-roles-1",
        )

        self.assertIn("proprietaires", reply["response"].lower())
        self.assertIn("membres", reply["response"].lower())
        self.assertIn("visiteurs", reply["response"].lower())

    def test_engine_answers_sharepoint_access_denied_question(self):
        engine = ChatbotEngine(
            knowledge_base=load_knowledge_base(),
            connector=SharePointConnector(),
            llm_client=LLMClient(),
        )

        reply = engine.safe_response(
            "Que faire si j'ai acces refuse sur un dossier SharePoint ?",
            session_id="sharepoint-access-1",
        )

        self.assertIn("acces refuse", reply["response"].lower())
        self.assertTrue(
            "proprietaire" in reply["response"].lower()
            or "administrateur" in reply["response"].lower()
        )

    def test_engine_answers_sharepoint_page_question(self):
        engine = ChatbotEngine(
            knowledge_base=load_knowledge_base(),
            connector=SharePointConnector(),
            llm_client=LLMClient(),
        )

        reply = engine.safe_response(
            "Comment creer une page SharePoint ?",
            session_id="sharepoint-page-1",
        )

        self.assertIn("page", reply["response"].lower())
        self.assertTrue(
            "webpart" in reply["response"].lower()
            or "nouveau" in reply["response"].lower()
        )

    def test_engine_answers_sharepoint_webpart_question(self):
        engine = ChatbotEngine(
            knowledge_base=load_knowledge_base(),
            connector=SharePointConnector(),
            llm_client=LLMClient(),
        )

        reply = engine.safe_response(
            "Comment rajouter un web part dans SharePoint ?",
            session_id="sharepoint-webpart-1",
        )

        self.assertTrue("webpart" in reply["response"].lower() or "web part" in reply["response"].lower())
        self.assertIn("modifier", reply["response"].lower())
        self.assertIn("+", reply["response"])

    def test_engine_answers_sharepoint_news_question(self):
        engine = ChatbotEngine(
            knowledge_base=load_knowledge_base(),
            connector=SharePointConnector(),
            llm_client=LLMClient(),
        )

        reply = engine.safe_response(
            "Comment publier une actualite sur SharePoint ?",
            session_id="sharepoint-news-1",
        )

        self.assertIn("actualites", reply["response"].lower())
        self.assertTrue(
            "site" in reply["response"].lower()
            or "teams" in reply["response"].lower()
        )

    def test_engine_answers_sharepoint_recycle_bin_question(self):
        engine = ChatbotEngine(
            knowledge_base=load_knowledge_base(),
            connector=SharePointConnector(),
            llm_client=LLMClient(),
        )

        reply = engine.safe_response(
            "Comment restaurer un fichier supprime dans la corbeille SharePoint ?",
            session_id="sharepoint-bin-1",
        )

        self.assertIn("corbeille", reply["response"].lower())
        self.assertIn("restaur", reply["response"].lower())

    def test_engine_answers_sharepoint_list_question(self):
        engine = ChatbotEngine(
            knowledge_base=load_knowledge_base(),
            connector=SharePointConnector(),
            llm_client=LLMClient(),
        )

        reply = engine.safe_response(
            "A quoi sert une liste SharePoint ?",
            session_id="sharepoint-list-1",
        )

        self.assertIn("liste", reply["response"].lower())
        self.assertTrue(
            "suivre" in reply["response"].lower()
            or "inventaire" in reply["response"].lower()
        )

    def test_engine_answers_sharepoint_content_type_question(self):
        engine = ChatbotEngine(
            knowledge_base=load_knowledge_base(),
            connector=SharePointConnector(),
            llm_client=LLMClient(),
        )

        reply = engine.safe_response(
            "A quoi sert un type de contenu SharePoint ?",
            session_id="sharepoint-content-type-1",
        )

        self.assertIn("type", reply["response"].lower())
        self.assertTrue(
            "coherence" in reply["response"].lower()
            or "metadonnees" in reply["response"].lower()
        )

    def test_engine_answers_tool_choice_question(self):
        engine = ChatbotEngine(
            knowledge_base=load_knowledge_base(),
            connector=SharePointConnector(),
            llm_client=LLMClient(),
        )

        reply = engine.safe_response(
            "Quand utiliser Teams SharePoint ou OneDrive ?",
            session_id="tool-choice-1",
        )

        self.assertIn("teams", reply["response"].lower())
        self.assertIn("sharepoint", reply["response"].lower())
        self.assertIn("onedrive", reply["response"].lower())

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

    def test_clarification_follow_up_stays_on_sharepoint_topic(self):
        engine = ChatbotEngine(
            knowledge_base=load_knowledge_base(),
            connector=SharePointConnector(),
            llm_client=LLMClient(),
        )

        engine.safe_response("sharepoint", session_id="clarify-followup-1")
        reply = engine.safe_response("les bonnes pratique", session_id="clarify-followup-1")

        self.assertIn("structure", reply["response"].lower())
        self.assertIn("sharepoint", reply["response"].lower())
        self.assertNotIn("onedrive", reply["response"].lower())

    def test_broad_topic_request_for_onedrive_stays_in_clarification_mode(self):
        engine = ChatbotEngine(
            knowledge_base=load_knowledge_base(),
            connector=SharePointConnector(),
            llm_client=LLMClient(),
        )

        reply = engine.safe_response("dis moi sur one drive", session_id="broad-topic-1")

        self.assertEqual(reply["intent"], "clarification")
        self.assertIn("OneDrive", reply["response"])
        self.assertNotIn("Corbeille", reply["response"])

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

    def test_api_status_endpoint(self):
        from API.app import app

        client = app.test_client()
        response = client.get("/api/status")

        payload = response.get_json()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload["status"], "success")
        self.assertIn("connector", payload)
        self.assertIn("graph", payload["connector"])


if __name__ == "__main__":
    unittest.main()
