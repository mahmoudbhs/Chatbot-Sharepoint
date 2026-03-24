import os
from typing import List, Optional

import requests
from dotenv import load_dotenv


class LLMClient:
    def __init__(self) -> None:
        load_dotenv()
        self.enabled = os.getenv("LLM_ENABLED", "false").strip().lower() == "true"
        self.provider = os.getenv("LLM_PROVIDER", "openai").strip().lower()
        self.base_url = os.getenv("LLM_BASE_URL", "https://api.openai.com/v1").rstrip("/")
        self.api_key = os.getenv("OPENAI_API_KEY", "").strip()
        self.model = os.getenv("OPENAI_MODEL", "gpt-4o-mini").strip()
        self.timeout = int(os.getenv("LLM_TIMEOUT_SECONDS", "30"))
        self.strategy = os.getenv("LLM_STRATEGY", "rewrite").strip().lower()

    @property
    def is_available(self) -> bool:
        return self.enabled and self.provider == "openai" and bool(self.api_key)

    def generate_reply(
        self,
        user_message: str,
        deterministic_reply: str,
        history: List[dict],
        knowledge_titles: Optional[List[str]] = None,
    ) -> Optional[str]:
        if not self.is_available:
            return None

        history_lines = []
        for turn in history[-6:]:
            role = turn.get("role", "user")
            text = turn.get("text", "").strip()
            if text:
                history_lines.append(f"{role}: {text}")

        extra_context = ""
        if knowledge_titles:
            extra_context = "Pistes documentaires utiles: " + ", ".join(knowledge_titles)

        system_prompt = (
            "Tu es un assistant M365. "
            "Tu dois garder le sens de la reponse deterministe fournie. "
            "Ne contredis jamais cette reponse. "
            "Tu peux la reformuler pour qu'elle soit plus naturelle, plus conversationnelle et plus claire. "
            "Si elle contient des etapes, conserve-les. "
            "N'invente pas d'informations non presentes dans la reponse deterministe ou le contexte fourni."
        )

        user_prompt = (
            f"Message utilisateur: {user_message}\n\n"
            f"Reponse deterministe a respecter: {deterministic_reply}\n\n"
            f"Historique recent:\n" + ("\n".join(history_lines) if history_lines else "aucun") + "\n\n"
            f"{extra_context}\n\n"
            "Reformule la reponse finale en francais naturel."
        )

        try:
            response = requests.post(
                f"{self.base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.model,
                    "temperature": 0.4,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                },
                timeout=self.timeout,
            )
            response.raise_for_status()
            payload = response.json()
            content = payload["choices"][0]["message"]["content"].strip()
            return content or None
        except Exception:
            return None
