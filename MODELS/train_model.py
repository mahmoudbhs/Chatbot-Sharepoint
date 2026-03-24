import os
import pickle
import sys


BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASE_DIR)

from API.engine import ARTIFACT_PATH, ChatbotEngine  # noqa: E402
from API.knowledge_base import load_knowledge_base  # noqa: E402


def main() -> None:
    knowledge_base = load_knowledge_base()
    engine = ChatbotEngine(knowledge_base=knowledge_base)
    bundle = engine.train_bundle()

    os.makedirs(os.path.dirname(ARTIFACT_PATH), exist_ok=True)
    with open(ARTIFACT_PATH, "wb") as file:
        pickle.dump(bundle, file)

    total_intents = len(knowledge_base["intents"])
    total_examples = sum(len(intent["patterns"]) for intent in knowledge_base["intents"])

    print("Modele entraine avec succes.")
    print(f"Artefact genere: {ARTIFACT_PATH}")
    print(f"Intentions: {total_intents}")
    print(f"Exemples: {total_examples}")


if __name__ == "__main__":
    main()
