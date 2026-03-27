import os
from typing import Dict, List, Optional

import requests
from dotenv import load_dotenv


GRAPH_BASE_URL = "https://graph.microsoft.com/v1.0"


class GraphConnector:
    def __init__(self) -> None:
        load_dotenv()
        self.enabled = os.getenv("GRAPH_ENABLED", "false").strip().lower() == "true"
        self.tenant_id = os.getenv("GRAPH_TENANT_ID", "").strip()
        self.client_id = os.getenv("GRAPH_CLIENT_ID", "").strip()
        self.client_secret = os.getenv("GRAPH_CLIENT_SECRET", "").strip()
        self.site_id = os.getenv("GRAPH_SITE_ID", "").strip()
        self.site_hostname = os.getenv("GRAPH_SITE_HOSTNAME", "").strip()
        self.site_path = os.getenv("GRAPH_SITE_PATH", "").strip()
        self.timeout_seconds = int(os.getenv("GRAPH_TIMEOUT_SECONDS", "20").strip() or "20")
        self.max_items = int(os.getenv("GRAPH_MAX_ITEMS", "25").strip() or "25")
        self._token_cache: Optional[str] = None

    @property
    def is_configured(self) -> bool:
        return bool(
            self.enabled
            and self.tenant_id
            and self.client_id
            and self.client_secret
        )

    def get_status(self) -> Dict[str, object]:
        return {
            "enabled": self.enabled,
            "configured": self.is_configured,
            "has_site_id": bool(self.site_id),
            "has_site_path": bool(self.site_hostname and self.site_path),
        }

    def _token_url(self) -> str:
        return f"https://login.microsoftonline.com/{self.tenant_id}/oauth2/v2.0/token"

    def _get_access_token(self) -> Optional[str]:
        if self._token_cache:
            return self._token_cache

        if not self.is_configured:
            return None

        response = requests.post(
            self._token_url(),
            data={
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "scope": "https://graph.microsoft.com/.default",
                "grant_type": "client_credentials",
            },
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()
        payload = response.json()
        self._token_cache = payload.get("access_token")
        return self._token_cache

    def _get(self, path: str, params: Optional[dict] = None) -> dict:
        token = self._get_access_token()
        if not token:
            return {}

        response = requests.get(
            f"{GRAPH_BASE_URL}{path}",
            params=params,
            headers={"Authorization": f"Bearer {token}"},
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()
        return response.json()

    def _resolve_site_id(self) -> Optional[str]:
        if self.site_id:
            return self.site_id

        if not (self.site_hostname and self.site_path):
            return None

        payload = self._get(f"/sites/{self.site_hostname}:{self.site_path}")
        return payload.get("id")

    def list_sites(self, search: str = "*", limit: int = 10) -> List[dict]:
        if not self.is_configured:
            return []

        payload = self._get("/sites", params={"search": search})
        sites = []
        for item in payload.get("value", [])[:limit]:
            sites.append(
                {
                    "id": item.get("id", ""),
                    "title": item.get("displayName", "") or item.get("name", ""),
                    "url": item.get("webUrl", ""),
                    "description": item.get("description", ""),
                }
            )
        return sites

    def fetch_site_pages(self, limit: Optional[int] = None) -> List[dict]:
        site_id = self._resolve_site_id()
        if not site_id:
            return []

        payload = self._get(f"/sites/{site_id}/pages")
        documents = []
        for item in payload.get("value", [])[: limit or self.max_items]:
            title = item.get("title") or item.get("name") or "Page SharePoint"
            documents.append(
                {
                    "id": f"graph-page-{item.get('id', title)}",
                    "title": title,
                    "category": "sharepoint",
                    "keywords": ["sharepoint", "page", "site", "graph"],
                    "content": item.get("description")
                    or f"Page SharePoint detectee dans le site Microsoft 365 : {title}.",
                    "url": item.get("webUrl", ""),
                    "source": "Microsoft Graph",
                }
            )
        return documents

    def fetch_site_lists(self, limit: Optional[int] = None) -> List[dict]:
        site_id = self._resolve_site_id()
        if not site_id:
            return []

        payload = self._get(f"/sites/{site_id}/lists")
        documents = []
        for item in payload.get("value", [])[: limit or self.max_items]:
            title = item.get("displayName") or item.get("name") or "Liste SharePoint"
            documents.append(
                {
                    "id": f"graph-list-{item.get('id', title)}",
                    "title": title,
                    "category": "sharepoint",
                    "keywords": ["sharepoint", "liste", "site", "graph"],
                    "content": f"Liste SharePoint disponible sur le site : {title}.",
                    "url": item.get("webUrl", ""),
                    "source": "Microsoft Graph",
                }
            )
        return documents

    def fetch_drive_items(self, limit: Optional[int] = None) -> List[dict]:
        site_id = self._resolve_site_id()
        if not site_id:
            return []

        payload = self._get(f"/sites/{site_id}/drive/root/children")
        documents = []
        for item in payload.get("value", [])[: limit or self.max_items]:
            title = item.get("name") or "Document SharePoint"
            documents.append(
                {
                    "id": f"graph-drive-{item.get('id', title)}",
                    "title": title,
                    "category": "sharepoint",
                    "keywords": ["sharepoint", "document", "bibliotheque", "graph"],
                    "content": f"Document ou dossier detecte dans la bibliotheque SharePoint : {title}.",
                    "url": item.get("webUrl", ""),
                    "source": "Microsoft Graph",
                }
            )
        return documents

    def fetch_knowledge_documents(self, limit: Optional[int] = None) -> List[dict]:
        if not self.is_configured:
            return []

        max_items = limit or self.max_items
        collected = []
        try:
            collected.extend(self.fetch_site_pages(limit=max_items))
            if len(collected) < max_items:
                collected.extend(self.fetch_site_lists(limit=max_items - len(collected)))
            if len(collected) < max_items:
                collected.extend(self.fetch_drive_items(limit=max_items - len(collected)))
        except Exception:
            return []

        deduped = []
        seen = set()
        for item in collected:
            key = (item.get("title"), item.get("url"))
            if key in seen:
                continue
            seen.add(key)
            deduped.append(item)
            if len(deduped) >= max_items:
                break
        return deduped
