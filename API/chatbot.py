from API.engine import ChatbotEngine


engine = ChatbotEngine()


def chatbot_response(message: str, session_id: str = "default") -> str:
    return engine.safe_response(message, session_id=session_id)["response"]


def chatbot_reply(message: str, session_id: str = "default") -> dict:
    return engine.safe_response(message, session_id=session_id)
