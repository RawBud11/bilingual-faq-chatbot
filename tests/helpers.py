"""Small fakes shared by the tests. No network, no API key.

Pattern copied from bilingual-reply-assistant (tests/helpers.py).
"""

import json

from chatbot.ai import AIError
from chatbot.handoff import MemoryStore
from chatbot.kb import load_kb
from chatbot.retrieve import build_indexes
from chatbot.turn import run_turn

INDEXES = build_indexes(load_kb())


class FakeAI:
    """Returns a fixed answer and remembers every request it got."""

    def __init__(self, answer):
        self.answer = answer
        self.requests = []

    def complete(self, request):
        self.requests.append(request)
        if isinstance(self.answer, Exception):
            raise self.answer
        return self.answer if isinstance(self.answer, str) else json.dumps(self.answer)

    def source_for(self, request):
        return "live"


class FailIfCalled:
    """An AI client that fails the test if anyone calls it."""

    def complete(self, request):
        raise AssertionError(f"The AI must not be called for: {request['messages']}")

    def source_for(self, request):
        raise AssertionError("The AI must not be called")


def template_client():
    """Behaves like demo mode with no fixture: every answer is the template."""
    return FakeAI(AIError("no_fixture"))


def ai_answer(reply, confidence=0.9):
    return {"reply": reply, "confidence": confidence}


def chat(message, history=None, client=None, store=None, ui_lang="en"):
    """Run one turn. Returns (result, store)."""
    store = store if store is not None else MemoryStore()
    result = run_turn(message, history or [], client=client or template_client(),
                      indexes=INDEXES, store=store, ui_lang=ui_lang)
    return result, store
