"""Handoffs: urgent cases skip the AI, customers can always reach a person,
and the saved record is masked. English and Spanish."""

import json
import threading

import pytest

from chatbot.handoff import JsonlStore, MemoryStore, build_record, clean_history, wants_human
from chatbot.strings import STRINGS
from chatbot.turn import run_button_handoff
from helpers import FailIfCalled, chat

URGENT = [
    ("en", "I lost my card", "card_lost_stolen"),
    ("es", "Me robaron la tarjeta", "card_lost_stolen"),
    ("en", "Someone logged into my account and changed my email", "account_access"),
    ("es", "Creo que me hackearon la cuenta", "account_access"),
    ("en", "There are purchases on my card that I did not make", "charge_dispute"),
    ("es", "Hay compras en mi tarjeta que yo no hice", "charge_dispute"),
]


@pytest.mark.parametrize("lang,message,category", URGENT)
def test_urgent_cases_hand_off_now_and_never_call_the_ai(lang, message, category):
    result, store = chat(message, client=FailIfCalled())
    assert result["action"] == "handoff_urgent" and result["reply_lang"] == lang
    assert result["handoff"] == {"id": "H-0001", "urgency": "urgent", "category": category}
    record = store.records[0]
    assert (record["urgency"], record["trigger"], record["category"]) == ("urgent", "urgent", category)
    s = STRINGS[lang]
    assert "H-0001" in result["reply"]
    assert s["honest_note"] in result["reply"] and s["never_ask"] in result["reply"]


@pytest.mark.parametrize("lang,message", [
    ("en", "Me robaron la tarjeta, el número es 0000 1234 5678 9012"),
    ("en", "I lost my card, the number is 0000 1234 5678 9012 and CVV 321"),
])
def test_urgent_with_typed_card_number_warns_and_still_hands_off(lang, message):
    result, store = chat(message, client=FailIfCalled())
    assert result["action"] == "handoff_urgent"
    assert STRINGS[result["reply_lang"]]["sensitive_warning"] in result["reply"]
    saved = json.dumps(store.records, ensure_ascii=False)
    assert "1234 5678" not in saved and "321" not in saved
    assert "[CARD NUMBER MASKED]" in saved


@pytest.mark.parametrize("lang,message", [
    ("en", "I want to talk to a person"),
    ("es", "Quiero hablar con alguien"),
    ("en", "Can I speak with a real human please"),
    ("es", "¿Me pasas con un agente?"),
    ("en", "this bot is useless, get me an agent"),
    ("es", "Necesito hablar con una persona de verdad"),
    ("es", "quiero que me atienda un asesor"),
    ("en", "Connect me to a representative"),
])
def test_asking_for_a_person_always_creates_a_handoff(lang, message):
    result, store = chat(message, client=FailIfCalled())
    assert result["action"] == "handoff_requested" and result["reply_lang"] == lang
    assert store.records[0]["trigger"] == "requested"
    assert STRINGS[lang]["honest_note"] in result["reply"]


def test_asking_for_a_person_wins_over_an_account_question():
    result, _ = chat("I want to talk to a person about my balance", client=FailIfCalled())
    assert result["action"] == "handoff_requested"


@pytest.mark.parametrize("lang,history", [
    ("en", []),
    ("es", []),
    ("es", [{"role": "customer", "text": "¿Cuál es mi saldo?"},
            {"role": "bot", "text": "Desde este chat no puedo...", "action": "refuse_account"}]),
])
def test_button_always_creates_a_handoff(lang, history):
    store = MemoryStore()
    result = run_button_handoff(history, store=store, ui_lang=lang)
    assert result["action"] == "handoff_requested" and result["reply_lang"] == lang
    assert store.records[0]["trigger"] == "button"
    # After an account-specific refusal the handoff is high priority.
    assert store.records[0]["urgency"] == ("high" if history else "low")


def test_not_a_human_request():
    for text in ("How do I add a person to my business account?", "¿Una persona puede tener dos cuentas?",
                 "Is there a fee to talk about?"):
        assert not wants_human(text)


def test_jsonl_store_numbers_records_and_masks_everything(tmp_path):
    store = JsonlStore(tmp_path / "out" / "handoffs.jsonl")
    history = [{"role": "customer", "text": "My card 0000 1111 2222 3333, CVV 123, email cliente.demo42@example.com, phone (555) 010-0199"},
               {"role": "bot", "text": "warning", "action": "sensitive_warning"},
               {"role": "hacker", "text": "dropped"}, "not a dict"]
    first = run_button_handoff(history, store=store, ui_lang="en")
    second, _ = chat("Quiero hablar con alguien", store=store)
    assert (first["handoff"]["id"], second["handoff"]["id"]) == ("H-0001", "H-0002")
    raw = (tmp_path / "out" / "handoffs.jsonl").read_text(encoding="utf-8")
    assert len(raw.strip().splitlines()) == 2
    for secret in ("1111", "123,", "cliente.demo42", "010-0199", "hacker", "dropped"):
        assert secret not in raw
    record = json.loads(raw.splitlines()[0])
    assert set(record) == {"id", "time", "language", "reply_lang", "category", "urgency", "trigger",
                           "summary", "transcript"}
    assert record["transcript"][-1]["text"].count("H-0001") == 1  # the saved reply quotes the reference


def test_store_gives_unique_ids_under_parallel_requests(tmp_path):
    store = JsonlStore(tmp_path / "handoffs.jsonl")
    threads = [threading.Thread(target=chat, args=("I want to talk to a person",), kwargs={"store": store})
               for _ in range(20)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    ids = [r["id"] for r in store.read_all()]
    assert sorted(ids) == [f"H-{n:04d}" for n in range(1, 21)]


def test_store_skips_broken_lines(tmp_path):
    path = tmp_path / "handoffs.jsonl"
    path.write_text('{"id": "H-0001"}\nnot json\n\n', encoding="utf-8")
    assert [r["id"] for r in JsonlStore(path).read_all()] == ["H-0001"]


def test_summary_is_deterministic_and_bilingual():
    transcript = [{"role": "customer", "text": "Me robaron la tarjeta"}]
    args = dict(language="es", reply_lang="es", category="card_lost_stolen", urgency="urgent",
                trigger="urgent", transcript=transcript)
    a, b = build_record(**args), build_record(**args)
    assert a["summary"] == b["summary"]
    assert a["summary"]["en"].startswith("Urgent | Card lost or stolen | language: Spanish")
    assert a["summary"]["es"].startswith("Urgente | Tarjeta perdida o robada | idioma: español")
    assert 'Último mensaje del cliente: "Me robaron la tarjeta"' in a["summary"]["es"]


def test_history_is_cut_to_a_maximum():
    history = [{"role": "customer", "text": "x" * 5000}] * 50
    cleaned = clean_history(history)
    assert len(cleaned) == 20 and all(len(e["text"]) == 2000 for e in cleaned)


# --- Short requests for a person ----------------------------------------------------

@pytest.mark.parametrize("lang,message", [
    ("en", "I want a human"),
    ("en", "human please"),
    ("en", "agent"),
    ("en", "representative please"),
    ("en", "I need an agent now"),
    ("en", "Can I get a real person?"),
    ("es", "quiero un humano"),
    ("es", "necesito un agente"),
    ("es", "Agente, por favor"),
    ("es", "Quisiera hablar con un asesor"),
    ("es", "necesito una persona real"),
])
def test_short_and_want_need_requests_for_a_person_hand_off(lang, message):
    result, store = chat(message, client=FailIfCalled(), ui_lang=lang)
    assert result["action"] == "handoff_requested"
    assert result["reply_lang"] == lang
    assert store.records[0]["trigger"] == "requested"


@pytest.mark.parametrize("text", [
    "I want to add a person to my business account",
    "I need someone's account number to send money",
    "Quiero pagarle a alguien en México",
    "Necesito enviar dinero a una persona en Colombia",
    "¿Una persona puede tener dos cuentas?",
])
def test_people_words_in_normal_questions_are_not_requests(text):
    assert not wants_human(text)


@pytest.mark.parametrize("lang,message", [
    ("es", "mi cuenta fue hackeada"),
    ("en", "I think someone is in my account"),
    ("es", "Creo que alguien está usando mi cuenta"),
    ("en", "I got a call from someone saying they were Puentara and asked for my code"),
    ("es", "Me llamaron de Puentara y me pidieron el código que me llegó"),
    ("en", "I got a text asking for my one-time code, is that you?"),
    ("es", "Recibí un mensaje que me pide mi clave, ¿son ustedes?"),
    ("en", "Someone emailed me asking me to confirm my password"),
    ("es", "Me escribieron por WhatsApp y me pidieron la contraseña"),
])
def test_takeover_and_phishing_are_urgent_and_never_call_the_ai(lang, message):
    result, store = chat(message, client=FailIfCalled())
    assert result["action"] == "handoff_urgent" and result["reply_lang"] == lang
    assert store.records[0]["urgency"] == "urgent"
    assert store.records[0]["category"] == "account_access"


@pytest.mark.parametrize("message,article", [
    ("How do I reset my password?", "KB-EN-02"),
    ("No me llega el código", "KB-ES-02"),
    ("I never got the login code by text", "KB-EN-02"),
    ("Me llegó un correo para restablecer mi contraseña", "KB-ES-02"),
])
def test_login_help_is_not_mistaken_for_phishing(message, article):
    result, _ = chat(message)
    assert result["action"] == "answer" and result["source"]["id"] == article
