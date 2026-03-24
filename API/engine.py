import os
import pickle
import random
import re
import unicodedata
from collections import defaultdict
from typing import Dict, List, Optional

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.pipeline import Pipeline

from API.knowledge_base import build_training_samples, load_knowledge_base
from API.llm_client import LLMClient
from API.memory_store import MemoryStore
from API.sharepoint_connector import SharePointConnector


BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODELS_DIR = os.path.join(BASE_DIR, "MODELS")
ARTIFACT_PATH = os.path.join(MODELS_DIR, "chatbot_artifacts.pkl")


def normalize_text(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text.lower())
    normalized = normalized.encode("ascii", "ignore").decode("ascii")
    normalized = normalized.replace("one drive", "onedrive")
    normalized = normalized.replace("share point", "sharepoint")
    normalized = normalized.replace("microsoft teams", "teams")
    normalized = re.sub(r"[^a-z0-9\s]", " ", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized


def build_pipeline() -> Pipeline:
    return Pipeline(
        [
            (
                "vectorizer",
                TfidfVectorizer(
                    preprocessor=normalize_text,
                    analyzer="char_wb",
                    ngram_range=(3, 5),
                    min_df=1,
                ),
            ),
            (
                "classifier",
                LogisticRegression(
                    max_iter=1500,
                    multi_class="auto",
                    class_weight="balanced",
                ),
            ),
        ]
    )


class ChatbotEngine:
    def __init__(
        self,
        knowledge_base: Optional[dict] = None,
        connector: Optional[SharePointConnector] = None,
        llm_client: Optional[LLMClient] = None,
        memory_store: Optional[MemoryStore] = None,
        model_bundle: Optional[dict] = None,
    ) -> None:
        self.knowledge_base = knowledge_base or load_knowledge_base()
        self.connector = connector or SharePointConnector()
        self.llm_client = llm_client or LLMClient()
        self.memory_store = memory_store or MemoryStore()
        self.intent_lookup = {
            intent["tag"]: intent for intent in self.knowledge_base["intents"]
        }
        self.defaults = self.knowledge_base.get("defaults") or [
            "Je ne suis pas certain de comprendre. Pouvez-vous reformuler votre besoin ?"
        ]
        self.error_responses = self.knowledge_base.get("errors") or [
            "Une erreur est survenue. Pouvez-vous r\u00e9essayer ?"
        ]
        self.quick_replies = self.knowledge_base.get("quick_replies", {})
        self.session_state: Dict[str, dict] = defaultdict(dict)

        if model_bundle is None:
            model_bundle = self._load_or_train_bundle()

        self.pipeline: Pipeline = model_bundle["pipeline"]
        self.retrieval_vectorizer: TfidfVectorizer = model_bundle["retrieval_vectorizer"]
        self.pattern_matrix = model_bundle["pattern_matrix"]
        self.pattern_samples = model_bundle["pattern_samples"]
        self.procedural_intents = {
            "sharepoint_creation",
            "sharepoint_partage",
            "sharepoint_suppression",
            "teams_reunion",
            "teams_partage_ecran",
            "teams_equipe",
            "onedrive_partage",
            "onedrive_synchro",
            "onedrive_corbeille",
            "outlook_absence",
            "outlook_signature",
            "mot_de_passe",
        }
        self.small_talk_patterns = {
            "greeting": {
                "salut",
                "bonjour",
                "hello",
                "hey",
                "yo",
                "coucou",
                "bonsoir",
                "cc",
                "slt",
                "bjr",
            },
            "how_are_you": {
                "ca va",
                "ca va ?",
                "cava",
                "tu vas bien",
                "comment tu vas",
                "comment ca va",
                "toi ca va",
                "toi cava",
            },
            "thanks": {
                "merci",
                "merci beaucoup",
                "super merci",
                "top merci",
                "parfait merci",
            },
            "ack": {
                "ok",
                "daccord",
                "d accord",
                "ça marche",
                "ca marche",
                "je vois",
                "compris",
            },
            "goodbye": {
                "bye",
                "au revoir",
                "a plus",
                "a bientot",
                "ciao",
            },
        }
        self.domain_keywords = {
            "sharepoint",
            "teams",
            "onedrive",
            "outlook",
            "mot",
            "passe",
            "m365",
            "site",
            "reunion",
            "ecran",
            "signature",
            "absence",
            "document",
            "fichier",
            "guide",
            "droit",
            "acces",
            "permission",
        }
        self.clarification_prompts = [
            "Je peux t'aider, mais il me faut juste le sujet. Tu parles de SharePoint, Teams, OneDrive ou Outlook ?",
            "Dis-moi juste sur quel outil tu bloques et je te reponds plus clairement : SharePoint, Teams, OneDrive ou Outlook ?",
        ]
        self.incomplete_sentence_prompts = [
            "Je te suis, mais je n'ai pas encore la fin de ta demande. Tu veux faire quoi exactement ?",
            "Vas-y, termine ta phrase et je te reponds plus precisement.",
            "Je crois que ta demande n'est pas complete. Dis-moi exactement ce que tu veux faire.",
        ]
        self.topic_only_prompts = {
            "sharepoint": "Tu veux faire quoi sur SharePoint exactement ?",
            "teams": "Tu veux faire quoi dans Teams exactement ?",
            "onedrive": "Tu veux faire quoi sur OneDrive exactement ?",
            "outlook": "Tu veux faire quoi dans Outlook exactement ?",
        }
        self.topic_aliases = {
            "sharepoint": {"sharepoint", "site sharepoint", "site"},
            "teams": {"teams", "team", "reunion teams"},
            "onedrive": {"onedrive", "one drive", "projet onedrive", "fichier onedrive"},
            "outlook": {"outlook", "mail outlook", "boite mail"},
        }
        self.source_required_intents = set(self.procedural_intents)
        self.reliable_answer_prompts = [
            "Je prefere ne pas te donner une indication hasardeuse. Je n'ai pas encore de source assez fiable pour repondre precisement a cette demande.",
            "Je n'ai pas encore d'information suffisamment fiable pour te repondre proprement sur ce point.",
        ]

    def _message_has_phrase(self, normalized_message: str, phrases: set[str]) -> bool:
        for phrase in phrases:
            if phrase in normalized_message:
                return True
        return False

    def _finalize_response(
        self,
        session_id: str,
        response: str,
        user_message: str,
        knowledge_titles: Optional[List[str]] = None,
    ) -> str:
        state = self._get_session(session_id)
        history = state.get("history", [])
        llm_reply = self.llm_client.generate_reply(
            user_message=user_message,
            deterministic_reply=response,
            history=history,
            knowledge_titles=knowledge_titles,
        )
        return llm_reply or response

    def _get_session(self, session_id: str) -> dict:
        state = self.session_state[session_id]
        state.setdefault("history", [])
        if "memory_loaded" not in state:
            persisted_memory = self.memory_store.get_user_memory(session_id)
            state["persisted_memory"] = persisted_memory
            recent_topics = persisted_memory.get("recent_topics", [])
            if recent_topics and "last_topic" not in state:
                state["last_topic"] = recent_topics[-1]
            if persisted_memory.get("last_intent") and "last_intent" not in state:
                state["last_intent"] = persisted_memory["last_intent"]
            state["memory_loaded"] = True
        return state

    def _remember_turn(self, session_id: str, role: str, text: str) -> None:
        state = self._get_session(session_id)
        state["history"].append({"role": role, "text": text})
        state["history"] = state["history"][-8:]

    def _extract_explicit_topic(self, normalized_message: str) -> Optional[str]:
        for topic, aliases in self.topic_aliases.items():
            for alias in aliases:
                if alias in normalized_message:
                    return topic
        return None

    def _small_talk_response(self, normalized_message: str, session_id: str) -> Optional[str]:
        state = self._get_session(session_id)
        last_intent = state.get("last_intent")
        persisted_memory = state.get("persisted_memory", {})
        preferred_topic = None
        topic_counts = persisted_memory.get("topic_counts", {})
        if topic_counts:
            preferred_topic = max(topic_counts, key=topic_counts.get)
        compact_message = normalized_message.replace(" ", "")

        if (
            normalized_message in self.small_talk_patterns["greeting"]
            or normalized_message.startswith("salut ")
            or normalized_message.startswith("bonjour ")
        ):
            if last_intent and preferred_topic:
                return random.choice(
                    [
                        f"Salut. Si tu veux, on peut repartir sur {preferred_topic}.",
                        f"Bonjour. Je me souviens qu'on parlait souvent de {preferred_topic}. On reprend ?",
                    ]
                )
            if last_intent:
                return random.choice(
                    [
                        "Salut. On reprend ou on s'etait arretes ?",
                        "Salut. Si tu veux, on peut continuer sur ton sujet precedent.",
                    ]
                )
            return random.choice(
                [
                    "Salut. Je peux t'aider sur SharePoint, Teams, OneDrive ou Outlook.",
                    "Bonjour. Dis-moi ce que tu essaies de faire et je t'aide.",
                    f"Salut. Si tu veux, on peut repartir sur {preferred_topic}."
                    if preferred_topic
                    else "Bonjour. Dis-moi ce que tu essaies de faire et je t'aide.",
                ]
            )

        if (
            self._message_has_phrase(normalized_message, self.small_talk_patterns["how_are_you"])
            or "cava" in compact_message
            or ("toi" in normalized_message and "ca va" in normalized_message)
        ):
            return random.choice(
                [
                    "Ca va, merci. Dis-moi plutot ce qu'il te faut et on avance.",
                    "Oui, ca va. Dis-moi sur quoi tu bloques.",
                ]
            )

        if self._message_has_phrase(normalized_message, self.small_talk_patterns["thanks"]):
            if last_intent:
                return random.choice(
                    [
                        "Avec plaisir. Si tu veux, on peut aussi regarder l'etape suivante.",
                        "Pas de souci. Si quelque chose bloque encore, envoie-moi la suite.",
                    ]
                )
            return random.choice(
                [
                    "Avec plaisir.",
                    "Pas de souci.",
                ]
            )

        if self._message_has_phrase(normalized_message, self.small_talk_patterns["ack"]):
            if last_intent:
                return random.choice(
                    [
                        "Parfait. Si tu veux, je peux aussi te detailler la suite.",
                        "Ok. Si tu veux aller plus loin, pose-moi la prochaine etape.",
                    ]
                )
            return random.choice(
                [
                    "Ok.",
                    "D'accord.",
                ]
            )

        if self._message_has_phrase(normalized_message, self.small_talk_patterns["goodbye"]):
            return random.choice(
                [
                    "A plus. Si tu rebloques, reviens vers moi.",
                    "Ca marche, a bientot.",
                ]
            )

        return None

    def _should_clarify(self, normalized_message: str, prediction: dict, knowledge_reply: Optional[dict]) -> bool:
        tokens = normalized_message.split()
        if not tokens:
            return False

        domain_overlap = set(tokens) & self.domain_keywords
        short_message = len(tokens) <= 5
        low_signal = prediction["confidence"] < 0.45 and not knowledge_reply

        vague_markers = {
            "aide",
            "help",
            "probleme",
            "bloque",
            "question",
            "besoin",
            "comment",
            "pk",
            "pourquoi",
        }
        is_vague = bool(set(tokens) & vague_markers) or short_message
        return is_vague and not domain_overlap and low_signal

    def _is_incomplete_request(self, normalized_message: str) -> bool:
        incomplete_starts = {
            "je veux",
            "j veux",
            "je dois",
            "je cherche",
            "je voudrais",
            "je souhaite",
            "j ai besoin",
            "jai besoin",
            "il faut",
            "aide moi",
            "dis moi",
            "montre moi",
        }

        if normalized_message in incomplete_starts:
            return True

        if normalized_message.startswith(
            ("je veux ", "je dois ", "je cherche ", "je voudrais ", "je souhaite ")
        ):
            token_count = len(normalized_message.split())
            if token_count <= 3:
                return True

        return False

    def _topic_only_response(self, normalized_message: str) -> Optional[str]:
        if normalized_message in self.topic_only_prompts:
            documents = self.connector.get_documents_by_category(normalized_message, limit=4)
            if documents:
                titles = [document["title"] for document in documents[:4]]
                response = (
                    f"{self.topic_only_prompts[normalized_message]} "
                    f"Par exemple : {', '.join(titles)}."
                )
                return response
            return self.topic_only_prompts[normalized_message]
        return None

    def _conversation_follow_up(self, normalized_message: str, session_id: str) -> Optional[str]:
        state = self._get_session(session_id)
        last_intent = state.get("last_intent")
        last_topic = state.get("last_topic")
        explicit_topic = self._extract_explicit_topic(normalized_message)

        if explicit_topic and explicit_topic != last_topic:
            return None

        if normalized_message in {"et", "ensuite", "sinon", "aussi", "et apres"} and last_topic:
            return f"On peut continuer sur {last_topic}. Dis-moi juste ce que tu veux faire exactement."

        if normalized_message in {"et pour les droits", "et les droits", "les droits", "les acces"}:
            if last_intent and last_intent.startswith("sharepoint"):
                return "Pour les droits sur SharePoint, va dans les autorisations du site puis ajoute ou ajuste les membres selon le besoin."

        if normalized_message in {"pourquoi", "comment"} and last_intent:
            return None

        return None

    def _pick_intro(self, intent: Optional[str], knowledge_based: bool = False) -> str:
        intros = {
            "salutations": [
                "Bonjour,",
                "Salut,",
            ],
            "sharepoint_creation": [
                "Oui, bien sur.",
                "Voici le plus simple pour le faire.",
            ],
            "sharepoint_partage": [
                "Oui.",
                "Pour gerer l'acces, le plus direct est de faire comme ca.",
            ],
            "sharepoint_suppression": [
                "Oui, c'est possible.",
                "Tu peux le faire, mais il faut faire attention.",
            ],
            "teams_reunion": [
                "Oui.",
                "Le plus simple pour lancer ca, c'est :",
            ],
            "teams_partage_ecran": [
                "Oui.",
                "Pendant la reunion, fais comme ca :",
            ],
            "teams_equipe": [
                "Oui.",
                "Pour creer une equipe, tu peux faire ca :",
            ],
            "onedrive_partage": [
                "Oui.",
                "Le plus propre pour partager un fichier, c'est :",
            ],
            "onedrive_synchro": [
                "Oui, il y a quelques verifications utiles a faire.",
                "Dans ce cas, je regarderais ca en premier.",
            ],
            "onedrive_corbeille": [
                "Oui, tu peux souvent le recuperer.",
                "Normalement, tu peux encore le restaurer.",
            ],
            "outlook_absence": [
                "Oui.",
                "Tu peux regler ca assez vite :",
            ],
            "outlook_signature": [
                "Oui.",
                "Pour la signature, fais plutot comme ca :",
            ],
            "mot_de_passe": [
                "Oui.",
                "Dans ce cas, commence par ca :",
            ],
            "identite_bot": [
                "Je suis la pour t'aider sur M365.",
                "Je sers surtout a repondre sur SharePoint, Teams, OneDrive et Outlook.",
            ],
            "remerciements": [
                "Avec plaisir.",
                "Pas de souci.",
            ],
            "au_revoir": [
                "D'accord.",
                "Ca marche.",
            ],
            "get_guide": [
                "J'ai trouve ca pour toi :",
                "Tu peux deja regarder ces ressources :",
            ],
            None: [
                "Voila ce que j'ai trouve.",
                "Je pense que ca peut t'aider :",
            ],
        }

        if knowledge_based:
            return random.choice(
                [
                    "Voila l'idee la plus utile sur ce sujet.",
                    "Sur ce point, retiens surtout ca.",
                ]
            )

        return random.choice(intros.get(intent, intros[None]))

    def _format_steps(self, text: str) -> str:
        matches = re.findall(r"(\d+)\.\s*([^\n]+)", text)
        if not matches:
            return text.strip()

        formatted_steps = [f"- {step_text.strip()}" for _, step_text in matches]
        return "\n".join(formatted_steps)

    def _humanize_response(
        self,
        response: str,
        intent: Optional[str],
        message: str,
        knowledge_based: bool = False,
    ) -> str:
        clean_response = response.strip()
        clean_response = re.sub(r"\s+\n", "\n", clean_response)
        clean_response = re.sub(r"\n{3,}", "\n\n", clean_response)

        if re.search(r"\d+\.\s*", clean_response):
            clean_response = self._format_steps(clean_response)

        intro = self._pick_intro(intent, knowledge_based=knowledge_based)

        if knowledge_based:
            return f"{intro}\n{clean_response}"

        if intent in {"salutations", "remerciements", "au_revoir", "identite_bot"}:
            return clean_response

        if clean_response.startswith("- "):
            return f"{intro}\n{clean_response}"

        return f"{intro} {clean_response}"

    def _knowledge_response(self, message: str) -> Optional[dict]:
        results = self.connector.search_knowledge(message, limit=2)
        if not results:
            return None

        top_result = results[0]
        if top_result["score"] < 0.34:
            return None

        return {
            "response": top_result["content"].strip(),
            "source_category": top_result.get("category"),
            "knowledge_score": top_result["score"],
            "source_title": top_result.get("title"),
            "source_url": top_result.get("url"),
        }

    def _has_reliable_source(self, knowledge_reply: Optional[dict], minimum_score: float = 0.55) -> bool:
        if not knowledge_reply:
            return False
        return float(knowledge_reply.get("knowledge_score", 0.0)) >= minimum_score

    def _knowledge_redirects(self, message: str, category: Optional[str] = None) -> List[str]:
        if category:
            documents = self.connector.get_documents_by_category(category, limit=4)
        else:
            documents = self.connector.search_knowledge(message, limit=4)

        titles = []
        for document in documents:
            title = document.get("title")
            if title and title not in titles:
                titles.append(title)
        return titles[:4]

    def _load_or_train_bundle(self) -> dict:
        if os.path.exists(ARTIFACT_PATH):
            with open(ARTIFACT_PATH, "rb") as file:
                return pickle.load(file)

        bundle = self.train_bundle()
        os.makedirs(MODELS_DIR, exist_ok=True)
        with open(ARTIFACT_PATH, "wb") as file:
            pickle.dump(bundle, file)
        return bundle

    def train_bundle(self) -> dict:
        samples = build_training_samples(self.knowledge_base)
        texts = [sample["text"] for sample in samples]
        labels = [sample["tag"] for sample in samples]

        pipeline = build_pipeline()
        pipeline.fit(texts, labels)

        retrieval_vectorizer = TfidfVectorizer(
            preprocessor=normalize_text,
            analyzer="char_wb",
            ngram_range=(3, 5),
            min_df=1,
        )
        pattern_matrix = retrieval_vectorizer.fit_transform(texts)

        return {
            "pipeline": pipeline,
            "retrieval_vectorizer": retrieval_vectorizer,
            "pattern_matrix": pattern_matrix,
            "pattern_samples": samples,
        }

    def _expand_with_context(self, message: str, session_id: str) -> str:
        state = self._get_session(session_id)
        last_intent = state.get("last_intent")
        normalized_message = normalize_text(message)
        explicit_topic = self._extract_explicit_topic(normalized_message)

        if not last_intent:
            return message

        if explicit_topic:
            return message

        if len(normalized_message.split()) > 4:
            return message

        follow_up_markers = {
            "et",
            "sinon",
            "aussi",
            "ensuite",
            "apres",
            "apres ca",
            "et pour",
            "comment",
        }
        if normalized_message in follow_up_markers or normalized_message.startswith("et "):
            return f"{last_intent} {message}"

        topic_hints = {
            "sharepoint",
            "teams",
            "onedrive",
            "outlook",
            "permission",
            "document",
            "fichier",
            "reunion",
        }
        if not set(normalized_message.split()) & topic_hints:
            return f"{last_intent} {message}"

        return message

    def _predict(self, message: str) -> dict:
        probabilities = self.pipeline.predict_proba([message])[0]
        classes = self.pipeline.classes_
        best_index = int(np.argmax(probabilities))
        predicted_intent = classes[best_index]
        classifier_confidence = float(probabilities[best_index])

        query_vector = self.retrieval_vectorizer.transform([message])
        similarities = cosine_similarity(query_vector, self.pattern_matrix)[0]
        retrieval_index = int(np.argmax(similarities))
        retrieval_match = self.pattern_samples[retrieval_index]
        retrieval_score = float(similarities[retrieval_index])

        final_intent = predicted_intent
        final_confidence = classifier_confidence
        if retrieval_score >= 0.35 and retrieval_match["tag"] != predicted_intent:
            final_intent = retrieval_match["tag"]
            final_confidence = max(classifier_confidence, retrieval_score)
        else:
            final_confidence = max(classifier_confidence, retrieval_score)

        return {
            "intent": final_intent,
            "confidence": final_confidence,
            "classifier_confidence": classifier_confidence,
            "retrieval_score": retrieval_score,
            "matched_pattern": retrieval_match["text"],
        }

    def _guides_response(self) -> str:
        guides = self.connector.get_user_guides()
        if not guides:
            return "Je n'ai pas trouv\u00e9 de guides disponibles pour le moment."

        lines = ["Voici les guides disponibles :"]
        for guide in guides[:3]:
            lines.append(f"- {guide['title']} : {guide['url']}")
        return self._humanize_response("\n".join(lines), "get_guide", "", knowledge_based=False)

    def _faq_response(self, tag: str) -> Optional[str]:
        topic = tag.replace("_usage", "")
        for faq in self.connector.get_faq_items():
            category = normalize_text(faq.get("category", ""))
            if topic in category:
                return faq.get("answer")
        return None

    def _build_response(self, intent: str, message: str) -> str:
        if intent == "get_guide":
            return self._guides_response()

        responses = self.intent_lookup.get(intent, {}).get("responses", [])
        if responses:
            return self._humanize_response(random.choice(responses), intent, message)

        return self._humanize_response(random.choice(self.defaults), None, message)

    def get_response(self, message: str, session_id: str = "default") -> dict:
        state = self._get_session(session_id)
        self._remember_turn(session_id, "user", message)
        normalized_message = normalize_text(message)

        small_talk_reply = self._small_talk_response(normalized_message, session_id)
        if small_talk_reply:
            final_response = self._finalize_response(session_id, small_talk_reply, message)
            self._remember_turn(session_id, "assistant", final_response)
            return {
                "response": final_response,
                "intent": "small_talk",
                "confidence": 1.0,
                "matched_pattern": None,
                "quick_replies": self.quick_replies,
            }

        if self._is_incomplete_request(normalized_message):
            response = random.choice(self.incomplete_sentence_prompts)
            final_response = self._finalize_response(session_id, response, message)
            self._remember_turn(session_id, "assistant", final_response)
            return {
                "response": final_response,
                "intent": "clarification",
                "confidence": 0.99,
                "matched_pattern": None,
                "quick_replies": self.quick_replies,
            }

        explicit_topic = self._extract_explicit_topic(normalized_message)
        if explicit_topic and normalized_message in {explicit_topic, f"un projet {explicit_topic}"}:
            topic_only_reply = self._topic_only_response(explicit_topic)
            if topic_only_reply:
                final_response = self._finalize_response(
                    session_id,
                    topic_only_reply,
                    message,
                    knowledge_titles=self._knowledge_redirects(explicit_topic, category=explicit_topic),
                )
                state["last_topic"] = explicit_topic
                self.memory_store.remember_topic(
                    session_id,
                    explicit_topic,
                    intent="clarification",
                    message=message,
                )
                self._remember_turn(session_id, "assistant", final_response)
                return {
                    "response": final_response,
                    "intent": "clarification",
                    "confidence": 0.98,
                    "matched_pattern": None,
                    "quick_replies": self.quick_replies,
                }

        topic_only_reply = self._topic_only_response(normalized_message)
        if topic_only_reply:
            final_response = self._finalize_response(
                session_id,
                topic_only_reply,
                message,
                knowledge_titles=self._knowledge_redirects(normalized_message, category=normalized_message),
            )
            self.memory_store.remember_topic(
                session_id,
                normalized_message,
                intent="clarification",
                message=message,
            )
            self._remember_turn(session_id, "assistant", final_response)
            return {
                "response": final_response,
                "intent": "clarification",
                "confidence": 0.98,
                "matched_pattern": None,
                "quick_replies": self.quick_replies,
            }

        conversational_follow_up = self._conversation_follow_up(normalized_message, session_id)
        if conversational_follow_up:
            final_response = self._finalize_response(session_id, conversational_follow_up, message)
            self._remember_turn(session_id, "assistant", final_response)
            return {
                "response": final_response,
                "intent": "follow_up",
                "confidence": 0.95,
                "matched_pattern": None,
                "quick_replies": self.quick_replies,
            }

        expanded_message = self._expand_with_context(message, session_id)
        prediction = self._predict(expanded_message)
        knowledge_reply = self._knowledge_response(expanded_message)
        prefer_procedural_reply = (
            prediction["intent"] in self.procedural_intents and prediction["confidence"] >= 0.45
        )
        generic_problem = {
            "j ai un probleme",
            "jai un probleme",
            "probleme",
            "j ai un souci",
            "jai un souci",
            "je suis bloque",
            "je bloque",
        }
        if normalized_message in generic_problem or self._should_clarify(normalized_message, prediction, knowledge_reply):
            response = random.choice(self.clarification_prompts)
            state["awaiting_clarification"] = True
            final_response = self._finalize_response(session_id, response, message)
            self.memory_store.remember_topic(
                session_id,
                state.get("last_topic"),
                intent="clarification",
                message=message,
            )
            self._remember_turn(session_id, "assistant", final_response)
            return {
                "response": final_response,
                "intent": "clarification",
                "confidence": max(prediction["confidence"], 0.4),
                "matched_pattern": prediction["matched_pattern"],
                "quick_replies": self.quick_replies,
            }

        if knowledge_reply and knowledge_reply["knowledge_score"] >= 0.55 and not prefer_procedural_reply:
            redirect_titles = self._knowledge_redirects(
                expanded_message,
                category=knowledge_reply.get("source_category"),
            )
            response = knowledge_reply["response"]
            if redirect_titles:
                response += "\n\nTu peux aussi regarder : " + ", ".join(redirect_titles[:3]) + "."
            final_response = self._finalize_response(
                session_id,
                response,
                message,
                knowledge_titles=redirect_titles,
            )
            response_payload = {
                "response": final_response,
                "intent": prediction["intent"],
                "confidence": knowledge_reply["knowledge_score"],
                "matched_pattern": knowledge_reply.get("source_title") or prediction["matched_pattern"],
                "quick_replies": self.quick_replies,
            }
            state["last_intent"] = prediction["intent"]
            state["last_message"] = message
            state["last_topic"] = knowledge_reply.get("source_category") or prediction["intent"]
            state["awaiting_clarification"] = False
            self.memory_store.remember_topic(
                session_id,
                state["last_topic"],
                intent=prediction["intent"],
                message=message,
            )
            self._remember_turn(session_id, "assistant", final_response)
            return response_payload

        if prediction["intent"] in self.source_required_intents and not self._has_reliable_source(knowledge_reply):
            response = random.choice(self.reliable_answer_prompts)
            explicit_topic = explicit_topic or state.get("last_topic")
            if explicit_topic in self.topic_only_prompts:
                response += " " + self.topic_only_prompts[explicit_topic]
            final_response = self._finalize_response(session_id, response, message)
            state["awaiting_clarification"] = True
            self.memory_store.remember_topic(
                session_id,
                explicit_topic,
                intent="clarification",
                message=message,
            )
            self._remember_turn(session_id, "assistant", final_response)
            return {
                "response": final_response,
                "intent": "clarification",
                "confidence": prediction["confidence"],
                "matched_pattern": prediction["matched_pattern"],
                "quick_replies": self.quick_replies,
            }

        if prediction["confidence"] < 0.30:
            if knowledge_reply:
                response_payload = {
                    "response": self._finalize_response(session_id, knowledge_reply["response"], message),
                    "intent": prediction["intent"],
                    "confidence": knowledge_reply["knowledge_score"],
                    "matched_pattern": prediction["matched_pattern"],
                    "quick_replies": self.quick_replies,
                }
                state["last_intent"] = prediction["intent"]
                state["last_message"] = message
                state["last_topic"] = knowledge_reply.get("source_category") or prediction["intent"]
                state["awaiting_clarification"] = False
                self.memory_store.remember_topic(
                    session_id,
                    state["last_topic"],
                    intent=prediction["intent"],
                    message=message,
                )
                self._remember_turn(session_id, "assistant", response_payload["response"])
                return response_payload
            response = random.choice(self.defaults)
            final_response = self._finalize_response(session_id, response, message)
            state["awaiting_clarification"] = False
            self._remember_turn(session_id, "assistant", final_response)
            return {
                "response": final_response,
                "intent": None,
                "confidence": prediction["confidence"],
                "matched_pattern": prediction["matched_pattern"],
                "quick_replies": self.quick_replies,
            }

        response = self._build_response(prediction["intent"], expanded_message)
        final_response = self._finalize_response(session_id, response, message)
        state["last_intent"] = prediction["intent"]
        state["last_message"] = message
        state["last_topic"] = explicit_topic or prediction["intent"].split("_")[0]
        state["awaiting_clarification"] = False
        self.memory_store.remember_topic(
            session_id,
            state["last_topic"],
            intent=prediction["intent"],
            message=message,
        )
        self._remember_turn(session_id, "assistant", final_response)
        return {
            "response": final_response,
            "intent": prediction["intent"],
            "confidence": prediction["confidence"],
            "matched_pattern": prediction["matched_pattern"],
            "quick_replies": self.quick_replies,
        }

    def safe_response(self, message: str, session_id: str = "default") -> dict:
        try:
            return self.get_response(message, session_id=session_id)
        except Exception:
            return {
                "response": random.choice(self.error_responses),
                "intent": None,
                "confidence": 0.0,
                "matched_pattern": None,
                "quick_replies": self.quick_replies,
            }
