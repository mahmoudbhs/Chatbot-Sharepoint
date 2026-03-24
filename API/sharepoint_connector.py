import json
import os
import re
import unicodedata
from typing import List

from dotenv import load_dotenv

try:
    from office365.runtime.auth.client_credential import ClientCredential
    from office365.sharepoint.client_context import ClientContext
except Exception:  # pragma: no cover
    ClientCredential = None
    ClientContext = None


BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "DATA")
KNOWLEDGE_PATH = os.path.join(DATA_DIR, "knowledge_documents.json")


def normalize_text(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text.lower())
    normalized = normalized.encode("ascii", "ignore").decode("ascii")
    normalized = normalized.replace("one drive", "onedrive")
    normalized = normalized.replace("share point", "sharepoint")
    normalized = normalized.replace("microsoft teams", "teams")
    normalized = re.sub(r"[^a-z0-9\s]", " ", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized


class SharePointConnector:
    def __init__(self) -> None:
        load_dotenv()
        self.site_url = os.getenv("SHAREPOINT_SITE_URL", "").strip()
        self.client_id = os.getenv("SHAREPOINT_CLIENT_ID", "").strip()
        self.client_secret = os.getenv("SHAREPOINT_CLIENT_SECRET", "").strip()
        self.faq_list_name = os.getenv("SHAREPOINT_FAQ_LIST", "ChatbotFAQ").strip()
        self.guides_list_name = os.getenv("SHAREPOINT_GUIDES_LIST", "ChatbotGuides").strip()
        self.documents = self._load_local_documents()

        if self.is_live_configured:
            print("Connecteur SharePoint initialise (Mode Live si accessible)")
        else:
            print("Connecteur SharePoint initialise (Base locale + fallback)")

    @property
    def is_live_configured(self) -> bool:
        return bool(
            self.site_url
            and self.client_id
            and self.client_secret
            and ClientContext is not None
            and ClientCredential is not None
        )

    def _load_local_documents(self) -> List[dict]:
        with open(KNOWLEDGE_PATH, "r", encoding="utf-8") as file:
            payload = json.load(file)
        return payload.get("documents", [])

    def _get_context(self):
        if not self.is_live_configured:
            return None

        credentials = ClientCredential(self.client_id, self.client_secret)
        return ClientContext(self.site_url).with_credentials(credentials)

    def _safe_field(self, item, field_name: str, default: str = "") -> str:
        properties = getattr(item, "properties", {})
        value = properties.get(field_name, default)
        if value is None:
            return default
        return str(value)

    def _fetch_list_items(self, list_name: str) -> List[dict]:
        context = self._get_context()
        if context is None:
            return []

        try:
            sp_list = context.web.lists.get_by_title(list_name)
            items = sp_list.items.top(100).get().execute_query()
        except Exception:
            return []

        results = []
        for item in items:
            results.append(
                {
                    "title": self._safe_field(item, "Title"),
                    "category": self._safe_field(item, "Category"),
                    "answer": self._safe_field(item, "Answer"),
                    "url": self._safe_field(item, "Url"),
                    "keywords": self._safe_field(item, "Keywords"),
                    "content": self._safe_field(item, "Content") or self._safe_field(item, "Answer"),
                }
            )
        return results

    def get_user_guides(self) -> List[dict]:
        live_guides = self._fetch_list_items(self.guides_list_name)
        guides = []

        for guide in live_guides:
            if guide["title"]:
                guides.append(
                    {
                        "title": guide["title"],
                        "url": guide["url"] or self.site_url,
                        "category": guide["category"] or "guide",
                    }
                )

        if guides:
            return guides

        return [
            {
                "title": document["title"],
                "url": document["url"],
                "category": document["category"],
            }
            for document in self.documents[:5]
        ]

    def get_faq_items(self) -> List[dict]:
        live_faq = self._fetch_list_items(self.faq_list_name)
        if live_faq:
            return [
                {
                    "category": item["category"] or "general",
                    "answer": item["answer"] or item["content"],
                    "title": item["title"],
                    "url": item["url"],
                }
                for item in live_faq
                if item["answer"] or item["content"]
            ]

        return [
            {
                "category": document["category"],
                "answer": document["content"],
                "title": document["title"],
                "url": document["url"],
            }
            for document in self.documents
        ]

    def search_knowledge(self, query: str, limit: int = 3) -> List[dict]:
        normalized_query = normalize_text(query)
        if not normalized_query:
            return []

        query_tokens = set(normalized_query.split())
        results = []

        for document in self.documents:
            haystack = " ".join(
                [
                    document.get("title", ""),
                    document.get("category", ""),
                    document.get("content", ""),
                    " ".join(document.get("keywords", [])),
                ]
            )
            normalized_haystack = normalize_text(haystack)
            document_tokens = set(normalized_haystack.split())

            overlap = len(query_tokens & document_tokens)
            if overlap == 0:
                continue

            score = overlap / max(len(query_tokens), 1)
            if document.get("category") and normalize_text(document["category"]) in normalized_query:
                score += 0.2

            results.append(
                {
                    "score": round(score, 4),
                    "title": document.get("title", ""),
                    "category": document.get("category", "general"),
                    "content": document.get("content", ""),
                    "url": document.get("url", ""),
                }
            )

        for item in self.get_faq_items():
            haystack = " ".join(
                [item.get("title", ""), item.get("category", ""), item.get("answer", "")]
            )
            normalized_haystack = normalize_text(haystack)
            document_tokens = set(normalized_haystack.split())
            overlap = len(query_tokens & document_tokens)
            if overlap == 0:
                continue

            score = overlap / max(len(query_tokens), 1)
            results.append(
                {
                    "score": round(score, 4),
                    "title": item.get("title", "FAQ"),
                    "category": item.get("category", "general"),
                    "content": item.get("answer", ""),
                    "url": item.get("url", ""),
                }
            )

        results.sort(key=lambda item: item["score"], reverse=True)

        deduped = []
        seen = set()
        for item in results:
            key = (item["title"], item["content"])
            if key in seen:
                continue
            seen.add(key)
            deduped.append(item)
            if len(deduped) >= limit:
                break
        return deduped

    def get_documents_by_category(self, category: str, limit: int = 4) -> List[dict]:
        normalized_category = normalize_text(category)
        matches = []
        for document in self.documents:
            if normalize_text(document.get("category", "")) == normalized_category:
                matches.append(document)
            if len(matches) >= limit:
                break
        return matches
