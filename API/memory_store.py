import json
import os
from threading import Lock
from typing import Optional


BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "DATA")
MEMORY_PATH = os.path.join(DATA_DIR, "user_memory.json")


class MemoryStore:
    def __init__(self, path: str = MEMORY_PATH) -> None:
        self.path = path
        self._lock = Lock()
        self._ensure_file()

    def _ensure_file(self) -> None:
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        if not os.path.exists(self.path):
            with open(self.path, "w", encoding="utf-8") as file:
                json.dump({"users": {}}, file, ensure_ascii=True, indent=2)

    def _read(self) -> dict:
        self._ensure_file()
        with open(self.path, "r", encoding="utf-8") as file:
            return json.load(file)

    def _write(self, payload: dict) -> None:
        with open(self.path, "w", encoding="utf-8") as file:
            json.dump(payload, file, ensure_ascii=True, indent=2)

    def get_user_memory(self, user_id: str) -> dict:
        with self._lock:
            payload = self._read()
            user_memory = payload.setdefault("users", {}).setdefault(
                user_id,
                {
                    "topic_counts": {},
                    "recent_topics": [],
                    "last_intent": None,
                    "last_message": None,
                },
            )
            return {
                "topic_counts": dict(user_memory.get("topic_counts", {})),
                "recent_topics": list(user_memory.get("recent_topics", [])),
                "last_intent": user_memory.get("last_intent"),
                "last_message": user_memory.get("last_message"),
            }

    def remember_topic(
        self,
        user_id: str,
        topic: Optional[str],
        intent: Optional[str] = None,
        message: Optional[str] = None,
    ) -> None:
        if not user_id:
            return

        with self._lock:
            payload = self._read()
            user_memory = payload.setdefault("users", {}).setdefault(
                user_id,
                {
                    "topic_counts": {},
                    "recent_topics": [],
                    "last_intent": None,
                    "last_message": None,
                },
            )

            if topic:
                topic_counts = user_memory.setdefault("topic_counts", {})
                topic_counts[topic] = int(topic_counts.get(topic, 0)) + 1

                recent_topics = user_memory.setdefault("recent_topics", [])
                if topic in recent_topics:
                    recent_topics.remove(topic)
                recent_topics.append(topic)
                user_memory["recent_topics"] = recent_topics[-5:]

            if intent is not None:
                user_memory["last_intent"] = intent
            if message is not None:
                user_memory["last_message"] = message

            self._write(payload)
