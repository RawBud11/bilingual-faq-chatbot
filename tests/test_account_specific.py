"""Account-specific questions are refused without calling the AI; general
questions with similar words are still answered. English and Spanish."""

import pytest

from chatbot.account_specific import account_specific_match
from chatbot.strings import STRINGS
from helpers import FailIfCalled, chat

REFUSE = [
    ("en", "What's my balance?"),
    ("es", "¿Cuál es mi saldo?"),
    ("en", "Is my refund approved?"),
    ("es", "¿Ya aprobaron mi reembolso?"),
    ("es", "¿Por qué rechazaron mi transferencia a Juan?"),
    ("en", "Why was my transfer to Juan declined?"),
    ("en", "Can you check if my payment to Maria went through?"),
    ("es", "¿Puedes revisar si mi pago a María ya salió?"),
    ("en", "What was my last transaction?"),
    ("es", "¿Cuál fue mi último movimiento?"),
    ("en", "Can you change the email on my account?"),
    ("es", "¿Puedes cambiar el correo de mi cuenta?"),
    ("es", "¿Me puedes decir cuánto me cobraron el mes pasado?"),
    ("en", "Why did you close my account?"),
]

# Hard negatives: they share words with the refused questions, but any help
# center can answer them.
ANSWER = [
    ("en", "How long do transfers take?", "KB-EN-04"),
    ("es", "¿Cuánto tarda una transferencia?", "KB-ES-04"),
    ("en", "How much does a new card cost?", "KB-EN-06"),
    ("es", "Si una transferencia falla, ¿me devuelven el dinero?", "KB-ES-04"),
    ("en", "How long do refunds take after a dispute?", "KB-EN-05"),
    ("es", "¿Qué documentos sirven para verificar mi cuenta?", "KB-ES-03"),
    ("en", "My ID photo keeps getting rejected", "KB-EN-03"),
]


@pytest.mark.parametrize("lang,message", REFUSE)
def test_account_specific_questions_are_refused_without_ai(lang, message):
    result, store = chat(message, client=FailIfCalled())
    assert result["action"] == "refuse_account"
    assert result["reply_lang"] == lang
    assert result["reply"].startswith(STRINGS[lang]["refuse_account"])
    assert result["offer_handoff"] is True
    assert store.records == []  # an offer, not a handoff yet


@pytest.mark.parametrize("lang,message,article", ANSWER)
def test_general_questions_with_similar_words_are_answered(lang, message, article):
    result, _ = chat(message)
    assert result["action"] == "answer"
    assert result["source"]["id"] == article


@pytest.mark.parametrize("message", ["How do I see my balance in the app?", "¿Cómo veo mi saldo en la app?",
                                     "Where can I check my transfer status?"])
def test_how_to_questions_are_never_refused(message):
    assert account_specific_match(message) == ""
    result, _ = chat(message)
    assert result["action"] != "refuse_account"


def test_match_quotes_the_customers_own_words():
    assert account_specific_match("¿Por qué RECHAZARON mi transferencia?") == "RECHAZARON mi transferencia"
