"""The AI layer with fake clients only. These tests never call the network.

Adapted from bilingual-reply-assistant (tests/test_ai.py).
"""

import json
from types import SimpleNamespace

import anthropic
import pytest

import config
from chatbot.ai import (AIError, FixtureClient, LiveClient, RecordingClient, build_request,
                        fixture_key, parse_answer)
from helpers import INDEXES, FakeAI, ai_answer, chat

ARTICLES = [a for a, _ in INDEXES["en"].search("transfer pending")]
IDS = [a.id for a in ARTICLES]


# --- Checking the answer ------------------------------------------------------

def test_parse_accepts_json_inside_code_fences():
    text = "```json\n" + json.dumps(ai_answer("Most transfers arrive in 1 to 3 days [KB-EN-04].")) + "\n```"
    assert parse_answer(text, IDS)["cited"] == ["KB-EN-04"]


@pytest.mark.parametrize("answer,code", [
    ("Sure! Here is an answer.", "bad_json"),
    ('{"reply": "Hi [KB-EN-04]", "confidence": 0.9', "bad_json"),
    (json.dumps(ai_answer("")), "no_reply"),
    (json.dumps(ai_answer("Hi [KB-EN-04]", confidence=True)), "bad_confidence"),
    (json.dumps(ai_answer("Hi [KB-EN-04]", confidence=1.4)), "bad_confidence"),
    (json.dumps(ai_answer("Hi [KB-EN-04]", confidence=0.3)), "low_confidence"),
    (json.dumps(ai_answer("Hi, no citation here.")), "no_citation"),
    (json.dumps(ai_answer("Hi [KB-EN-04] and [KB-EN-07]")), "bad_citation"),
])
def test_parse_rejects_bad_answers(answer, code):
    with pytest.raises(AIError) as info:
        parse_answer(answer, IDS)
    assert info.value.code == code


@pytest.mark.parametrize("lang,message,answer", [
    ("en", "My transfer is still pending.", ai_answer("Hi [KB-EN-07]")),    # not retrieved
    ("es", "Mi transferencia sigue pendiente.", ai_answer("Hola [KB-ES-07]")),
    ("en", "My transfer is still pending.", "Not JSON at all"),
    ("es", "Mi transferencia sigue pendiente.", "{\"reply\": \"Hola"),
    ("en", "My transfer is still pending.", ai_answer("Hi [KB-EN-04]", confidence=0.2)),
    ("es", "Mi transferencia sigue pendiente.", ai_answer("Hola [KB-ES-04]", confidence=0.2)),
    ("en", "My transfer is still pending.", AIError("timeout")),
    ("es", "Mi transferencia sigue pendiente.", AIError("connection")),
])
def test_bad_or_unsure_ai_answers_become_no_answer(lang, message, answer):
    result, _ = chat(message, client=FakeAI(answer))
    assert result["reply_lang"] == lang
    assert result["action"] == "no_answer" and result["source"] is None
    assert result["ai_problem"]
    assert result["offer_handoff"] is True


def test_fatal_error_is_reported_but_the_customer_gets_a_safe_reply():
    result, _ = chat("My transfer is still pending.", client=FakeAI(AIError("auth", fatal=True)))
    assert result["action"] == "no_answer" and result["ai_fatal"] is True


@pytest.mark.parametrize("lang,name", [("en", "English"), ("es", "Spanish")])
def test_request_has_articles_message_and_reply_language(lang, name):
    request = build_request("My transfer is pending", ARTICLES, lang, "model-x")
    assert f"Write the answer in {name}." in request["system"]
    user = request["messages"][0]["content"]
    assert '<article id="KB-EN-04">' in user and "<ticket>\nMy transfer is pending\n</ticket>" in user
    assert request["model"] == "model-x" and request["max_tokens"] == config.AI_MAX_TOKENS


def test_fixture_key_ignores_case_accents_and_punctuation():
    assert fixture_key("¿Cuánto TARDA una transferencia?") == fixture_key("cuanto tarda una transferencia")


# --- Clients ----------------------------------------------------------------------

class FakeMessages:
    def __init__(self, reply=None, error=None):
        self.reply, self.error, self.calls = reply, error, []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        return SimpleNamespace(content=[SimpleNamespace(type="text", text=self.reply)])


def fake_sdk(reply=None, error=None):
    return SimpleNamespace(messages=FakeMessages(reply, error))


def test_live_client_sends_only_api_fields():
    sdk = fake_sdk(reply='{"ok": true}')
    client = LiveClient("test-key", "model-x", sdk_client=sdk)
    assert client.complete(build_request("Hi", ARTICLES, "en", "model-x")) == '{"ok": true}'
    assert set(sdk.messages.calls[0]) == {"model", "max_tokens", "system", "messages"}


@pytest.mark.parametrize("error_cls,code,fatal", [
    (anthropic.AuthenticationError, "auth", True),
    (anthropic.PermissionDeniedError, "permission", True),
    (anthropic.NotFoundError, "model", True),
    (anthropic.APITimeoutError, "timeout", False),
    (anthropic.APIConnectionError, "connection", False),
    (anthropic.RateLimitError, "rate_limit", False),
    (anthropic.InternalServerError, "server", False),
])
def test_live_client_turns_sdk_errors_into_clear_codes(error_cls, code, fatal):
    error = error_cls.__new__(error_cls)  # an SDK exception without a real HTTP call
    client = LiveClient("test-key", "model-x", sdk_client=fake_sdk(error=error))
    with pytest.raises(AIError) as info:
        client.complete(build_request("Hi", ARTICLES, "en", "model-x"))
    assert (info.value.code, info.value.fatal) == (code, fatal)


def test_fixture_client_by_message_and_language(tmp_path):
    path = tmp_path / "fx.json"
    path.write_text(json.dumps({"answers": {"hi there": {
        "en": {"source": "hand-written", "response": ai_answer("Hi [KB-EN-04]")},
        "es": {"source": "recorded", "response": "not json"}}}}), encoding="utf-8")
    client = FixtureClient(path)
    assert json.loads(client.complete({"key": "hi there", "reply_lang": "en"}))["reply"] == "Hi [KB-EN-04]"
    assert client.complete({"key": "hi there", "reply_lang": "es"}) == "not json"
    assert client.source_for({"key": "hi there", "reply_lang": "es"}) == "recorded"
    with pytest.raises(AIError) as info:
        client.complete({"key": "other", "reply_lang": "en"})
    assert info.value.code == "no_fixture"


def test_recording_marks_answers_as_recorded_and_keeps_others(tmp_path):
    path = tmp_path / "fx.json"
    path.write_text(json.dumps({"_about": "x", "answers": {
        "hi": {"en": {"source": "hand-written", "response": ai_answer("Hi [KB-EN-04]")}}}}), encoding="utf-8")
    reply = json.dumps(ai_answer("Hola, tu transferencia [KB-ES-04]"), ensure_ascii=False)
    recorder = RecordingClient(LiveClient("test-key", "model-x", sdk_client=fake_sdk(reply=reply)))
    recorder.complete(build_request("Mi transferencia", ARTICLES, "es", "model-x"))
    assert recorder.save(path) == 1
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["answers"]["mi transferencia"]["es"]["source"] == "recorded"
    assert data["answers"]["mi transferencia"]["es"]["model"] == "model-x"
    assert data["answers"]["hi"]["en"]["source"] == "hand-written"
    assert data["_about"] == "x"


def test_sample_fixtures_are_labeled_hand_written_and_match_the_demo():
    with open(config.FIXTURES_FILE, encoding="utf-8") as f:
        data = json.load(f)
    assert "NOT real model output" in data["_about"]
    sources = {e["source"] for by_lang in data["answers"].values() for e in by_lang.values()}
    assert sources <= {"hand-written", "recorded"}
    with open(config.DATA_DIR / "demo_conversations.json", encoding="utf-8") as f:
        said = {fixture_key(t["say"]) for c in json.load(f)["conversations"] for t in c["turns"] if "say" in t}
    assert set(data["answers"]) <= said  # every fixture is used by a demo conversation


# --- The real SDK with a fake HTTP layer (still no network) ---------------------

def sdk_with_fake_http(handler):
    # httpx2 is not in requirements.txt: it is the HTTP library the anthropic
    # SDK 1.x installs and uses. If a future SDK switches libraries, these
    # tests are skipped instead of failing.
    httpx2 = pytest.importorskip("httpx2")
    return anthropic.Anthropic(api_key="test-key", max_retries=0,
                               http_client=httpx2.Client(transport=httpx2.MockTransport(handler)))


def test_live_client_with_real_sdk_and_fake_http():
    httpx2 = pytest.importorskip("httpx2")
    sent = {}

    def handler(request):
        sent["url"], sent["body"] = str(request.url), json.loads(request.content)
        return httpx2.Response(200, json={
            "id": "msg_test", "type": "message", "role": "assistant", "model": "model-x",
            "content": [{"type": "text", "text": json.dumps(ai_answer("Most arrive in 1 to 3 days [KB-EN-04]."))}],
            "stop_reason": "end_turn", "stop_sequence": None,
            "usage": {"input_tokens": 1, "output_tokens": 1}})

    client = LiveClient("test-key", "model-x", sdk_client=sdk_with_fake_http(handler))
    result, _ = chat("My transfer is pending. My email is cliente.demo42@example.com", client=client)
    assert sent["url"].endswith("/v1/messages")
    assert "cliente.demo42" not in json.dumps(sent["body"])
    assert (result["action"], result["answer_from"]) == ("answer", "live")


@pytest.mark.parametrize("status,error_type,code,fatal", [
    (401, "authentication_error", "auth", True),
    (404, "not_found_error", "model", True),
    (429, "rate_limit_error", "rate_limit", False),
    (529, "overloaded_error", "server", False),
])
def test_real_sdk_http_errors_become_clear_codes(status, error_type, code, fatal):
    httpx2 = pytest.importorskip("httpx2")

    def handler(request):
        return httpx2.Response(status, json={"type": "error", "error": {"type": error_type, "message": "test"}})

    client = LiveClient("test-key", "model-x", sdk_client=sdk_with_fake_http(handler))
    with pytest.raises(AIError) as info:
        client.complete(build_request("Hi", ARTICLES, "en", "model-x"))
    assert (info.value.code, info.value.fatal) == (code, fatal)
