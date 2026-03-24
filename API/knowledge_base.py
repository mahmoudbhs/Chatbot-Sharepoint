import json
import os
from typing import Dict, List


BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "DATA")

INTENTS_PATH = os.path.join(DATA_DIR, "intents.json")
TRAINING_DATA_PATH = os.path.join(DATA_DIR, "training_data.json")
RESPONSES_PATH = os.path.join(DATA_DIR, "responses.json")


class KnowledgeBaseError(Exception):
    """Raised when the chatbot knowledge base is invalid."""


def _load_json(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as file:
        return json.load(file)


def load_knowledge_base() -> dict:
    responses_payload = _load_json(RESPONSES_PATH)
    intents_payload = _load_json(INTENTS_PATH)
    training_payload = _load_json(TRAINING_DATA_PATH)

    responses_by_tag = {
        intent["tag"]: intent["responses"]
        for intent in intents_payload.get("intents", [])
    }
    patterns_by_tag = {
        entry["intent"]: entry["examples"]
        for entry in training_payload.get("training_data", [])
    }

    missing_patterns = sorted(set(responses_by_tag) - set(patterns_by_tag))
    missing_responses = sorted(set(patterns_by_tag) - set(responses_by_tag))

    if missing_patterns or missing_responses:
        raise KnowledgeBaseError(
            "Les fichiers de donn\u00e9es ne sont pas align\u00e9s. "
            f"Sans exemples: {missing_patterns}. Sans r\u00e9ponses: {missing_responses}."
        )

    intents: List[Dict[str, object]] = []
    for tag in sorted(patterns_by_tag):
        intents.append(
            {
                "tag": tag,
                "patterns": patterns_by_tag[tag],
                "responses": responses_by_tag[tag],
            }
        )

    return {
        "intents": intents,
        "defaults": responses_payload.get("responses", {}).get("default", []),
        "errors": responses_payload.get("responses", {}).get("error", []),
        "quick_replies": responses_payload.get("responses", {}).get("quick_replies", {}),
        "metadata": training_payload.get("metadata", {}),
    }


def build_training_samples(knowledge_base: dict) -> List[dict]:
    samples: List[dict] = []
    for intent in knowledge_base["intents"]:
        for pattern in intent["patterns"]:
            samples.append({"text": pattern, "tag": intent["tag"]})
    return samples
